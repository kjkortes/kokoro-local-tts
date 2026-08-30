from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Gender(StrEnum):
    female = "female"
    male = "male"


class OutputFormat(StrEnum):
    wav = "wav"
    mp3 = "mp3"
    flac = "flac"
    ogg = "ogg"


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


class ExpressionSettings(BaseModel):
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    pitch: float | None = Field(default=None, ge=-4.0, le=4.0)
    tempo: float | None = Field(default=None, ge=0.75, le=1.25)
    pause_scale: float | None = Field(default=None, ge=0.5, le=2.0)
    volume: float | None = Field(default=None, ge=0.0, le=1.5)


class GenerationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    language: str = "a"
    primary_voice: str = "af_heart"
    secondary_voice: str | None = None
    blend_ratio: float = Field(default=0.35, ge=0.0, le=1.0)
    preset: Literal["neutral", "warm", "calm", "bright", "serious", "dramatic"] = "neutral"
    expression: ExpressionSettings | None = None
    output_format: OutputFormat = OutputFormat.wav
    normalize: bool = True

    @model_validator(mode="after")
    def validate_voice_selection(self) -> GenerationRequest:
        from kokoro_app.catalog import voice_by_id

        if not self.text.strip():
            raise ValueError("Text must contain something to speak")
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
    transcript: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    action: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
