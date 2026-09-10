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


@dataclass(frozen=True)
class SpeechPlan:
    chunks: tuple[TextChunk, ...]
    chunk_text_ranges: tuple[tuple[int, int], ...]
    storyboard_ranges: tuple[tuple[int, int], ...] | None


def _filename_for(request: GenerationRequest) -> str:
    words = re.findall(r"[\w'-]+", request.text, flags=re.UNICODE)[:6]
    stem = "-".join(words).lower() or "kokoro-speech"
    stem = re.sub(r"[^\w-]+", "", stem)[:64] or "kokoro-speech"
    return f"{stem}.{request.output_format.value}"


def _normalized_speech(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _locate_chunks(text: str, chunks: tuple[TextChunk, ...]) -> tuple[tuple[int, int], ...]:
    ranges = []
    cursor = 0
    for chunk in chunks:
        start = text.find(chunk.text, cursor)
        if start < 0:
            raise ValueError("Speech chunk could not be mapped to its source text")
        end = start + len(chunk.text)
        ranges.append((start, end))
        cursor = end
    return tuple(ranges)


def _speech_plan(request: GenerationRequest) -> SpeechPlan:
    if request.segments is None:
        chunks = tuple(chunk_script(request.text))
        return SpeechPlan(chunks, (), None)

    spoken_segments = tuple(_normalized_speech(segment) for segment in request.segments)
    synthesis_text = " ".join(spoken_segments)
    chunks = tuple(chunk_script(synthesis_text))
    segment_ranges = []
    cursor = 0
    for segment in spoken_segments:
        start = cursor
        end = start + len(segment)
        segment_ranges.append((start, end))
        cursor = end + 1
    return SpeechPlan(chunks, _locate_chunks(synthesis_text, chunks), tuple(segment_ranges))


def _sample_at_text_offset(
    offset: int,
    chunk_text_ranges: tuple[tuple[int, int], ...],
    chunk_audio_ranges: list[tuple[int, int]],
) -> int:
    if not chunk_audio_ranges:
        return 0
    for (text_start, text_end), (audio_start, audio_end) in zip(
        chunk_text_ranges, chunk_audio_ranges, strict=True
    ):
        if offset <= text_start:
            return audio_start
        if offset <= text_end:
            text_length = max(1, text_end - text_start)
            position = min(text_length, max(0, offset - text_start))
            return audio_start + round((audio_end - audio_start) * position / text_length)
    return chunk_audio_ranges[-1][1]


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
            plan = _speech_plan(record.request)
            generated = []
            aligned_words: list[tuple[AlignedWord, ...]] = []
            pauses = []
            for index, chunk in enumerate(plan.chunks):
                if self._cancelled(record):
                    return
                self._set(
                    record,
                    JobState.synthesizing,
                    f"Speaking segment {index + 1} of {len(plan.chunks)}",
                    0.05 + (index / len(plan.chunks)) * 0.80,
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
                pauses.append(
                    record.request.pause_ms
                    if record.request.pause_ms is not None
                    else round(chunk.pause_after_ms * expression.pause_scale)
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
            chunk_audio_ranges = []
            cursor = 0
            for index, audio in enumerate(generated):
                spoken_end = cursor + len(audio)
                chunk_audio_ranges.append((cursor, spoken_end))
                cursor = spoken_end
                if index < len(generated) - 1:
                    cursor += round(SAMPLE_RATE * pauses[index] / 1000)
            with self._lock:
                record.result_path = destination
                record.filename = _filename_for(record.request)
                record.duration = len(pcm) / SAMPLE_RATE / expression.tempo
                record.segments = []
                record.words = []
                if plan.storyboard_ranges is None:
                    for chunk, (audio_start, audio_end) in zip(
                        plan.chunks, chunk_audio_ranges, strict=True
                    ):
                        record.segments.append({
                            "text": chunk.text,
                            "start": audio_start / SAMPLE_RATE / expression.tempo,
                            "end": audio_end / SAMPLE_RATE / expression.tempo,
                            "paragraph_end": chunk.kind == "paragraph",
                        })
                else:
                    for text, (text_start, text_end) in zip(
                        record.request.segments, plan.storyboard_ranges, strict=True
                    ):
                        audio_start = _sample_at_text_offset(
                            text_start, plan.chunk_text_ranges, chunk_audio_ranges
                        )
                        audio_end = _sample_at_text_offset(
                            text_end, plan.chunk_text_ranges, chunk_audio_ranges
                        )
                        record.segments.append({
                            "text": text,
                            "start": audio_start / SAMPLE_RATE / expression.tempo,
                            "end": audio_end / SAMPLE_RATE / expression.tempo,
                            "paragraph_end": True,
                        })
                for (audio_start, _), words in zip(
                    chunk_audio_ranges, aligned_words, strict=True
                ):
                    for word in words:
                        record.words.append({
                            "text": word.text,
                            "start": round(
                                (audio_start / SAMPLE_RATE + word.start) / expression.tempo, 6
                            ),
                            "end": round(
                                (audio_start / SAMPLE_RATE + word.end) / expression.tempo, 6
                            ),
                        })
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
