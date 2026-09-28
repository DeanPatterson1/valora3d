"""Phase 6 lane R (Tasks 100-102): the rigid sims' manifests and their checker behaviour (pure). The lane keeps its
own file so the parallel lanes never edit one test module (the recipe's test_blocks_phase6.py is shared)."""
import copy
import json
import shutil
from pathlib import Path

import pytest

from engine.catalog import BLOCKS_DIR, Catalog
from engine.checker import check
from engine.tests.test_director_package import _p

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def cat():
    return Catalog.load()


def _script(sims, motion="static", world="studio_cyc"):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["sims"] = sims
    s["subject"]["motion"] = {"id": motion, "params": {}}
    if world != "studio_cyc":
        s["world"] = {"id": world, "params": {}}
    return s


def _num(m, k):
    return (m["params"][k]["min"], m["params"][k]["max"], m["params"][k]["default"])


# ---------------------------------------------------------------- T100 rigid_scatter

def test_rigid_scatter_manifest(cat):
    m = cat.get("sim", "rigid_scatter")
    assert m["directorSelectable"] is False and m["tierMax"] == "T4"
    assert m["params"]["pieces"]["values"] == ["beans", "coffee_beans", "ice", "gems", "coins", "pills",
                                               "candies", "pebbles"]
    assert _num(m, "count") == (30, 500, 150)
    assert m["params"]["zone"]["values"] == ["onto", "around", "behind"] and m["params"]["zone"]["default"] == "onto"
    assert _num(m, "timeScale") == (0.3, 1.0, 0.5)
    assert _num(m, "drop") == (0.3, 1.5, 0.8)
    ph = m["physics"]
    assert ph["spawnZone"] == {"kind": "above", "heightFrac": 1.2, "radiusFrac": 0.6}
    assert ph["touchesSubject"] is True and ph["state"] == "baked" and ph["timeScaleParam"] == "timeScale"
    assert ph["requiresWorld"] == {"hasGround": True} and "RB-05" in ph["taxonomy"]
    b = m["bake"]
    assert (b["method"], b["costClass"], b["prerollS"], b["maxFrames"], b["cacheMBMax"]) == \
        ("rigid_keys", "medium", 0.3, 240, 20)   # pre-roll: pieces enter in flight (key_pieces)
    assert b["estimateS"] == 180 and b["proxies"] == ["shell"]
    assert m["capabilities"] == ["rigid.scatter"]


def test_rigid_scatter_checks_clean_on_the_studio(cat):
    r = check(_script([{"id": "rigid_scatter", "params": {}, "startS": 0.5, "endS": 3.5}]), _p("sneaker"), cat)
    assert r.ok, [i for i in r.issues if i.severity == "error"]


def test_rigid_scatter_spawn_inside_the_subject_fails_the_checker(tmp_path):
    root = tmp_path / "cat"
    shutil.copytree(BLOCKS_DIR, root, ignore=shutil.ignore_patterns("__pycache__"))
    f = root / "sim" / "rigid_scatter" / "block.json"
    m = json.loads(f.read_text(encoding="utf-8"))
    m["physics"]["spawnZone"]["heightFrac"] = 0.5            # inside the bounds
    f.write_text(json.dumps(m), encoding="utf-8")
    r = check(_script([{"id": "rigid_scatter", "params": {"zone": "onto"}, "startS": 0.5, "endS": 3.5}]),
              _p("sneaker"), Catalog.load(root))
    assert any(i.code == "sim_spawn_in_subject" for i in r.issues)


def test_rigid_scatter_time_scale_is_clamped(cat):
    r = check(_script([{"id": "rigid_scatter", "params": {"timeScale": 3.0}, "startS": 0.5, "endS": 3.5}]),
              _p("sneaker"), cat)
    assert r.script["sims"][0]["params"]["timeScale"] == 1.0


# ---------------------------------------------------------------- T101 debris_float

def test_debris_float_manifest(cat):
    m = cat.get("sim", "debris_float")
    assert m["directorSelectable"] is False
    assert _num(m, "count") == (5, 60, 20) and _num(m, "sizeFrac") == (0.02, 0.15, 0.05)
    assert m["params"]["pieces"]["values"] == ["pebbles", "gems", "shards", "leaves_dry"]
    assert "timeScale" not in m["params"] and m["physics"]["timeScaleParam"] is None
    assert m["bake"] == {"method": "none", "costClass": "cheap"} and m["physics"]["state"] == "stateless"
    assert m["capabilities"] == ["rigid.float_debris"] and "RB-07" in m["physics"]["taxonomy"]


def test_debris_float_plans_no_bake_and_checks_clean(cat):
    from engine.bake.run import plan_bakes
    s = _script([{"id": "debris_float", "params": {}, "startS": 0.0, "endS": 10.0}])
    r = check(s, _p("pocket_watch"), cat)
    assert r.ok, [i for i in r.issues if i.severity == "error"]
    assert plan_bakes(r.script, _p("pocket_watch"), "unused.glb", cat) == []

