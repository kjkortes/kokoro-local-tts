import importlib
import json
from io import BytesIO
from urllib.error import HTTPError

import pytest


class FakeResponse:
    def __init__(
        self,
        body: bytes = b"mp3 audio",
        *,
        status: int = 200,
        content_type: str = "audio/mpeg",
        generation_id: str | None = "generation-123",
    ) -> None:
        self.status = status
        self.headers = {"Content-Type": content_type}
        if generation_id:
            self.headers["X-Generation-Id"] = generation_id
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return self._body


def fish_audio_module():
    return importlib.import_module("kokoro_app.fish_audio")


def test_request_uses_only_the_free_model_and_omits_an_empty_voice() -> None:
    captured = {}

    def opener(request, timeout):
        captured.update(request=request, timeout=timeout)
        return FakeResponse()

    module = fish_audio_module()
    client = module.FishAudioOpenRouterClient(opener=opener)
    result = client.synthesize("Hello world", api_key="secret-key", voice_id="  ")

    request = captured["request"]
    assert request.full_url == "https://openrouter.ai/api/v1/audio/speech"
    assert json.loads(request.data) == {
        "model": "fish-audio/s2.1-pro-free:free",
        "input": "Hello world",
        "response_format": "mp3",
    }
    assert request.get_header("Authorization") == "Bearer secret-key"
    assert request.get_header("Content-type") == "application/json"
    assert captured["timeout"] == 120
    assert result.audio == b"mp3 audio"
    assert result.content_type == "audio/mpeg"
    assert result.generation_id == "generation-123"


def test_request_includes_a_custom_fish_voice_reference() -> None:
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        return FakeResponse()

    module = fish_audio_module()
    module.FishAudioOpenRouterClient(opener=opener).synthesize(
        "Hello world",
        api_key="secret-key",
        voice_id="802e3bc2b27e49c2995d23ef70e6ac89",
    )

    assert json.loads(captured["request"].data)["voice"] == "802e3bc2b27e49c2995d23ef70e6ac89"


@pytest.mark.parametrize(
    ("style", "custom", "expected"),
    [
        (
            "documentary",
            None,
            "[calm, curious documentary narration with natural pacing]\nThe Pacific is changing.",
        ),
        ("custom", "quiet and thoughtful", "[quiet and thoughtful]\nThe Pacific is changing."),
        ("custom", "[slightly excited]", "[slightly excited]\nThe Pacific is changing."),
        (None, None, "The Pacific is changing."),
    ],
)
def test_delivery_style_is_added_without_stripping_raw_instructions(
    style: str | None,
    custom: str | None,
    expected: str,
) -> None:
    module = fish_audio_module()
    original = "The Pacific is changing."
    assert module.prepare_fish_input(original, style, custom) == expected
    assert original == "The Pacific is changing."


@pytest.mark.parametrize(
    ("status", "provider_message", "expected"),
    [
        (401, "User not found.", "OpenRouter rejected the API key."),
        (429, "Rate limit exceeded.", "The Fish Audio free endpoint is currently rate-limited."),
        (500, "Upstream failed.", "Fish Audio is temporarily unavailable."),
    ],
)
def test_json_api_errors_become_readable_without_exposing_the_key(
    status: int,
    provider_message: str,
    expected: str,
) -> None:
    body = json.dumps({"error": {"code": status, "message": provider_message}}).encode()

    def opener(request, timeout):
        raise HTTPError(
            request.full_url,
            status,
            "error",
            {"Content-Type": "application/json"},
            BytesIO(body),
        )

    module = fish_audio_module()
    with pytest.raises(module.FishAudioError, match=expected) as raised:
        module.FishAudioOpenRouterClient(opener=opener).synthesize(
            "Hello", api_key="do-not-leak-this"
        )

    assert "do-not-leak-this" not in str(raised.value)
    assert provider_message in raised.value.detail


def test_success_rejects_json_or_empty_responses_instead_of_saving_them_as_mp3() -> None:
    module = fish_audio_module()
    for response in (
        FakeResponse(b'{"error": {"message": "bad"}}', content_type="application/json"),
        FakeResponse(b"", content_type="audio/mpeg"),
    ):
        client = module.FishAudioOpenRouterClient(opener=lambda request, timeout, item=response: item)
        with pytest.raises(module.FishAudioError, match="invalid audio response"):
            client.synthesize("Hello", api_key="secret-key")


def test_missing_api_key_fails_before_making_a_network_request(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    called = False

    def opener(request, timeout):
        nonlocal called
        called = True
        return FakeResponse()

    module = fish_audio_module()
    with pytest.raises(module.FishAudioError, match="An OpenRouter API key is required"):
        module.FishAudioOpenRouterClient(opener=opener).synthesize("Hello")
    assert called is False


def test_environment_api_key_is_used_when_no_request_key_is_supplied(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "environment-key")
    captured = {}

    def opener(request, timeout):
        captured["authorization"] = request.get_header("Authorization")
        return FakeResponse()

    module = fish_audio_module()
    module.FishAudioOpenRouterClient(opener=opener).synthesize("Hello")
    assert captured["authorization"] == "Bearer environment-key"


def test_environment_api_key_takes_precedence_over_a_request_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "preferred-environment-key")
    captured = {}

    def opener(request, timeout):
        captured["authorization"] = request.get_header("Authorization")
        return FakeResponse()

    module = fish_audio_module()
    module.FishAudioOpenRouterClient(opener=opener).synthesize(
        "Hello", api_key="browser-key"
    )
    assert captured["authorization"] == "Bearer preferred-environment-key"
