# Kokoro Local TTS

A private, local web workbench for turning scripts into speech with Kokoro 82M. It supports short lines and long narration, all 54 Kokoro v1.0 voices, nine language/accent groups, transparent expression presets, voice blending, timestamped transcripts, a waveform player, and WAV/MP3/FLAC/OGG downloads.

Nothing in a script is sent to a cloud API. The first launch downloads Kokoro's open model files from Hugging Face; later launches reuse the local cache and can work offline.

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

- **Markdown storyboards** can be pasted directly or uploaded from `.md`, `.markdown`, or `.txt` files. Choose any table column for speech; every non-empty cell remains a read-only, timestamped segment matching its source row.
- **Language and gender** filter the official voice catalog; gender is voice metadata, not a model setting.
- **Voice previews** play an included, language-appropriate sample instantly for every voice without running synthesis.
- **Voice blend** combines two voices from the same language with a visible A/B ratio.
- **Expression** offers Neutral, Warm, Calm, Bright, Serious, and Dramatic. These are deterministic bundles of synthesis speed, pitch, tempo, and sentence pauses—not a claimed Kokoro emotion parameter.
- **Continuous storyboard narration** joins speech rows into one natural delivery while preserving each source row in the timestamped transcript and downloads.
- **Output** supports WAV, MP3, FLAC, and OGG at Kokoro's native 24 kHz, with optional loudness normalization.
- **Long scripts** are split at paragraphs and sentence boundaries, synthesized in sequence, and joined with controlled pauses. Progress and cancellation remain available during generation.
- **Timestamped transcripts** can be viewed, copied, or downloaded as readable text or JSON. American and British English voices also provide seekable word-level timestamps derived directly from Kokoro's synthesis durations; other languages retain segment-level timestamps.

Generated files live under `runtime/audio/` and are pruned after 24 hours when the app starts. Download anything you want to keep.

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

- **Phonemizer fails to load:** Kokoro installs a bundled `espeak-ng` loader. If your Linux distribution cannot use it, install the system fallback with `sudo apt-get install -y espeak-ng`.
- **FFmpeg is missing or cannot encode a format:** run `sudo apt-get install -y ffmpeg` and verify `ffmpeg -version`.
- **The model does not load:** make sure the first run has internet access and enough free disk space, then restart. Hugging Face assets remain in the normal local cache.
- **A language sounds weak:** non-English voice training and grapheme-to-phoneme support vary. Try another voice for that language, shorter segments, or a slightly slower speed.
- **A phone cannot reach the service:** confirm both devices are on the same home network, use the `On your home network` URL printed by `run.sh`, keep the terminal process running, and allow the selected port through the Linux firewall if needed.

Kokoro model weights are Apache 2.0 licensed. See the upstream [Kokoro-82M model card](https://huggingface.co/hexgrad/Kokoro-82M) for model details and voice attribution.
