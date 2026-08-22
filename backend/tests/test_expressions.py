from kokoro_app.expressions import PRESETS, resolve_expression
from kokoro_app.schemas import ExpressionSettings


def test_neutral_is_a_no_op() -> None:
    value = resolve_expression("neutral", None)
    assert (value.speed, value.pitch, value.tempo, value.pause_scale) == (1.0, 0.0, 1.0, 1.0)
    assert value.is_custom is False


def test_override_marks_preset_custom_without_losing_other_values() -> None:
    value = resolve_expression("calm", ExpressionSettings(speed=0.91))
    assert value.speed == 0.91
    assert value.pitch == PRESETS["calm"].pitch
    assert value.is_custom is True


def test_preset_descriptions_explain_audible_change() -> None:
    assert all(preset.description.strip() for preset in PRESETS.values())

