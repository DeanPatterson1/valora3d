"""Task 72: world-lighting pairing and the lighting_world_mismatch repair."""
import copy

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.lighting.pairing import allowed_lighting, repair_lighting
from engine.tests.test_director_package import _p
from engine.tests.test_growth_floor import T3, _road_side

PAIRS = {"studio_cyc": ["softbox_three_point", "reflection_rig"],
         "rain_courtyard": ["hdri_only", "hard_sun", "reflection_rig"],
         "night_street": ["rim_neon", "reflection_rig"],
         "golden_field": ["hard_sun", "reflection_rig"]}


def test_every_world_names_its_pairs():
    cat = Catalog.load()
    assert {w: allowed_lighting(cat.get("world", w)) for w in cat.ids("world")} == PAIRS
    for pairs in PAIRS.values():
        assert all(cat.get("lighting", b) for b in pairs)


def _script(world, lighting, params=None):
    s = copy.deepcopy(T3)
    s["world"] = {"id": world, "params": {}}
    s["lighting"] = {"id": lighting, "params": params or {}}
    return _road_side(s) if world == "night_street" else s   # the street's cameras shoot from the road


def test_the_studio_is_unchanged():
    cat = Catalog.load()
    for lighting in PAIRS["studio_cyc"]:
        r = check(_script("studio_cyc", lighting), _p("sports_car"), cat)
        assert r.script["lighting"]["id"] == lighting
        assert "lighting_world_mismatch" not in {i.code for i in r.issues}


def test_night_street_with_a_softbox_becomes_rim_neon_keeping_shared_params():
    cat = Catalog.load()
    r = check(_script("night_street", "softbox_three_point", {"rimStrength": 2.2, "keyAzimuthDeg": 150.0}),
              _p("sports_car"), cat)
    assert r.ok and r.script["lighting"]["id"] == "rim_neon"
    assert r.script["lighting"]["params"]["rimStrength"] == 2.2 and r.script["lighting"]["params"]["keyAzimuthDeg"] == 150.0
    mm = [i for i in r.issues if i.code == "lighting_world_mismatch"]
    assert len(mm) == 1 and mm[0].severity == "repaired"


def test_golden_field_keeps_a_reflection_rig_for_gloss():
    cat = Catalog.load()
    r = check(_script("golden_field", "reflection_rig"), _p("sports_car"), cat)
    assert r.ok and r.script["lighting"]["id"] == "reflection_rig"
    assert "lighting_world_mismatch" not in {i.code for i in r.issues}


def test_the_courtyard_softbox_is_repaired_to_the_sky():
    """chunk 3 look-check t68: the rim softbox mirrored in the wet courtyard as a white blob."""
    cat = Catalog.load()
    r = check(_script("rain_courtyard", "softbox_three_point"), _p("sports_car"), cat)
    assert r.ok and r.script["lighting"]["id"] == "hdri_only"


def test_a_world_without_pairs_accepts_any_lighting():
    cat = Catalog.load()
    grown = copy.copy(cat)
    grown._blocks = copy.deepcopy(cat._blocks)
    del grown._blocks[("world", "night_street")]["lightingPairs"]
    s, issues = _script("night_street", "softbox_three_point"), []
    assert repair_lighting(s, grown, issues) is False and not issues


@pytest.mark.parametrize("model", ["camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair",
                                   "pocket_watch", "sneaker", "sports_car", "toycar", "vintage_microscope"])
def test_the_studio_pairs_cover_every_phase3_default_lighting(model):
    """Frozen-baseline check: building the phase-3 default for the 9 eval subjects, every lighting it uses is
    one the studio pairs with, so the repair can never touch a frozen script."""
    from engine.director.direction import interim_direction
    from engine.director.floor import phase3_default
    from engine.director.job import make_job
    cat, p = Catalog.load(), _p(model)
    for seed in range(0, 40, 4):
        d = interim_direction(seed, p, cat)
        s = phase3_default(make_job("", p, cat, seed=seed, direction=d), p, cat)
        assert s["lighting"]["id"] in PAIRS["studio_cyc"], (model, seed, s["lighting"]["id"])
