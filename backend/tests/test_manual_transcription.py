import threading
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from kokoro_app import app as app_module
from kokoro_app.app import create_app
from kokoro_app.fish_audio import FishAudioResult
from kokoro_app.engine import SynthesisResult
from kokoro_app.jobs import JobManager
from kokoro_app.schemas import GenerationRequest, JobState
from kokoro_app.transcription import TimedSegment, TimedWord, WhisperTranscript


def wait_until(check):
    deadline = time.monotonic() + 3
    while not check() and time.monotonic() < deadline:
        time.sleep(.01)
    assert check()


class FakeFish:
    def __init__(self):
        self.calls = 0

    def synthesize(self, *args, **kwargs):
        self.calls += 1
        return FishAudioResult(b"saved audio", "audio/mpeg")


class Transcriber:
    def __init__(self):
        self.calls = 0
        self.release = threading.Event()
        self.fail = False

    def transcribe(self, path, *, prompt=None):
        self.calls += 1
        assert path.read_bytes() == b"saved audio"
        assert self.release.wait(3)
        if self.fail:
            raise RuntimeError("Alignment unavailable. Choose Whisper and retry.")
        return WhisperTranscript(1.0, (TimedSegment("Hello.", .1, .9),), (TimedWord("Hello.", .1, .9),))


def test_audio_is_ready_without_transcription_and_manual_work_preserves_audio(tmp_path: Path):
    fish, transcriber = FakeFish(), Transcriber()
    manager = JobManager(object(), tmp_path, fish_client=fish, whisperx_transcriber=transcriber)
    client = TestClient(create_app(engine=object(), jobs=manager, preload_model=False))
    try:
        created = client.post("/api/jobs", json={"engine": "fish_audio", "text": "Hello."}).json()
        wait_until(lambda: manager.get(created["id"]).state == JobState.complete)
        audio = client.get(f"/api/jobs/{created['id']}").json()
        assert audio["transcription_state"] == "idle"
        assert audio["segments"] == [] and audio["words"] == [] and audio["transcript"] is None
        assert transcriber.calls == 0
        assert client.get(audio["audio_url"]).content == b"saved audio"

        endpoint = f"/api/jobs/{created['id']}/transcript"
        response = client.post(endpoint, json={"timestamp_engine": "whisperx"})
        assert response.status_code == 202
        wait_until(lambda: transcriber.calls == 1)
        assert client.post(endpoint, json={"timestamp_engine": "whisperx"}).status_code == 202
        during = client.get(f"/api/jobs/{created['id']}").json()
        assert during["state"] == "complete"
        assert during["transcription_state"] == "transcribing"
        assert client.get(during["audio_url"]).content == b"saved audio"
        assert client.get(during["download_url"]).content == b"saved audio"

        transcriber.release.set()
        wait_until(lambda: manager.get(created["id"]).transcription_state.value == "complete")
        finished = client.get(f"/api/jobs/{created['id']}").json()
        assert finished["timing_source"] == "whisperx"
        assert finished["words"] == [{"text": "Hello.", "start": .1, "end": .9}]
        assert fish.calls == transcriber.calls == 1
    finally:
        transcriber.release.set()
        manager.shutdown()


def test_automatic_transcription_failure_keeps_audio_and_manual_retry_uses_saved_file(tmp_path: Path):
    fish, broken, working = FakeFish(), Transcriber(), Transcriber()
    broken.fail = True
    broken.release.set()
    working.release.set()
    manager = JobManager(object(), tmp_path, fish_client=fish, whisperx_transcriber=broken, fish_transcriber=working)
    client = TestClient(create_app(engine=object(), jobs=manager, preload_model=False))
    try:
        record = manager.create(GenerationRequest(engine="fish_audio", text="Hello.", auto_transcribe=True))
        wait_until(lambda: manager.get(record.id).transcription_state.value == "failed")
        failed = client.get(f"/api/jobs/{record.id}").json()
        assert failed["state"] == "complete" and failed["error"] is None
        assert "Choose Whisper" in failed["transcription_error"]["action"]
        assert client.get(failed["audio_url"]).content == b"saved audio"
        assert client.post(f"/api/jobs/{record.id}/transcript", json={"timestamp_engine": "whisper"}).status_code == 202
        wait_until(lambda: manager.get(record.id).transcription_state.value == "complete")
        assert manager.get(record.id).timing_source == "whisper"
        assert fish.calls == broken.calls == working.calls == 1
    finally:
        manager.shutdown()


