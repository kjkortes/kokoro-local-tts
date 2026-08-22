from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from kokoro_app.app import _safe_load, create_app
from kokoro_app.engine import EngineStatus
from kokoro_app.jobs import JobManager


class FakeEngine:
    def status(self) -> EngineStatus:
        return EngineStatus("ready")

    def synthesize(self, *args, **kwargs) -> np.ndarray:
        return np.ones(1200, dtype=np.float32)


def fake_encode(pcm, destination: Path, *args, **kwargs) -> None:
    destination.write_bytes(b"audio")


def make_client(tmp_path: Path) -> tuple[TestClient, JobManager]:
    engine = FakeEngine()
    jobs = JobManager(engine, tmp_path, encoder=fake_encode)
    return TestClient(create_app(engine=engine, jobs=jobs, preload_model=False)), jobs


def test_config_exposes_catalog_presets_formats_and_bounds(tmp_path: Path) -> None:
    client, jobs = make_client(tmp_path)
    response = client.get("/api/config")
    assert response.status_code == 200
    body = response.json()
    assert len(body["voices"]) == 54
    assert set(body["formats"]) == {"wav", "mp3", "flac", "ogg"}
    assert body["limits"]["speed"] == {"min": 0.5, "max": 2.0}
    jobs.shutdown()


def test_blank_generation_is_actionable(tmp_path: Path) -> None:
    client, jobs = make_client(tmp_path)
    response = client.post(
        "/api/jobs",
        json={"text": "   ", "language": "a", "primary_voice": "af_heart"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_text"
    jobs.shutdown()


def test_status_describes_local_runtime(tmp_path: Path) -> None:
    client, jobs = make_client(tmp_path)
    assert client.get("/api/status").json() == {
        "state": "ready", "device": "cpu", "version": "0.1.0", "detail": None
    }
    jobs.shutdown()


def test_preload_uses_bundled_phonemizer_when_system_espeak_is_absent(monkeypatch) -> None:
    class LoadableEngine:
        loaded = False

        def load(self, language: str) -> None:
            assert language == "a"
            self.loaded = True

    engine = LoadableEngine()
    monkeypatch.setattr("shutil.which", lambda _: None)
    _safe_load(engine)
    assert engine.loaded is True
