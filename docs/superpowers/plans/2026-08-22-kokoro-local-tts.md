# Kokoro Local TTS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished local web workbench that turns short or long scripts into playable and downloadable audio with Kokoro v1.0.

**Architecture:** A FastAPI application owns the persistent Kokoro CPU pipeline, background generation jobs, deterministic expression controls, FFmpeg post-processing, and generated files. A React/TypeScript SPA consumes a small local REST API, polls job progress, and provides the responsive editor, voice controls, and audio transport; FastAPI serves the compiled SPA in production.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, Kokoro 0.9+, PyTorch CPU, NumPy, SoundFile, FFmpeg, React 19, TypeScript, Vite, Vitest, Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-22-kokoro-local-tts-design.md`

## Global Constraints

- Linux x86_64, CPU-only inference on an AMD Ryzen 5 5500U with 14 GiB RAM.
- All inference and audio processing remain local; only the first model download may access the network.
- Kokoro v1.0 voices and languages are discovered from a single catalog and exposed with language and gender metadata.
- Expression presets are transparent deterministic bundles, never presented as a native Kokoro emotion parameter.
- Kokoro source audio remains 24 kHz; exports support WAV, MP3, FLAC, and OGG.
- No account system, cloud API, database, generation history, voice cloning, or LLM dependency.
- The UI uses bundled Instrument Sans and IBM Plex Mono, meets 44 px touch targets, shows visible keyboard focus, and respects `prefers-reduced-motion`.
- The completed app starts through one documented Linux command after system prerequisites are installed.

## File Map

```text
pyproject.toml                         Python package, runtime, and test dependencies
.gitignore                            Generated, cache, environment, and audio exclusions
run.sh                                One-command production build and local server startup
README.md                             Linux installation, use, offline behavior, and troubleshooting
backend/kokoro_app/app.py             FastAPI lifecycle, routes, and compiled SPA serving
backend/kokoro_app/schemas.py         API request/response models and control bounds
backend/kokoro_app/catalog.py         Language/voice catalog and filtering helpers
backend/kokoro_app/expressions.py     Preset definitions and Custom resolution
backend/kokoro_app/chunking.py        Paragraph/sentence-aware script segmentation
backend/kokoro_app/audio.py           PCM assembly and FFmpeg post-processing
backend/kokoro_app/engine.py          Lazy Kokoro adapter and voice blending
backend/kokoro_app/jobs.py            Background job lifecycle, cancellation, and cleanup
backend/tests/                         Focused unit/API tests plus opt-in inference smoke test
frontend/package.json                 Frontend scripts and dependencies
frontend/vite.config.ts               React build, test, and local API proxy
frontend/src/types.ts                 Shared frontend API contracts
frontend/src/api.ts                   Typed API client
frontend/src/hooks/useGeneration.ts   Polling and cancellation state machine
frontend/src/components/              Focused editor, controls, status, and transport components
frontend/src/App.tsx                  Workspace composition and cross-control state
frontend/src/styles.css               Token system, responsive layout, and interactions
frontend/tests/                       Component, integration, and responsive browser tests
```

---

### Task 1: Project Foundation and Catalog Contract

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `backend/kokoro_app/__init__.py`
- Create: `backend/kokoro_app/schemas.py`
- Create: `backend/kokoro_app/catalog.py`
- Create: `backend/tests/test_catalog.py`

**Interfaces:**
- Produces: `LANGUAGES: tuple[LanguageInfo, ...]`, `VOICES: tuple[VoiceInfo, ...]`, `voices_for(language: str, gender: Gender | None) -> list[VoiceInfo]`.
- Produces: Pydantic models `GenerationRequest`, `JobResponse`, `StatusResponse`, `AppConfig`, plus `ExpressionSettings` and enum types used by all later backend tasks.

- [ ] **Step 1: Write catalog contract tests**

```python
def test_catalog_has_every_kokoro_v1_language_and_unique_voice_ids():
    assert {item.code for item in LANGUAGES} == {"a", "b", "e", "f", "h", "i", "j", "p", "z"}
    assert len(VOICES) == 54
    assert len({voice.id for voice in VOICES}) == len(VOICES)

