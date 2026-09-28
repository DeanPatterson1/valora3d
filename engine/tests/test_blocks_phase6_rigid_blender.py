"""Phase 6 lane R (Tasks 100-102), recipe step 4: bake + compile (render=False) on the named eval subject, then the
simProbe conditions (no piece inside the subject's shell, stable and settled, velocity present) and the cache
under bake.cacheMBMax. Serial: bakes take the machine lock. Each bake here is > 30 s on the 9800X3D, so the
module is also `slow`."""
import json
import os
from pathlib import Path

import pytest

from engine.bake import run as bake_run
from engine.catalog import Catalog
from engine.compiler.run import compile_scene
from engine.tests.conftest import requires_blender
from engine.tests.test_director_package import _p

pytestmark = [pytest.mark.blender, pytest.mark.slow, requires_blender]

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"


def model(name):
    return ROOT / "assets-in" / "models" / name / f"{name}.glb"


def script(sid, params, start=0.5, end=2.5, dur=3.0, motion="static"):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["format"]["durationS"] = dur
    s["subject"]["motion"] = {"id": motion, "params": {}}
    s["shots"] = [{"startS": 0, "endS": dur, "camera": {"id": "low_hero_push", "params": {}}, "focus": "subject"}]
    s["sims"] = [{"id": sid, "params": params, "startS": start, "endS": end}]
    return s


@pytest.fixture(scope="module")
def store_root(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rl")
    mp = pytest.MonkeyPatch()
    mp.setenv("VALORA_BAKE_ROOT", str(tmp / "b"))
    yield tmp
    mp.undo()


def _bake_and_compile(store_root, s, subject, name):
    cat = Catalog.load()
    bakes = bake_run.bake_sims(s, _p(subject), model(subject), catalog=cat, lock_timeout_s=3600)
    res = compile_scene(s, _p(subject), model(subject), store_root / name, catalog=cat, render=False, frames=[1],
                        bakes=bakes)
    return cat, bakes, res


def _mb(b):
    return b["bytes"] / 2 ** 20


# ---------------------------------------------------------------- T100 rigid_scatter

def test_rigid_scatter_bakes_settles_and_stays_out_of_the_sneaker(store_root):
    s = script("rigid_scatter", {"pieces": "coffee_beans", "count": 60})
    cat, bakes, res = _bake_and_compile(store_root, s, "sneaker", "scatter")
    b = bakes["rigid_scatter"]
    m = cat.get("sim", "rigid_scatter")
    p = res["simProbe"]["rigid_scatter"]
    assert p["inside"]["ok"] and p["inside"]["points"] > 0, p
    assert p["stable"]["finite"] and p["stable"]["ok"], p             # KE of the last 10% <= 1% of its peak
    assert p["velocityPresent"] is True
    assert b["bakeSeconds"] <= 300 and _mb(b) <= m["bake"]["cacheMBMax"]
    keys = json.loads((Path(b["dir"]) / "keys.json").read_text(encoding="utf-8"))
    assert len(keys["pieces"]) == 60
    assert min(r[2] for rows in keys["pieces"].values() for r in rows) >= -0.001      # nothing through the floor
    first = [rows[0][2] for rows in keys["pieces"].values()]
    last = [rows[-1][2] for rows in keys["pieces"].values()]
    assert min(first) > _p("sneaker").boundsMax[2] and max(last) < min(first)       # they fell
    pieces = [o for o in res["objects"] if o["block"] == "sim/rigid_scatter"]
    assert len(pieces) == 60


# ---------------------------------------------------------------- T101 debris_float

def test_debris_float_needs_no_bake_and_keys_every_piece(store_root):
    s = script("debris_float", {"count": 20, "pieces": "gems"}, start=0.0, end=3.0)
    cat, bakes, res = _bake_and_compile(store_root, s, "pocket_watch", "debris")
    assert bakes == {}                                            # the stateless sim kind never bakes
    assert "sim:debris_float" in res["built"]
    pieces = [o for o in res["objects"] if o["block"] == "sim/debris_float"]
    assert len(pieces) == 20

