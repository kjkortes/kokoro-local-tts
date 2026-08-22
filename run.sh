#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
port="${KOKORO_PORT:-8000}"

for dependency in uv npm ffmpeg; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    if [[ "$dependency" == "ffmpeg" ]]; then
      echo "Missing FFmpeg. Install it with:"
      echo "  sudo apt-get update && sudo apt-get install -y ffmpeg"
    else
      echo "Missing $dependency. Install it, then run ./run.sh again."
    fi
    exit 1
  fi
done

cd "$project_dir/frontend"
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run build

cd "$project_dir"
echo "Kokoro Local TTS → http://127.0.0.1:$port"
exec uv run uvicorn kokoro_app.app:app --app-dir backend --host 127.0.0.1 --port "$port"