def test_voice_filter_respects_language_and_gender():
    voices = voices_for("a", Gender.female)
    assert voices
    assert all(v.language == "a" and v.gender == Gender.female for v in voices)
```

- [ ] **Step 2: Run the catalog test and confirm the missing-module failure**

Run: `uv run pytest backend/tests/test_catalog.py -v`

Expected: collection fails because `kokoro_app.catalog` does not exist.

- [ ] **Step 3: Add package metadata, dependencies, schemas, and the Kokoro v1.0 catalog**

Use a `src` entry of `backend` in the build configuration. Pin compatible major ranges and define a `test` extra for pytest/httpx. In `schemas.py`, enforce these exact bounds: text 1–100,000 characters, speed 0.5–2.0, pitch -4–4 semitones, tempo 0.75–1.25, pause scale 0.5–2.0, volume 0–1.5, and blend ratio 0–1. Reject a secondary voice with a mismatched language.

The catalog must contain the 54 official v1.0 identifiers from Kokoro's `VOICES.md`, with human-readable names, language code, locale label, and female/male metadata. Do not derive metadata by display-name heuristics at runtime.

- [ ] **Step 4: Run the catalog and schema tests**

Run: `uv run pytest backend/tests/test_catalog.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit the foundation**

```bash
git add pyproject.toml .gitignore backend
git commit -m "feat: define Kokoro voice and API contracts"
```

### Task 2: Expression Presets and Script Chunking

**Files:**
- Create: `backend/kokoro_app/expressions.py`
- Create: `backend/kokoro_app/chunking.py`
- Create: `backend/tests/test_expressions.py`
- Create: `backend/tests/test_chunking.py`

**Interfaces:**
- Consumes: `ExpressionSettings` from `kokoro_app.schemas`.
- Produces: `PRESETS: dict[str, ExpressionPreset]`, `resolve_expression(preset: str, overrides: ExpressionSettings | None) -> ResolvedExpression`.
- Produces: `TextChunk(text: str, pause_after_ms: int, kind: Literal["sentence", "paragraph"])`, `chunk_script(text: str, max_chars: int = 420) -> list[TextChunk]`.

- [ ] **Step 1: Write failing expression tests**

```python
def test_neutral_is_a_no_op():
    value = resolve_expression("neutral", None)
    assert (value.speed, value.pitch, value.tempo, value.pause_scale) == (1.0, 0.0, 1.0, 1.0)
    assert value.is_custom is False

def test_override_marks_preset_custom_without_losing_other_values():
    value = resolve_expression("calm", ExpressionSettings(speed=0.91))
    assert value.speed == 0.91
    assert value.pitch == PRESETS["calm"].pitch
    assert value.is_custom is True
```

- [ ] **Step 2: Write failing chunking tests**

```python
def test_chunking_preserves_text_and_paragraph_pause():
    chunks = chunk_script("First sentence. Second one!\n\nA new paragraph.", max_chars=24)
    assert " ".join(c.text for c in chunks) == "First sentence. Second one! A new paragraph."
    assert any(c.kind == "paragraph" and c.pause_after_ms > 400 for c in chunks)

def test_oversized_sentence_splits_on_words():
    chunks = chunk_script("word " * 150, max_chars=80)
    assert all(len(c.text) <= 80 for c in chunks)
```

- [ ] **Step 3: Run both test modules and confirm they fail**

Run: `uv run pytest backend/tests/test_expressions.py backend/tests/test_chunking.py -v`

Expected: collection fails for the two missing modules.

- [ ] **Step 4: Implement conservative preset bundles and boundary-aware splitting**

Use these preset baselines:

```python
PRESET_VALUES = {
    "neutral":  (1.00,  0.0, 1.00, 1.00),
    "warm":     (0.96, -0.4, 0.98, 1.08),
    "calm":     (0.90, -0.7, 0.94, 1.25),
    "bright":   (1.05,  0.8, 1.04, 0.88),
    "serious":  (0.93, -1.0, 0.97, 1.15),
    "dramatic": (0.88, -0.6, 1.00, 1.55),
}
```

