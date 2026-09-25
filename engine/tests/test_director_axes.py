import copy

import pytest

from engine.catalog import Catalog
from engine.director.axes import DICE, axis_values, compatible, opener_of, validate_axes
from engine.director.direction import AXES
from engine.tests.test_director_package import _p

FMT = {"aspect": "9:16", "durationS": 10, "fps": 30}
NINE = ["camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
        "sports_car", "toycar", "vintage_microscope"]


@pytest.mark.parametrize("model", NINE)
def test_every_eval_subject_has_a_value_on_every_axis(model):
    v = axis_values(_p(model), Catalog.load(), FMT)
    assert tuple(v) == AXES and all(v[a] for a in AXES), v


def test_turntable_is_never_an_opener_negative_control():
    cat = Catalog.load()
    assert "turntable" in [b for (k, b) in cat._blocks if k == "camera"]  # the control exists ...
    for model in NINE:
        assert "turntable" not in axis_values(_p(model), cat, FMT)["opener"]  # ... and is never rolled


def test_rare_and_future_values_are_pin_only():
    cat, p = Catalog.load(), _p("pocket_watch")
    rolled, known = axis_values(p, cat, FMT), axis_values(p, cat, FMT, rollable=False)
    assert "noir" not in rolled["mood"] and "noir" in known["mood"]
    # phase 5 Task 87: weather and wind roll (each world's `weathers` and the floor narrow them per candidate)
    assert set(rolled["weather"]) == set(known["weather"]) and set(rolled["wind"]) == set(known["wind"])
    assert "rain" in known["weather"] and "windy" in known["wind"]


def test_values_come_from_the_catalog():
    cat = Catalog.load()
    moods = cat.get("grade", "mood_grade")["params"]["preset"]["values"]
    v = axis_values(_p("pocket_watch"), cat, FMT, rollable=False)
    assert set(v["mood"]) == set(moods) and set(v["world"]) <= set(cat.selectable_ids("world"))
    assert set(v["opener"]) <= set(cat.selectable_ids("camera"))


def test_tone_compatibility():
    assert compatible({"mood": "premium_dark", "tone": "black"}) and not compatible({"mood": "premium_dark",
                                                                                        "tone": "white"})
    assert compatible({"mood": "unknown_mood", "tone": "white"})  # unknown moods combine freely


def test_openers_are_full_framing_hook_cameras():
    v = axis_values(_p("pocket_watch"), Catalog.load(), FMT)
    assert v["opener"] == ["low_hero_push", "arc_orbit"]   # macro_detail cannot open: seq_bad_hook


def test_opener_of_and_validate_axes():
    assert opener_of({"shots": [{"purpose": "hook", "camera": {"id": "arc_orbit"}}]}) == "arc_orbit"
    cat, p = Catalog.load(), _p("pocket_watch")
    ok = {"world": "studio_cyc", "mood": "clean", "tone": "white", "pace": "calm", "opener": "arc_orbit",
          "weather": "dry", "wind": "calm"}
    assert validate_axes(ok, p, cat, FMT) == []
    assert validate_axes({**ok, "mood": "<script>", "opener": "turntable"}, p, cat, FMT) == ["mood", "opener"]
    assert validate_axes("junk", p, cat, FMT) == list(AXES)


def test_dice_json_is_consistent():
    assert set(DICE["axisWeights"]) == set(AXES)
    assert set(DICE["weather"]["rollable"]) <= set(DICE["weather"]["values"])
    assert set(DICE["wind"]["rollable"]) <= set(DICE["wind"]["values"])


def _cat_without(kind, bid, param, value):
    cat = copy.deepcopy(Catalog.load())
    vals = cat._blocks[(kind, bid)]["params"][param]["values"]
    vals.remove(value)
    return cat


@pytest.mark.parametrize("model", ["pocket_watch", "sports_car"])
def test_a_value_the_catalog_drops_is_no_longer_rollable(model):
    """dice.json lists are intersected with the catalog enum, so the catalog always wins."""
    p = _p(model)
    assert "hype" in axis_values(p, Catalog.load(), FMT)["pace"]
    cat = _cat_without("edit", "sequence", "pace", "hype")
    for rollable in (True, False):
        assert "hype" not in axis_values(p, cat, FMT, rollable=rollable)["pace"]
    cat = _cat_without("grade", "mood_grade", "preset", "vivid")
    for rollable in (True, False):
        assert "vivid" not in axis_values(p, cat, FMT, rollable=rollable)["mood"]
    cat = _cat_without("world", "studio_cyc", "tone", "grey")
    assert "grey" not in axis_values(p, cat, FMT)["tone"]


