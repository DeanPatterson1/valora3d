"""Task 85 (amendment 85): a checker error that means 'this block cannot be here' ends as an `unsupported`
entry with the block's own note, not a failed job or a repair round, and the video renders without the
block. One test per mapped code, through direct() with a FakeProvider reply."""
import copy

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from engine.tests.test_capabilities import _grown
from engine.director.direction import interim_direction
from engine.tests.test_catalog_growth import profile_of as _p
from engine.tests.test_director_pipeline import CAR, WATCH
from engine.tests.test_growth_floor import _road_side


def _run(reply, prompt, model, cat):
    """A fixed interim direction: nothing is enforced, so the only thing the pipeline changes is the block."""
    p, prof = FakeProvider([reply]), _p(model)
    return direct(prompt, prof, provider=p, seed=11, duration=10, catalog=cat,
                  direction=interim_direction(11, prof, cat)), p


def _in(script, tag):
    return next((u for u in script.get("unsupported", []) if u["capability"] == tag), None)


def _studio(base, **kw):
    s = copy.deepcopy(base)
    s.update(kw)
    return s


CASES = [
    # code, model, prompt, reply mutation, tag, note fragment, block that must be gone
    ("effect_needs_world", "sports_car", "rain on the car",
     lambda s: s.update(effects=[{"id": "rain", "params": {}}]), "weather.rain", "outdoor", ("effect", "rain")),
    ("effect_needs_profile", "bare_tube", "dewy droplets",
     lambda s: s.update(effects=[{"id": "droplets", "params": {}}]), "liquid.droplets", "face up", ("effect", "droplets")),
    ("effect_needs_source", "sports_car", "water on the lens",
     lambda s: _road_side(s.update(world={"id": "night_street", "params": {}},
                                   lighting={"id": "rim_neon", "params": {}},
                                   effects=[{"id": "haze_volume", "params": {}}, {"id": "lens_drops", "params": {}}])
                          or s),
     "camera.lens_drops", "rain in the clip", ("effect", "lens_drops")),
    ("motion_needs_profile", "pocket_watch", "the watch rolls across the table",
     lambda s: s["subject"].update(motion={"id": "roll", "params": {}}), "motion.roll", "round", ("motion", "roll")),
    ("camera_needs_motion", "pocket_watch", "tracking shot of the watch",
     lambda s: s["shots"][1].update(camera={"id": "rolling_track", "params": {}}), "camera.tracking", "move",
     ("camera", "rolling_track")),
]


def _full(reply):
    """The reply as the checker sees it after sanitize (the pipeline owns schema, seed and format)."""
    from engine import SCHEMA
    return {**copy.deepcopy(reply), "schema": SCHEMA, "seed": 11, "format": {"aspect": "9:16", "durationS": 10, "fps": 30}}


def _gone(script, kind, bid):
    if kind == "effect":
        return all(e["id"] != bid for e in script.get("effects", []))
    if kind == "motion":
        return script["subject"]["motion"]["id"] != bid
    return all(sh["camera"]["id"] != bid for sh in script["shots"])


@pytest.mark.parametrize("code,model,prompt,mutate,tag,frag,block", CASES, ids=[c[0] for c in CASES])
def test_blocked_error_ends_as_unsupported_not_a_failed_job(code, model, prompt, mutate, tag, frag, block):
    cat = _grown()
    reply = copy.deepcopy(CAR if model == "sports_car" else WATCH)
    mutate(reply)
    raw = check(_full(reply), _p(model), cat)
    assert code in {i.code for i in raw.issues if i.severity == "error"}, "the fixture must trip the code"
    r, prov = _run(reply, prompt, model, cat)
    assert len(prov.calls) == 1 and r.source == "llm", "no repair round, no fallback"
    u = _in(r.script, tag)
    assert u is not None and frag in u["note"] and u["note"] in r.script["assumptions"]
    assert _gone(r.script, *block)
    assert check(r.script, _p(model), cat).ok                       # the video renders without the block
    assert "blocked_to_unsupported" in {c for rd in r.rounds for c in rd["repaired"]}


