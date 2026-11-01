import json
import time
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from kokoro_app.app import create_app
from kokoro_app.engine import KokoroEngine
from kokoro_app.fish_audio import FishAudioOpenRouterClient
from kokoro_app.jobs import JobManager
from kokoro_app.schemas import GenerationRequest


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "server-secret")
    monkeypatch.setenv("FISH_AUDIO_DEFAULT_VOICE", "configured-voice")
    audio = (Path(__file__).parents[2] / "frontend/public/voice-samples/af_heart.mp3").read_bytes()
    outbound = []
    loads = []
    transcriptions = []
    provider = SimpleNamespace(error=None, audio=audio, content_type="audio/mpeg")

    def opener(request, timeout):
        outbound.append((json.loads(request.data), request.get_header("Authorization"), timeout))
        if provider.error:
            raise provider.error
        response = BytesIO(provider.audio)
        response.status = 200
        response.headers = {"Content-Type": provider.content_type}
        return response

    def pipeline(language):
        loads.append(language)
        raise AssertionError("Fish requests must not load Kokoro")

    class Transcriber:
        def transcribe(self, *args, **kwargs):
            transcriptions.append(args)
            raise AssertionError("Speech requests must not transcribe")

    engine = KokoroEngine(pipeline_factory=pipeline)
    jobs = JobManager(
        engine, tmp_path / "audio", fish_client=FishAudioOpenRouterClient(opener=opener),
        fish_transcriber=Transcriber(), whisperx_transcriber=Transcriber(),
    )
    with TestClient(create_app(engine=engine, jobs=jobs, fish_voice_db=tmp_path / "voices.db")) as client:
        yield SimpleNamespace(
            client=client, jobs=jobs, engine=engine, provider=provider,
            outbound=outbound, loads=loads, transcriptions=transcriptions, audio=audio,
        )


