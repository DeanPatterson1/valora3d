"""Block recipe step 4: compile each phase-5 block's fixture headless (no render) and assert its probe
conditions from compile.json."""
import copy
import json
import math
from pathlib import Path

import pytest

from engine.compiler.run import compile_scene
from engine.tests.conftest import requires_blender
from engine.tests.test_director_package import _p

pytestmark = [pytest.mark.blender, requires_blender]
FIX = Path(__file__).parent / "fixtures"
MODELS = Path(__file__).resolve().parents[2] / "assets-in" / "models"
T3 = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))


def _glb(model):
    glb = MODELS / model / f"{model}.glb"
    if not glb.exists():
        pytest.skip(f"{model} not present")
    return glb


def fog_script(mode="fog", wind=None):
    s = copy.deepcopy(T3)
    s["effects"] = [{"id": "ground_fog", "params": {"heightM": 0.4, "mode": mode}}]
    if wind:
        s["wind"] = {"id": "wind", "params": {"speedMs": wind}}
    return s


def test_ground_fog_is_one_tagged_volume_with_a_clear_pocket(tmp_path):     # Task 60
    from engine.physics import fog as F
    p = _p("sports_car")
    res = compile_scene(fog_script(wind=3.0), p, _glb("sports_car"), tmp_path, render=False)
    vols = [o for o in res["objects"] if o["volume"]]
    tagged = [o for o in vols if o["block"] == "effect/ground_fog"]
    assert len(tagged) == 1 and tagged[0]["name"] == "valora_fog", vols
    fog = res["fog"]
    assert fog["pocketRadiusM"] == pytest.approx(F.POCKET * p.radius)
    assert fog["heightM"] == pytest.approx(0.4) and fog["sigma0"] == pytest.approx(0.4 * F.FOG_SIGMA)
    # the pocket holds the subject centre: its distance from the fog centre is 0 < pocket radius
    assert math.dist(fog["centre"], p.center) == pytest.approx(0.0, abs=1e-6)
    far = max(math.dist(c, p.center) for c in res["cameraPositions"])
    width = fog["domainMax"][0] - fog["domainMin"][0]
    assert width == pytest.approx(F.domain_width(p.longest, far)) and fog["domainMin"][2] == 0.0
    assert fog["drift"] is True and "effect:ground_fog" in res["built"]


def test_mist_is_taller_and_thinner(tmp_path):
    p = _p("sports_car")
    res = compile_scene(fog_script("mist"), p, _glb("sports_car"), tmp_path, render=False)
    assert res["fog"]["heightM"] == pytest.approx(1.2) and res["fog"]["density"] == pytest.approx(0.16)
    assert res["fog"]["drift"] is False                      # no wind field: no wisps
