from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from kokoro_app.fish_reference import normalize_fish_reference


class Gender(StrEnum):
    female = "female"
    male = "male"


class OutputFormat(StrEnum):
    wav = "wav"
    mp3 = "mp3"
    flac = "flac"
    ogg = "ogg"


class TtsEngine(StrEnum):
    kokoro = "kokoro"
    fish_audio = "fish_audio"


class TimestampEngine(StrEnum):
    whisperx = "whisperx"
    whisper = "whisper"


class FishDeliveryStyle(StrEnum):
    natural = "natural"
    documentary = "documentary"
    conversational = "conversational"
    educational = "educational"
    energetic = "energetic"
    mysterious = "mysterious"
    dramatic = "dramatic"
    calm = "calm"
    custom = "custom"


class JobState(StrEnum):
    queued = "queued"
    loading_model = "loading_model"
    synthesizing = "synthesizing"
    processing = "processing"
    complete = "complete"
    cancelled = "cancelled"
    failed = "failed"


class LanguageInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    name: str
    locale: str


class VoiceInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    language: str
    gender: Gender


class FishVoiceDetails(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    reference_id: str = Field(min_length=1, max_length=256)


class FishVoiceInput(FishVoiceDetails):
    @field_validator("reference_id", mode="before")
    @classmethod
    def normalize_reference(cls, value: object) -> object:
        return normalize_fish_reference(value) if isinstance(value, str) else value


class FishVoiceReference(FishVoiceDetails):
    id: str


class FishVoicePage(BaseModel):
    items: list[FishVoiceReference]
    total: int
    page: int
    page_size: int


class ExpressionSettings(BaseModel):
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    pitch: float | None = Field(default=None, ge=-4.0, le=4.0)
    tempo: float | None = Field(default=None, ge=0.75, le=1.25)
    pause_scale: float | None = Field(default=None, ge=0.5, le=2.0)
    volume: float | None = Field(default=None, ge=0.0, le=1.5)


class GenerationRequest(BaseModel):
    engine: TtsEngine = TtsEngine.kokoro
    text: str = Field(min_length=1, max_length=100_000)
    segments: list[str] | None = Field(default=None, min_length=1, max_length=10_000)
    language: str = "a"
    primary_voice: str = "af_heart"
    secondary_voice: str | None = None
    blend_ratio: float = Field(default=0.35, ge=0.0, le=1.0)
    preset: Literal["neutral", "warm", "calm", "bright", "serious", "dramatic"] = "neutral"
    expression: ExpressionSettings | None = None
    pause_ms: int | None = Field(default=None, ge=0, le=5000)
    output_format: OutputFormat = OutputFormat.wav
    normalize: bool = True
    fish_voice: str | None = Field(default=None, max_length=256)
    fish_style: FishDeliveryStyle = FishDeliveryStyle.natural
    timestamp_engine: TimestampEngine = TimestampEngine.whisperx
    fish_custom_style: str | None = Field(default=None, max_length=500)
    openrouter_api_key: SecretStr | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_voice_selection(self) -> GenerationRequest:
        from kokoro_app.catalog import voice_by_id

        if not self.text.strip():
            raise ValueError("Text must contain something to speak")
        if self.segments is not None:
            if any(not segment.strip() for segment in self.segments):
                raise ValueError("Storyboard segments must contain speech text")
            if "\n\n".join(self.segments) != self.text:
                raise ValueError("Storyboard segments must exactly match the submitted text")
        if self.engine == TtsEngine.fish_audio:
            if self.fish_style == FishDeliveryStyle.custom and not (
                self.fish_custom_style and self.fish_custom_style.strip()
            ):
                raise ValueError("A custom Fish delivery instruction is required")
            return self
        primary = voice_by_id(self.primary_voice)
        if primary is None or primary.language != self.language:
            raise ValueError("Primary voice must match the selected language")
        if self.secondary_voice:
            secondary = voice_by_id(self.secondary_voice)
            if secondary is None or secondary.language != self.language:
                raise ValueError("Blended voices must use the same language")
            if secondary.id == primary.id:
                raise ValueError("Choose two different voices for a blend")
        return self


class ExpressionPresetInfo(BaseModel):
    id: str
    name: str
    description: str
    speed: float
    pitch: float
    tempo: float
    pause_scale: float


class AppConfig(BaseModel):
    languages: list[LanguageInfo]
    voices: list[VoiceInfo]
    presets: list[ExpressionPresetInfo]
    formats: list[OutputFormat]
    defaults: dict[str, object]
    limits: dict[str, dict[str, float]]
    openrouter_configured: bool = False


class StatusResponse(BaseModel):
    state: Literal["unloaded", "loading", "ready", "error"]
    device: str = "cpu"
    version: str
    detail: str | None = None


class TranscriptSegment(BaseModel):
    text: str
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)
    paragraph_end: bool = False


class TranscriptWord(BaseModel):
    text: str
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)


class JobResponse(BaseModel):
    id: str
    state: JobState
    phase: str
    progress: float = Field(ge=0.0, le=1.0)
    error: dict[str, str] | None = None
    audio_url: str | None = None
    download_url: str | None = None
    filename: str | None = None
    duration: float | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)
    words: list[TranscriptWord] = Field(default_factory=list)
    transcript: str | None = None
    timing_source: Literal["kokoro", "whisper", "whisperx"] | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    action: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
