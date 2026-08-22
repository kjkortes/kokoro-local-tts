from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from collections.abc import Sequence

import numpy as np
import soundfile as sf

from kokoro_app.expressions import ResolvedExpression
from kokoro_app.schemas import OutputFormat


LOGGER = logging.getLogger(__name__)
SAMPLE_RATE = 24_000


class AudioProcessingError(RuntimeError):
    pass


def append_silence(
    parts: Sequence[np.ndarray], pauses_ms: Sequence[int], sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    if not parts:
        return np.array([], dtype=np.float32)
    joined: list[np.ndarray] = []
    for index, part in enumerate(parts):
        joined.append(np.asarray(part, dtype=np.float32).reshape(-1))
        if index < len(parts) - 1:
            pause_ms = pauses_ms[index] if index < len(pauses_ms) else 0
            joined.append(np.zeros(round(sample_rate * pause_ms / 1000), dtype=np.float32))
    return np.concatenate(joined)


def build_ffmpeg_filter(
    settings: ResolvedExpression, normalize: bool, sample_rate: int = SAMPLE_RATE
) -> str:
    pitch_factor = 2 ** (settings.pitch / 12)
    filters = [
        f"asetrate={sample_rate}*{pitch_factor:.8f}",
        f"aresample={sample_rate}",
        f"atempo={settings.tempo / pitch_factor:.8f}",
        f"volume={settings.volume:.4f}",
    ]
    if normalize:
        filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")
    return ",".join(filters)


def _codec_arguments(output_format: OutputFormat) -> list[str]:
    if output_format == OutputFormat.wav:
        return ["-c:a", "pcm_s16le"]
    if output_format == OutputFormat.mp3:
        return ["-c:a", "libmp3lame", "-q:a", "2"]
    if output_format == OutputFormat.flac:
        return ["-c:a", "flac"]
    return ["-c:a", "libvorbis", "-q:a", "5"]


def encode_audio(
    pcm: np.ndarray,
    destination: Path,
    output_format: OutputFormat,
    settings: ResolvedExpression,
    normalize: bool,
    sample_rate: int = SAMPLE_RATE,
) -> None:
    if pcm.size == 0:
        raise AudioProcessingError("Generated audio was empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_fd, source_name = tempfile.mkstemp(suffix=".wav", dir=destination.parent)
    output_fd, output_name = tempfile.mkstemp(suffix=f".{output_format.value}", dir=destination.parent)
    os.close(source_fd)
    os.close(output_fd)
    source_path = Path(source_name)
    output_path = Path(output_name)
    try:
        sf.write(source_path, np.asarray(pcm, dtype=np.float32), sample_rate, subtype="PCM_16")
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source_path),
            "-af", build_ffmpeg_filter(settings, normalize, sample_rate),
            "-ar", str(sample_rate),
            *_codec_arguments(output_format),
            str(output_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            LOGGER.error("FFmpeg failed: %s", completed.stderr.strip())
            raise AudioProcessingError("Audio encoding failed. Check that FFmpeg supports the selected format.")
        os.replace(output_path, destination)
    except FileNotFoundError as error:
        raise AudioProcessingError("FFmpeg is not installed or is not available on PATH.") from error
    finally:
        source_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
