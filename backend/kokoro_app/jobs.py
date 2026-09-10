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
from kokoro_app.chunking import TextChunk, chunk_script
from kokoro_app.engine import AlignedWord, KokoroEngine
from kokoro_app.expressions import resolve_expression
from kokoro_app.schemas import GenerationRequest, JobState


Encoder = Callable[..., None]
_CONTINUATION_COMMAS = (",", "，", "、")


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
    segments: list[dict[str, str | float | bool]] = field(default_factory=list)
    words: list[dict[str, str | float]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class JobNotFoundError(KeyError):
    pass


def _filename_for(request: GenerationRequest) -> str:
    words = re.findall(r"[\w'-]+", request.text, flags=re.UNICODE)[:6]
    stem = "-".join(words).lower() or "kokoro-speech"
    stem = re.sub(r"[^\w-]+", "", stem)[:64] or "kokoro-speech"
    return f"{stem}.{request.output_format.value}"


def _speech_chunks(
    request: GenerationRequest,
) -> tuple[list[TextChunk], list[int], list[tuple[str, bool]]]:
    if request.segments is None:
        chunks = chunk_script(request.text)
        return (
            chunks,
            list(range(len(chunks))),
            [(chunk.text, chunk.kind == "paragraph") for chunk in chunks],
        )

    chunks: list[TextChunk] = []
    segment_indexes: list[int] = []
    for segment_index, segment in enumerate(request.segments):
        segment_chunks = chunk_script(segment)
        chunks.extend(segment_chunks)
        segment_indexes.extend([segment_index] * len(segment_chunks))
    return chunks, segment_indexes, [(segment, True) for segment in request.segments]


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
            chunks, chunk_segment_indexes, segment_specs = _speech_chunks(record.request)
            generated = []
            aligned_words: list[tuple[AlignedWord, ...]] = []
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
                synthesis = self.engine.synthesize(
                    chunk.text,
                    record.request.language,
                    record.request.primary_voice,
                    record.request.secondary_voice,
                    record.request.blend_ratio,
                    expression.speed,
                )
                generated.append(synthesis.audio)
                aligned_words.append(synthesis.words)
                is_storyboard_comma_boundary = (
                    record.request.segments is not None
                    and index < len(chunks) - 1
                    and chunk_segment_indexes[index] != chunk_segment_indexes[index + 1]
                    and record.request.segments[chunk_segment_indexes[index]].rstrip().endswith(
                        _CONTINUATION_COMMAS
                    )
                )
                pauses.append(
                    record.request.comma_pause_ms
                    if is_storyboard_comma_boundary
                    else (
                        record.request.pause_ms
                        if record.request.pause_ms is not None
                        else round(chunk.pause_after_ms * expression.pause_scale)
                    )
                )
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
                cursor = 0
                record.segments = []
                record.words = []
                segment_records: dict[int, dict[str, str | float | bool]] = {}
                for index, (chunk, audio, words) in enumerate(
                    zip(chunks, generated, aligned_words, strict=True)
                ):
                    spoken_end = cursor + len(audio)
                    segment_index = chunk_segment_indexes[index]
                    if segment_index not in segment_records:
                        text, paragraph_end = segment_specs[segment_index]
                        segment_record: dict[str, str | float | bool] = {
                            "text": text,
                            "start": cursor / SAMPLE_RATE / expression.tempo,
                            "end": spoken_end / SAMPLE_RATE / expression.tempo,
                            "paragraph_end": paragraph_end,
                        }
                        segment_records[segment_index] = segment_record
                        record.segments.append(segment_record)
                    else:
                        segment_records[segment_index]["end"] = (
                            spoken_end / SAMPLE_RATE / expression.tempo
                        )
                    for word in words:
                        record.words.append({
                            "text": word.text,
                            "start": round((cursor / SAMPLE_RATE + word.start) / expression.tempo, 6),
                            "end": round((cursor / SAMPLE_RATE + word.end) / expression.tempo, 6),
                        })
                    cursor = spoken_end
                    if index < len(generated) - 1:
                        cursor += round(SAMPLE_RATE * pauses[index] / 1000)
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
