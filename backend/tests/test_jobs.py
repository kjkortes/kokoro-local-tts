import time
from pathlib import Path

import numpy as np
import pytest

from kokoro_app.jobs import JobManager
from kokoro_app.engine import AlignedWord, SynthesisResult
from kokoro_app.schemas import ExpressionSettings, GenerationRequest, JobState
from kokoro_app.transcription import TimedSegment, TimedWord, WhisperTranscript


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
    rows = ["The  thought begins,", "and\ncontinues naturally."]
    record = manager.create(GenerationRequest(
        text="\n\n".join(rows),
        segments=rows,
    ))
    wait_for(manager, record.id, JobState.complete)

    assert engine.calls == ["The thought begins, and continues naturally."]
    assert [segment["text"] for segment in manager.get(record.id).segments] == rows
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
    assert first["end"] == 0.32
    assert second["start"] == 0.34
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


def test_fish_job_uses_one_remote_request_and_saves_the_returned_mp3(tmp_path: Path) -> None:
    from kokoro_app.fish_audio import FishAudioResult

    class FakeFishClient:
        def __init__(self) -> None:
            self.calls = []

        def synthesize(self, text, **options):
            self.calls.append((text, options))
            return FishAudioResult(b"remote mp3", "audio/mpeg", "generation-456")

    def unexpected_encoder(*args, **kwargs):
        raise AssertionError("Fish MP3 bytes must not pass through the Kokoro PCM encoder")

    class FakeTranscriber:
        def __init__(self) -> None:
            self.calls = []

        def transcribe(self, audio_path: Path, *, prompt: str | None = None):
            assert audio_path.read_bytes() == b"remote mp3"
            self.calls.append((audio_path, prompt))
            return WhisperTranscript(
                duration=3.2,
                segments=(TimedSegment("Why do airplane windows have rounded corners?", 0.1, 3.0),),
                words=(
                    TimedWord("Why", 0.1, 0.4),
                    TimedWord("do", 0.45, 0.62),
                ),
            )

    fish = FakeFishClient()
    transcriber = FakeTranscriber()
    manager = JobManager(
        FakeEngine(),
        tmp_path,
        encoder=unexpected_encoder,
        fish_client=fish,
        fish_transcriber=transcriber,
    )
    record = manager.create(GenerationRequest(
        engine="fish_audio",
        text="[curious]\nWhy do airplane windows have rounded corners?",
        fish_voice="voice-reference",
        fish_style="documentary",
        openrouter_api_key="request-key",
    ))
    wait_for(manager, record.id, JobState.complete)
    finished = manager.get(record.id)

    assert fish.calls == [(
        "[calm, curious documentary narration with natural pacing]\n"
        "[curious]\nWhy do airplane windows have rounded corners?",
        {"voice_id": "voice-reference", "api_key": "request-key"},
    )]
    assert finished.result_path and finished.result_path.read_bytes() == b"remote mp3"
    assert finished.result_path.suffix == ".mp3"
    assert finished.filename and finished.filename.endswith(".mp3")
    assert finished.generation_id == "generation-456"
    assert finished.duration == 3.2
    assert finished.segments == [{
        "text": "Why do airplane windows have rounded corners?",
        "start": 0.1,
        "end": 3.0,
        "paragraph_end": True,
    }]
    assert finished.words == [
        {"text": "Why", "start": 0.1, "end": 0.4},
        {"text": "do", "start": 0.45, "end": 0.62},
    ]
    assert finished.timing_source == "whisper"
    assert transcriber.calls == [(finished.result_path, record.request.text)]
    manager.shutdown()


def test_fish_storyboard_transcript_keeps_source_phrase_rows(tmp_path: Path) -> None:
    from kokoro_app.fish_audio import FishAudioResult

    class FakeFishClient:
        def synthesize(self, *args, **kwargs):
            return FishAudioResult(b"remote mp3", "audio/mpeg", "generation-789")

    class FakeTranscriber:
        def transcribe(self, *args, **kwargs):
            return WhisperTranscript(
                duration=1.2,
                segments=(TimedSegment("Source first. Source second.", 0.1, 1.1),),
                words=(
                    TimedWord("Source", 0.1, 0.3),
                    TimedWord("first.", 0.35, 0.6),
                    TimedWord("Source", 0.7, 0.82),
                    TimedWord("second.", 0.86, 1.1),
                ),
            )

    rows = ["Source first.", "Source second."]
    manager = JobManager(
        FakeEngine(),
        tmp_path,
        encoder=lambda *args, **kwargs: None,
        fish_client=FakeFishClient(),
        fish_transcriber=FakeTranscriber(),
    )
    record = manager.create(GenerationRequest(
        engine="fish_audio",
        text="\n\n".join(rows),
        segments=rows,
    ))
    wait_for(manager, record.id, JobState.complete)

    assert manager.get(record.id).segments == [
        {"text": "Source first.", "start": 0.1, "end": 0.6, "paragraph_end": True},
        {"text": "Source second.", "start": 0.7, "end": 1.1, "paragraph_end": True},
    ]
    manager.shutdown()


def test_kokoro_job_does_not_require_or_call_openrouter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class UnexpectedFishClient:
        def synthesize(self, *args, **kwargs):
            raise AssertionError("Kokoro must not contact OpenRouter")

    manager = JobManager(
        FakeEngine(), tmp_path, encoder=fake_encode, fish_client=UnexpectedFishClient()
    )
    record = manager.create(GenerationRequest(text="Offline speech."))
    wait_for(manager, record.id, JobState.complete)
    assert manager.get(record.id).result_path.read_bytes() == b"local audio"
    manager.shutdown()
