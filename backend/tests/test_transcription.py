from pathlib import Path
from types import SimpleNamespace

import pytest

from kokoro_app.transcription import TranscriptionError, WhisperTranscriber


class FakeWhisperModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def transcribe(self, audio_path: str, **options):
        self.calls.append((audio_path, options))
        segments = iter([
            SimpleNamespace(
                text=" Hello world.",
                start=0.12,
                end=1.18,
                words=[
                    SimpleNamespace(word=" Hello", start=0.12, end=0.51),
                    SimpleNamespace(word=" world.", start=0.59, end=1.18),
                ],
            ),
            SimpleNamespace(
                text=" Accurate timing.",
                start=1.34,
                end=2.42,
                words=[
                    SimpleNamespace(word=" Accurate", start=1.34, end=1.88),
                    SimpleNamespace(word=" timing.", start=1.94, end=2.42),
                ],
            ),
        ])
        return segments, SimpleNamespace(duration=2.75)


def test_transcriber_uses_word_timestamps_and_returns_downloadable_timing_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KOKORO_WHISPER_MODEL", raising=False)
    model = FakeWhisperModel()
    factory_calls: list[tuple[str, dict[str, str]]] = []

    def factory(model_name: str, **options: str) -> FakeWhisperModel:
        factory_calls.append((model_name, options))
        return model

    audio_path = tmp_path / "fish.mp3"
    audio_path.write_bytes(b"fake mp3")
    transcriber = WhisperTranscriber(model_factory=factory)

    result = transcriber.transcribe(
        audio_path,
        prompt="[calm]\nHello world. Accurate timing.",
    )

    assert factory_calls == [("small", {"device": "cpu", "compute_type": "int8"})]
    assert model.calls == [(
        str(audio_path),
        {
            "beam_size": 5,
            "initial_prompt": "Hello world. Accurate timing.",
            "word_timestamps": True,
        },
    )]
    assert result.duration == pytest.approx(2.75)
    assert [segment.as_dict() for segment in result.segments] == [
        {"text": "Hello world.", "start": 0.12, "end": 1.18, "paragraph_end": True},
        {"text": "Accurate timing.", "start": 1.34, "end": 2.42, "paragraph_end": True},
    ]
    assert [word.as_dict() for word in result.words] == [
        {"text": "Hello", "start": 0.12, "end": 0.51},
        {"text": "world.", "start": 0.59, "end": 1.18},
        {"text": "Accurate", "start": 1.34, "end": 1.88},
        {"text": "timing.", "start": 1.94, "end": 2.42},
    ]


def test_transcriber_loads_the_model_only_once(tmp_path: Path) -> None:
    model = FakeWhisperModel()
    calls = 0

    def factory(*args, **kwargs) -> FakeWhisperModel:
        nonlocal calls
        calls += 1
        return model

    audio_path = tmp_path / "fish.mp3"
    audio_path.write_bytes(b"fake mp3")
    transcriber = WhisperTranscriber(model_factory=factory)

    transcriber.transcribe(audio_path)
    transcriber.transcribe(audio_path)

    assert calls == 1


def test_transcriber_rejects_audio_without_recognized_speech(tmp_path: Path) -> None:
    class SilentModel:
        def transcribe(self, *args, **kwargs):
            return iter(()), SimpleNamespace(duration=1.5)

    audio_path = tmp_path / "silent.mp3"
    audio_path.write_bytes(b"fake mp3")
    transcriber = WhisperTranscriber(model_factory=lambda *args, **kwargs: SilentModel())

    with pytest.raises(TranscriptionError, match="did not detect any speech"):
        transcriber.transcribe(audio_path)