def test_detail_and_harness_cameras_are_never_openers_even_if_listed():
    """A selectable macro_detail (framing 'detail') and a selectable turntable injected into the dice
    openers are both rejected, in both modes: macro_detail by its framing, turntable by being harness-only,
    and still by its T1 tier cap once it is made selectable."""
    cat, p = copy.deepcopy(Catalog.load()), _p("pocket_watch")
    dice = {**DICE, "openers": ["macro_detail", "turntable", "low_hero_push", "arc_orbit"]}
    assert "macro_detail" in cat.selectable_ids("camera")
    for rollable in (True, False):
        v = axis_values(p, cat, FMT, dice=dice, rollable=rollable)["opener"]
        assert v == ["low_hero_push", "arc_orbit"], v
    cat._blocks[("camera", "turntable")]["directorSelectable"] = True    # a selectable turntable ...
    assert "turntable" in cat.selectable_ids("camera")
    for rollable in (True, False):
        assert "turntable" not in axis_values(p, cat, FMT, dice=dice, rollable=rollable)["opener"]  # ... never opens


# ---- Task 73: tone per world ('na' for worlds without a toneParam) ----

def _grown_street():
    """The real catalog with night_street director-selectable (it flips in Task 88) and rollable."""
    cat = copy.deepcopy(Catalog.load())
    cat._blocks[("world", "night_street")]["directorSelectable"] = True
    return cat, {**DICE, "worlds": ["studio_cyc", "night_street"]}


def test_tone_values_per_world():
    from engine.director.axes import TONE_NA, tone_values
    cat = Catalog.load()
    assert tone_values(cat.get("world", "studio_cyc")) == ["white", "grey", "black"]
    assert TONE_NA == "na"
    for w in ("night_street", "golden_field", "rain_courtyard"):
        assert cat.get("world", w)["toneParam"] is None and tone_values(cat.get("world", w)) == ["na"]


@pytest.mark.parametrize("model", NINE)
def test_a_studio_direction_is_unchanged(model):
    """The studio's tones are unchanged; since Task 88 the outdoor worlds add 'na' (tone does not apply)."""
    v = axis_values(_p(model), Catalog.load(), FMT)
    assert [t for t in v["tone"] if t != "na"] == ["white", "grey", "black"]
    assert ("na" in v["tone"]) == any(w != "studio_cyc" for w in v["world"])


def test_a_night_street_direction_has_tone_na_and_no_tone_param():
    from engine.director.dice import candidates
    from engine.director.direction import direction_of
    from engine.director.fallback import build_fallback
    from engine.director.job import make_job
    cat, dice = _grown_street()
    p = _p("sports_car")
    vals = axis_values(p, cat, FMT, dice=dice)
    assert "night_street" in vals["world"] and "na" in vals["tone"]
    cands = candidates(vals, dice=dice, catalog=cat)
    street = [c for c in cands if c["world"] == "night_street"]
    assert street and all(c["tone"] == "na" for c in street)
    assert all(c["tone"] != "na" for c in cands if c["world"] == "studio_cyc")
    assert not candidates(vals, pins={"world": "night_street", "tone": "white"}, dice=dice, catalog=cat)
    d = direction_of(street[0], "dice")
    assert d.id.split("/")[2] == "na"
    s = build_fallback(make_job("", p, cat, seed=3, direction=d), p, cat)
    assert s["world"]["id"] == "night_street" and "tone" not in s["world"]["params"]


def test_compatible_needs_the_catalog_for_the_world_rule():
    cat = Catalog.load()
    street = {"world": "night_street", "mood": "premium_dark", "tone": "na"}
    assert compatible(street, catalog=cat) and not compatible({**street, "tone": "black"}, catalog=cat)
    assert not compatible({"world": "studio_cyc", "mood": "clean", "tone": "na"}, catalog=cat)


def test_validate_axes_accepts_na_only_with_a_toneless_world():
    cat, _ = _grown_street()
    p = _p("sports_car")
    ok = {"world": "night_street", "mood": "teal_night", "tone": "na", "pace": "hype", "opener": "arc_orbit",
          "weather": "dry", "wind": "calm"}
    assert validate_axes(ok, p, cat, FMT) == []
    assert validate_axes({**ok, "tone": "black"}, p, cat, FMT) == ["tone"]
    assert validate_axes({**ok, "world": "studio_cyc"}, p, cat, FMT) == ["tone"]


def test_na_ids_round_trip_and_memory_records_them(tmp_path):
    from engine.director.direction import direction_of, make_id, parse_id
    from engine.director.memory import VarietyMemory
    cat, _ = _grown_street()
    p = _p("sports_car")
    axes = {"world": "night_street", "mood": "teal_night", "tone": "na", "pace": "hype", "opener": "arc_orbit",
            "weather": "dry", "wind": "calm"}
    assert parse_id(make_id(axes)) == axes
    mem = VarietyMemory(tmp_path, dev=True)
    user = mem.issue_user_token()
    known = axis_values(p, cat, FMT, rollable=False)
    mem.record(user, "0123456789abcdef", direction_of(axes, "dice"), seed=1, duration_s=10, known=known)
    assert mem.recent(user, "0123456789abcdef") == [make_id(axes)]
