# Kokoro Local TTS — Design Specification

## Purpose

Build a private, local-first text-to-speech workbench for this Linux machine. A user can paste anything from a short line to a long narration script, choose a Kokoro voice and delivery treatment, generate audio, listen in the browser, and download the result.

The product should feel like a focused audio tool rather than a dashboard or promotional site. It must represent Kokoro's capabilities honestly: language, voice, voice metadata, voice blending, and synthesis speed are model-level controls; expression presets combine those capabilities with deterministic text timing and local audio post-processing.

## Scope

### Included

- A responsive single-page web interface for desktop and mobile.
- A large script editor with character, word, and estimated-duration feedback.
- All voices and languages made available by the installed Kokoro v1.0 package.
- Voice filtering by language and gender metadata.
- Optional blending of two compatible voices with an adjustable ratio.
- Expression presets: Neutral, Warm, Calm, Bright, Serious, and Dramatic.
- Manual controls for synthesis speed, pitch, tempo, sentence-pause scale, and volume.
- WAV, MP3, FLAC, and OGG export.
- Optional loudness normalization.
- Long-form generation through sentence-aware chunking and audio assembly.
- Visible generation progress and cancellation.
- In-browser waveform, seeking, play/pause, elapsed time, and download.
- Local model status and actionable setup/runtime errors.
- A one-command Linux development/startup workflow.

### Excluded

- Accounts, authentication, analytics, cloud inference, and external AI APIs.
- Voice cloning or controls Kokoro does not support.
- A database, project library, or generation history in the first version.
- A text-generating or LLM-based emotion system.
- Native desktop packaging.

## Technical Approach

### Backend

Use Python and FastAPI. The backend owns Kokoro inference, job state, long-text chunking, audio assembly, post-processing, and file delivery.

The model is loaded once and reused. Device selection is explicit and reports CPU on this machine. The first run may download model assets; subsequent use works offline while the assets remain in the local model cache.

FFmpeg performs output encoding, pitch/tempo processing, volume adjustment, and optional normalization. Kokoro's native 24 kHz output remains the source sample rate unless the selected container requires conversion.

### Frontend

Use React, TypeScript, and Vite. The production backend serves the compiled frontend so the finished app has one local URL and one startup command. The development workflow may run Vite and FastAPI together with proxying.

The frontend owns editor state, control state, job progress, cancellation, audio transport, and error presentation. It does not perform inference or send text anywhere except the local backend.

### API Boundaries

- `GET /api/status`: model state, runtime device, setup problems, and version.
- `GET /api/config`: languages, voices, metadata, presets, formats, defaults, and allowed ranges.
- `POST /api/jobs`: validate settings and create a generation job.
- `GET /api/jobs/{id}`: phase, progress, error, and result metadata.
- `DELETE /api/jobs/{id}`: request cancellation.
- `GET /api/jobs/{id}/audio`: stream the generated audio.
- `GET /api/jobs/{id}/download`: download with a useful filename and content type.

Job progress uses lightweight polling. This avoids an unnecessary WebSocket/SSE lifecycle while still providing reliable progress for local long-form work.

No database is used. Jobs and generated files live in a runtime-owned local directory. Old temporary jobs are pruned on startup and after a bounded retention window. A downloaded file is never modified.

## Synthesis and Expression Model

### Voice Selection

The backend reads the installed Kokoro voice catalog and returns stable metadata: identifier, display name, language, locale, and gender. The UI never invents gender or expression labels beyond this metadata.

The primary voice is required. A secondary voice is optional and must use the same language. When blending is enabled, a ratio control determines the contribution of each voice.

### Expression Presets

Presets are deterministic control bundles, not claims that Kokoro has an emotion parameter. Each preset defines:

- a synthesis speed baseline;
- a pitch offset in semitones;
- a post-processing tempo multiplier;
- an inter-sentence pause multiplier;
- an optional recommended compatible secondary voice and blend ratio.

Neutral applies no tonal post-processing. Warm, Calm, Bright, Serious, and Dramatic use conservative ranges designed to preserve intelligibility. The interface shows a short plain-language summary of what the selected preset changes. Editing a constituent value changes the preset label to Custom.

