# Kokoro Local TTS

A web workbench for turning scripts into speech. Fish Audio S2.1 Pro Free is the default engine through OpenRouter, using voice reference `b0204e37cbc94a16954c78697b844af2`. Kokoro 82M remains available as a private, offline engine with all 54 Kokoro v1.0 voices, nine language/accent groups, expression presets, voice blending, timestamped transcripts, a waveform player, and WAV/MP3/FLAC/OGG downloads.

In Kokoro mode, no script text is sent to a cloud API. The first launch downloads Kokoro's open model files from Hugging Face; later launches reuse the local cache and can work offline. Fish Audio mode sends the submitted script and optional voice reference ID to OpenRouter for synthesis; the interface marks this mode clearly.

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

The launcher prints two addresses:

```text
On this computer       → http://127.0.0.1:8000
On your home network   → http://192.168.x.x:8000
```

Open the home-network address from a phone, tablet, or another computer connected to the same Wi-Fi or Ethernet network. The app listens on all network interfaces by default.

There is no sign-in screen. Anyone who can reach the app can submit scripts, use this machine's CPU, and access generated audio. Only run it on a home network you trust; do not expose port 8000 through your router to the public internet.

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

To restore localhost-only access for a session:

```bash
KOKORO_HOST=127.0.0.1 ./run.sh
```

If Ubuntu's firewall blocks another device, allow the selected port on the local network:

```bash
sudo ufw allow 8000/tcp
```

The first start can take several minutes while Kokoro downloads and loads. The header reports `Loading model`, `Model ready`, or an actionable setup error.

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
- **Timestamped transcripts** can be viewed, copied, or downloaded as readable text or JSON. American and British English Kokoro voices provide seekable word-level timestamps derived directly from Kokoro's synthesis durations. Fish Audio results use local **WhisperX** word alignment by default; **Whisper (faster-whisper)** remains selectable under **Timestamp engine**.

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

   The launcher reads `OPENROUTER_API_KEY` from `.env` without treating the file as a shell script. An already exported environment value takes precedence.

   If no environment key is configured, you can paste a key into the password-style field in Fish mode. That key is kept only in the current browser session. `OPENROUTER_API_KEY` takes precedence and disables the browser field; environment configuration is preferred, especially when accessing the app over a local network.

3. **Fish Audio S2.1 Pro Free — OpenRouter** is selected by default under **TTS Engine**.
4. Under **Voice / Accent**, choose a saved **Fish voice**. The library starts with reference `b0204e37cbc94a16954c78697b844af2`, named **Original Fish voice**. Use **Add voice** to enter **Name**, **Description** (optional), and **Reference ID**. You can paste a Fish Audio voice URL such as `https://fish.audio/app/m/689b47ca83dd48dba90b160affb8a118/` into **Reference ID**; the app extracts `689b47ca83dd48dba90b160affb8a118` automatically. Saving from the studio selects that voice for generation. Select an existing voice to **Edit voice** or **Delete voice**. Choose **Custom reference ID…** for a one-time ID, or **Provider default** to omit the reference. Voice identity is the preferred way to choose an accent.
5. Choose a **Delivery Style**. The app prepends the corresponding Fish bracket instruction, while preserving any bracketed instructions already in the script. **Custom** accepts your own instruction.
6. Generate, play, and download the returned MP3 through the existing audio controls. The timestamp panel also lets you switch between segment and word timing, select **JSON**, and download the timescript.

The free model is intended for testing and lower-volume use and is subject to OpenRouter's free-model rate limits and availability. Fish mode uses one request for the complete narration rather than one request per sentence. Kokoro does not require this key and remains fully functional offline.

Open **Voices** or **Manage all voices** to browse the paginated library, read descriptions, edit or delete any voice, or choose **Use voice** to return to the studio with that voice selected. Your current script stays in place while you manage voices.

Use **Copy ID** beside a voice reference to copy just its reference ID. **Open in Fish Audio** opens that voice's Fish Audio page in a new tab so you can listen to its samples. These actions are available in both the management list and the studio's selected voice controls. If the browser blocks automatic copying, the app provides a selected ID field for manual copying.

