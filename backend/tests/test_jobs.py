import time
from pathlib import Path

import numpy as np

from kokoro_app.jobs import JobManager
from kokoro_app.schemas import GenerationRequest, JobState


class FakeEngine:
    def synthesize(self, *args, **kwargs) -> np.ndarray:
        return np.ones(1200, dtype=np.float32) * 0.1


def fake_encode(pcm, destination: Path, *args, **kwargs) -> None:
    destination.write_bytes(b"local audio")


def wait_for(manager: JobManager, job_id: str, state: JobState) -> None:
    deadline = time.time() + 2
    while time.time() < deadline:
        if manager.get(job_id).state == state:
            return
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} never reached {state}")


def test_job_moves_from_queued_to_complete_and_reports_progress(tmp_path: Path) -> None:
    manager = JobManager(FakeEngine(), tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(text="One. Two."))
    wait_for(manager, record.id, JobState.complete)
    finished = manager.get(record.id)
    assert finished.progress == 1.0
    assert finished.result_path and finished.result_path.exists()
    manager.shutdown()


def test_cancelled_queued_job_does_not_expose_partial_audio(tmp_path: Path) -> None:
    class SlowEngine(FakeEngine):
        def synthesize(self, *args, **kwargs) -> np.ndarray:
            time.sleep(0.08)
            return super().synthesize(*args, **kwargs)

    manager = JobManager(SlowEngine(), tmp_path, encoder=fake_encode)
    first = manager.create(GenerationRequest(text="Hold the worker."))
    second = manager.create(GenerationRequest(text="Sentence. " * 100))
    manager.cancel(second.id)
    wait_for(manager, second.id, JobState.cancelled)
    assert manager.get(second.id).result_path is None
    wait_for(manager, first.id, JobState.complete)
    manager.shutdown()

