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
    s["lighting"] = {"id": "hdri_only", "params": {}}                # the courtyard's first pair (Task 72)
    return s


def _street():
    s = copy.deepcopy(T3)                    # keeps its haze_volume: T2-07 wants atmosphere outside a studio
    s["world"] = {"id": "night_street", "params": {}}
    s["lighting"] = {"id": "rim_neon", "params": {}}                 # the street's first pair (Task 72)
    return s


def _field():
    s = copy.deepcopy(T3)                    # keeps its haze_volume: T2-07 wants atmosphere outside a studio
    s["world"] = {"id": "golden_field", "params": {}}
    s["lighting"] = {"id": "hard_sun", "params": {}}                 # the field's first pair (Task 72)
    return s


def _weather(*effects):
    """The courtyard (outdoor, with a ground) plus weather effects, as a floor fixture."""
    def make():
        s = _courtyard()
        s["effects"] = list(s.get("effects", [])) + [{"id": e, "params": {}} for e in effects]
        return s
    return make


def _studio_droplets():
    s = copy.deepcopy(T3)                    # droplets need no outdoor world: a bottle in the studio is fine
    s["effects"] = list(s.get("effects", [])) + [{"id": "droplets", "params": {}}]
    return s


def _lens_drops():
    s = _weather("rain")()
    s["effects"].append({"id": "lens_drops", "params": {"shot": 0, "amount": 0.3}})
    return s


def _motion(bid, params=None, world=None, lighting=None):
    """script_t3 with this subject motion (Chunk 5 floors), optionally in another world."""
    def make():
        s = copy.deepcopy(T3)
        s["subject"]["motion"] = {"id": bid, "params": dict(params or {})}
        if world:
            s["world"], s["lighting"] = {"id": world, "params": {}}, {"id": lighting, "params": {}}
        return s
    return make


# block ref -> (fixture script factory, eval subject)
FLOORS = {
    "field/wind": (_with_wind, "pocket_watch"),
    "effect/ground_fog": (_with_fog, "sports_car"),                  # Task 60
    "world/rain_courtyard": (_courtyard, "sports_car"),              # Task 63
    "effect/rain": (_weather("rain"), "sports_car"),                 # Task 64
    "effect/wet_surface": (_weather("wet_surface"), "pocket_watch"), # Task 65
    "effect/droplets": (_studio_droplets, "pocket_watch"),           # Task 66
    "effect/snow": (_weather("snow"), "sports_car"),                 # Task 67
    "effect/lens_drops": (_lens_drops, "sports_car"),                # Task 68
    "world/night_street": (_street, "sports_car"),                   # Task 70
    "world/golden_field": (_field, "sports_car"),                    # Task 71
    "lighting/rim_neon": (_street, "sneaker"),                       # Task 72
    "lighting/hard_sun": (_field, "mid_century_lounge_chair"),       # Task 72
    "lighting/hdri_only": (_courtyard, "pocket_watch"),              # Task 72
    "motion/drop_settle": (_motion("drop_settle"), "sneaker"),       # Task 74
    "motion/float_drift": (_motion("float_drift"), "pocket_watch"),  # Task 75
    "motion/plinth_spin": (_motion("plinth_spin"), "sneaker"),       # Task 75
    "motion/slide_in": (_motion("slide_in"), "sneaker"),             # Task 76
    "motion/roll": (_motion("roll", {"startS": 0.2, "distanceFrac": 0.5}, "rain_courtyard", "hdri_only"), "can"),  # Task 77
    "motion/topple": (_motion("topple"), "bottle"),                    # Task 77
}


def _profile(model):
    """An eval model, or a TEST ONLY synthetic shape (fixtures/synthetic_profiles: the can, the bottle)."""
    from engine.profile import SubjectProfile
    f = FIX / "synthetic_profiles" / f"{model}.json"
    return SubjectProfile.from_dict(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else _p(model)


def floor_outcome(ref, floors=None):
    """The floor verdict for one block, as a list of problems (empty = the block reaches the floor): its fixture
    exists, check(...).ok, the block survives the checker and script_tier is T3. test_catalog_growth.py runs
    this for every growth entry itself, so the floor cannot be made vacuous by editing the test below
    (review chunk 2 #5)."""
    floors = FLOORS if floors is None else floors
    if ref not in floors:
        return [f"{ref}: no floor fixture in engine/tests/test_growth_floor.py FLOORS"]
    make, model = floors[ref]
    cat, p = Catalog.load(), _profile(model)
    r = check(make(), p, cat)
    out = []
    if not r.ok:
        out.append(f"{ref}: check not ok {[(i.code, i.path) for i in r.issues if i.severity == 'error']}")
    try:
        present = _has_block(r.script, ref)
    except (AssertionError, KeyError, TypeError) as e:
        present = False
        out.append(f"{ref}: presence rule failed: {e}")
    if not present:
        out.append(f"{ref} was dropped by the checker")
    tier = script_tier(r.script, p, cat)
    if tier != "T3":
        out.append(f"{ref}: script_tier {tier} != T3")
    return out


@pytest.mark.parametrize("ref", sorted(FLOORS))
def test_block_reaches_the_floor(ref):
    make, model = FLOORS[ref]
    cat, p = Catalog.load(), _profile(model)
    r = check(make(), p, cat)
    assert r.ok, [(i.code, i.path, i.message) for i in r.issues if i.severity == "error"]
    assert _has_block(r.script, ref), f"{ref} was dropped by the checker"
    assert script_tier(r.script, p, cat) == "T3"
    assert floor_outcome(ref) == []