def test_generation_schema_defaults_to_fish_and_configured_voice(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_DEFAULT_VOICE", "configured-voice")
    request = GenerationRequest(text="Hello.")
    assert request.engine == "fish_audio"
    assert request.fish_voice == "configured-voice"


def test_startup_and_configuration_do_not_load_kokoro(service):
    config = service.client.get("/api/config").json()
    assert config["defaults"]["engine"] == "fish_audio"
    assert config["defaults"]["fish_voice"] == "configured-voice"
    assert config["defaults"]["model"] == "fish-audio/s2.1-pro-free:free"
    assert service.client.get("/api/status").json()["state"] == "unloaded"
    assert service.loads == []


def test_speech_returns_decodable_mp3_using_server_defaults(service):
    response = service.client.post("/v1/audio/speech", json={"input": "Hello from OpenMontage."})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == service.audio
    audio, sample_rate = sf.read(BytesIO(response.content))
    assert len(audio) > sample_rate // 2
    payload, authorization, timeout = service.outbound[0]
    assert payload == {
        "input": "[natural conversational speech]\nHello from OpenMontage.",
        "model": "fish-audio/s2.1-pro-free:free",
        "voice": "configured-voice", "response_format": "mp3",
    }
    assert authorization == "Bearer server-secret"
    assert timeout == 120
    assert service.loads == service.transcriptions == []
    assert list(service.jobs.output_dir.iterdir()) == []


@pytest.mark.parametrize("voice", ["custom-voice", ""])
def test_speech_respects_explicit_voice_including_provider_default(service, voice):
    response = service.client.post("/v1/audio/speech", json={"input": "Hello.", "voice": voice})
    assert response.status_code == 200
    payload = service.outbound[0][0]
    assert payload.get("voice") == (voice or None)


@pytest.mark.parametrize("voice", [None, "omitted"])
def test_async_job_defaults_to_fish_and_configured_voice(service, voice):
    payload = {"text": "A background narration."}
    if voice is None:
        payload["fish_voice"] = None
    created = service.client.post("/api/jobs", json=payload)
    assert created.status_code == 202
    job_id = created.json()["id"]
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = service.client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in {"complete", "failed"}:
            break
        time.sleep(.01)
    assert job["state"] == "complete", job
    assert job["engine"] == "fish_audio"
    assert job["transcription_state"] == "idle"
    assert service.client.get(job["download_url"]).content == service.audio
    assert service.outbound[0][0]["voice"] == "configured-voice"
    assert service.loads == service.transcriptions == []


@pytest.mark.parametrize("payload", [
    {}, {"input": " "}, {"input": "x" * 5001},
    {"input": "Hello.", "model": "fish-audio/s2.1-pro"},
    {"input": "Hello.", "model": "kokoro"},
    {"input": "Hello.", "response_format": "wav"},
    {"input": "Hello.", "auto_transcribe": True},
    {"input": "Hello.", "voice": "x" * 257},
])
def test_invalid_speech_settings_fail_before_contacting_provider(service, payload):
    response = service.client.post("/v1/audio/speech", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert service.outbound == []


@pytest.mark.parametrize("upstream, expected", [(400, 502), (401, 502), (402, 502), (404, 502), (408, 504), (429, 429), (503, 502)])
def test_speech_provider_errors_are_clear_and_never_fall_back(service, caplog, upstream, expected):
    service.provider.error = HTTPError(
        "https://openrouter.ai/api/v1/audio/speech", upstream, "error", {},
        BytesIO(b'{"error":{"message":"Provider rejected server-secret"}}'),
    )
    response = service.client.post("/v1/audio/speech", json={"input": "Hello."})
    assert response.status_code == expected
    assert response.json()["error"]["code"] == f"openrouter_{upstream}"
    if upstream == 429:
        assert "rate-limited" in response.json()["error"]["message"]
    assert "server-secret" not in response.text + caplog.text
    assert len(service.outbound) == 1
    assert service.outbound[0][0]["model"] == "fish-audio/s2.1-pro-free:free"
    assert service.loads == []


@pytest.mark.parametrize("error, code, status", [
    (TimeoutError(), "openrouter_timeout", 504),
    (URLError(TimeoutError()), "openrouter_timeout", 504),
    (URLError("offline"), "openrouter_connection_failed", 503),
])
def test_speech_network_errors_are_bounded_and_actionable(service, error, code, status):
    service.provider.error = error
    response = service.client.post("/v1/audio/speech", json={"input": "Hello."})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert len(service.outbound) == 1
    assert service.loads == []


def test_speech_missing_server_key_is_actionable(service, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    response = service.client.post("/v1/audio/speech", json={"input": "Hello."})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "openrouter_key_required"
    assert service.outbound == []


def test_speech_rejects_provider_json_disguised_as_success(service):
    service.provider.audio = b'{"error":{"message":"unavailable"}}'
    service.provider.content_type = "application/json"
    response = service.client.post("/v1/audio/speech", json={"input": "Hello."})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_audio_response"


@pytest.mark.parametrize("upstream", [429, 503])
def test_async_fish_failures_preserve_errors_without_engine_fallback(service, upstream):
    service.provider.error = HTTPError(
        "https://openrouter.ai/api/v1/audio/speech", upstream, "error", {}, BytesIO(b"{}"),
    )
    created = service.client.post("/api/jobs", json={"text": "Hello."}).json()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = service.client.get(f"/api/jobs/{created['id']}").json()
        if job["state"] == "failed":
            break
        time.sleep(.01)
    assert job["state"] == "failed"
    assert job["error"]["code"] == f"openrouter_{upstream}"
    assert job["engine"] == "fish_audio"
    assert job["audio_url"] is None
    assert len(service.outbound) == 1
    assert service.loads == []


def test_explicit_kokoro_request_loads_model_only_on_first_use(tmp_path):
    loads = []

    class Pipeline:
        def __call__(self, text, **kwargs):
            yield SimpleNamespace(audio=np.ones(1200, dtype=np.float32), tokens=[])

    def factory(language):
        loads.append(language)
        return Pipeline()

    engine = KokoroEngine(pipeline_factory=factory)
    jobs = JobManager(engine, tmp_path / "audio", encoder=lambda pcm, path, *args: path.write_bytes(b"local audio"))
    with TestClient(create_app(engine=engine, jobs=jobs, fish_voice_db=tmp_path / "voices.db")) as client:
        assert loads == []
        for _ in range(2):
            created = client.post("/api/jobs", json={"engine": "kokoro", "text": "Local speech."}).json()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                job = client.get(f"/api/jobs/{created['id']}").json()
                if job["state"] in {"complete", "failed"}:
                    break
                time.sleep(.01)
            assert job["state"] == "complete", job
            assert job["engine"] == "kokoro"
            assert client.get(job["download_url"]).content == b"local audio"
        assert loads == ["a"]
