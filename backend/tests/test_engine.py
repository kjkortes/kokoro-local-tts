from dataclasses import dataclass

import numpy as np

from kokoro_app.engine import KokoroEngine


@dataclass
class Result:
    audio: np.ndarray


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def load_voice(self, voice: str) -> np.ndarray:
        return np.ones((2, 2), dtype=np.float32) * (1 if voice == "af_heart" else 3)

    def __call__(self, text: str, *, voice: object, speed: float, split_pattern: str | None):
        self.calls.append({"text": text, "voice": voice, "speed": speed, "split_pattern": split_pattern})
        yield Result(np.array([0.1, 0.2], dtype=np.float32))
        yield Result(np.array([0.3], dtype=np.float32))


def test_synthesize_collects_segments_and_uses_weighted_voice_tensor() -> None:
    pipeline = FakePipeline()
    engine = KokoroEngine(pipeline_factory=lambda language: pipeline)
    audio = engine.synthesize("Hello.", "a", "af_heart", "af_bella", 0.25, 0.95)
    assert np.allclose(audio, [0.1, 0.2, 0.3])
    assert np.allclose(pipeline.calls[0]["voice"], np.full((2, 2), 1.5))
    assert pipeline.calls[0]["speed"] == 0.95
    assert pipeline.calls[0]["split_pattern"] is None


def test_pipeline_is_cached_by_language() -> None:
    created: list[str] = []

    def factory(language: str) -> FakePipeline:
        created.append(language)
        return FakePipeline()

    engine = KokoroEngine(pipeline_factory=factory)
    engine.synthesize("One.", "a", "af_heart", None, 0.0, 1.0)
    engine.synthesize("Two.", "a", "af_bella", None, 0.0, 1.0)
    assert created == ["a"]