Voice choice remains under the user's control. A preset may suggest or initialize a blend, but it does not silently replace the selected primary voice.

### Long-form Flow

1. Normalize line endings and reject blank input.
2. Split text at paragraph and sentence boundaries while respecting Kokoro's practical input size.
3. Generate chunks sequentially through the shared model.
4. Add expression-controlled silence between sentence and paragraph chunks.
5. Concatenate PCM audio.
6. Apply pitch, tempo, volume, and optional normalization through FFmpeg.
7. Encode the selected format and expose the result to the browser.

Cancellation is checked between chunks and before post-processing. Partial output is discarded when a job is cancelled or fails.

## Interface Design

### Visual System

- Paper gray: `#F4F5F3`
- Ink: `#171A18`
- Muted text: `#6D736F`
- Cobalt action: `#3157E5`
- Signal mint: `#B9E8CF`
- Surface white: `#FCFCFB`
- Instrument Sans: interface and editorial copy
- IBM Plex Mono: status, timing, counts, format, and model data

Fonts are bundled with the frontend so the local interface does not depend on a network connection. Controls use restrained 10–14 px radii, crisp one-pixel borders, and minimal shadow.

### Desktop Layout

The application header shows the product name and compact local model status. The main workspace is a two-column split: a wide script editor on the left and a narrower voice/output inspector on the right. A full-width generate row separates configuration from playback. The latest result occupies a persistent bottom transport strip with waveform, seek position, playback controls, and download.

### Mobile Layout

The workspace becomes a single column in task order: script, voice, expression, output, generate, then transport. The waveform remains usable without horizontal page scrolling. Touch targets are at least 44 px, and the primary action remains easy to reach without becoming a permanently obstructive floating button.

### Interaction Details

- Advanced controls are grouped by their audible effect, not by backend terminology.
- Voice choices update immediately when language or gender filters change.
- A voice blend is clearly visualized as A/B with a percentage, not hidden inside an advanced menu.
- Generate changes to a progress treatment with the current phase and Cancel action.
- The editor remains editable while a job runs, but the running job uses the submitted snapshot.
- A completed generation enters the transport and is ready to play without autoplay.
- Download uses a filename derived from the first meaningful words plus the selected format.
- Focus styles are visible, controls have programmatic labels, and motion respects `prefers-reduced-motion`.

## Error Handling

Errors state what failed and how to correct it. Required cases include:

- `espeak-ng` is absent or cannot phonemize the selected language.
- Model assets are downloading, unavailable, or fail to load.
- Input is blank or exceeds a defensive maximum size.
- A voice is invalid or incompatible with the selected language/blend.
- FFmpeg is absent or cannot encode the selected format.
- A generation job is cancelled.
- The local backend becomes unreachable.

Backend errors use structured codes and safe messages. Internal stack traces remain in local logs, not in the browser response.

## Verification

### Backend Tests

- Sentence and paragraph chunking, including punctuation and oversized sentences.
- Preset resolution and manual Custom-state calculations.
- Voice filtering and blend compatibility.
- Validation of text, ranges, voices, formats, and cancellation.
- Audio concatenation and FFmpeg command construction.
- API job lifecycle and result headers.
- One opt-in smoke test that performs real Kokoro inference.

### Frontend Tests

- Initial configuration and model-status states.
- Language, gender, voice, and blend interactions.
- Preset application and transition to Custom.
- Job progress, cancellation, failure, completion, playback, and download states.
- Keyboard accessibility and meaningful labels.
- Responsive behavior at representative desktop and phone widths.

### Manual Acceptance

- Start the app with the documented command on this Linux machine.
- Generate and play a short English sample on CPU.
- Generate a multi-paragraph script and observe chunk progress.
- Export and open WAV, MP3, FLAC, and OGG results.
- Confirm that the app makes no inference request to a remote service after initial model download.
- Confirm there is no horizontal overflow at 375 px and the desktop split remains balanced at 1440 px.

## Success Criteria

The project is complete when a user can start it locally with one documented command, paste either short or long text, configure any compatible Kokoro voice and transparent expression settings, generate on this CPU, listen in the browser, and download a valid audio file in each supported format from a polished responsive interface.
