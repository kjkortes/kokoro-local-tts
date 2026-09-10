import time
from pathlib import Path

import numpy as np
import pytest

from kokoro_app.jobs import JobManager
from kokoro_app.engine import AlignedWord, SynthesisResult
from kokoro_app.schemas import ExpressionSettings, GenerationRequest, JobState


class FakeEngine:
    def synthesize(self, *args, **kwargs) -> SynthesisResult:
        return SynthesisResult(np.ones(1200, dtype=np.float32) * 0.1)


def fake_encode(pcm, destination: Path, *args, **kwargs) -> None:
    destination.write_bytes(b"local audio")


def wait_for(manager: JobManager, job_id: str, state: JobState) -> None:
    deadline = time.time() + 2
    while time.time() < deadline:
        if manager.get(job_id).state == state:
            return
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} never reached {state}")


def test_job_moves_from_queued_to_complete_and_reports_progress(tmp_path: Path) -> None:
    manager = JobManager(FakeEngine(), tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(text="One. Two."))
    wait_for(manager, record.id, JobState.complete)
    finished = manager.get(record.id)
    assert finished.progress == 1.0
    assert finished.result_path and finished.result_path.exists()
    manager.shutdown()


def test_completed_job_records_spoken_segment_timestamps(tmp_path: Path) -> None:
    manager = JobManager(FakeEngine(), tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(text="One. Two."))
    wait_for(manager, record.id, JobState.complete)

    assert manager.get(record.id).segments == [
        {"text": "One.", "start": 0.0, "end": 0.05, "paragraph_end": False},
        {"text": "Two.", "start": 0.27, "end": 0.32, "paragraph_end": True},
    ]
    manager.shutdown()


def test_completed_job_offsets_word_timestamps_by_chunks_pauses_and_tempo(tmp_path: Path) -> None:
    class AlignedEngine(FakeEngine):
        def synthesize(self, *args, **kwargs) -> SynthesisResult:
            return SynthesisResult(
                np.ones(1200, dtype=np.float32),
                (AlignedWord(str(args[0]), 0.01, 0.04),),
            )

    manager = JobManager(AlignedEngine(), tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(
        text="One. Two.",
        expression=ExpressionSettings(tempo=1.25, pause_scale=1.5),
    ))
    wait_for(manager, record.id, JobState.complete)

    assert manager.get(record.id).words == [
        {"text": "One.", "start": pytest.approx(0.008), "end": pytest.approx(0.032)},
        {"text": "Two.", "start": pytest.approx(0.312), "end": pytest.approx(0.336)},
    ]
    manager.shutdown()


def test_segment_timestamps_follow_chunk_lengths_pause_scaling_and_tempo(tmp_path: Path) -> None:
    class VaryingEngine(FakeEngine):
        calls = 0

        def synthesize(self, *args, **kwargs) -> SynthesisResult:
            self.calls += 1
            return SynthesisResult(np.ones(1200 * self.calls, dtype=np.float32))

    manager = JobManager(VaryingEngine(), tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(
        text="One. Two.",
        expression=ExpressionSettings(tempo=1.25, pause_scale=1.5),
    ))
    wait_for(manager, record.id, JobState.complete)
    finished = manager.get(record.id)

    assert finished.segments[0]["start"] == 0.0
    assert finished.segments[0]["end"] == pytest.approx(0.04)
    assert finished.segments[1]["start"] == pytest.approx(0.304)
    assert finished.segments[1]["end"] == pytest.approx(0.384)
    assert finished.duration == pytest.approx(0.384)
    manager.shutdown()


def test_exact_pause_duration_overrides_chunk_defaults_and_expression_scale(tmp_path: Path) -> None:
    manager = JobManager(FakeEngine(), tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(
        text="One. Two.",
        pause_ms=750,
        expression=ExpressionSettings(tempo=1.25, pause_scale=2),
    ))
    wait_for(manager, record.id, JobState.complete)
    finished = manager.get(record.id)

    assert finished.segments[1]["start"] == pytest.approx(0.64)
    assert finished.duration == pytest.approx(0.68)
    manager.shutdown()


