from pathlib import Path

from fastapi.testclient import TestClient

from kokoro_app.app import create_app
from kokoro_app.engine import EngineStatus
from kokoro_app.jobs import JobManager


class FakeEngine:
    def status(self) -> EngineStatus:
        return EngineStatus("ready")


def test_unknown_non_api_route_returns_spa_shell(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    (dist / "assets" / "app.js").write_text("export {};", encoding="utf-8")
    engine = FakeEngine()
    jobs = JobManager(engine, tmp_path / "audio")
    client = TestClient(create_app(engine=engine, jobs=jobs, preload_model=False, frontend_dist=dist))
    assert '<div id="root"></div>' in client.get("/workspace").text
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/api/unknown").status_code == 404
    jobs.shutdown()


def test_built_voice_preview_is_served_as_audio(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    samples = dist / "voice-samples"
    samples.mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    preview = b"ID3\x04\x00\x00preview-audio"
    (samples / "af_heart.mp3").write_bytes(preview)
    engine = FakeEngine()
    jobs = JobManager(engine, tmp_path / "audio")
    client = TestClient(create_app(engine=engine, jobs=jobs, preload_model=False, frontend_dist=dist))

    response = client.get("/voice-samples/af_heart.mp3")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == preview
    jobs.shutdown()
