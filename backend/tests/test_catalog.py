from kokoro_app.catalog import LANGUAGES, VOICES, voices_for
from kokoro_app.schemas import Gender, GenerationRequest


def test_catalog_has_every_kokoro_v1_language_and_unique_voice_ids() -> None:
    assert {item.code for item in LANGUAGES} == {"a", "b", "e", "f", "h", "i", "j", "p", "z"}
    assert len(VOICES) == 54
    assert len({voice.id for voice in VOICES}) == len(VOICES)


def test_voice_filter_respects_language_and_gender() -> None:
    voices = voices_for("a", Gender.female)
    assert voices
    assert all(voice.language == "a" and voice.gender == Gender.female for voice in voices)


def test_generation_request_rejects_incompatible_blend() -> None:
    try:
        GenerationRequest(
            text="Hello",
            language="a",
            primary_voice="af_heart",
            secondary_voice="bf_emma",
        )
    except ValueError as error:
        assert "same language" in str(error)
    else:
        raise AssertionError("An incompatible blend was accepted")
