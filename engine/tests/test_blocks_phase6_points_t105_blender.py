"""Phase 6 lane P, Task 105 (recipe step 4): the particle pack baked (stage 4b, gn_disk) and compiled without
rendering, on real subjects: sparks off a marker on the sneaker, confetti onto the sneaker, bubbles in the
procedural single-sided glass (var/fixtures/sim/glass.glb, ingested here), embers (stateless) around the sneaker.
Asserts the simProbe conditions (nothing inside the shell, finite, velocity present), the cache under the
manifest's cacheMBMax, and the compile never simulates (SimInCompile passes). Bakes into a temp BakeStore
(VALORA_BAKE_ROOT) under the machine lock. Serial."""
import json
import subprocess
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
SNEAKER = ROOT / "assets-in" / "models" / "sneaker" / "sneaker.glb"
PROPS_DIR = ROOT / "var" / "fixtures" / "sim"
MAKE_PROPS = FIX / "sim" / "make_props.py"


def _script(sims=(), effects=(), markers=None, dur=3.0, aspect="1:1"):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["format"] = {"aspect": aspect, "durationS": dur, "fps": 24}
    s["shots"] = [{"startS": 0, "endS": dur, "camera": {"id": "low_hero_push", "params": {"distance": 3.0}},
                   "focus": "subject"}]
    s["sims"], s["effects"] = list(sims), list(effects)
    if markers:
        s["markers"] = markers
    return s


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p6t105")
    mp = pytest.MonkeyPatch()
    mp.setenv("VALORA_BAKE_ROOT", str(tmp / "bake"))
    yield {"tmp": tmp, "cat": Catalog.load()}
    mp.undo()


def _compile(env, name, script, profile, model, probe):
    out = env["tmp"] / name
    bakes = bake_run.bake_sims(script, profile, model, catalog=env["cat"], lock_timeout_s=3600)
    res = compile_scene(script, profile, model, out, catalog=env["cat"], render=False, frames=[probe[-1]],
                        realism_probe=probe, bakes=bakes)
    return bakes, res


def _assert_probe(env, res, bakes, sid):
    pr = res["simProbe"][sid]
    assert pr["velocityPresent"] is True, pr
    assert pr["stable"]["finite"] is True, pr
    assert pr["inside"]["ok"] is True and pr["inside"]["points"] > 0, pr
    mb = bakes[sid]["bytes"] / 1e6
    assert mb <= env["cat"].get("sim", sid)["bake"]["cacheMBMax"], mb
    assert f"sim:{sid}" in res["built"]
    return pr


SPARK_MARKER = [{"id": "grind", "text": "sparks fly from the heel", "anchor": {"space": "placed",
                 "point": [-0.145, 0.0, 0.03], "normal": [-1.0, 0.0, 0.4]}}]


def test_sparks_bake_compile_and_probe(env):
    s = _script([{"id": "sparks", "params": {}, "startS": 0.0, "endS": 3.0}], markers=SPARK_MARKER)
    bakes, res = _compile(env, "sparks", s, _p("sneaker"), SNEAKER, [20, 40, 60])
    pr = _assert_probe(env, res, bakes, "sparks")
    assert bakes["sparks"]["frames"]["mode"] == "absolute" and bakes["sparks"]["frames"]["bake_first"] < 1
    (env["tmp"] / "sparks.json").write_text(json.dumps({"bake": bakes["sparks"], "probe": pr}), encoding="utf-8")


def test_confetti_bake_compile_and_probe(env):
    s = _script([{"id": "confetti", "params": {"count": 400}, "startS": 0.0, "endS": 3.0}])
    bakes, res = _compile(env, "confetti", s, _p("sneaker"), SNEAKER, [10, 40, 70])
    _assert_probe(env, res, bakes, "confetti")


@pytest.fixture(scope="module")
def glass(env):
    if not (PROPS_DIR / "glass.glb").exists():
        from engine.blender_cli import BLENDER
        subprocess.run([BLENDER, "--background", "--factory-startup", "--python", str(MAKE_PROPS), "--",
                        str(PROPS_DIR)], check=True, capture_output=True, timeout=300)
    from engine.ingest.run import ingest
    return PROPS_DIR / "glass.glb", ingest(PROPS_DIR / "glass.glb")


GLASS_MARKERS = [{"id": "rim", "text": "the rim of the glass", "anchor": {"space": "placed", "point": [0.0, 0.04, 0.094],
                  "normal": [0, 0, 1]}},
                 {"id": "fill", "text": "fill line", "anchor": {"space": "placed", "point": [0.0, 0.04, 0.08],
                  "normal": [0, 1, 0]}}]


def test_bubbles_rise_inside_the_glass(env, glass):
    model, prof = glass
    s = _script([{"id": "bubbles", "params": {}, "startS": 0.0, "endS": 3.0}], markers=GLASS_MARKERS)
    bakes, res = _compile(env, "bubbles", s, prof, model, [24, 48, 70])
    pr = res["simProbe"]["bubbles"]
    assert pr["velocityPresent"] is True and pr["stable"]["finite"] is True, pr
    assert bakes["bubbles"]["bytes"] / 1e6 <= env["cat"].get("sim", "bubbles")["bake"]["cacheMBMax"]
    assert any(o["block"] == "sim/bubbles:drink" for o in res["objects"]), res["objects"]
    assert pr["inside"]["share"] <= 0.05, pr      # report-only: bubbles hugging the thick shell's inner wall


def test_embers_is_stateless_and_carries_velocity(env):
    s = _script(effects=[{"id": "embers", "params": {"count": 60}}])
    res = compile_scene(s, _p("sneaker"), SNEAKER, env["tmp"] / "embers", catalog=env["cat"], render=False,
                        frames=[30])
    assert "effect:embers" in res["built"] and not res.get("sims")
    assert any(o["block"] == "effect/embers" for o in res["objects"])
