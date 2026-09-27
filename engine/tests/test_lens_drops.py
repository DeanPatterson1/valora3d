"""Task 68: lens_drops checker rules (pure)."""
import copy
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.tests.test_director_package import _p
from engine.weather_rules import lens_drop_rules

FIX = Path(__file__).parent / "fixtures"
T3 = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))   # shots: full, detail, full, detail, full


def _script(shot, rain=True):
    s = copy.deepcopy(T3)
    s["world"] = {"id": "rain_courtyard", "params": {}}
    s["lighting"] = {"id": "hdri_only", "params": {}}   # the courtyard's own light (round 13: an unpaired rig fails)
    s["effects"] = list(s.get("effects", [])) + ([{"id": "rain", "params": {}}] if rain else []) + \
        [{"id": "lens_drops", "params": {"shot": shot, "amount": 0.3}}]
    return s


def _run(s):
    issues = []
    lens_drop_rules(s, Catalog.load(), issues)
    return issues


def test_lens_drops_need_rain():
    assert [(i.code, i.severity) for i in _run(_script(0, rain=False))] == [("effect_needs_source", "error")]
    assert _run(_script(0)) == []


def test_a_detail_shot_moves_to_the_nearest_full_shot():
    s = _script(1)                                          # shot 1 is macro_detail
    issues = _run(s)
    assert [(i.code, i.severity) for i in issues] == [("lens_drops_moved", "repaired")]
    assert s["effects"][-1]["params"]["shot"] in (0, 2)
    s = _script(3)
    _run(s)
    assert s["effects"][-1]["params"]["shot"] in (2, 4)


def test_no_full_shot_is_an_error():
    s = _script(1)
    for sh in s["shots"]:
        sh["camera"] = copy.deepcopy(T3["shots"][1]["camera"])
    assert [(i.code, i.severity) for i in _run(s)] == [("lens_drops_no_shot", "error")]


def test_out_of_range_and_one_per_clip():
    s = _script(7)
    r = check(s, _p("sports_car"), Catalog.load())
    assert "effect_off_screen" in {i.code for i in r.issues if i.severity == "error"}
    s = _script(0)
    s["effects"].append({"id": "lens_drops", "params": {"shot": 2}})
    r = check(s, _p("sports_car"), Catalog.load())
    assert "effect_max_per_clip" in {i.code for i in r.issues if i.severity == "error"}


def test_the_checked_script_keeps_lens_drops_with_rain():
    r = check(_script(1), _p("sports_car"), Catalog.load())
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    ld = next(e for e in r.script["effects"] if e["id"] == "lens_drops")
    assert ld["params"]["shot"] in (0, 2)
