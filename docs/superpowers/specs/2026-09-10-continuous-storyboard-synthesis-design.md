# Continuous Storyboard Synthesis Design

## Goal

Storyboard rows must sound like one continuous narration instead of a sequence of separately generated clips. Row boundaries remain visible in the timestamped and downloadable transcript, but they no longer force synthesis boundaries or pauses.

## Root cause

The current job planner runs `chunk_script()` independently for every storyboard row and calls `engine.synthesize()` for every resulting row chunk. Even when the explicit silence between comma-ended rows is reduced to 100 ms, each synthesis call can carry its own ending cadence and trailing audio. Adjusting appended silence cannot make separately spoken clips sound like a single sentence.

## Synthesis design

For a storyboard request, normalize whitespace within every row and join the rows with one ordinary space. Feed this combined narration to the existing `chunk_script()` flow once. Storyboard row boundaries therefore have no special meaning to speech generation:

- A comma-ended row and the following row normally remain in the same synthesis chunk and are spoken as one continuing thought.
- Sentence punctuation and the existing model-length limit may still create chunks, preserving the application's long-script safety behavior.
- General automatic or explicit pause settings apply only between actual speech chunks.
- Plain pasted scripts retain their existing behavior.

The `text` and `segments` request fields remain unchanged. `text` continues to be the rows joined by blank lines for API validation and transcript preservation; only the internal text sent to synthesis uses single-space joining.

The comma-specific pause setting becomes obsolete and will be removed from the request schema, configuration response, frontend state, Fine-tune control, documentation, and tests. Older clients that still send the field remain compatible because unknown request fields are currently ignored by Pydantic.

## Transcript segmentation and timestamps

The original storyboard rows remain the source of transcript segment text. The backend will build character ranges for their normalized spoken forms inside the combined narration and separately track each generated chunk's character range and audio range.

Each storyboard row boundary maps to audio time as follows:

1. If the boundary lies inside a synthesized chunk, interpolate its timestamp by character position within that chunk's spoken-audio duration.
2. If a boundary falls between chunks, use the preceding chunk's spoken end for the earlier row and the following chunk's spoken start for the next row. Any real inter-chunk pause therefore remains outside both spoken segment ranges.
3. Clamp timestamps to the audio duration and keep them monotonic.

This yields deterministic row timestamps for every supported language. It is necessarily an estimate for row boundaries inside a shared audio chunk because Kokoro supplies word timings only for the two English pipelines. Existing word-level timestamps remain model-aligned wherever Kokoro provides them.

Every storyboard transcript segment keeps its exact original row text and `paragraph_end: true`, so readable and JSON transcript downloads retain the storyboard row structure. The full transcript remains the submitted `text` value.

## Error handling and compatibility

- Empty storyboard rows and mismatched `text`/`segments` remain rejected by existing validation.
- Normalization is internal and never rewrites downloadable transcript text.
- A chunk with zero audio duration maps contained boundaries to that chunk's start instead of dividing by zero.
- The regular non-storyboard path and public response shape do not change.

## Testing

Backend regression tests will prove that:

- Comma-ended adjacent storyboard rows are sent to the engine together rather than in separate calls.
- Rows remain distinct transcript segments after continuous synthesis.
- Estimated row timestamps are monotonic and reflect positions inside a shared audio chunk.
- Storyboards long enough to require normal chunking still retain exact row text and valid segment timing.
- Plain-script synthesis and existing general pause behavior remain unchanged.

Frontend tests will prove that storyboard requests still submit the original rows and that the removed comma-pause setting is no longer presented or submitted. The complete backend, frontend, production-build, and browser suites will be run before completion.
