from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from kokoro_app.audio import append_silence, build_ffmpeg_filter, encode_audio
from kokoro_app.expressions import ResolvedExpression
from kokoro_app.schemas import OutputFormat


def settings(**changes: float) -> ResolvedExpression:
    values = dict(speed=1.0, pitch=0.0, tempo=1.0, pause_scale=1.0, volume=1.0, is_custom=False)
    values.update(changes)
    return ResolvedExpression(**values)


def test_append_silence_uses_24khz_duration() -> None:
    joined = append_silence([np.ones(2400), np.ones(2400)], [250], 24000)
    assert len(joined) == 2400 + 6000 + 2400
    assert np.all(joined[2400:8400] == 0)


def test_filter_chain_contains_pitch_tempo_volume_and_normalization() -> None:
    value = build_ffmpeg_filter(settings(pitch=2, tempo=0.9, volume=0.8), normalize=True)
    assert "asetrate=24000*" in value
    assert "atempo=" in value
    assert "volume=0.8000" in value
    assert "loudnorm=" in value


@pytest.mark.parametrize("output_format", list(OutputFormat))
def test_encode_audio_creates_readable_file(tmp_path: Path, output_format: OutputFormat) -> None:
    time = np.arange(0, 0.1, 1 / 24000)
    pcm = (np.sin(2 * np.pi * 220 * time) * 0.1).astype(np.float32)
    destination = tmp_path / f"tone.{output_format.value}"
    encode_audio(pcm, destination, output_format, settings(), normalize=False)
    assert destination.stat().st_size > 0
    audio, sample_rate = sf.read(destination)
    assert sample_rate == 24000
    assert len(audio) > 0