Split paragraphs first, then sentences using punctuation followed by whitespace, then oversized sentences at the last word boundary below `max_chars`. Normalize whitespace but preserve punctuation. Base sentence and paragraph pauses are 220 ms and 520 ms before applying `pause_scale`.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest backend/tests/test_expressions.py backend/tests/test_chunking.py -v`

Expected: all tests pass.

```bash
git add backend/kokoro_app backend/tests
git commit -m "feat: add transparent expression and chunking rules"
```

### Task 3: Audio Assembly and Local Post-processing

**Files:**
- Create: `backend/kokoro_app/audio.py`
- Create: `backend/tests/test_audio.py`

**Interfaces:**
- Produces: `append_silence(parts: Sequence[np.ndarray], pauses_ms: Sequence[int], sample_rate: int = 24000) -> np.ndarray`.
- Produces: `build_ffmpeg_filter(settings: ResolvedExpression, normalize: bool) -> str`.
- Produces: `encode_audio(pcm: np.ndarray, destination: Path, output_format: OutputFormat, settings: ResolvedExpression, normalize: bool, sample_rate: int = 24000) -> None`.

- [ ] **Step 1: Write failing audio unit tests**

```python
def test_append_silence_uses_24khz_duration():
    joined = append_silence([np.ones(2400), np.ones(2400)], [250], 24000)
    assert len(joined) == 2400 + 6000 + 2400
    assert np.all(joined[2400:8400] == 0)

def test_filter_chain_contains_pitch_tempo_volume_and_normalization():
    settings = ResolvedExpression(speed=1, pitch=2, tempo=.9, pause_scale=1, volume=.8, is_custom=True)
    value = build_ffmpeg_filter(settings, normalize=True)
    assert "asetrate=24000*" in value
    assert "atempo=" in value
    assert "volume=0.8" in value
    assert "loudnorm=" in value
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest backend/tests/test_audio.py -v`

Expected: collection fails for missing `kokoro_app.audio`.

- [ ] **Step 3: Implement pure PCM assembly and safe FFmpeg execution**

Write source PCM to a temporary WAV with SoundFile, construct FFmpeg arguments as a list without `shell=True`, encode to a temporary destination, then atomically replace the final file. Use `libmp3lame` for MP3, `flac` for FLAC, `libvorbis` for OGG, and PCM 16-bit for WAV. Raise `AudioProcessingError` with a stable public message and keep captured stderr for local logging.

Pitch correction uses `asetrate=24000*2^(semitones/12),aresample=24000`, followed by an `atempo` factor that preserves the requested tempo independently. Clamp all inputs through Pydantic before command creation.

- [ ] **Step 4: Run unit and real-FFmpeg tests**

Run: `uv run pytest backend/tests/test_audio.py -v`

Expected: all tests pass and tiny fixtures are encoded in all four formats.

- [ ] **Step 5: Commit audio processing**

```bash
git add backend/kokoro_app/audio.py backend/tests/test_audio.py
git commit -m "feat: assemble and encode local speech audio"
```

### Task 4: Kokoro Engine Adapter

**Files:**
- Create: `backend/kokoro_app/engine.py`
- Create: `backend/tests/test_engine.py`
- Create: `backend/tests/test_inference_smoke.py`

**Interfaces:**
- Consumes: voice identifiers from `catalog.py` and chunk text from `chunking.py`.
- Produces: `KokoroEngine.status() -> EngineStatus`, `KokoroEngine.load() -> None`, `KokoroEngine.synthesize(text: str, language: str, primary_voice: str, secondary_voice: str | None, blend_ratio: float, speed: float) -> np.ndarray`.

- [ ] **Step 1: Write adapter tests around a fake KPipeline**

```python
def test_synthesize_collects_generator_audio_and_blends_voice_name(fake_pipeline):
    engine = KokoroEngine(pipeline_factory=lambda lang: fake_pipeline)
    audio = engine.synthesize("Hello.", "a", "af_heart", "af_bella", 0.35, 0.95)
    assert audio.dtype == np.float32
    assert fake_pipeline.calls[0].voice == "af_heart(0.65)+af_bella(0.35)"
    assert fake_pipeline.calls[0].speed == 0.95
