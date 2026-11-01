#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
port="${KOKORO_PORT:-8000}"
host="${KOKORO_HOST:-127.0.0.1}"

load_fish_config() {
  local env_file="${KOKORO_ENV_FILE:-$project_dir/.env}"
  local line name value first_character last_character
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?(OPENROUTER_API_KEY|FISH_AUDIO_DEFAULT_VOICE)[[:space:]]*=(.*)$ ]]; then
      name="${BASH_REMATCH[2]}"
      value="${BASH_REMATCH[3]}"
      if [[ -n "${!name:-}" ]]; then
        continue
      fi
      value="${value#"${value%%[![:space:]]*}"}"
      value="${value%"${value##*[![:space:]]}"}"
      first_character="${value:0:1}"
      last_character="${value: -1}"
      if [[ ${#value} -ge 2 && (
        ("$first_character" == '"' && "$last_character" == '"')
        || ("$first_character" == "'" && "$last_character" == "'")
      ) ]]; then
        value="${value:1:${#value}-2}"
      fi
      export "$name=$value"
    fi
  done < "$env_file"
}

load_fish_config

require_commands() {
  local dependency
  for dependency in "$@"; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
      echo "Missing $dependency. Install the launcher tools with:" >&2
      echo "  sudo apt-get update && sudo apt-get install -y curl iproute2 lsof procps util-linux" >&2
      return 1
    fi
  done
}

listener_pids() {
  lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
}

port_is_open() {
  [[ -n "$(ss -H -ltn "sport = :$port" 2>/dev/null)" ]]
}

kokoro_is_running() {
  local response
  response="$(curl --fail --silent --max-time 1 "http://127.0.0.1:$port/api/status" 2>/dev/null)" || return 1
  [[ "$response" == *'"state":'* && "$response" == *'"version":'* ]]
}

stop_kokoro() {
  local listener_pids listener_pid command_line
  listener_pids="$(listener_pids)"
  if [[ -z "$listener_pids" ]]; then
    if port_is_open; then
      echo "A process is listening on port $port, but lsof cannot identify it." >&2
      echo "Inspect it with: sudo lsof -nP -iTCP:$port -sTCP:LISTEN" >&2
      return 1
    fi
    echo "No process is listening on port $port."
    return 0
  fi

  for listener_pid in $listener_pids; do
    command_line="$(ps -p "$listener_pid" -o args= 2>/dev/null || true)"
    if [[ "$command_line" != *"uvicorn kokoro_app.app:app"* ]]; then
      echo "Refusing to stop PID $listener_pid because it is not Kokoro Local TTS." >&2
      echo "Process: $command_line" >&2
      return 1
    fi
  done

  for listener_pid in $listener_pids; do
    kill -TERM "$listener_pid"
  done
  for _ in $(seq 1 50); do
    local processes_stopped=true process_state
    for listener_pid in $listener_pids; do
      process_state="$(ps -p "$listener_pid" -o stat= 2>/dev/null || true)"
      if [[ -n "$process_state" && "$process_state" != Z* ]]; then
        processes_stopped=false
        break
      fi
    done
    if ! port_is_open && [[ "$processes_stopped" == true ]]; then
      echo "Stopped Kokoro Local TTS on port $port."
      return 0
    fi
    sleep 0.1
  done

  echo "Kokoro did not stop within 5 seconds. Find the listener with:" >&2
  echo "  lsof -nP -iTCP:$port -sTCP:LISTEN" >&2
  return 1
}

require_available_port() {
  if ! port_is_open; then
    return 0
  fi
  if kokoro_is_running; then
    echo
    echo "Kokoro Local TTS is already running."
    echo "Open → http://127.0.0.1:$port"
    echo "Stop → KOKORO_PORT=$port ./run.sh --stop"
    echo
    exit 0
  fi
  echo "Port $port is already in use by another process." >&2
  echo "Find it with: lsof -nP -iTCP:$port -sTCP:LISTEN" >&2
  echo "Or use another port: KOKORO_PORT=8080 ./run.sh" >&2
  exit 1
}

if [[ $# -gt 1 || ($# -eq 1 && "$1" != "--stop") ]]; then
  echo "Usage: ./run.sh [--stop]" >&2
  exit 2
fi

if [[ ${1:-} == "--stop" ]]; then
  require_commands lsof ps ss
  stop_kokoro
  exit $?
fi

require_commands curl lsof flock ss
require_available_port

lock_dir="${XDG_RUNTIME_DIR:-/tmp}"
lock_path="$lock_dir/kokoro-local-tts-$port.lock"
exec 9>"$lock_path"
if ! flock -n 9; then
  echo "Another Kokoro launcher is already starting on port $port." >&2
  echo "Wait for it to finish, or use another port: KOKORO_PORT=8080 ./run.sh" >&2
  exit 1
fi

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
# Recheck immediately before startup in case a non-Kokoro process claimed the
# port while the frontend was building.
require_available_port

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
if [[ "$host" != "127.0.0.1" && "$host" != "localhost" ]]; then
  if [[ -n "$lan_ip" ]]; then
    echo "On your home network → http://$lan_ip:$port"
  else
    echo "Home network address unavailable. Run 'hostname -I' after connecting to Wi-Fi or Ethernet."
  fi
  echo "LAN access has no sign-in. Only run this on a network you trust."
fi
echo
exec uv run uvicorn kokoro_app.app:app --app-dir backend --host "$host" --port "$port"