The voice library is stored in `runtime/fish_voices.sqlite3`, separate from expiring audio files. Back up this file to keep your saved names, descriptions, and references. Existing libraries are upgraded automatically; older voices start with an empty description. The list loads when Fish controls open; use **Reload voices** to pick up changes made on another device. Deleting a library entry only removes the local shortcut, not the voice on Fish Audio. API keys are never stored in the library.

Under **Timestamps → Timestamp engine**, choose **WhisperX — word alignment (default)** or **Whisper — faster-whisper**. The API also defaults to `timestamp_engine: "whisperx"`; submit `"whisper"` to use the original word timestamps.

After OpenRouter returns the MP3, the app runs the multilingual `small` [faster-whisper](https://github.com/SYSTRAN/faster-whisper) model locally with CPU int8 inference. With **WhisperX**, the detected speech language selects a local alignment model, and [WhisperX](https://github.com/m-bain/whisperX) aligns the recognized words to the audio. The first run downloads the recognition and alignment models; later runs reuse their local caches. The recognition model is shared between the two timestamp modes. Audio is not sent to another transcription service. Because text comes from speech recognition, recognized text can occasionally differ slightly from the submitted script. The panel identifies the actual mode as **Timed locally with WhisperX** or **Timed locally with Whisper**.

WhisperX adds CPU processing and a language-specific model download. If alignment is unavailable for the detected language, or its model cannot be downloaded, the app reports the problem; choose **Whisper — faster-whisper** and retry. It does not silently change timestamp engines. Kokoro continues using its own synthesis timing.

To trade more processing time and memory for a larger Whisper model, set `KOKORO_WHISPER_MODEL` in the shell before launch, for example:

```bash
KOKORO_WHISPER_MODEL=medium ./run.sh
```

An empty configuration template is included at `.env.example`. The real `.env` file is ignored by Git.

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
- **Fish Audio finishes but timestamping fails:** make sure the first Fish run has internet access so Whisper and WhisperX can download their local models, and confirm there is enough free disk space. For unsupported alignment languages or download problems, choose **Whisper — faster-whisper** under **Timestamp engine** and retry. After updating the app, run `uv sync` (or restart with `./run.sh`) to install its dependencies.
- **Port 8000 is already in use:** `run.sh` now detects an existing Kokoro instance and prints its address instead of starting a duplicate. Stop it with `./run.sh --stop`, or use `KOKORO_PORT=8080 ./run.sh` to start another instance. To inspect the listener manually, install the required tools with `sudo apt-get install -y curl iproute2 lsof procps util-linux`, then run `lsof -nP -iTCP:8000 -sTCP:LISTEN` (or `sudo ss -ltnp 'sport = :8000'`). Note the PID, inspect it with `ps -fp <PID>`, and stop it gracefully with `kill <PID>`. Only kill a process after confirming it belongs to you; avoid `kill -9` unless an ordinary stop fails.
- **Phonemizer fails to load:** Kokoro installs a bundled `espeak-ng` loader. If your Linux distribution cannot use it, install the system fallback with `sudo apt-get install -y espeak-ng`.
- **FFmpeg is missing or cannot encode a format:** run `sudo apt-get install -y ffmpeg` and verify `ffmpeg -version`.
- **The model does not load:** make sure the first run has internet access and enough free disk space, then restart. Hugging Face assets remain in the normal local cache.
- **A language sounds weak:** non-English voice training and grapheme-to-phoneme support vary. Try another voice for that language, shorter segments, or a slightly slower speed.
- **A phone cannot reach the service:** confirm both devices are on the same home network, use the `On your home network` URL printed by `run.sh`, keep the terminal process running, and allow the selected port through the Linux firewall if needed.

Kokoro model weights are Apache 2.0 licensed. See the upstream [Kokoro-82M model card](https://huggingface.co/hexgrad/Kokoro-82M) for model details and voice attribution.
