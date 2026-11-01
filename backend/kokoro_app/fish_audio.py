from __future__ import annotations

import json
import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENROUTER_TTS_URL = "https://openrouter.ai/api/v1/audio/speech"
FISH_AUDIO_MODEL = "fish-audio/s2.1-pro-free:free"
DEFAULT_FISH_VOICE = "b0204e37cbc94a16954c78697b844af2"
DEFAULT_RESPONSE_FORMAT = "mp3"
DEFAULT_TIMEOUT_SECONDS = 120


FISH_STYLE_INSTRUCTIONS = {
    "natural": "natural conversational speech",
    "documentary": "calm, curious documentary narration with natural pacing",
    "conversational": "relaxed conversational speech with natural pacing",
    "educational": "friendly, clear and engaging educational narration",
    "energetic": "energetic and enthusiastic narration",
    "mysterious": "quiet, mysterious storytelling with controlled pacing",
    "dramatic": "dramatic storytelling with controlled intensity",
    "calm": "calm, warm and relaxed narration",
}


def default_fish_voice() -> str:
    return os.getenv("FISH_AUDIO_DEFAULT_VOICE", DEFAULT_FISH_VOICE).strip()


@dataclass(frozen=True)
class FishAudioResult:
    audio: bytes
    content_type: str
    generation_id: str | None = None


class FishAudioError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "fish_audio_failed",
        detail: str = "",
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail
        self.status_code = status_code


def prepare_fish_input(
    text: str,
    style: str | None,
    custom_style: str | None = None,
) -> str:
    if style is None:
        return text
    instruction = custom_style.strip() if style == "custom" and custom_style else ""
    if not instruction:
        instruction = FISH_STYLE_INSTRUCTIONS.get(style, "")
    if not instruction:
        return text
    if not (instruction.startswith("[") and instruction.endswith("]")):
        instruction = f"[{instruction}]"
    return f"{instruction}\n{text}"


def _error_detail(body: bytes, api_key: str) -> str:
    try:
        payload = json.loads(body)
        detail = str(payload.get("error", {}).get("message", "")).strip()
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        detail = ""
    return detail.replace(api_key, "[redacted]") if api_key else detail


def _http_error(status: int, body: bytes, api_key: str) -> FishAudioError:
    detail = _error_detail(body, api_key)
    messages = {
        400: "Fish Audio rejected the speech request.",
        401: "OpenRouter rejected the API key.",
        402: "OpenRouter reports insufficient credits for this request.",
        403: "OpenRouter denied access to Fish Audio.",
        404: "The Fish Audio free endpoint is currently unavailable.",
        408: "The Fish Audio request timed out.",
        429: "The Fish Audio free endpoint is currently rate-limited.",
    }
    if status >= 500:
        message = "Fish Audio is temporarily unavailable."
    else:
        message = messages.get(status, f"OpenRouter returned HTTP {status}.")
    if detail and status == 400:
        message = f"{message} {detail}"
    return FishAudioError(
        message, code=f"openrouter_{status}", detail=detail,
        status_code={408: 504, 429: 429}.get(status, 502),
    )


Opener = Callable[[Request, float], Any]


class FishAudioOpenRouterClient:
    def __init__(
        self,
        *,
        opener: Opener = urlopen,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._opener = opener
        self.timeout = timeout

    def synthesize(
        self,
        text: str,
        *,
        api_key: str | None = None,
        voice_id: str | None = None,
    ) -> FishAudioResult:
        key = (os.getenv("OPENROUTER_API_KEY", "") or api_key or "").strip()
        if not key:
            raise FishAudioError(
                "An OpenRouter API key is required for Fish Audio.",
                code="openrouter_key_required",
                status_code=503,
            )

        payload = {
            "model": FISH_AUDIO_MODEL,
            "input": text,
            "response_format": DEFAULT_RESPONSE_FORMAT,
        }
        voice = (voice_id or "").strip()
        if voice:
            payload["voice"] = voice
        request = Request(
            OPENROUTER_TTS_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self._opener(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", 200))
                body = response.read()
                content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].lower()
                generation_id = response.headers.get("X-Generation-Id")
        except HTTPError as error:
            raise _http_error(error.code, error.read(), key) from None
        except (TimeoutError, socket.timeout) as error:
            raise FishAudioError(
                "The Fish Audio request timed out.",
                code="openrouter_timeout",
                status_code=504,
            ) from None
        except (URLError, OSError) as error:
            if isinstance(getattr(error, "reason", None), TimeoutError):
                raise FishAudioError(
                    "The Fish Audio request timed out.",
                    code="openrouter_timeout", status_code=504,
                ) from None
            raise FishAudioError(
                "Could not connect to OpenRouter.",
                code="openrouter_connection_failed",
                status_code=503,
            ) from None

        if not 200 <= status < 300:
            raise _http_error(status, body, key)
        if content_type not in {"audio/mpeg", "audio/mp3"} or not body:
            raise FishAudioError(
                "OpenRouter returned an invalid audio response.",
                code="invalid_audio_response",
            )
        return FishAudioResult(body, content_type, generation_id)
