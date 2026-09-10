# Continuous Storyboard Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Speak storyboard rows as one continuous narration while preserving the original rows as timestamped transcript segments.

**Architecture:** Build one normalized single-space narration string for storyboard requests and run the existing long-script chunker over that combined text. Track source-character ranges for synthesis chunks and storyboard rows, then map row boundaries into generated audio ranges for deterministic cross-language transcript timestamps without making rows synthesis boundaries.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, NumPy, pytest, React 19, TypeScript, Vitest, Playwright

**Spec:** `docs/superpowers/specs/2026-09-10-continuous-storyboard-synthesis-design.md`

## Global Constraints

- Storyboard rows must not directly create synthesis calls or inserted pauses.
- Normalize internal spoken whitespace and join rows with exactly one ordinary space.
- Keep normal sentence/model-length chunking and general pause behavior.
- Preserve exact original storyboard row text and `paragraph_end: true` in transcript segments.
- Preserve the submitted `text` as the full downloadable transcript.
- Keep row timestamps monotonic for every supported language, including languages without word alignment.
- Remove the obsolete comma-specific pause setting while continuing to accept it harmlessly from older clients through Pydantic's existing unknown-field behavior.
- Do not change plain-script synthesis behavior or the public job-response shape.

---

### Task 1: Plan Continuous Storyboard Speech and Segment Timing

**Files:**
- Modify: `backend/kokoro_app/jobs.py`
- Modify: `backend/tests/test_jobs.py`

**Interfaces:**
- Consumes: `GenerationRequest.text`, `GenerationRequest.segments`, `chunk_script(text)`, generated PCM arrays, and per-chunk pauses.
- Produces: `_speech_plan(request: GenerationRequest) -> SpeechPlan`, where `SpeechPlan` contains the speech chunks, their ranges in normalized synthesis text, and optional original storyboard segment ranges.
- Produces: `_sample_at_text_offset(offset: int, chunk_text_ranges: tuple[tuple[int, int], ...], chunk_audio_ranges: list[tuple[int, int]]) -> int` for deterministic row-to-audio mapping.

- [ ] **Step 1: Write the failing continuous-synthesis regression test**

Add a recording engine to `backend/tests/test_jobs.py` and assert that two comma-linked storyboard rows become one engine call while the completed transcript still has two rows:

```python
def test_storyboard_rows_are_synthesized_as_one_continuous_narration(tmp_path: Path) -> None:
    class RecordingEngine(FakeEngine):
        calls: list[str]

        def __init__(self) -> None:
            self.calls = []

        def synthesize(self, text, *args, **kwargs) -> SynthesisResult:
            self.calls.append(text)
            return super().synthesize(text, *args, **kwargs)

    engine = RecordingEngine()
    manager = JobManager(engine, tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(
        text="The thought begins,\n\nand continues naturally.",
        segments=["The thought begins,", "and continues naturally."],
    ))
    wait_for(manager, record.id, JobState.complete)

    assert engine.calls == ["The thought begins, and continues naturally."]
    assert [segment["text"] for segment in manager.get(record.id).segments] == [
        "The thought begins,",
        "and continues naturally.",
    ]
    manager.shutdown()
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `uv run pytest -q backend/tests/test_jobs.py -k storyboard_rows_are_synthesized_as_one_continuous_narration`

Expected: FAIL because `engine.calls` contains one call per storyboard row.

- [ ] **Step 3: Add a failing timestamp-mapping test**

Use a recording fake that returns 24,000 samples for the joined text. Assert both storyboard rows are present, ordered, non-empty, and end at 1 second:

```python
def test_storyboard_rows_keep_monotonic_timestamps_inside_shared_audio(tmp_path: Path) -> None:
    class OneSecondEngine(FakeEngine):
        def synthesize(self, *args, **kwargs) -> SynthesisResult:
            return SynthesisResult(np.ones(24_000, dtype=np.float32))

    manager = JobManager(OneSecondEngine(), tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(
        text="Short first row,\n\na considerably longer second row.",
        segments=["Short first row,", "a considerably longer second row."],
    ))
    wait_for(manager, record.id, JobState.complete)
    first, second = manager.get(record.id).segments

    assert first["start"] == 0.0
    assert 0 < first["end"] <= second["start"] < second["end"]
    assert second["end"] == pytest.approx(1.0)
    manager.shutdown()