def test_transcription_endpoint_rejects_missing_or_unready_audio(tmp_path: Path):
    fish, transcriber = FakeFish(), Transcriber()
    manager = JobManager(object(), tmp_path, fish_client=fish, whisperx_transcriber=transcriber)
    client = TestClient(create_app(engine=object(), jobs=manager, preload_model=False))
    try:
        assert client.post("/api/jobs/missing/transcript", json={}).status_code == 404
        record = manager.create(GenerationRequest(engine="fish_audio", text="Hello."))
        wait_until(lambda: record.state == JobState.complete)
        invalid = client.post(f"/api/jobs/{record.id}/transcript", json={"timestamp_engine": "invalid"})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_transcription_settings"
        record.result_path.unlink()
        response = client.post(f"/api/jobs/{record.id}/transcript", json={})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "audio_not_ready"
        assert transcriber.calls == 0
    finally:
        transcriber.release.set()
        manager.shutdown()


def test_kokoro_transcript_can_be_revealed_manually_without_synthesizing_again(tmp_path: Path):
    class LocalEngine:
        calls = 0

        def synthesize(self, *args, **kwargs):
            self.calls += 1
            return SynthesisResult(np.ones(1200, dtype=np.float32))

    engine = LocalEngine()
    manager = JobManager(engine, tmp_path, encoder=lambda pcm, path, *args: path.write_bytes(b"local audio"))
    client = TestClient(create_app(engine=engine, jobs=manager, preload_model=False))
    try:
        record = manager.create(GenerationRequest(engine="kokoro", text="Hello."))
        wait_until(lambda: record.state == JobState.complete)
        before = client.get(f"/api/jobs/{record.id}").json()
        assert before["transcript"] is None and before["segments"] == []
        after = client.post(f"/api/jobs/{record.id}/transcript", json={}).json()
        assert after["transcription_state"] == "complete"
        assert after["transcript"] == "Hello."
        assert after["segments"][0]["text"] == "Hello."
        assert after["timing_source"] == "kokoro"
        assert engine.calls == 1
    finally:
        manager.shutdown()


def test_status_response_is_consistent_when_transcription_finishes_during_serialization(tmp_path: Path, monkeypatch):
    transcriber = Transcriber()
    manager = JobManager(object(), tmp_path, fish_client=FakeFish(), whisperx_transcriber=transcriber)
    client = TestClient(create_app(engine=object(), jobs=manager, preload_model=False))
    try:
        record = manager.create(GenerationRequest(engine="fish_audio", text="Hello."))
        wait_until(lambda: record.state == JobState.complete)
        client.post(f"/api/jobs/{record.id}/transcript", json={})
        wait_until(lambda: record.transcription_state.value == "transcribing")
        serialize = app_module._job_response

        def finish_then_serialize(snapshot):
            transcriber.release.set()
            wait_until(lambda: record.transcription_state.value == "complete")
            return serialize(snapshot)

        monkeypatch.setattr(app_module, "_job_response", finish_then_serialize)
        during = client.get(f"/api/jobs/{record.id}").json()
        assert during["transcription_state"] == "transcribing"
        assert during["segments"] == []
        after = client.get(f"/api/jobs/{record.id}").json()
        assert after["transcription_state"] == "complete"
        assert len(after["segments"]) == len(after["words"]) == 1
    finally:
        transcriber.release.set()
        manager.shutdown()
