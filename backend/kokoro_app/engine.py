from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from kokoro_app.audio import SAMPLE_RATE


PipelineFactory = Callable[[str], Any]


@dataclass(frozen=True)
class EngineStatus:
    state: str
    device: str = "cpu"
    detail: str | None = None


@dataclass(frozen=True)
class AlignedWord:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class SynthesisResult:
    audio: np.ndarray
    words: tuple[AlignedWord, ...] = ()


def _default_pipeline_factory(language: str) -> Any:
    from kokoro import KPipeline

    return KPipeline(lang_code=language, repo_id="hexgrad/Kokoro-82M")


def _as_numpy(audio: Any) -> np.ndarray:
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    return np.asarray(audio, dtype=np.float32).reshape(-1)


class KokoroEngine:
    def __init__(self, pipeline_factory: PipelineFactory | None = None) -> None:
        self._pipeline_factory = pipeline_factory or _default_pipeline_factory
        self._pipelines: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._state = "unloaded"
        self._detail: str | None = None

    def status(self) -> EngineStatus:
        with self._lock:
            return EngineStatus(self._state, detail=self._detail)

    def load(self, language: str = "a") -> None:
        self._get_pipeline(language)

    def _get_pipeline(self, language: str) -> Any:
        if language in self._pipelines:
            return self._pipelines[language]
        self._state = "loading"
        self._detail = "Loading Kokoro voice model"
        try:
            pipeline = self._pipeline_factory(language)
        except Exception as error:
            self._state = "error"
            self._detail = str(error)
            raise
        self._pipelines[language] = pipeline
        self._state = "ready"
        self._detail = None
        return pipeline

    @staticmethod
    def _voice_spec(
        pipeline: Any,
        primary_voice: str,
        secondary_voice: str | None,
        blend_ratio: float,
    ) -> Any:
        if not secondary_voice or blend_ratio <= 0:
            return primary_voice
        primary = pipeline.load_voice(primary_voice)
        secondary = pipeline.load_voice(secondary_voice)
        return primary * (1 - blend_ratio) + secondary * blend_ratio

    def synthesize(
        self,
        text: str,
        language: str,
        primary_voice: str,
        secondary_voice: str | None,
        blend_ratio: float,
        speed: float,
    ) -> SynthesisResult:
        with self._lock:
            pipeline = self._get_pipeline(language)
            voice = self._voice_spec(pipeline, primary_voice, secondary_voice, blend_ratio)
            pieces: list[np.ndarray] = []
            words: list[AlignedWord] = []
            sample_offset = 0
            pending_prefix = ""
            try:
                for result in pipeline(text, voice=voice, speed=speed, split_pattern=None):
                    audio = getattr(result, "audio", None)
                    if audio is None:
                        audio = result[2]
                    piece = _as_numpy(audio)
                    tokens = getattr(result, "tokens", None) if language in {"a", "b"} else None
                    preceded_by_space = True
                    for token in tokens or ():
                        token_text = str(getattr(token, "text", ""))
                        start = getattr(token, "start_ts", None)
                        end = getattr(token, "end_ts", None)
                        if any(character.isalnum() for character in token_text):
                            if start is not None and end is not None:
                                words.append(AlignedWord(
                                    text=pending_prefix + token_text,
                                    start=round(sample_offset / SAMPLE_RATE + float(start), 6),
                                    end=round(sample_offset / SAMPLE_RATE + float(end), 6),
                                ))
                            pending_prefix = ""
                        elif preceded_by_space or not words:
                            pending_prefix += token_text
                        else:
                            previous = words[-1]
                            words[-1] = AlignedWord(
                                text=previous.text + token_text,
                                start=previous.start,
                                end=previous.end,
                            )
                        preceded_by_space = bool(getattr(token, "whitespace", ""))
                    pieces.append(piece)
                    sample_offset += len(piece)
            except Exception as error:
                self._state = "error"
                self._detail = str(error)
                raise
            self._state = "ready"
            self._detail = None
            audio = np.concatenate(pieces) if pieces else np.array([], dtype=np.float32)
            return SynthesisResult(audio=audio, words=tuple(words))