```

- [ ] **Step 4: Run both focused tests and verify RED**

Run: `uv run pytest -q backend/tests/test_jobs.py -k 'continuous_narration or shared_audio'`

Expected: FAIL because current row-level synthesis cannot place two transcript rows inside one shared audio clip.

- [ ] **Step 5: Implement speech planning and character-range mapping**

In `backend/kokoro_app/jobs.py`, replace row-by-row `_speech_chunks()` planning with a focused immutable plan:

```python
@dataclass(frozen=True)
class SpeechPlan:
    chunks: tuple[TextChunk, ...]
    chunk_text_ranges: tuple[tuple[int, int], ...]
    storyboard_ranges: tuple[tuple[int, int], ...] | None


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
```

Add `_sample_at_text_offset()` so offsets inside a chunk interpolate from its audio start to end, offsets in an inter-chunk gap select the adjacent spoken edge, and empty audio maps to its start. Update `JobManager._run()` to synthesize only `plan.chunks`, keep `(audio_start, audio_end)` for each chunk while applying existing pauses, and build storyboard `record.segments` from original row text plus the mapped row start/end. Keep the existing chunk-based transcript construction unchanged when `storyboard_ranges is None`.

```python
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
```

Build audio ranges once after synthesis and reuse them for timestamps:

```python
chunk_audio_ranges = []
cursor = 0
for index, audio in enumerate(generated):
    spoken_end = cursor + len(audio)
    chunk_audio_ranges.append((cursor, spoken_end))
    cursor = spoken_end
    if index < len(generated) - 1:
        cursor += round(SAMPLE_RATE * pauses[index] / 1000)
```

- [ ] **Step 6: Run focused tests and verify GREEN**

Run: `uv run pytest -q backend/tests/test_jobs.py -k 'continuous_narration or shared_audio'`

Expected: PASS.

- [ ] **Step 7: Replace obsolete comma tests with long-storyboard coverage**

Remove tests that assert `comma_pause_ms` behavior. Add a test with three storyboard rows whose joined normalized narration exceeds 420 characters. Assert the engine receives normal long-script chunks, never receives an individual row merely because it is a row, and the completed transcript contains all three exact original row strings with monotonic timestamps ending at the complete audio duration.

```python
def test_long_storyboard_keeps_rows_separate_from_speech_chunks(tmp_path: Path) -> None:
    class RecordingEngine(FakeEngine):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def synthesize(self, text, *args, **kwargs) -> SynthesisResult:
            self.calls.append(text)
            return super().synthesize(text, *args, **kwargs)

    rows = ["alpha " * 50, "beta " * 50, "gamma " * 50]
    rows = [row.strip() for row in rows]
    engine = RecordingEngine()
    manager = JobManager(engine, tmp_path, encoder=fake_encode)
    record = manager.create(GenerationRequest(text="\n\n".join(rows), segments=rows))
    wait_for(manager, record.id, JobState.complete)
    finished = manager.get(record.id)

    assert len(engine.calls) >= 2
    assert all(call not in rows for call in engine.calls)
    assert [segment["text"] for segment in finished.segments] == rows
    assert all(
        current["end"] <= following["start"]
        for current, following in zip(finished.segments, finished.segments[1:])
    )
    assert finished.segments[-1]["end"] == pytest.approx(finished.duration)
    manager.shutdown()
```

- [ ] **Step 8: Run backend job tests**

Run: `uv run pytest -q backend/tests/test_jobs.py`

Expected: all tests pass.

- [ ] **Step 9: Commit backend continuous synthesis**

```bash
git add backend/kokoro_app/jobs.py backend/tests/test_jobs.py
git commit -m "fix: synthesize storyboards as continuous narration"
```

---

### Task 2: Remove the Obsolete Comma-Pause Contract

**Files:**
- Modify: `backend/kokoro_app/schemas.py`
- Modify: `backend/kokoro_app/app.py`
- Modify: `backend/tests/test_api.py`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ExpressionControls.tsx`
- Modify: `frontend/tests/App.test.tsx`
- Modify: `frontend/tests/useGeneration.test.tsx`
- Modify: `frontend/tests/e2e/responsive.spec.ts`

**Interfaces:**
- Removes: `GenerationRequest.comma_pause_ms`, `/api/config.defaults.comma_pause_ms`, `/api/config.limits.comma_pause_ms`, and the corresponding React prop/state/control.
- Preserves: `GenerationRequest.segments`, existing `pause_ms`, and unknown-field compatibility for older clients.

- [ ] **Step 1: Write failing API contract assertions**

Change `test_config_exposes_catalog_presets_formats_and_bounds` to assert the obsolete setting is absent:

```python
assert "comma_pause_ms" not in body["limits"]
assert "comma_pause_ms" not in body["defaults"]
```

Delete the upper-bound validation test that exists only for the removed field.

- [ ] **Step 2: Run the API contract test and verify RED**

Run: `uv run pytest -q backend/tests/test_api.py -k config_exposes_catalog_presets_formats_and_bounds`

Expected: FAIL because the config currently exposes the setting.

- [ ] **Step 3: Write a failing frontend removal test**

