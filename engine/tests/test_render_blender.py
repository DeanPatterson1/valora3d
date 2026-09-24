import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from engine.compiler.run import compile_scene
from engine.profile import SubjectProfile
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]
FIX = Path(__file__).parent / "fixtures"
MODELS = Path(__file__).resolve().parents[2] / "assets-in" / "models"


def _run(tmp, grade=None, limit=3):
    prof = SubjectProfile.from_dict(json.loads((FIX / "profiles" / "toycar.json").read_text(encoding="utf-8")))
    s = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))
    if grade:
        s["grade"] = {"id": "mood_grade", "params": {"preset": grade}}
    return compile_scene(s, prof, MODELS / "toycar" / "toycar.glb", tmp, tier="keyframes", key_limit=limit)


def test_three_key_frames_render_with_passes_and_a_log(tmp_path):
    _run(tmp_path)
    log = json.loads((tmp_path / "render_log.json").read_text())
    assert len(log["frames"]) == 3 and log["resolution"] == [144, 256] and log["samples"] == 4
    for f in (e["frame"] for e in log["frames"]):
        rgb = np.asarray(Image.open(tmp_path / "beauty" / f"{f:04d}.png").convert("RGB"), dtype=np.float32) / 255
        assert rgb.mean() > 0.02  # B-01: not black
        mask = np.asarray(Image.open(next((tmp_path / "passes").glob(f"mask*{f:04d}*.png"))))
        assert (mask > 127).any()  # subject visible in every key frame
        assert next((tmp_path / "passes").glob(f"gloss*{f:04d}*.png"), None) is not None
        assert next((tmp_path / "passes").glob(f"mist*{f:04d}*.png"), None) is not None


def test_mood_presets_change_the_picture(tmp_path):
    _run(tmp_path / "a", "clean", limit=1)
    _run(tmp_path / "b", "teal_night", limit=1)
    fa = next((tmp_path / "a" / "beauty").glob("*.png"))
    fb = next((tmp_path / "b" / "beauty").glob("*.png"))
    da = np.asarray(Image.open(fa), dtype=np.float32)
    db = np.asarray(Image.open(fb), dtype=np.float32)
    assert np.abs(da - db).mean() > 2.0  # 8-bit levels
