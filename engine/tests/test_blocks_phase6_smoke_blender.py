"""Phase 6 lane S (Tasks 112, 113, recipe step 4): the smoke / fire blocks compiled without rendering on real
subjects. The effects and tyre_smoke read the pinned VDB library when it is on disk (else their procedural
fallback, which is also compiled here with VALORA_ASSET_LIBRARY pointed at an empty folder); smoke_sim bakes a
Mantaflow gas (stage 4b, gas_vdb) around a MOVING sneaker (slide_in) and the compile only reads the VDBs:
the bake's per-frame probe measured smoke inside the shell at each frame's pose (the moving shell), density
finite and growing smoothly, velocity grid present, cache under cacheMBMax. Serial; takes the machine lock."""
import json
from pathlib import Path

import pytest

from engine.bake import run as bake_run
from engine.catalog import Catalog
from engine.compiler.run import compile_scene
from engine.tests.conftest import requires_blender
from engine.tests.test_director_package import _p

pytestmark = [pytest.mark.blender, requires_blender]

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"


def model(name):
    return ROOT / "assets-in" / "models" / name / f"{name}.glb"


def _script(sims=(), effects=(), motion="static", markers=None, dur=4.0, world=None):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["format"] = {"aspect": "16:9", "durationS": dur, "fps": 30}
    s["shots"] = [{"startS": 0, "endS": dur, "camera": {"id": "low_hero_push", "params": {}}, "focus": "subject"}]
    s["subject"]["motion"] = {"id": motion, "params": {}}
    s["sims"], s["effects"] = list(sims), list(effects)
    if markers:
        s["markers"] = markers
    if world:
        s["world"] = world
    return s


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p6smoke")
    mp = pytest.MonkeyPatch()
    mp.setenv("VALORA_BAKE_ROOT", str(tmp / "bake"))
    yield {"tmp": tmp, "cat": Catalog.load()}
    mp.undo()


def _objects(res, block):
    return [o for o in res["objects"] if o["block"] == block]


def steam_mark():
    """A vent marker on camera_01's highest surface sample (markers must sit on the subject)."""
    top = max(_p("camera_01").surfaceSamples, key=lambda q: q[2])
    return [{"id": "vent", "text": "steam from the vent", "anchor": {"space": "placed", "point": list(top),
             "normal": [0, 0, 1]}}]


@pytest.mark.parametrize("fallback", [False, True])
def test_the_effects_compile_from_the_library_or_their_fallback(env, fallback, monkeypatch):
    if fallback:
        monkeypatch.setenv("VALORA_ASSET_LIBRARY", str(env["tmp"] / "empty_library"))
    s = _script(effects=[{"id": "smoke_plume", "params": {"placement": "around", "count": 2}},
                         {"id": "fire", "params": {}}])
    res = compile_scene(s, _p("sports_car"), model("sports_car"), env["tmp"] / f"fx_car_{fallback}",
                        catalog=env["cat"], render=False, frames=[60])
    assert {"effect:smoke_plume", "effect:fire"} <= set(res["built"]), res["built"]
    assert len(_objects(res, "effect/smoke_plume")) == 2 and _objects(res, "effect/fire")
    assert _objects(res, "effect/fire:light")
    s = _script(effects=[{"id": "steam", "params": {}}], markers=steam_mark())
    res = compile_scene(s, _p("camera_01"), model("camera_01"), env["tmp"] / f"fx_steam_{fallback}",
                        catalog=env["cat"], render=False, frames=[30])
    assert "effect:steam" in res["built"] and _objects(res, "effect/steam")


def test_tyre_smoke_compiles_at_the_rear_axle(env):
    s = _script([{"id": "tyre_smoke", "params": {}, "startS": 0.5, "endS": 4.0}])
    res = compile_scene(s, _p("sports_car"), model("sports_car"), env["tmp"] / "tyre_smoke", catalog=env["cat"],
                        render=False, frames=[60])
    assert "sim:tyre_smoke" in res["built"] and _objects(res, "sim/tyre_smoke")
    assert not res.get("bakes")


def test_smoke_sim_bakes_around_a_moving_subject_and_the_compile_only_reads(env):
    s = _script([{"id": "smoke_sim", "params": {"res": 64}, "startS": 0.0, "endS": 3.0}], motion="slide_in",
                dur=3.0)
    bakes = bake_run.bake_sims(s, _p("sneaker"), model("sneaker"), catalog=env["cat"], lock_timeout_s=3600)
    b = bakes["smoke_sim"]
    assert b["method"] == "gas_vdb" and b["frames"]["mode"] == "shift" and b["frames"]["preroll"] == 60
    res = compile_scene(s, _p("sneaker"), model("sneaker"), env["tmp"] / "smoke_sim", catalog=env["cat"],
                        render=False, frames=[80], realism_probe=[30, 60, 80], bakes=bakes)
    assert "sim:smoke_sim" in res["built"] and _objects(res, "sim/smoke_sim")
    pr = res["simProbe"]["smoke_sim"]
    assert pr["velocityPresent"] is True
    assert pr["stable"]["finite"] is True and pr["stable"]["ok"] is True, pr
    assert pr["inside"]["movingShell"] is True and pr["inside"]["points"] > 0, pr
    assert pr["inside"]["ok"] is True, pr                              # report-only: recorded, and holds here
    assert b["bytes"] / 1e6 <= env["cat"].get("sim", "smoke_sim")["bake"]["cacheMBMax"]
    man = json.loads((Path(b["dir"]) / "bake.json").read_text(encoding="utf-8"))
    assert man["moving"] is True and set(man["files"]) <= {f for f in man["files"] if f.startswith("data/")}
    (env["tmp"] / "smoke_sim.json").write_text(json.dumps({"bake": b, "probe": pr, "domain": man["domain"],
                                                           "simSeconds": man["simSeconds"]}), encoding="utf-8")
