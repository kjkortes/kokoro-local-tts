from pathlib import Path
from types import SimpleNamespace

import pytest

from kokoro_app.transcription import TimedSegment, TimedWord, TranscriptionError, WhisperTranscript, WhisperTranscriber, WhisperXTranscriber


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
        return segments, SimpleNamespace(duration=2.75, language="en")


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
    assert result.language == "en"
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


class FakeRecognizer:
    def transcribe(self, audio_path: Path, *, prompt: str | None = None):
        return WhisperTranscript(
            duration=2.0,
            segments=(TimedSegment("Hello world.", 0.0, 1.9),),
            words=(TimedWord("Hello", 0.0, 1.0),),
            language="en",
        )


class FakeWhisperX:
    def __init__(self):
        self.languages = []
        self.transcripts = []

    def load_audio(self, path):
        return [0.0] * 32_000

    def load_align_model(self, *, language_code, device):
        assert device == "cpu"
        self.languages.append(language_code)
        return "alignment-model", {"language": language_code}

    def align(self, segments, model, metadata, audio, device, *, return_char_alignments):
        assert model == "alignment-model"
        assert metadata == {"language": "en"}
        assert device == "cpu"
        assert return_char_alignments is False
        self.transcripts.append(segments)
        return {"segments": [{"text": "Hello world.", "start": 0.15, "end": 1.6, "words": [
            {"word": "Hello", "start": 0.15, "end": 0.55},
            {"word": "world.", "start": 0.65, "end": 1.6},
            {"word": "untimed"},
            {"word": "invalid", "start": float("nan"), "end": 1.8},
        ]}]}


def test_whisperx_uses_aligned_words_and_reuses_the_language_model(tmp_path: Path) -> None:
    backend = FakeWhisperX()
    transcriber = WhisperXTranscriber(recognizer=FakeRecognizer(), alignment_backend=backend)
    result = transcriber.transcribe(tmp_path / "fish.mp3", prompt="[calm] Hello world.")
    assert result.duration == 2.0
    assert result.language == "en"
    assert result.segments == (TimedSegment("Hello world.", 0.15, 1.6),)
    assert result.words == (TimedWord("Hello", 0.15, 0.55), TimedWord("world.", 0.65, 1.6))
    assert backend.transcripts == [[{"text": "Hello world.", "start": 0.0, "end": 1.9}]]
    transcriber.transcribe(tmp_path / "fish.mp3")
    assert backend.languages == ["en"]


def test_whisperx_reports_unsupported_alignment_languages_without_silent_fallback(tmp_path: Path) -> None:
    class UnsupportedBackend(FakeWhisperX):
        def load_align_model(self, **kwargs):
            raise ValueError("No alignment model for this language")

    transcriber = WhisperXTranscriber(recognizer=FakeRecognizer(), alignment_backend=UnsupportedBackend())
    with pytest.raises(TranscriptionError, match="faster-whisper"):
        transcriber.transcribe(tmp_path / "fish.mp3")


def test_whisperx_rejects_results_without_aligned_words(tmp_path: Path) -> None:
    class UnalignedBackend(FakeWhisperX):
        def align(self, *args, **kwargs):
            return {"segments": [{"text": "Hello world.", "start": 0.0, "end": 1.9, "words": []}]}

    transcriber = WhisperXTranscriber(recognizer=FakeRecognizer(), alignment_backend=UnalignedBackend())
    with pytest.raises(TranscriptionError, match="align"):
        transcriber.transcribe(tmp_path / "fish.mp3")