```

- [ ] **Step 2: Run the adapter test and confirm failure**

Run: `uv run pytest backend/tests/test_engine.py -v`

Expected: collection fails for missing `kokoro_app.engine`.

- [ ] **Step 3: Implement lazy per-language pipelines and serialized CPU inference**

Import Kokoro only inside the default pipeline factory so API tests do not download a model. Cache one `KPipeline` per language code and protect synthesis with a process-wide lock because generation jobs share CPU and model memory. Flatten generated segments in order. Report `unloaded`, `loading`, `ready`, or `error`, with device fixed to `cpu` for this target.

Use the installed Kokoro package's supported weighted-voice syntax. If the installed API requires loaded voice tensors instead, isolate that compatibility handling inside `_voice_spec` and keep the public adapter signature unchanged.

- [ ] **Step 4: Run fake tests, then the opt-in real inference smoke test**

Run: `uv run pytest backend/tests/test_engine.py -v`

Expected: fake tests pass without downloading assets.

Run after `espeak-ng` installation: `KOKORO_SMOKE=1 uv run pytest backend/tests/test_inference_smoke.py -v -s`

Expected: a non-empty finite 24 kHz waveform is produced for one short sentence.

- [ ] **Step 5: Commit the engine adapter**

```bash
git add backend/kokoro_app/engine.py backend/tests/test_engine.py backend/tests/test_inference_smoke.py
git commit -m "feat: add reusable Kokoro CPU engine"
```

### Task 5: Job Service and FastAPI

**Files:**
- Create: `backend/kokoro_app/jobs.py`
- Create: `backend/kokoro_app/app.py`
- Create: `backend/tests/test_jobs.py`
- Create: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `GenerationRequest`, `KokoroEngine`, `chunk_script`, `resolve_expression`, `append_silence`, and `encode_audio`.
- Produces: `JobManager.create(request) -> JobRecord`, `JobManager.get(job_id) -> JobRecord`, `JobManager.cancel(job_id) -> JobRecord`, and `JobManager.prune() -> int`.
- Produces: `create_app(engine: KokoroEngine | None = None, jobs: JobManager | None = None) -> FastAPI`.

- [ ] **Step 1: Write failing lifecycle tests with fake synthesis and encoding**

```python
def test_job_moves_from_queued_to_complete_and_reports_progress(manager):
    record = manager.create(valid_request(text="One. Two."))
    wait_until(lambda: manager.get(record.id).state == "complete")
    finished = manager.get(record.id)
    assert finished.progress == 1.0
    assert finished.result_path.exists()

def test_cancelled_job_does_not_expose_partial_audio(manager):
    record = manager.create(valid_request(text="Sentence. " * 200))
    manager.cancel(record.id)
    wait_until(lambda: manager.get(record.id).state == "cancelled")
    assert manager.get(record.id).result_path is None
