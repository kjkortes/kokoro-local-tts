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
        {"text": "Third row, exactly!", "start": 0.84, "end": 0.89, "paragraph_end": True},
    ]
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
