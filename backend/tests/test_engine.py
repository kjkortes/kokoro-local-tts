from dataclasses import dataclass

import numpy as np

from kokoro_app.engine import KokoroEngine


@dataclass
class Result:
    audio: np.ndarray
    tokens: list[object] | None = None


@dataclass
class Token:
    text: str
    start_ts: float
    end_ts: float
    whitespace: str = ""


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
    result = engine.synthesize("Hello.", "a", "af_heart", "af_bella", 0.25, 0.95)
    assert np.allclose(result.audio, [0.1, 0.2, 0.3])
    assert np.allclose(pipeline.calls[0]["voice"], np.full((2, 2), 1.5))
    assert pipeline.calls[0]["speed"] == 0.95
    assert pipeline.calls[0]["split_pattern"] is None


def test_synthesize_preserves_word_alignment_across_audio_pieces() -> None:
    class AlignedPipeline(FakePipeline):
        def __call__(self, text: str, *, voice: object, speed: float, split_pattern: str | None):
            yield Result(
                np.ones(2_400, dtype=np.float32),
                [Token("Hello", 0.01, 0.07), Token(",", 0.07, 0.08)],
            )
            yield Result(
                np.ones(4_800, dtype=np.float32),
                [Token("world", 0.02, 0.15), Token("!", 0.15, 0.17)],
            )

    result = KokoroEngine(pipeline_factory=lambda language: AlignedPipeline()).synthesize(
        "Hello, world!", "a", "af_heart", None, 0.0, 1.0,
    )

    assert [(word.text, word.start, word.end) for word in result.words] == [
        ("Hello,", 0.01, 0.07),
        ("world!", 0.12, 0.25),
    ]


def test_synthesize_does_not_expose_word_alignment_for_non_english_audio() -> None:
    class UnexpectedTokenPipeline(FakePipeline):
        def __call__(self, text: str, *, voice: object, speed: float, split_pattern: str | None):
            yield Result(
                np.ones(2_400, dtype=np.float32),
                [Token("Hola", 0.01, 0.07)],
            )

    result = KokoroEngine(pipeline_factory=lambda language: UnexpectedTokenPipeline()).synthesize(
        "Hola", "e", "ef_dora", None, 0.0, 1.0,
    )

    assert result.words == ()


def test_synthesize_keeps_leading_and_trailing_punctuation_with_words() -> None:
    class PunctuatedPipeline(FakePipeline):
        def __call__(self, text: str, *, voice: object, speed: float, split_pattern: str | None):
            yield Result(
                np.ones(4_800, dtype=np.float32),
                [
                    Token("Pay", 0.01, 0.04, " "),
                    Token("$", 0.04, 0.04),
                    Token("13.60", 0.05, 0.13),
                    Token("!", 0.13, 0.15),
                ],
            )

    result = KokoroEngine(pipeline_factory=lambda language: PunctuatedPipeline()).synthesize(
        "Pay $13.60!", "a", "af_heart", None, 0.0, 1.0,
    )

    assert [(word.text, word.start, word.end) for word in result.words] == [
        ("Pay", 0.01, 0.04),
        ("$13.60!", 0.05, 0.13),
    ]


def test_pipeline_is_cached_by_language() -> None:
    created: list[str] = []

    def factory(language: str) -> FakePipeline:
        created.append(language)
        return FakePipeline()

    engine = KokoroEngine(pipeline_factory=factory)
    engine.synthesize("One.", "a", "af_heart", None, 0.0, 1.0)
    engine.synthesize("Two.", "a", "af_bella", None, 0.0, 1.0)
    assert created == ["a"]
