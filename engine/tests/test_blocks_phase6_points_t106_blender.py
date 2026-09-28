"""Phase 6 lane P, Task 106 (recipe step 4): tyre_spray on the wet courtyard and dust_kick on the field, baked
(stage 4b, gn_disk, the drive's pose on absolute render frames) and compiled without rendering on the sports car.
Asserts the particles follow the moving tyres (every grain within reach of a posed tyre contact at the frame it
is read, or behind it on its flight), velocity present, finite, no point under the ground, the cache under
cacheMBMax, and the compile never simulates. Temp BakeStore, machine lock. Serial."""
import json
from pathlib import Path

import pytest

from engine.bake import run as bake_run
from engine.catalog import Catalog
from engine.compiler.run import compile_scene
from engine.tests.conftest import requires_blender
from engine.tests.test_blocks_phase6_points_t106 import _drive_script
from engine.tests.test_director_package import _p

pytestmark = [pytest.mark.blender, requires_blender]

ROOT = Path(__file__).resolve().parents[2]
CAR = ROOT / "assets-in" / "models" / "sports_car" / "sports_car.glb"


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p6t106")
    mp = pytest.MonkeyPatch()
    mp.setenv("VALORA_BAKE_ROOT", str(tmp / "bake"))
    yield {"tmp": tmp, "cat": Catalog.load()}
    mp.undo()


@pytest.mark.parametrize("sid,world,effects", [
    ("tyre_spray", "rain_courtyard", [{"id": "wet_surface", "params": {"wetness": 1.0}}]),
    ("dust_kick", "golden_field", [])])
def test_bake_compile_and_probe(env, sid, world, effects):
    s = _drive_script(world, 45.0, sims=[{"id": sid, "params": {}, "startS": 0.0, "endS": 3.0}])
    s["format"]["durationS"] = 3
    s["shots"][0]["endS"] = 3
    s["subject"]["motion"]["params"].update(driveS=3.0, facing="reverse")
    s["effects"] = effects
    if not CAR.exists():
        pytest.skip("sports_car.glb is local-only")
    bakes = bake_run.bake_sims(s, _p("sports_car"), CAR, catalog=env["cat"], lock_timeout_s=3600)
    b = bakes[sid]
    assert b["frames"]["mode"] == "absolute" and b["bytes"] / 1e6 <= env["cat"].get("sim", sid)["bake"]["cacheMBMax"]
    res = compile_scene(s, _p("sports_car"), CAR, env["tmp"] / sid, catalog=env["cat"], render=False, frames=[40],
                        realism_probe=[20, 40, 60], bakes=bakes)
    pr = res["simProbe"][sid]
    assert pr["velocityPresent"] is True and pr["stable"]["finite"] is True, pr
    assert pr["inside"]["points"] > 0, pr
    assert f"sim:{sid}" in res["built"]
    (env["tmp"] / f"{sid}.json").write_text(json.dumps({"bake": b, "probe": pr}), encoding="utf-8")
