"""Growth-contract floor tests (block recipe step 8; review amendment: chunks 2-6 use a hand-written
fixture script per block). Each case builds the block's fixture on the task's eval subject and proves the
block is still present after the checker, the script checks ok and it reaches T3 at script level.
engine/catalog_growth.json points each block's `floor` at its case here, and test_catalog_growth.py
resolves that node id against pytest's own collection."""
import copy
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.director.floor import script_tier
from engine.tests.test_director_package import _p

FIX = Path(__file__).resolve().parent / "fixtures"
T3 = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))


def _with_wind():
    s = copy.deepcopy(T3)
    s["wind"] = {"id": "wind", "params": {"speedMs": 4.0}}
    return s


def _has_block(script, ref):
    """The block survives the checker: it is the script's world/lighting/grade/wind, a shot camera, the
    subject motion, or an effect."""
    kind, bid = ref.split("/")
    single = {"world": "world", "lighting": "lighting", "grade": "grade", "field": "wind", "edit": "edit"}
    if kind in single:
        return (script.get(single[kind]) or {}).get("id") == bid
    if kind == "camera":
        return any(sh["camera"]["id"] == bid for sh in script["shots"])
    if kind == "motion":
        return (script["subject"].get("motion") or {}).get("id") == bid
    if kind == "effect":
        return any(e["id"] == bid for e in script.get("effects", []))
    raise AssertionError(f"no presence rule for kind {kind}")


def _with_fog():
    s = copy.deepcopy(T3)
    s["effects"] = [{"id": "ground_fog", "params": {"heightM": 0.4}}]
    return s


def _courtyard():
    s = copy.deepcopy(T3)                    # keeps its haze_volume: T2-07 wants atmosphere outside a studio
    s["world"] = {"id": "rain_courtyard", "params": {}}
    s["lighting"] = {"id": "softbox_three_point", "params": {}}      # hdri_only lands in Task 72
    return s


def _weather(*effects):
    """The courtyard (outdoor, with a ground) plus weather effects, as a floor fixture."""
    def make():
        s = _courtyard()
        s["effects"] = list(s.get("effects", [])) + [{"id": e, "params": {}} for e in effects]
        return s
    return make


# block ref -> (fixture script factory, eval subject)
FLOORS = {
    "field/wind": (_with_wind, "pocket_watch"),
    "effect/ground_fog": (_with_fog, "sports_car"),                  # Task 60
    "world/rain_courtyard": (_courtyard, "sports_car"),              # Task 63
    "effect/rain": (_weather("rain"), "sports_car"),                 # Task 64
}


@pytest.mark.parametrize("ref", sorted(FLOORS))
def test_block_reaches_the_floor(ref):
    make, model = FLOORS[ref]
    cat, p = Catalog.load(), _p(model)
    r = check(make(), p, cat)
    assert r.ok, [(i.code, i.path, i.message) for i in r.issues if i.severity == "error"]
    assert _has_block(r.script, ref), f"{ref} was dropped by the checker"
    assert script_tier(r.script, p, cat) == "T3"
