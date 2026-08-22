from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np


PipelineFactory = Callable[[str], Any]


@dataclass(frozen=True)
class EngineStatus:
    state: str
    device: str = "cpu"
    detail: str | None = None


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
    ) -> np.ndarray:
        with self._lock:
            pipeline = self._get_pipeline(language)
            voice = self._voice_spec(pipeline, primary_voice, secondary_voice, blend_ratio)
            pieces: list[np.ndarray] = []
            try:
                for result in pipeline(text, voice=voice, speed=speed, split_pattern=None):
                    audio = getattr(result, "audio", None)
                    if audio is None:
                        audio = result[2]
                    pieces.append(_as_numpy(audio))
            except Exception as error:
                self._state = "error"
                self._detail = str(error)
                raise
            self._state = "ready"
            self._detail = None
            return np.concatenate(pieces) if pieces else np.array([], dtype=np.float32)
