# Kokoro Local TTS

A web workbench and reusable TTS microservice for turning scripts into speech, including narration for OpenMontage. Fish Audio S2.1 Pro Free is the default engine through OpenRouter, using configurable voice reference `b0204e37cbc94a16954c78697b844af2`. Kokoro 82M remains available when explicitly selected as a private, offline engine with all 54 Kokoro v1.0 voices, nine language/accent groups, expression presets, voice blending, timestamped transcripts, a waveform player, and WAV/MP3/FLAC/OGG downloads.

In Kokoro mode, no script text is sent to a cloud API. The first Kokoro request downloads its open model files from Hugging Face; later requests reuse the local cache and can work offline. Fish Audio mode sends the submitted script and optional voice reference ID to OpenRouter for synthesis; the interface marks this mode clearly.

## Start on Ubuntu or Debian

Install FFmpeg once:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

The machine also needs Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 20+ and npm. This project already targets the versions installed on the development machine.

Then run:

```bash
./run.sh
```

The launcher listens on localhost by default:

```text
On this computer       → http://127.0.0.1:8000
```

For access from another device on your home network, explicitly enable LAN access:

```bash
KOKORO_HOST=0.0.0.0 ./run.sh
```

The launcher then also prints a home-network address such as `http://192.168.x.x:8000`. Open it from a device connected to the same Wi-Fi or Ethernet network.

There is no authentication. Anyone who can reach the app can submit scripts using your server's OpenRouter key and quota, use this machine's CPU, change the shared voice library, and access generated audio by job ID. Prefer localhost for integrations on the same computer. Enable LAN access only on a trusted network; do not expose port 8000 through your router to the public internet. Remote deployments need an authenticated reverse proxy, TLS, and access restrictions.

To choose another port:

```bash
KOKORO_PORT=8080 ./run.sh
```

To stop a Kokoro instance running in the background:

```bash
./run.sh --stop
```

If Kokoro is running in the active terminal, press `Ctrl+C` instead.
For an instance started on another port, include that port when stopping it:

```bash
KOKORO_PORT=8080 ./run.sh --stop
```

To explicitly select localhost-only access for a session:

```bash
KOKORO_HOST=127.0.0.1 ./run.sh
```

If Ubuntu's firewall blocks another device, allow the selected port on the local network:

```bash
sudo ufw allow 8000/tcp
```

Startup does not preload Kokoro. The header initially reports `Model on demand`; Kokoro downloads and loads only when you submit an explicitly selected Kokoro request. That first local request can take several minutes.

## Controls

- **TTS engine** switches between offline Kokoro Local and Fish Audio S2.1 Pro Free through OpenRouter. Fish Audio is selected by default.
- **Saved Fish voices** lets you save names, descriptions, and reference IDs, edit them, and delete them with confirmation. Open **Voices** in the main navigation for a management page with 10 voices per page and **Use voice** actions. Saved voices appear in the Fish voice selector and persist across restarts, shared by devices using the same server.
- **Markdown storyboards** can be pasted directly or uploaded from `.md`, `.markdown`, or `.txt` files. Choose any table column for speech; every non-empty cell remains a read-only, timestamped segment matching its source row.
- **Language and gender** filter the official voice catalog; gender is voice metadata, not a model setting.
- **Voice previews** play an included, language-appropriate sample instantly for every voice without running synthesis.
- **Voice blend** combines two voices from the same language with a visible A/B ratio.
- **Expression** offers Neutral, Warm, Calm, Bright, Serious, and Dramatic. These are deterministic bundles of synthesis speed, pitch, tempo, and sentence pauses—not a claimed Kokoro emotion parameter.
- **Continuous storyboard narration** joins speech rows into one natural delivery while preserving each source row in the timestamped transcript and downloads.
- **Output** supports WAV, MP3, FLAC, and OGG at Kokoro's native 24 kHz, with optional loudness normalization.
- **Long scripts** are split at paragraphs and sentence boundaries, synthesized in sequence, and joined with controlled pauses. Progress and cancellation remain available during generation.
- **Optional transcripts** are off by default so you can hear generated audio first. Check **Automatically transcribe generated audio**, or use **Transcribe audio** beside the finished audio. Timestamped transcripts can be viewed, copied, or downloaded as text or JSON. Fish Audio transcription uses local **WhisperX** by default; **Whisper (faster-whisper)** remains selectable under **Timestamp engine**. Kokoro uses its built-in synthesis timing.

Generated files live under `runtime/audio/` and are pruned after 24 hours when the app starts. Download anything you want to keep.

