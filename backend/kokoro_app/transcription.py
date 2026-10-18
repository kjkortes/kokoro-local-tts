from __future__ import annotations

import math
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


class TranscriptionError(RuntimeError):
    """Raised when local timestamp extraction cannot produce a transcript."""


@dataclass(frozen=True)
class TimedSegment:
    text: str
    start: float
    end: float

    def as_dict(self) -> dict[str, str | float | bool]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "paragraph_end": True,
        }


@dataclass(frozen=True)
class TimedWord:
    text: str
    start: float
    end: float

    def as_dict(self) -> dict[str, str | float]:
        return {"text": self.text, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class WhisperTranscript:
    duration: float
    segments: tuple[TimedSegment, ...]
    words: tuple[TimedWord, ...]
    language: str | None = None


class AudioTranscriber(Protocol):
    def transcribe(
        self, audio_path: Path, *, prompt: str | None = None
    ) -> WhisperTranscript: ...


ModelFactory = Callable[..., object]


def _spoken_prompt(text: str | None) -> str | None:
    if not text:
        return None
    without_directions = re.sub(r"\[[^\]\n]{1,200}\]", " ", text)
    prompt = re.sub(r"\s+", " ", without_directions).strip()
    return prompt or None


def _timestamp(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(max(0.0, number), 6)


class WhisperTranscriber:
    """Lazily transcribe audio with faster-whisper and word timestamps."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.model_name = model_name or os.environ.get("KOKORO_WHISPER_MODEL", "small")
        self._model_factory = model_factory
        self._model: object | None = None
        self._model_lock = threading.Lock()

    def _load_model(self) -> object:
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            try:
                factory = self._model_factory
                if factory is None:
                    from faster_whisper import WhisperModel

                    factory = WhisperModel
                self._model = factory(
                    self.model_name,
                    device="cpu",
                    compute_type="int8",
                )
            except Exception as error:
                raise TranscriptionError(
                    "The local Whisper model could not be loaded. Check the network on the "
                    "first run so the model can be downloaded, then try again."
                ) from error
        return self._model

    def transcribe(
        self, audio_path: Path, *, prompt: str | None = None
    ) -> WhisperTranscript:
        model = self._load_model()
        options: dict[str, object] = {
            "beam_size": 5,
            "word_timestamps": True,
        }
        initial_prompt = _spoken_prompt(prompt)
        if initial_prompt:
            options["initial_prompt"] = initial_prompt
        try:
            raw_segments, info = model.transcribe(str(audio_path), **options)  # type: ignore[attr-defined]
            segments: list[TimedSegment] = []
            words: list[TimedWord] = []
            for raw_segment in raw_segments:
                text = str(getattr(raw_segment, "text", "")).strip()
                start = _timestamp(getattr(raw_segment, "start", None))
                end = _timestamp(getattr(raw_segment, "end", None))
                if text and start is not None and end is not None and end >= start:
                    segments.append(TimedSegment(text, start, end))
                for raw_word in getattr(raw_segment, "words", None) or ():
                    word_text = str(getattr(raw_word, "word", "")).strip()
                    word_start = _timestamp(getattr(raw_word, "start", None))
                    word_end = _timestamp(getattr(raw_word, "end", None))
                    if (
                        word_text
                        and word_start is not None
                        and word_end is not None
                        and word_end >= word_start
                    ):
                        words.append(TimedWord(word_text, word_start, word_end))
        except TranscriptionError:
            raise
        except Exception as error:
            raise TranscriptionError(
                "Local Whisper could not transcribe the Fish Audio result."
            ) from error

        if not segments:
            raise TranscriptionError(
                "Local Whisper did not detect any speech in the Fish Audio result."
            )

        measured_duration = _timestamp(getattr(info, "duration", None))
        duration = max(
            measured_duration or 0.0,
            segments[-1].end,
            words[-1].end if words else 0.0,
        )
        return WhisperTranscript(duration, tuple(segments), tuple(words), getattr(info, "language", None))


class WhisperXTranscriber:
    """Recognize locally, then use WhisperX's language-specific forced alignment."""

    def __init__(self, *, recognizer: AudioTranscriber | None = None, alignment_backend: Any = None) -> None:
        self.recognizer = recognizer or WhisperTranscriber()
        self._backend = alignment_backend
        self._models: dict[str, tuple[Any, Any]] = {}
        self._model_lock = threading.Lock()

    def _load_backend(self) -> Any:
        if self._backend is None:
            try:
                import whisperx

                self._backend = whisperx
            except Exception as error:
                raise TranscriptionError(
                    "WhisperX could not be loaded. Run `uv sync` and restart the app, "
                    "or select Whisper (faster-whisper) for timestamps."
                ) from error
        return self._backend

    def _alignment_model(self, backend: Any, language: str) -> tuple[Any, Any]:
        with self._model_lock:
            if language not in self._models:
                try:
                    self._models[language] = backend.load_align_model(language_code=language, device="cpu")
                except Exception as error:
                    raise TranscriptionError(
                        f"WhisperX could not load alignment for language '{language}'. "
                        "Check the network for the first model download, or select Whisper (faster-whisper)."
                    ) from error
            return self._models[language]

    def transcribe(self, audio_path: Path, *, prompt: str | None = None) -> WhisperTranscript:
        backend = self._load_backend()
        recognized = self.recognizer.transcribe(audio_path, prompt=prompt)
        if not recognized.language:
            raise TranscriptionError("WhisperX could not determine the speech language. Select Whisper (faster-whisper) or retry with clearer speech.")
        model, metadata = self._alignment_model(backend, recognized.language)
        try:
            audio = backend.load_audio(str(audio_path))
            duration = len(audio) / 16_000
            aligned = backend.align(
                [{"text": segment.text, "start": segment.start, "end": segment.end} for segment in recognized.segments],
                model, metadata, audio, "cpu", return_char_alignments=False,
            )
            segments: list[TimedSegment] = []
            words: list[TimedWord] = []
            for segment in aligned.get("segments", []):
                text = str(segment.get("text", "")).strip()
                bounds = _aligned_bounds(segment, duration)
                if text and bounds is not None:
                    segments.append(TimedSegment(text, *bounds))
                for word in segment.get("words", []):
                    text = str(word.get("word", "")).strip()
                    bounds = _aligned_bounds(word, duration)
                    if text and bounds is not None:
                        words.append(TimedWord(text, *bounds))
        except Exception as error:
            raise TranscriptionError(
                "WhisperX could not align the Fish Audio result. Retry or select Whisper (faster-whisper) for timestamps."
            ) from error
        if not segments or not words:
            raise TranscriptionError(
                "WhisperX did not produce aligned words. Retry or select Whisper (faster-whisper) for timestamps."
            )
        return WhisperTranscript(duration, tuple(segments), tuple(words), recognized.language)


def _aligned_bounds(item: dict, duration: float) -> tuple[float, float] | None:
    start, end = _timestamp(item.get("start")), _timestamp(item.get("end"))
    if start is None or end is None or end < start or start >= duration:
        return None
    return start, min(end, duration)
