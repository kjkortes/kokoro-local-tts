from __future__ import annotations

from kokoro_app.schemas import Gender, LanguageInfo, VoiceInfo


LANGUAGES = (
    LanguageInfo(code="a", name="American English", locale="en-US"),
    LanguageInfo(code="b", name="British English", locale="en-GB"),
    LanguageInfo(code="e", name="Spanish", locale="es-ES"),
    LanguageInfo(code="f", name="French", locale="fr-FR"),
    LanguageInfo(code="h", name="Hindi", locale="hi-IN"),
    LanguageInfo(code="i", name="Italian", locale="it-IT"),
    LanguageInfo(code="j", name="Japanese", locale="ja-JP"),
    LanguageInfo(code="p", name="Brazilian Portuguese", locale="pt-BR"),
    LanguageInfo(code="z", name="Mandarin Chinese", locale="zh-CN"),
)


_VOICE_IDS = (
    "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore",
    "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael",
    "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "ef_dora", "em_alex", "em_santa", "ff_siwis",
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola",
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    "pf_dora", "pm_alex", "pm_santa",
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
    "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
)


def _display_name(identifier: str) -> str:
    return identifier.split("_", 1)[1].replace("_", " ").title()


VOICES = tuple(
    VoiceInfo(
        id=identifier,
        name=_display_name(identifier),
        language=identifier[0],
        gender=Gender.female if identifier[1] == "f" else Gender.male,
    )
    for identifier in _VOICE_IDS
)

_BY_ID = {voice.id: voice for voice in VOICES}


def voice_by_id(identifier: str) -> VoiceInfo | None:
    return _BY_ID.get(identifier)


def voices_for(language: str, gender: Gender | None = None) -> list[VoiceInfo]:
    return [
        voice
        for voice in VOICES
        if voice.language == language and (gender is None or voice.gender == gender)
    ]
