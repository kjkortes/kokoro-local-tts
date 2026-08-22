#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
port="${KOKORO_PORT:-8000}"

for dependency in uv npm ffmpeg espeak-ng; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    if [[ "$dependency" == "espeak-ng" || "$dependency" == "ffmpeg" ]]; then
      echo "Missing $dependency. Install audio prerequisites with:"
      echo "  sudo apt-get update && sudo apt-get install -y espeak-ng ffmpeg"
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

