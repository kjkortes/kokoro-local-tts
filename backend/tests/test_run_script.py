from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_SCRIPT = PROJECT_ROOT / "run.sh"


def _executable(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


class _StatusHandler(BaseHTTPRequestHandler):
    kokoro = True

    def do_GET(self) -> None:
        if self.path == "/api/status" and self.kokoro:
            body = b'{"state":"ready","device":"cpu","version":"0.1.0","detail":null}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, *args: object) -> None:
        pass


def _run_script(port: int, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(RUN_SCRIPT), *arguments],
        cwd=PROJECT_ROOT,
        env={**os.environ, "KOKORO_PORT": str(port)},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _wait_for_port(port: int) -> None:
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    raise AssertionError(f"port {port} never became available")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.mark.parametrize("lan", [False, True])
def test_launcher_defaults_to_localhost_and_allows_explicit_lan_access(tmp_path: Path, lan: bool) -> None:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    _executable(binaries, "npm", 'echo "npm $*"')
    _executable(binaries, "uv", 'echo "uv $*"')
    _executable(binaries, "ffmpeg", "exit 0")
    _executable(binaries, "hostname", 'echo "192.168.1.42 172.17.0.1"')
    environment = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "KOKORO_PORT": "8123",
    }
    environment.pop("KOKORO_HOST", None)
    if lan:
        environment["KOKORO_HOST"] = "0.0.0.0"

    completed = subprocess.run(
        ["bash", str(RUN_SCRIPT)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "On this computer  → http://127.0.0.1:8123" in completed.stdout
    if lan:
        assert "On your home network → http://192.168.1.42:8123" in completed.stdout
        assert "--host 0.0.0.0 --port 8123" in completed.stdout
        assert "no sign-in" in completed.stdout.lower()
    else:
        assert "On your home network" not in completed.stdout
        assert "--host 127.0.0.1 --port 8123" in completed.stdout


@pytest.mark.parametrize("exported", [False, True])
def test_launcher_loads_fish_config_from_env_file_and_prefers_environment(tmp_path: Path, exported: bool) -> None:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=loaded-test-key\nFISH_AUDIO_DEFAULT_VOICE=voice-from-file\n", encoding="utf-8")
    _executable(binaries, "npm", "exit 0")
    expected_key = "exported-test-key" if exported else "loaded-test-key"
    expected_voice = "exported-voice" if exported else "voice-from-file"
    _executable(
        binaries,
        "uv",
        f'[[ "${{OPENROUTER_API_KEY:-}}" == "{expected_key}" && "${{FISH_AUDIO_DEFAULT_VOICE:-}}" == "{expected_voice}" ]] && echo "OpenRouter key and voice loaded"',
    )
    _executable(binaries, "ffmpeg", "exit 0")
    _executable(binaries, "hostname", 'echo "127.0.0.1"')
    environment = {
        key: value for key, value in os.environ.items() if key not in {"OPENROUTER_API_KEY", "FISH_AUDIO_DEFAULT_VOICE"}
    }
    environment.update({
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "KOKORO_PORT": str(_free_port()),
        "KOKORO_ENV_FILE": str(env_file),
    })
    if exported:
        environment.update(OPENROUTER_API_KEY="exported-test-key", FISH_AUDIO_DEFAULT_VOICE="exported-voice")

    completed = subprocess.run(
        ["bash", str(RUN_SCRIPT)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "OpenRouter key and voice loaded" in completed.stdout


def test_run_reports_when_kokoro_is_already_running() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StatusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _run_script(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert result.returncode == 0
    assert "Kokoro Local TTS is already running" in result.stdout
    assert "./run.sh --stop" in result.stdout
    assert "address already in use" not in result.stderr


def test_run_explains_when_another_application_owns_the_port() -> None:
    class OtherHandler(_StatusHandler):
        kokoro = False

    server = ThreadingHTTPServer(("127.0.0.1", 0), OtherHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _run_script(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert result.returncode == 1
    assert "is already in use by another process" in result.stderr
    assert "KOKORO_PORT=8080 ./run.sh" in result.stderr
    assert "address already in use" not in result.stderr


def test_run_detects_a_listener_bound_to_another_local_address() -> None:
    class OtherHandler(_StatusHandler):
        kokoro = False

    server = ThreadingHTTPServer(("127.0.0.2", 0), OtherHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _run_script(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert result.returncode == 1
    assert "is already in use by another process" in result.stderr
    assert "address already in use" not in result.stderr


def test_run_detects_a_listener_even_when_lsof_cannot_see_it(tmp_path: Path) -> None:
    class OtherHandler(_StatusHandler):
        kokoro = False

    server = ThreadingHTTPServer(("127.0.0.1", 0), OtherHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    _executable(binaries, "lsof", "exit 0")
    _executable(binaries, "npm", 'echo "npm $*"')
    _executable(binaries, "uv", 'echo "uv $*"')
    _executable(binaries, "ffmpeg", "exit 0")
    _executable(binaries, "hostname", 'echo "127.0.0.1"')
    try:
        result = subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                "PATH": f"{binaries}:{os.environ['PATH']}",
                "KOKORO_PORT": str(server.server_port),
            },
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert result.returncode == 1
    assert "is already in use by another process" in result.stderr


def test_concurrent_launcher_is_rejected_during_build(tmp_path: Path) -> None:
    port = _free_port()
    build_started = tmp_path / "build-started"
    binaries = tmp_path / "bin"
    binaries.mkdir()
    _executable(binaries, "npm", 'touch "$KOKORO_TEST_BUILD_STARTED"; sleep 2')
    _executable(binaries, "uv", 'echo "uv $*"')
    _executable(binaries, "ffmpeg", "exit 0")
    _executable(binaries, "hostname", 'echo "127.0.0.1"')
    environment = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "KOKORO_PORT": str(port),
        "KOKORO_TEST_BUILD_STARTED": str(build_started),
    }
    first = subprocess.Popen(
        ["bash", str(RUN_SCRIPT)],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 5
        while not build_started.exists() and time.time() < deadline:
            time.sleep(0.02)
        assert build_started.exists(), "first launcher never entered the build"
        second = subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        first.wait(timeout=10)
    finally:
        if first.poll() is None:
            first.terminate()
            first.wait(timeout=5)

    assert second.returncode == 1
    assert f"Another Kokoro launcher is already starting on port {port}" in second.stderr


def test_stop_terminates_only_a_kokoro_listener() -> None:
    port = _free_port()

    server_code = """
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"state":"ready","device":"cpu","version":"0.1.0","detail":null}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", server_code, str(port), "uvicorn", "kokoro_app.app:app"],
        start_new_session=True,
    )
    try:
        _wait_for_port(port)
        result = _run_script(port, "--stop")
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)

    assert result.returncode == 0
    assert f"Stopped Kokoro Local TTS on port {port}" in result.stdout


def test_stop_waits_for_the_kokoro_process_to_exit() -> None:
    port = _free_port()
    server_code = """
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import signal
import sys
import time

server = ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), BaseHTTPRequestHandler)

def stop_slowly(*_args):
    server.server_close()
    time.sleep(1)
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop_slowly)
server.serve_forever()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", server_code, str(port), "uvicorn", "kokoro_app.app:app"],
        start_new_session=True,
    )
    try:
        _wait_for_port(port)
        result = _run_script(port, "--stop")
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)

    assert result.returncode == 0
    assert f"Stopped Kokoro Local TTS on port {port}" in result.stdout


def test_stop_refuses_to_terminate_an_unrelated_listener() -> None:
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        _wait_for_port(port)
        result = _run_script(port, "--stop")
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=5)

    assert result.returncode == 1
    assert "Refusing to stop" in result.stderr