## Fish Audio via OpenRouter

Fish Audio uses OpenRouter's Speech API and the exact free-only model:

```text
fish-audio/s2.1-pro-free:free
```

There is no fallback to `fish-audio/s2.1-pro` or any other paid model. If the free model is rate-limited or unavailable, the app reports the error.

1. Create an [OpenRouter account](https://openrouter.ai/) and an [API key](https://openrouter.ai/settings/keys).
2. Set the key before launching the app, either in your shell:

   ```bash
   export OPENROUTER_API_KEY="sk-or-..."
   ./run.sh
   ```

   Or copy the local environment template and add the key there:

   ```bash
   cp .env.example .env
   ./run.sh
   ```

   The launcher reads `OPENROUTER_API_KEY` and `FISH_AUDIO_DEFAULT_VOICE` from `.env` without treating the file as a shell script. Already exported non-empty environment values take precedence. When starting Uvicorn directly, export these variables yourself; only the launcher reads `.env`.

   If no environment key is configured, you can paste a key into the password-style field in Fish mode. That key is kept only in the current browser session. `OPENROUTER_API_KEY` takes precedence and disables the browser field; environment configuration is preferred, especially when accessing the app over a local network.

3. **Fish Audio S2.1 Pro Free — OpenRouter** is selected by default under **TTS Engine**.
4. Under **Voice / Accent**, choose a saved **Fish voice**. The library starts with reference `b0204e37cbc94a16954c78697b844af2`, named **Original Fish voice**. Use **Add voice** to enter **Name**, **Description** (optional), and **Reference ID**. You can paste a Fish Audio voice URL such as `https://fish.audio/app/m/689b47ca83dd48dba90b160affb8a118/` into **Reference ID**; the app extracts `689b47ca83dd48dba90b160affb8a118` automatically. Saving from the studio selects that voice for generation. Select an existing voice to **Edit voice** or **Delete voice**. Choose **Custom reference ID…** for a one-time ID, or **Provider default** to omit the reference. Voice identity is the preferred way to choose an accent.
5. Choose a **Delivery Style**. The app prepends the corresponding Fish bracket instruction, while preserving any bracketed instructions already in the script. **Custom** accepts your own instruction.
6. Generate, play, and download the returned MP3. Audio is ready without waiting for transcription. Choose **Transcribe audio** when you want timestamps, or check **Automatically transcribe generated audio** before generating. The timestamp panel lets you switch between segment and word timing, select **JSON**, and download the timescript.

The free model is intended for testing and lower-volume use and is subject to OpenRouter's free-model rate limits and availability. Fish mode uses one request for the complete narration rather than one request per sentence. Kokoro does not require this key and remains fully functional offline.

Set `FISH_AUDIO_DEFAULT_VOICE` in the server environment or `.env` to change the voice used by the UI, `/api/jobs`, and `/v1/audio/speech` when the caller omits a voice. It initially defaults to `b0204e37cbc94a16954c78697b844af2`. An explicit empty voice (`"voice": ""` for speech, `"fish_voice": ""` for jobs) selects the provider default; `null` uses the configured server voice. Changing this setting does not edit or delete your saved voice library.

Open **Voices** or **Manage all voices** to browse the paginated library, read descriptions, edit or delete any voice, or choose **Use voice** to return to the studio with that voice selected. Your current script stays in place while you manage voices.

Use **Copy ID** beside a voice reference to copy just its reference ID. **Open in Fish Audio** opens that voice's Fish Audio page in a new tab so you can listen to its samples. These actions are available in both the management list and the studio's selected voice controls. If the browser blocks automatic copying, the app provides a selected ID field for manual copying.

The voice library is stored in `runtime/fish_voices.sqlite3`, separate from expiring audio files. Back up this file to keep your saved names, descriptions, and references. Existing libraries are upgraded automatically; older voices start with an empty description. The list loads when Fish controls open; use **Reload voices** to pick up changes made on another device. Deleting a library entry only removes the local shortcut, not the voice on Fish Audio. API keys are never stored in the library.

Under **Transcript → Timestamp engine**, choose **WhisperX — word alignment (default)** or **Whisper — faster-whisper**. Automatic transcription is unchecked by default. You can listen and download while transcription is running. If transcription fails, the audio stays available; choose another timestamp engine if needed and click **Retry transcription**. This uses the saved audio without sending another synthesis request to OpenRouter.

The API defaults to `auto_transcribe: false`. Set it to `true` on `POST /api/jobs` to request automatic transcription, or call `POST /api/jobs/{id}/transcript` with `{"timestamp_engine": "whisperx"}` (or `"whisper"`) afterward. Audio generation and transcription have separate status fields: `state: "complete"` makes audio available, while `transcription_state` reports `idle`, `queued`, `transcribing`, `complete`, or `failed`. Poll the job until transcription finishes. Transcription failures are reported in `transcription_error` and do not fail or delete the audio.

When transcription is requested, the app runs the multilingual `small` [faster-whisper](https://github.com/SYSTRAN/faster-whisper) model locally with CPU int8 inference. With **WhisperX**, the detected speech language selects a local alignment model, and [WhisperX](https://github.com/m-bain/whisperX) aligns the recognized words to the audio. The first transcription downloads the recognition and alignment models; later runs reuse their local caches. The recognition model is shared between the two timestamp modes. Audio is not sent to another transcription service. Because text comes from speech recognition, recognized text can occasionally differ slightly from the submitted script. The panel identifies the actual mode as **Timed locally with WhisperX** or **Timed locally with Whisper**.

WhisperX adds CPU processing and a language-specific model download. If alignment is unavailable for the detected language, or its model cannot be downloaded, the app reports the problem; choose **Whisper — faster-whisper** and retry. It does not silently change timestamp engines. Kokoro continues using its own synthesis timing.

To trade more processing time and memory for a larger Whisper model, set `KOKORO_WHISPER_MODEL` in the shell before launch, for example:

```bash
KOKORO_WHISPER_MODEL=medium ./run.sh
```

A configuration template is included at `.env.example`. The real `.env` file is ignored by Git.

## Microservice API / OpenMontage integration

Start the server with `OPENROUTER_API_KEY` configured as above. Applications on the same computer can call `http://127.0.0.1:8000`; they do not need an OpenRouter account or API key. Use `/docs` for the API schema. If the caller runs in a container or on another machine, `127.0.0.1` refers to that caller: configure a reachable server address and restrict network access accordingly.

### Synchronous MP3 speech

`POST /v1/audio/speech` returns binary MP3 with `Content-Type: audio/mpeg`. It uses the same Fish synthesis client and delivery preparation as async jobs, including the natural delivery instruction. Existing Fish bracket instructions in `input` are preserved.

| JSON field | Behavior |
| --- | --- |
| `input` | Required non-blank narration, up to 5,000 characters. |
| `voice` | Optional Fish reference ID, up to 256 characters; defaults to `FISH_AUDIO_DEFAULT_VOICE`. |
| `model` | Optional; only `fish-audio/s2.1-pro-free:free` is accepted. |
| `response_format` | Optional; only `mp3` is accepted. |

The endpoint performs no transcription and saves no job or audio file on the server. Other models, formats, and unsupported fields are rejected with HTTP 422. Use the async API for longer scripts (up to 100,000 characters), Kokoro, or audio plus transcripts.

Generate narration with server defaults:

```bash
curl --fail-with-body --max-time 130 \
  http://127.0.0.1:8000/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"Welcome to this OpenMontage video."}' \
  --output narration.mp3
```

Node.js 20+ using native `fetch` (save as `speech.mjs`, then run `node speech.mjs`):

```js
import {writeFile} from 'node:fs/promises';

const baseUrl = process.env.TTS_BASE_URL ?? 'http://127.0.0.1:8000';
const response = await fetch(`${baseUrl}/v1/audio/speech`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    input: 'Welcome to this OpenMontage video.',
    // Omit voice to use the server configuration.
    model: 'fish-audio/s2.1-pro-free:free',
    response_format: 'mp3',
  }),
  signal: AbortSignal.timeout(130_000),
});
if (!response.ok) throw new Error(`TTS ${response.status}: ${await response.text()}`);
await writeFile('narration.mp3', Buffer.from(await response.arrayBuffer()));
```

The upstream connection/read timeout is 120 seconds. Client or reverse proxy timeouts should allow slightly longer. Errors use `{"error":{"code":"...","message":"...","action":null}}`: HTTP 429 for free-model rate limits, 504 for upstream timeouts, 503 for missing server configuration or connection failures, and 502 for other provider failures or invalid audio responses. There are no automatic retries, paid-model fallbacks, or engine switches. On a timeout, a provider may already have processed the request; retry deliberately. Aborting a caller's connection does not guarantee cancellation of upstream synthesis.

### Async audio and WhisperX timestamps

Keep using `/api/jobs` for narration plus word and segment timing. Omitting `engine` selects Fish Audio; omitting `fish_voice` selects the configured server voice. For example, create a job and poll it with curl (Python 3 is used only to read the returned ID):

```bash
JOB_ID=$(curl --fail-with-body --silent --show-error \
  http://127.0.0.1:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"text":"Welcome to this OpenMontage video.","auto_transcribe":true,"timestamp_engine":"whisperx"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl --fail-with-body "http://127.0.0.1:8000/api/jobs/$JOB_ID"
# Repeat the GET until state is complete and transcription_state is complete.
curl --fail-with-body "http://127.0.0.1:8000/api/jobs/$JOB_ID/download" --output narration.mp3
curl --fail-with-body "http://127.0.0.1:8000/api/jobs/$JOB_ID" --output narration-job.json
```

The final job JSON includes `words` and `segments` with `start`/`end` times in seconds, plus `timing_source: "whisperx"`. Check `state: "failed"` and `error` while polling. Audio becomes available at `state: "complete"`; transcription has its own state and `transcription_error`, so a timestamp failure does not remove the MP3. Jobs live in memory and are lost on server restart; generated files are pruned after 24 hours at startup.

For audio first, omit `auto_transcribe` (it defaults to `false`), then request alignment explicitly:

```bash
curl --fail-with-body "http://127.0.0.1:8000/api/jobs/$JOB_ID/transcript" \
  -H 'Content-Type: application/json' -d '{"timestamp_engine":"whisperx"}'
```

Kokoro remains available through `POST /api/jobs` with `{"engine":"kokoro","text":"Offline narration.","output_format":"mp3"}`. It is never selected automatically after a Fish error. Existing clients that relied on omitted `engine` meaning Kokoro must now send `"engine":"kokoro"` explicitly.

## Development

Run the API:

```bash
uv run --extra test uvicorn kokoro_app.app:app --app-dir backend --reload
```

Run the frontend in another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `127.0.0.1:8000`.

Run verification:

```bash
uv run --extra test pytest backend/tests -v -m "not smoke"
cd frontend
npm test -- --run
npm run typecheck
npm run build
npm run test:e2e
```

Run one real model smoke test:

```bash
KOKORO_SMOKE=1 uv run --extra test pytest backend/tests/test_inference_smoke.py -v -s
```

## Troubleshooting

- **Fish Audio asks for an API key:** set `OPENROUTER_API_KEY` before starting the server, or enter the key in Fish mode. Kokoro mode never needs it.
- **Fish Audio is rate-limited or unavailable:** the app intentionally does not switch to a paid model. Wait and retry later, or switch back to Kokoro Local.
- **Timestamping fails:** the audio remains playable and downloadable. Make sure the first transcription has internet access so Whisper and WhisperX can download their local models, and confirm there is enough free disk space. For unsupported alignment languages or download problems, choose **Whisper — faster-whisper** under **Timestamp engine** and click **Retry transcription**. After updating the app, run `uv sync` (or restart with `./run.sh`) to install its dependencies.
- **Port 8000 is already in use:** `run.sh` now detects an existing Kokoro instance and prints its address instead of starting a duplicate. Stop it with `./run.sh --stop`, or use `KOKORO_PORT=8080 ./run.sh` to start another instance. To inspect the listener manually, install the required tools with `sudo apt-get install -y curl iproute2 lsof procps util-linux`, then run `lsof -nP -iTCP:8000 -sTCP:LISTEN` (or `sudo ss -ltnp 'sport = :8000'`). Note the PID, inspect it with `ps -fp <PID>`, and stop it gracefully with `kill <PID>`. Only kill a process after confirming it belongs to you; avoid `kill -9` unless an ordinary stop fails.
- **Phonemizer fails to load:** Kokoro installs a bundled `espeak-ng` loader. If your Linux distribution cannot use it, install the system fallback with `sudo apt-get install -y espeak-ng`.
- **FFmpeg is missing or cannot encode a format:** run `sudo apt-get install -y ffmpeg` and verify `ffmpeg -version`.
- **The model does not load:** make sure the first run has internet access and enough free disk space, then restart. Hugging Face assets remain in the normal local cache.
- **A language sounds weak:** non-English voice training and grapheme-to-phoneme support vary. Try another voice for that language, shorter segments, or a slightly slower speed.
- **A phone cannot reach the service:** confirm both devices are on the same home network, use the `On your home network` URL printed by `run.sh`, keep the terminal process running, and allow the selected port through the Linux firewall if needed.

Kokoro model weights are Apache 2.0 licensed. See the upstream [Kokoro-82M model card](https://huggingface.co/hexgrad/Kokoro-82M) for model details and voice attribution.
