import os

import numpy as np
import pytest

from kokoro_app.engine import KokoroEngine


@pytest.mark.smoke
@pytest.mark.skipif(os.environ.get("KOKORO_SMOKE") != "1", reason="Set KOKORO_SMOKE=1 for real inference")
def test_real_kokoro_produces_finite_audio() -> None:
    audio = KokoroEngine().synthesize(
        "Kokoro is running locally.", "a", "af_heart", None, 0.0, 1.0
    )
    assert audio.size > 2400
    assert np.isfinite(audio).all()
