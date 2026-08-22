#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
port="${KOKORO_PORT:-8000}"
host="${KOKORO_HOST:-0.0.0.0}"

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
all_ips="$(hostname -I 2>/dev/null || true)"
lan_ip="$(printf '%s\n' "$all_ips" | tr ' ' '\n' | awk '
  /^10\./ || /^192\.168\./ || /^172\.(1[6-9]|2[0-9]|3[01])\./ { print; exit }
')"
if [[ -z "$lan_ip" ]]; then
  lan_ip="$(printf '%s\n' "$all_ips" | tr ' ' '\n' | awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ && $0 !~ /^127\./ { print; exit }')"
fi

echo
echo "Kokoro Local TTS"
echo "On this computer  → http://127.0.0.1:$port"
if [[ -n "$lan_ip" ]]; then
  echo "On your home network → http://$lan_ip:$port"
else
  echo "Home network address unavailable. Run 'hostname -I' after connecting to Wi-Fi or Ethernet."
fi
echo "LAN access has no sign-in. Only run this on a network you trust."
echo
exec uv run uvicorn kokoro_app.app:app --app-dir backend --host "$host" --port "$port"
