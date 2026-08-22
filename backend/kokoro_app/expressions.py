from __future__ import annotations

from dataclasses import dataclass, replace

from kokoro_app.schemas import ExpressionSettings


@dataclass(frozen=True)
class ExpressionPreset:
    id: str
    name: str
    description: str
    speed: float
    pitch: float
    tempo: float
    pause_scale: float
    volume: float = 1.0


@dataclass(frozen=True)
class ResolvedExpression:
    speed: float
    pitch: float
    tempo: float
    pause_scale: float
    volume: float
    is_custom: bool


def _preset(identifier: str, name: str, description: str, values: tuple[float, float, float, float]) -> ExpressionPreset:
    return ExpressionPreset(identifier, name, description, *values)


PRESETS = {
    "neutral": _preset("neutral", "Neutral", "Natural timing with no tonal processing.", (1.00, 0.0, 1.00, 1.00)),
    "warm": _preset("warm", "Warm", "A touch lower, slower, and more relaxed.", (0.96, -0.4, 0.98, 1.08)),
    "calm": _preset("calm", "Calm", "Measured delivery with softer pitch and longer pauses.", (0.90, -0.7, 0.94, 1.25)),
    "bright": _preset("bright", "Bright", "Lighter pitch and brisker sentence flow.", (1.05, 0.8, 1.04, 0.88)),
    "serious": _preset("serious", "Serious", "Lower register with deliberate pacing.", (0.93, -1.0, 0.97, 1.15)),
    "dramatic": _preset("dramatic", "Dramatic", "Slower delivery with pronounced pauses.", (0.88, -0.6, 1.00, 1.55)),
}


def resolve_expression(preset: str, overrides: ExpressionSettings | None) -> ResolvedExpression:
    base = PRESETS[preset]
    values = {
        "speed": base.speed,
        "pitch": base.pitch,
        "tempo": base.tempo,
        "pause_scale": base.pause_scale,
        "volume": base.volume,
    }
    if overrides is not None:
        for key in values:
            candidate = getattr(overrides, key)
            if candidate is not None:
                values[key] = candidate
    custom = any(values[key] != getattr(base, key) for key in values)
    return ResolvedExpression(**values, is_custom=custom)


def with_volume(expression: ResolvedExpression, volume: float) -> ResolvedExpression:
    return replace(expression, volume=volume, is_custom=expression.is_custom or volume != 1.0)

