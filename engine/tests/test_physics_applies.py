import copy
import json
import shutil
from pathlib import Path

import pytest

from engine.catalog import BLOCKS_DIR, Catalog
from engine.checker import check
from engine.issues import errors
from engine.physics.applies import ORDER, facts, resolve_realism, resolve_wind
from engine.profile import SubjectProfile
from engine.realism import realism_defaults

FIX = Path(__file__).parent / "fixtures"


def _p(name):
    return SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))


def _script():
    return json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))


def _manifest(bid, applies, params=None, auto=()):
    return {"id": bid, "kind": "realism", "description": "test", "alwaysOn": True, "directorSelectable": False,
            "appliesWhen": applies, "autoParams": list(auto), "params": params or {},
            "subjectSizeM": [0.01, 30.0], "aspects": ["9:16", "16:9", "1:1", "4:5"], "costWeight": 1.0,
            "tierMax": "T3", "tags": {"mood": [], "energy": [], "palette": []}}


def _cat(tmp_path, manifests):
    root = tmp_path / "blocks"
    shutil.copytree(BLOCKS_DIR, root, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.rmtree(root / "realism", ignore_errors=True)          # the test controls the realism set
    for m in manifests:
        d = root / "realism" / m["id"]
        d.mkdir(parents=True)
        (d / "block.json").write_text(json.dumps(m), encoding="utf-8")
    return Catalog.load(root)


SINK = {"sinkMm": {"type": "number", "min": 0, "max": 30, "default": 5}}
CONTACT = _manifest("contact_ground", {"placement": ["ground"]}, SINK, auto=["sinkMm"])
TYRE = _manifest("tyre_contact", {"placement": ["ground"], "profile": ["wheels", "tyreBand"]},
                 {"patchLenFrac": {"type": "number", "min": 0.3, "max": 0.6, "default": 0.45}})
ROLL = _manifest("wheel_roll", {"profile": ["wheelsSeparable"], "motion": ["translates"]})
DUST = _manifest("shaft_dust", {"effects": ["haze_volume"]})
GLASS = _manifest("glass_caustics", {"materials": {"glass": 0.05}})


def _ids(s):
    return [r["id"] for r in s.get("realism", [])]


def test_rules_pick_the_blocks_that_fit_each_subject(tmp_path):
    cat = _cat(tmp_path, [CONTACT, TYRE, ROLL, DUST, GLASS])
    car = check(_script(), _p("sports_car"), cat)
    watch = check(_script(), _p("pocket_watch"), cat)
    assert car.ok and watch.ok
    assert _ids(car.script) == ["contact_ground", "tyre_contact"]            # static: no roll; no haze; no glass
    assert _ids(watch.script) == ["contact_ground", "glass_caustics"]
    for r in (car, watch):
        assert all(i.severity == "info" for i in r.issues if i.code.startswith(("realism_", "wind_")))


def test_effects_gate(tmp_path):
    cat = _cat(tmp_path, [DUST])
    s = _script()
    s["effects"] = [{"id": "haze_volume", "params": {}}]
    assert _ids(check(s, _p("toycar"), cat).script) == ["shaft_dust"]


def test_low_confidence_wheels_are_skipped_with_an_info_issue(tmp_path):
    cat = _cat(tmp_path, [TYRE])
    p = copy.deepcopy(_p("sports_car"))
    for w in p.wheels:
        w["confidence"] = "low"
    assert facts(p)["wheels"] == (False, True)
    r = check(_script(), p, cat)
    assert _ids(r.script) == [] and [i.code for i in r.issues if i.path == "realism.tyre_contact"] == [
        "realism_skipped_low_confidence"]


def test_auto_params_and_pins(tmp_path):
    cat = _cat(tmp_path, [CONTACT])
    s = _script()
    r = check(s, _p("toycar"), cat)
    assert r.script["realism"][0]["params"] == {"sinkMm": 0.0}             # studio: no sink
    s["realism"] = [{"kind": "realism", "id": "contact_ground", "params": {"sinkMm": 9.0}}]
    assert check(s, _p("toycar"), cat).script["realism"][0]["params"] == {"sinkMm": 9.0}
    s["realism"] = [{"kind": "realism", "id": "contact_ground", "params": {"sinkMm": 999}}]
    r = check(s, _p("toycar"), cat)
    assert r.script["realism"][0]["params"] == {"sinkMm": 0.0}
    assert any(i.code == "realism_param_ignored" and i.severity == "info" for i in r.issues)


def test_order_is_the_build_order_and_unknown_given_entries_are_dropped(tmp_path):
    cat = _cat(tmp_path, [GLASS, CONTACT])
    s = _script()
    s["realism"] = [{"kind": "realism", "id": "wheel_roll", "params": {}}]
    r = check(s, _p("pocket_watch"), cat)
    assert _ids(r.script) == ["contact_ground", "glass_caustics"]
    assert ORDER.index("wheel_roll") < ORDER.index("tyre_contact")        # spin before flatten
    assert ORDER.index("suspension") < ORDER.index("wheel_roll")          # body motion first


def test_wind_defaults_from_the_world_and_a_script_wind_is_kept():
    cat = Catalog.load()
    if cat.get("field", "wind") is None:
        pytest.skip("the wind field block lands in Task 13")
    r = check(_script(), _p("toycar"), cat)
    w = r.script["wind"]
    assert w["id"] == "wind" and w["params"]["speedMs"] == 0.0 and 0 <= w["params"]["directionDeg"] < 360
    assert check(_script(), _p("toycar"), cat).script["wind"] == w          # seeded: deterministic
    s = _script()
    s["wind"] = {"id": "wind", "params": {"speedMs": 4.0}}
    assert check(s, _p("toycar"), cat).script["wind"]["params"]["speedMs"] == 4.0


def test_realism_defaults_with_a_script_equals_the_checker(tmp_path):
    cat = _cat(tmp_path, [CONTACT, TYRE])
    s = check(_script(), _p("sports_car"), cat).script
    assert realism_defaults(_p("sports_car"), cat, script=_script()) == s["realism"]


def test_resolution_is_pure_and_adds_no_errors(tmp_path):
    cat = _cat(tmp_path, [CONTACT, TYRE])
    s, issues = _script(), []
    resolve_wind(s, cat, issues)
    resolve_realism(s, _p("sports_car"), cat, issues)
    assert errors(issues) == [] and all(i.severity == "info" for i in issues)