In `frontend/tests/App.test.tsx`, upload or paste a two-row storyboard, open Fine-tune delivery, assert `queryByLabelText("Comma continuation (ms)")` is absent, generate, and assert the request body does not contain `comma_pause_ms`.

```tsx
it("does not expose a row pause override for continuously synthesized storyboards", async () => {
  const calls = stubApi();
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Script");
  await user.click(screen.getByRole("button", {name: "Upload storyboard"}));
  await user.type(screen.getByLabelText("Paste Markdown storyboard"), `
| Beat | VO script |
| --- | --- |
| 1 | First clause, |
| 2 | continuing naturally. |
`);
  await user.click(screen.getByRole("button", {name: "Use pasted table"}));
  await user.selectOptions(screen.getByLabelText("Speech column"), "1");
  await user.click(screen.getByText("Fine-tune delivery"));
  expect(screen.queryByLabelText("Comma continuation (ms)")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", {name: "Generate speech"}));
  await waitFor(() => expect(calls.some(({init}) => init?.method === "POST")).toBe(true));
  const body = JSON.parse(String(calls.find(({init}) => init?.method === "POST")?.init?.body));
  expect(body).not.toHaveProperty("comma_pause_ms");
});
```

- [ ] **Step 4: Run the frontend removal test and verify RED**

Run: `npm test -- --run tests/App.test.tsx -t 'does not expose a row pause override'`

Expected: FAIL because the control and request property are still present.

- [ ] **Step 5: Remove the backend and frontend contract**

Delete `comma_pause_ms` from the Pydantic request model and API config. Delete the React state, request property, `ExpressionControls` props, number control, clamp helper, and TypeScript properties. Remove obsolete comma-control tests and update mocked config objects. Keep `pause_ms` unchanged.

- [ ] **Step 6: Run focused API and UI tests and verify GREEN**

Run: `uv run pytest -q backend/tests/test_api.py -k config_exposes_catalog_presets_formats_and_bounds`

Run: `npm test -- --run tests/App.test.tsx -t 'does not expose a row pause override'`

Expected: both pass.

- [ ] **Step 7: Run backend and frontend unit suites**

Run: `uv run pytest -q`

Run: `npm test -- --run` from `frontend/`.

Expected: all unit tests pass; only the explicitly opt-in real-inference smoke test may be skipped.

- [ ] **Step 8: Commit contract cleanup**

```bash
git add backend/kokoro_app/schemas.py backend/kokoro_app/app.py backend/tests/test_api.py frontend/src/types.ts frontend/src/App.tsx frontend/src/components/ExpressionControls.tsx frontend/tests/App.test.tsx frontend/tests/useGeneration.test.tsx frontend/tests/e2e/responsive.spec.ts
git commit -m "refactor: remove storyboard row pause override"
```

---

### Task 3: Document, Build, Review, and Activate

**Files:**
- Modify: `README.md`
- Verify: `frontend/dist/` (generated and ignored)

**Interfaces:**
- Documents: Storyboard rows are synthesized continuously while downloads retain row segmentation.
- Activates: rebuilt frontend and restarted local FastAPI process on port 8000.

- [ ] **Step 1: Update user-facing documentation**

Replace the comma-pause Fine-tune wording in `README.md` with:

```markdown
- **Continuous storyboard narration** joins speech rows into one natural delivery while preserving each source row in the timestamped transcript and downloads.
```

- [ ] **Step 2: Run all fresh verification commands**

Run from repository root:

```bash
uv run pytest -q
cd frontend && npm test -- --run
cd frontend && npm run build
cd frontend && npm run test:e2e
git diff --check
```

Expected: backend and frontend tests pass, production build succeeds, Playwright passes at desktop and mobile sizes, and the diff has no whitespace errors.

- [ ] **Step 3: Request independent code review**

Use `superpowers:requesting-code-review` against the design and this plan. Fix all Critical and Important findings and rerun the affected focused and full verification commands.

- [ ] **Step 4: Commit documentation and review fixes**

```bash
git add README.md
git commit -m "docs: explain continuous storyboard narration"
```

Include any review-fix files in the same commit only when they have not already been committed in Tasks 1 or 2.

- [ ] **Step 5: Restart and smoke-check the local app**

Stop only the verified Kokoro process group currently listening on port 8000, start `./run.sh` detached, and poll `/api/status` until it returns `ready`. Confirm the rebuilt browser asset does not contain `Comma continuation (ms)`, `/api/config` no longer exposes `comma_pause_ms`, and a validated storyboard request is accepted by the updated server.

- [ ] **Step 6: Report completion evidence**

Report the continuous synthesis behavior, preserved transcript segmentation, removed obsolete control, exact test/build counts, local URL, and any intentionally skipped smoke test.
