from pathlib import Path
import time

import numpy as np
from fastapi.testclient import TestClient

from kokoro_app.app import _safe_load, create_app
from kokoro_app.engine import AlignedWord, EngineStatus, SynthesisResult
from kokoro_app.jobs import JobManager


class FakeEngine:
    def status(self) -> EngineStatus:
        return EngineStatus("ready")

    def synthesize(self, *args, **kwargs) -> SynthesisResult:
        return SynthesisResult(
            np.ones(1200, dtype=np.float32),
            (AlignedWord(str(args[0]), 0.01, 0.04),),
        )


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
    assert body["limits"]["pause_ms"] == {"min": 0.0, "max": 5000.0}
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


def test_generation_rejects_pause_duration_above_five_seconds(tmp_path: Path) -> None:
    client, jobs = make_client(tmp_path)
    response = client.post(
        "/api/jobs",
        json={
            "text": "One. Two.",
            "language": "a",
            "primary_voice": "af_heart",
            "pause_ms": 5001,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    jobs.shutdown()


def test_completed_generation_exposes_timestamped_transcript(tmp_path: Path) -> None:
    client, jobs = make_client(tmp_path)
    created = client.post(
        "/api/jobs",
        json={"text": "One. Two.", "language": "a", "primary_voice": "af_heart"},
    ).json()
    deadline = time.time() + 2
    body = created
    while body["state"] != "complete" and time.time() < deadline:
        body = client.get(f"/api/jobs/{created['id']}").json()

    assert body["segments"] == [
        {"text": "One.", "start": 0.0, "end": 0.05, "paragraph_end": False},
        {"text": "Two.", "start": 0.27, "end": 0.32, "paragraph_end": True},
    ]
    assert body["words"] == [
        {"text": "One.", "start": 0.01, "end": 0.04},
        {"text": "Two.", "start": 0.28, "end": 0.31},
    ]
    jobs.shutdown()


def test_completed_generation_preserves_the_full_transcript(tmp_path: Path) -> None:
    client, jobs = make_client(tmp_path)
    original = "First paragraph.\n\nSecond paragraph."
    created = client.post(
        "/api/jobs",
        json={"text": original, "language": "a", "primary_voice": "af_heart"},
    ).json()
    deadline = time.time() + 2
    body = created
    while body["state"] != "complete" and time.time() < deadline:
        body = client.get(f"/api/jobs/{created['id']}").json()

    assert body["transcript"] == original
    jobs.shutdown()


def test_generation_rejects_storyboard_segments_that_do_not_match_text(tmp_path: Path) -> None:
    client, jobs = make_client(tmp_path)
    response = client.post(
        "/api/jobs",
        json={
            "text": "Joined text is different.",
            "segments": ["First row.", "Second row."],
            "language": "a",
            "primary_voice": "af_heart",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
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