def test_drive_in_the_studio_ends_as_unsupported():
    """A drive in a world without a road (studio): the motion comes out, the ask gets the world note."""
    cat = _grown()
    reply = copy.deepcopy(CAR)
    reply["subject"]["motion"] = {"id": "drive", "params": {}}
    raw = check(_full(reply), _p("sports_car"), cat)
    codes = {i.code for i in raw.issues if i.severity == "error"}
    assert codes & {"path_through_world", "motion_needs_world"}, codes
    r, prov = _run(reply, "driving through", "sports_car", cat)
    assert len(prov.calls) == 1 and r.script["subject"]["motion"]["id"] == "static"
    assert "road" in _in(r.script, "motion.drive")["note"]


def test_world_blocked_ask_the_reply_ignored_is_reported():
    """The model left rain out of a studio script: the ask is still reported (never silently dropped)."""
    cat = _grown()
    r, _ = _run(copy.deepcopy(CAR), "rain on the car", "sports_car", cat)
    assert "outdoor" in _in(r.script, "weather.rain")["note"]


def test_unblock_leaves_other_errors_to_the_repair_loop():
    cat = _grown()
    reply = copy.deepcopy(WATCH)
    reply["world"] = {"id": "moon", "params": {}}
    p, prof = FakeProvider([reply, copy.deepcopy(WATCH)]), _p("pocket_watch")
    r = direct("luxury", prof, provider=p, seed=11, duration=10, catalog=cat, direction=interim_direction(11, prof, cat))
    assert len(p.calls) == 2 and r.source == "llm+repair1"


def test_ground_motion_in_a_float_script_lands_the_subject_not_the_motion():
    """review chunk7 #6: motion_needs_ground is a placement conflict (path subject.placement), not a profile
    miss. The subject is put on the ground and keeps the motion it can play; a float ask gets a placement note."""
    cat = _grown()
    reply = copy.deepcopy(WATCH)
    reply["subject"].update(placement="float", motion={"id": "drop_settle", "params": {}})
    raw = check(_full(reply), _p("pocket_watch"), cat)
    assert "motion_needs_ground" in {i.code for i in raw.issues if i.severity == "error"}
    r, prov = _run(reply, "the watch floats, then drops in", "pocket_watch", cat)
    assert len(prov.calls) == 1 and r.source == "llm"
    assert r.script["subject"]["motion"]["id"] == "drop_settle" and r.script["subject"]["placement"] == "ground"
    assert _in(r.script, "motion.drop") is None                     # the drop was delivered
    u = _in(r.script, "motion.float")
    assert u is not None and "ground" in u["note"] and "suit this model" not in u["note"]
    assert check(r.script, _p("pocket_watch"), cat).ok
    assert "blocked_to_unsupported" in {c for rd in r.rounds for c in rd["repaired"]}


def _fell_back(prompt, seed, model="sports_car", cat=None):
    return direct(prompt, _p(model), provider=FakeProvider([{"error": "down"}] * 5), seed=seed,
                  catalog=cat or _grown()).script


@pytest.mark.parametrize("prompt", ["a car on a beach", "a car in the forest", "a car in the mountains",
                                    "a car in a garden", "a car in the desert"])
def test_an_outdoor_location_no_world_delivers_is_reported(prompt):
    """review chunk7 #2: world.nature is deliverable (golden_field, rain_courtyard) but no world is a beach or a
    forest. The rolled world must not silently stand in for the place asked for: the note says which set was used."""
    cat = _grown()
    for seed in range(3):
        s = _fell_back(prompt, seed, cat=cat)
        u = _in(s, "world.nature")
        assert u is not None, (seed, s["world"]["id"])
        assert "isn't available" in u["note"] and u["note"] in s["assumptions"]
        place = {"studio_cyc": "studio", "night_street": "street", "golden_field": "field",
                 "rain_courtyard": "courtyard"}[s["world"]["id"]]
        assert place in u["note"]


@pytest.mark.parametrize("prompt", ["a car in a wheat field", "a car in a meadow at golden hour",
                                    "a car on a city street at night"])
def test_a_location_the_world_delivers_is_not_reported(prompt):
    cat = _grown()
    for seed in range(3):
        s = _fell_back(prompt, seed, cat=cat)
        assert _in(s, "world.nature") is None and _in(s, "world.street") is None, (seed, s["world"]["id"])


def test_outdoors_is_delivered_by_any_outdoor_world_but_not_the_studio():
    cat = _grown()
    for seed in range(3):
        s = _fell_back("a car outdoors", seed, cat=cat)
        outdoor = (cat.get("world", s["world"]["id"]) or {}).get("outdoor")
        assert (_in(s, "world.nature") is None) == bool(outdoor), (seed, s["world"]["id"])
