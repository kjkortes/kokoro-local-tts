from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _executable(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def test_launcher_exposes_lan_by_default_and_prints_phone_url(tmp_path: Path) -> None:
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

    completed = subprocess.run(
        ["bash", str(PROJECT_ROOT / "run.sh")],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "On this computer  → http://127.0.0.1:8123" in completed.stdout
    assert "On your home network → http://192.168.1.42:8123" in completed.stdout
    assert "--host 0.0.0.0 --port 8123" in completed.stdout
    assert "no sign-in" in completed.stdout.lower()
