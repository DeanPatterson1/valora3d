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
    assert rolled["weather"] == ["dry"] and rolled["wind"] == ["calm"]
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
