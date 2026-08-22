from __future__ import annotations

import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from kokoro_app.audio import SAMPLE_RATE, append_silence, encode_audio
from kokoro_app.chunking import chunk_script
from kokoro_app.engine import KokoroEngine
from kokoro_app.expressions import resolve_expression
from kokoro_app.schemas import GenerationRequest, JobState


Encoder = Callable[..., None]


@dataclass
class JobRecord:
    id: str
    request: GenerationRequest
    state: JobState = JobState.queued
    phase: str = "Waiting to generate"
    progress: float = 0.0
    error: dict[str, str] | None = None
    result_path: Path | None = None
    filename: str | None = None
    duration: float | None = None
    created_at: float = field(default_factory=time.time)


class JobNotFoundError(KeyError):
    pass


def _filename_for(request: GenerationRequest) -> str:
    words = re.findall(r"[\w'-]+", request.text, flags=re.UNICODE)[:6]
    stem = "-".join(words).lower() or "kokoro-speech"
    stem = re.sub(r"[^\w-]+", "", stem)[:64] or "kokoro-speech"
    return f"{stem}.{request.output_format.value}"


class JobManager:
    def __init__(
        self,
        engine: KokoroEngine,
        output_dir: Path,
        *,
        encoder: Encoder = encode_audio,
    ) -> None:
        self.engine = engine
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.encoder = encoder
        self._records: dict[str, JobRecord] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kokoro-job")

    def create(self, request: GenerationRequest) -> JobRecord:
        identifier = uuid.uuid4().hex
        record = JobRecord(id=identifier, request=request)
        with self._lock:
            self._records[identifier] = record
            self._cancel_events[identifier] = threading.Event()
        self._executor.submit(self._run, identifier)
        return record

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            try:
                return self._records[job_id]
            except KeyError as error:
                raise JobNotFoundError(job_id) from error

    def cancel(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self.get(job_id)
            self._cancel_events[job_id].set()
            if record.state == JobState.queued:
                record.state = JobState.cancelled
                record.phase = "Cancelled"
                record.progress = 0.0
            return record

    def _set(self, record: JobRecord, state: JobState, phase: str, progress: float) -> None:
        with self._lock:
            record.state = state
            record.phase = phase
            record.progress = progress

    def _cancelled(self, record: JobRecord) -> bool:
        if not self._cancel_events[record.id].is_set():
            return False
        if record.result_path:
            record.result_path.unlink(missing_ok=True)
        record.result_path = None
        self._set(record, JobState.cancelled, "Cancelled", record.progress)
        return True

    def _run(self, job_id: str) -> None:
        record = self.get(job_id)
        if self._cancelled(record):
            return
        try:
            self._set(record, JobState.loading_model, "Loading Kokoro", 0.02)
            expression = resolve_expression(record.request.preset, record.request.expression)
            chunks = chunk_script(record.request.text)
            generated = []
            pauses = []
            for index, chunk in enumerate(chunks):
                if self._cancelled(record):
                    return
                self._set(
                    record,
                    JobState.synthesizing,
                    f"Speaking segment {index + 1} of {len(chunks)}",
                    0.05 + (index / len(chunks)) * 0.80,
                )
                generated.append(
                    self.engine.synthesize(
                        chunk.text,
                        record.request.language,
                        record.request.primary_voice,
                        record.request.secondary_voice,
                        record.request.blend_ratio,
                        expression.speed,
                    )
                )
                pauses.append(round(chunk.pause_after_ms * expression.pause_scale))
            if self._cancelled(record):
                return
            self._set(record, JobState.processing, "Finishing audio", 0.88)
            pcm = append_silence(generated, pauses, SAMPLE_RATE)
            destination = self.output_dir / f"{record.id}.{record.request.output_format.value}"
            self.encoder(
                pcm,
                destination,
                record.request.output_format,
                expression,
                record.request.normalize,
                SAMPLE_RATE,
            )
            if self._cancelled(record):
                destination.unlink(missing_ok=True)
                return
            with self._lock:
                record.result_path = destination
                record.filename = _filename_for(record.request)
                record.duration = len(pcm) / SAMPLE_RATE / expression.tempo
            self._set(record, JobState.complete, "Audio ready", 1.0)
        except Exception as error:
            if record.result_path:
                record.result_path.unlink(missing_ok=True)
            with self._lock:
                record.result_path = None
                record.error = {
                    "code": "generation_failed",
                    "message": "Speech generation failed.",
                    "action": str(error) or "Check the local server log and try again.",
                }
            self._set(record, JobState.failed, "Generation failed", record.progress)

    def prune(self, older_than_seconds: float = 86_400) -> int:
        cutoff = time.time() - older_than_seconds
        removed = 0
        for path in self.output_dir.iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)

