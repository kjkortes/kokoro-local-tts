from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from kokoro_app import __version__
from kokoro_app.catalog import LANGUAGES, VOICES
from kokoro_app.engine import KokoroEngine
from kokoro_app.expressions import PRESETS
from kokoro_app.jobs import JobManager, JobNotFoundError, JobRecord
from kokoro_app.schemas import (
    AppConfig,
    ExpressionPresetInfo,
    GenerationRequest,
    JobResponse,
    OutputFormat,
    StatusResponse,
)


RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime" / "audio"
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _job_response(record: JobRecord) -> JobResponse:
    complete = record.state.value == "complete"
    return JobResponse(
        id=record.id,
        state=record.state,
        phase=record.phase,
        progress=record.progress,
        error=record.error,
        audio_url=f"/api/jobs/{record.id}/audio" if complete else None,
        download_url=f"/api/jobs/{record.id}/download" if complete else None,
        filename=record.filename,
        duration=record.duration,
        segments=record.segments,
        words=record.words,
        transcript=record.request.text if complete else None,
    )


def _error(code: str, message: str, action: str | None = None) -> dict[str, dict[str, str | None]]:
    return {"error": {"code": code, "message": message, "action": action}}


def create_app(
    engine: KokoroEngine | None = None,
    jobs: JobManager | None = None,
    *,
    preload_model: bool = True,
    frontend_dist: Path | None = None,
) -> FastAPI:
    active_engine = engine or KokoroEngine()
    active_jobs = jobs or JobManager(active_engine, RUNTIME_DIR)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        active_jobs.prune()
        if preload_model:
            threading.Thread(target=_safe_load, args=(active_engine,), daemon=True).start()
        yield
        active_jobs.shutdown()

    application = FastAPI(title="Kokoro Local TTS", version=__version__, lifespan=lifespan)
    application.state.engine = active_engine
    application.state.jobs = active_jobs
    dist = Path(frontend_dist) if frontend_dist is not None else FRONTEND_DIST

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        text_error = (
            isinstance(error.body, dict)
            and not str(error.body.get("text", "")).strip()
        ) or any("text" in tuple(str(part) for part in item["loc"]) for item in error.errors())
        if text_error:
            payload = _error("invalid_text", "Enter some text to generate speech.", "Paste a script and try again.")
        else:
            payload = _error("invalid_request", "One or more speech settings are invalid.", "Review the highlighted controls.")
        return JSONResponse(payload, status_code=422)

    @application.get("/api/status", response_model=StatusResponse)
    def runtime_status() -> StatusResponse:
        current = active_engine.status()
        return StatusResponse(state=current.state, device=current.device, version=__version__, detail=current.detail)

    @application.get("/api/config", response_model=AppConfig)
    def configuration() -> AppConfig:
        return AppConfig(
            languages=list(LANGUAGES),
            voices=list(VOICES),
            presets=[
                ExpressionPresetInfo(
                    id=item.id,
                    name=item.name,
                    description=item.description,
                    speed=item.speed,
                    pitch=item.pitch,
                    tempo=item.tempo,
                    pause_scale=item.pause_scale,
                )
                for item in PRESETS.values()
            ],
            formats=list(OutputFormat),
            defaults={
                "language": "a",
                "voice": "af_heart",
                "preset": "neutral",
                "format": "wav",
                "comma_pause_ms": 100,
            },
            limits={
                "speed": {"min": 0.5, "max": 2.0},
                "pitch": {"min": -4.0, "max": 4.0},
                "tempo": {"min": 0.75, "max": 1.25},
                "pause_scale": {"min": 0.5, "max": 2.0},
                "pause_ms": {"min": 0.0, "max": 5000.0},
                "comma_pause_ms": {"min": 0.0, "max": 1000.0},
                "volume": {"min": 0.0, "max": 1.5},
            },
        )

    @application.post("/api/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def create_job(request: GenerationRequest) -> JobResponse:
        return _job_response(active_jobs.create(request))

    def lookup(job_id: str) -> JobRecord:
        try:
            return active_jobs.get(job_id)
        except JobNotFoundError as error:
            raise HTTPException(status_code=404, detail="Generation job not found") from error

    @application.get("/api/jobs/{job_id}", response_model=JobResponse)
    def get_job(job_id: str) -> JobResponse:
        return _job_response(lookup(job_id))

    @application.delete("/api/jobs/{job_id}", response_model=JobResponse)
    def cancel_job(job_id: str) -> JobResponse:
        return _job_response(active_jobs.cancel(lookup(job_id).id))

    def result_file(job_id: str) -> tuple[JobRecord, Path]:
        record = lookup(job_id)
        if record.result_path is None or not record.result_path.exists():
            raise HTTPException(status_code=409, detail="Audio is not ready")
        return record, record.result_path

    @application.get("/api/jobs/{job_id}/audio")
    def stream_audio(job_id: str) -> FileResponse:
        _, path = result_file(job_id)
        return FileResponse(path)

    @application.get("/api/jobs/{job_id}/download")
    def download_audio(job_id: str) -> FileResponse:
        record, path = result_file(job_id)
        return FileResponse(path, filename=record.filename)

    if dist.joinpath("assets").is_dir():
        application.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    if dist.joinpath("voice-samples").is_dir():
        application.mount(
            "/voice-samples",
            StaticFiles(directory=dist / "voice-samples"),
            name="voice-samples",
        )

    @application.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str):
        if path.startswith("api/"):
            return JSONResponse(_error("not_found", "API route not found."), status_code=404)
        index = dist / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            _error("frontend_missing", "The web interface has not been built.", "Run ./run.sh to build and start the app."),
            status_code=503,
        )

    return application


def _safe_load(engine: KokoroEngine) -> None:
    try:
        engine.load("a")
    except Exception:
        # The engine stores a user-facing status; detailed errors remain in local logs on first use.
        return


app = create_app()