```

- [ ] **Step 2: Write failing API contract tests**

```python
def test_config_exposes_catalog_presets_formats_and_bounds(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    body = response.json()
    assert len(body["voices"]) == 54
    assert set(body["formats"]) == {"wav", "mp3", "flac", "ogg"}

def test_blank_generation_is_actionable(client):
    response = client.post("/api/jobs", json={**valid_payload(), "text": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_text"
```

- [ ] **Step 3: Run the tests and confirm failure**

Run: `uv run pytest backend/tests/test_jobs.py backend/tests/test_api.py -v`

Expected: missing service and application modules.

- [ ] **Step 4: Implement thread-backed jobs and REST routes**

Use one `ThreadPoolExecutor(max_workers=1)` to prevent CPU contention. Store records behind a lock. Set phases to `queued`, `loading_model`, `synthesizing`, `processing`, `complete`, `cancelled`, or `failed`; progress during synthesis is `completed_chunks / total_chunks * 0.85`, processing occupies 0.85–0.98, and completion is 1.0. Check cancellation between every chunk and before encoding. Delete partial files on all non-complete exits.

Return structured errors as `{"error":{"code":"...","message":"...","action":"..."}}`. Serve audio with inline disposition and downloads with attachment disposition. On startup create the output directory, prune files older than 24 hours, verify FFmpeg, and begin lazy model loading without blocking the status route.

- [ ] **Step 5: Run all backend tests and commit**

Run: `uv run pytest backend/tests -v -m "not smoke"`

Expected: all non-smoke tests pass.

```bash
git add backend/kokoro_app backend/tests
git commit -m "feat: expose local generation job API"
```

### Task 6: Frontend Foundation and Typed API State

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/hooks/useGeneration.ts`
- Create: `frontend/tests/useGeneration.test.tsx`

**Interfaces:**
- Consumes: the Task 5 REST JSON contracts.
- Produces: `getStatus()`, `getConfig()`, `createJob(request)`, `getJob(id)`, `cancelJob(id)`.
- Produces: `useGeneration()` returning `{job, isRunning, error, generate, cancel, clearError}`.

- [ ] **Step 1: Scaffold the Vite test environment and write the failing hook test**

```tsx
it("polls a submitted job until its audio is ready", async () => {
  server.use(jobSequence("queued", "synthesizing", "complete"));
  const {result} = renderHook(() => useGeneration());
  act(() => result.current.generate(validRequest));
  await waitFor(() => expect(result.current.job?.state).toBe("complete"));
  expect(result.current.job?.audioUrl).toBe("/api/jobs/job-1/audio");
});
```

- [ ] **Step 2: Run the hook test and confirm failure**

Run: `cd frontend && npm test -- --run tests/useGeneration.test.tsx`

Expected: module resolution fails for the missing hook.

- [ ] **Step 3: Implement exact API types, error normalization, polling, and cancellation**

Poll active jobs every 350 ms with `AbortController` cleanup. Stop polling on complete, failed, or cancelled. A new generation replaces the visible job only after the create request succeeds. Normalize network failure to: `The local Kokoro service is not reachable. Start the app and try again.`

- [ ] **Step 4: Run frontend unit tests and typecheck**

Run: `cd frontend && npm test -- --run && npm run typecheck`

Expected: all tests and TypeScript checks pass.

- [ ] **Step 5: Commit frontend infrastructure**

```bash
git add frontend
git commit -m "feat: add typed generation client"
```

### Task 7: Responsive Voice and Expression Workspace

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/AppHeader.tsx`
- Create: `frontend/src/components/ScriptEditor.tsx`
- Create: `frontend/src/components/VoiceControls.tsx`
- Create: `frontend/src/components/ExpressionControls.tsx`
- Create: `frontend/src/components/OutputControls.tsx`
- Create: `frontend/src/components/GenerateBar.tsx`
- Create: `frontend/src/components/ErrorNotice.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/tests/App.test.tsx`

**Interfaces:**
- Consumes: `AppConfig`, `StatusResponse`, `GenerationRequest`, and `useGeneration` from Task 6.
- Produces: a fully operable form that submits an exact `GenerationRequest` and exposes cancellation/progress/error states.

- [ ] **Step 1: Write failing workspace interaction tests**

```tsx
it("filters voices and submits transparent custom expression values", async () => {
  render(<App />);
  await user.selectOptions(screen.getByLabelText("Language"), "b");
  await user.selectOptions(screen.getByLabelText("Gender"), "female");
  expect(screen.getByLabelText("Primary voice")).toHaveValue("bf_emma");
  await user.click(screen.getByRole("button", {name: "Calm"}));
  await user.keyboard("{Tab}");
  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  expect(lastCreatePayload.expression.preset).toBe("calm");
});
```

Add tests for word/character estimates, same-language blend options, A/B ratio output, manual edits changing the label to Custom, progress/cancel rendering, and structured error actions.

- [ ] **Step 2: Run the app tests and confirm failure**

Run: `cd frontend && npm test -- --run tests/App.test.tsx`

Expected: `App` and component modules are missing.

- [ ] **Step 3: Implement the workspace with the approved visual system**

Bundle Instrument Sans and IBM Plex Mono through local npm font packages. Define CSS custom properties for the six approved colors, spacing, typography, radii, and focus ring. At 900 px and above, use a `minmax(0, 1fr) minmax(320px, 420px)` workspace grid; below 900 px, use a single column. The editor must have a useful 420 px desktop minimum and 280 px mobile minimum.

Use native labeled form elements. Keep preset controls as a compact segmented group, expose actual changed values in a one-sentence summary, and place manual controls in a disclosure titled `Fine-tune delivery`. Keep all touch targets at least 44 px. Use only opacity/transform transitions and disable them under reduced motion.

- [ ] **Step 4: Run component tests, typecheck, and production build**

Run: `cd frontend && npm test -- --run && npm run typecheck && npm run build`

Expected: tests pass and `frontend/dist` is produced without warnings that affect runtime.

- [ ] **Step 5: Commit the responsive workspace**

```bash
git add frontend
git commit -m "feat: build responsive Kokoro speech workspace"
```

### Task 8: Waveform Transport and Downloads

**Files:**
- Create: `frontend/src/components/AudioTransport.tsx`
- Create: `frontend/src/hooks/useAudioTransport.ts`
- Create: `frontend/tests/AudioTransport.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: completed `JobResponse.audioUrl`, `JobResponse.downloadUrl`, duration, and filename.
- Produces: `useAudioTransport(audioElement)` with play/pause, seek, elapsed/duration state, and a canvas waveform envelope decoded from the generated audio.

- [ ] **Step 1: Write failing playback and download tests**

```tsx
it("makes the completed result playable and downloadable without autoplay", async () => {
  render(<AudioTransport result={completedResult} />);
  expect(screen.getByRole("button", {name: "Play"})).toBeEnabled();
  expect(screen.getByRole("link", {name: "Download MP3"})).toHaveAttribute(
    "href", "/api/jobs/job-1/download"
  );
  expect(mockAudio.play).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run the transport tests and confirm failure**

Run: `cd frontend && npm test -- --run tests/AudioTransport.test.tsx`

Expected: transport modules are missing.

- [ ] **Step 3: Implement native audio control integration and waveform rendering**

Use one hidden `<audio preload="metadata">` element and accessible custom buttons/range input. Fetch and decode the completed audio only for visualization, reduce channel samples into a fixed envelope, and draw it on a device-pixel-ratio-aware canvas. If decoding fails, retain fully functional playback and render a simple progress rail. Recompute canvas geometry with `ResizeObserver`. Revoke object URLs and cancel decode work during cleanup.

- [ ] **Step 4: Run tests and manually inspect both breakpoints**

Run: `cd frontend && npm test -- --run && npm run build`

Expected: tests and build pass.

Run the app and inspect at 1440×900 and 375×812. Expected: no horizontal overflow; transport controls remain usable; waveform resizes; keyboard seeking and focus indicators work.

- [ ] **Step 5: Commit the transport**

```bash
git add frontend/src frontend/tests
git commit -m "feat: add waveform playback and downloads"
```

### Task 9: Production Serving, One-command Startup, and Documentation

**Files:**
- Modify: `backend/kokoro_app/app.py`
- Create: `run.sh`
- Create: `README.md`
- Create: `backend/tests/test_spa_serving.py`
- Create: `frontend/tests/responsive.spec.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`

**Interfaces:**
- Consumes: `frontend/dist` and the complete FastAPI app.
- Produces: `./run.sh` as the supported local startup command and SPA fallback serving for non-API paths.

- [ ] **Step 1: Write failing compiled-SPA and browser layout tests**

```python
def test_unknown_non_api_route_returns_spa_shell(client_with_dist):
    response = client_with_dist.get("/workspace")
    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text
```

```ts
for (const viewport of [{width: 375, height: 812}, {width: 1440, height: 900}]) {
  test(`workspace fits ${viewport.width}px`, async ({page}) => {
    await page.setViewportSize(viewport);
    await page.goto("/");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    expect(overflow).toBe(false);
  });
}
```

- [ ] **Step 2: Run tests and confirm the production gaps**

Run: `uv run pytest backend/tests/test_spa_serving.py -v`

Run: `cd frontend && npm run test:e2e`

Expected: serving and browser tests fail until production wiring exists.

- [ ] **Step 3: Add safe SPA fallback and startup script**

Mount immutable built assets at `/assets` and return `index.html` only for non-API paths; unknown `/api/*` routes stay JSON 404 responses. `run.sh` must use `set -euo pipefail`, resolve its own directory, verify `ffmpeg` and `espeak-ng`, run `npm ci` when dependencies are absent or lockfile changed, build the frontend, then execute `uv run uvicorn kokoro_app.app:app --app-dir backend --host 127.0.0.1 --port "${KOKORO_PORT:-8000}"`. Never bind publicly by default.

- [ ] **Step 4: Document setup, privacy, controls, and troubleshooting**

README instructions must include Ubuntu/Debian installation of `espeak-ng` and FFmpeg, the single `./run.sh` command, first-run model download expectations, the local URL, output retention, supported languages/formats, explanation of expression presets, offline reuse, optional smoke test, test commands, and fixes for missing phonemizer/model/FFmpeg errors.

- [ ] **Step 5: Run the complete automated suite**

Run: `uv run pytest backend/tests -v -m "not smoke"`

Run: `cd frontend && npm test -- --run && npm run typecheck && npm run build && npm run test:e2e`

Expected: all commands pass.

- [ ] **Step 6: Commit production workflow and documentation**

```bash
git add backend frontend run.sh README.md
git commit -m "feat: ship one-command local Kokoro app"
```

### Task 10: Real-machine Acceptance and Final Polish

**Files:**
- Modify only files implicated by concrete acceptance failures.

**Interfaces:**
- Consumes: the complete application from Tasks 1–9.
- Produces: verified CPU synthesis and valid local audio in every documented format.

- [ ] **Step 1: Install the missing Linux phonemizer prerequisite**

Run: `sudo apt-get update && sudo apt-get install -y espeak-ng`

Expected: `espeak-ng --version` succeeds. If passwordless sudo is unavailable, provide the exact command to the user and continue all non-inference verification.

- [ ] **Step 2: Start the production app**

Run: `./run.sh`

Expected: the frontend build succeeds, FastAPI listens only on `127.0.0.1:8000`, and `/api/status` transitions from loading to ready after the first model download.

- [ ] **Step 3: Run a real short inference and validate the output**

Submit `Kokoro is running entirely on this computer.` with American English, `af_heart`, Neutral, and WAV. Confirm completion, playability, 24 kHz sample rate, non-zero duration, finite samples, and download headers.

- [ ] **Step 4: Exercise long text, presets, blending, cancellation, and four formats**

Generate a three-paragraph script using Calm and a compatible two-voice blend. Confirm chunk progress rises monotonically. Cancel a second long job and confirm no audio endpoint is exposed. Generate tiny fixtures in MP3, FLAC, and OGG and inspect each with `ffprobe`.

- [ ] **Step 5: Perform visual and accessibility review**

Capture desktop and phone screenshots. Check against the approved palette, typography, spacing, single visual signature, no generic dashboard cards, no clipped controls, clear active/focus states, and usable reduced-motion behavior. Remove one non-functional decorative element if the composition feels busy.

- [ ] **Step 6: Re-run all verification and commit only evidence-driven fixes**

Run: `uv run pytest backend/tests -v -m "not smoke"`

Run: `cd frontend && npm test -- --run && npm run typecheck && npm run build && npm run test:e2e`

Run: `KOKORO_SMOKE=1 uv run pytest backend/tests/test_inference_smoke.py -v -s`

Expected: all tests pass, the smoke test produces audio, and all four formats pass `ffprobe`.

```bash
git add -A
git commit -m "fix: complete local acceptance polish"
```