def test_storyboard_rows_remain_exact_segments_when_a_row_uses_multiple_chunks(tmp_path: Path) -> None:
    manager = JobManager(FakeEngine(), tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(
        text="One. Two.\n\nThird row, exactly!",
        segments=["One. Two.", "Third row, exactly!"],
    ))
    wait_for(manager, record.id, JobState.complete)

    assert manager.get(record.id).segments == [
        {"text": "One. Two.", "start": 0.0, "end": 0.32, "paragraph_end": True},
        {"text": "Third row, exactly!", "start": 0.54, "end": 0.59, "paragraph_end": True},
    ]
    manager.shutdown()


def test_storyboard_rows_are_synthesized_as_one_continuous_narration(tmp_path: Path) -> None:
    class RecordingEngine(FakeEngine):
        calls: list[str]

        def __init__(self) -> None:
            self.calls = []

        def synthesize(self, text, *args, **kwargs) -> SynthesisResult:
            self.calls.append(text)
            return super().synthesize(text, *args, **kwargs)

    engine = RecordingEngine()
    manager = JobManager(engine, tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(
        text="The thought begins,\n\nand continues naturally.",
        segments=["The thought begins,", "and continues naturally."],
    ))
    wait_for(manager, record.id, JobState.complete)

    assert engine.calls == ["The thought begins, and continues naturally."]
    assert [segment["text"] for segment in manager.get(record.id).segments] == [
        "The thought begins,",
        "and continues naturally.",
    ]
    manager.shutdown()


def test_storyboard_rows_keep_monotonic_timestamps_inside_shared_audio(tmp_path: Path) -> None:
    class OneSecondEngine(FakeEngine):
        def synthesize(self, *args, **kwargs) -> SynthesisResult:
            return SynthesisResult(np.ones(24_000, dtype=np.float32))

    manager = JobManager(OneSecondEngine(), tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(
        text="Short first row,\n\na considerably longer second row.",
        segments=["Short first row,", "a considerably longer second row."],
    ))
    wait_for(manager, record.id, JobState.complete)
    first, second = manager.get(record.id).segments

    assert first["start"] == 0.0
    assert 0 < first["end"] <= second["start"] < second["end"]
    assert second["end"] == pytest.approx(1.0)
    manager.shutdown()


def test_long_storyboard_keeps_rows_separate_from_speech_chunks(tmp_path: Path) -> None:
    class RecordingEngine(FakeEngine):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def synthesize(self, text, *args, **kwargs) -> SynthesisResult:
            self.calls.append(text)
            return super().synthesize(text, *args, **kwargs)

    rows = ["alpha " * 50, "beta " * 50, "gamma " * 50]
    rows = [row.strip() for row in rows]
    engine = RecordingEngine()
    manager = JobManager(engine, tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(text="\n\n".join(rows), segments=rows))
    wait_for(manager, record.id, JobState.complete)
    finished = manager.get(record.id)

    assert len(engine.calls) >= 2
    assert all(call not in rows for call in engine.calls)
    assert [segment["text"] for segment in finished.segments] == rows
    assert all(
        current["end"] <= following["start"]
        for current, following in zip(finished.segments, finished.segments[1:])
    )
    assert finished.segments[-1]["end"] == pytest.approx(finished.duration)
    manager.shutdown()


def test_cancelled_queued_job_does_not_expose_partial_audio(tmp_path: Path) -> None:
    class SlowEngine(FakeEngine):
        def synthesize(self, *args, **kwargs) -> SynthesisResult:
            time.sleep(0.08)
            return super().synthesize(*args, **kwargs)

    manager = JobManager(SlowEngine(), tmp_path, encoder=fake_encode)
    first = manager.create(GenerationRequest(text="Hold the worker."))
    second = manager.create(GenerationRequest(text="Sentence. " * 100))
    manager.cancel(second.id)
    wait_for(manager, second.id, JobState.cancelled)
    assert manager.get(second.id).result_path is None
    wait_for(manager, first.id, JobState.complete)
    manager.shutdown()
