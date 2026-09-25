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
    assert check(s, _p("sports_car"), cat).script["realism"][0]["params"] == {"sinkMm": 9.0}
    s["realism"] = [{"kind": "realism", "id": "contact_ground", "params": {"sinkMm": 999}}]
    r = check(s, _p("toycar"), cat)
    assert r.script["realism"][0]["params"] == {"sinkMm": 0.0}
    assert any(i.code == "realism_param_ignored" and i.severity == "info" for i in r.issues)


def test_a_pinned_sink_obeys_the_same_cap_as_the_auto_value(tmp_path):
    # review fix 1: a 30 mm pin must not bury a 2.9 cm toy (contact.MAX_SINK_FRAC of its height)
    from engine.physics.contact import MAX_SINK_FRAC
    cat = _cat(tmp_path, [CONTACT])
    s = _script()
    s["realism"] = [{"kind": "realism", "id": "contact_ground", "params": {"sinkMm": 30.0}}]
    r = check(s, _p("toycar"), cat)
    cap = 1000.0 * MAX_SINK_FRAC * _p("toycar").sizeM[2]
    assert r.script["realism"][0]["params"]["sinkMm"] == pytest.approx(cap)
    assert any(i.code == "realism_param_capped" and i.severity == "info" for i in r.issues)


def _cat_with_lawn(tmp_path, manifests):
    """_cat plus a grass world with a breeze (a copy of studio_cyc's builder, grass/wind facts only)."""
    cat = _cat(tmp_path, manifests)
    root = Path(cat.root)
    lawn = root / "world" / "lawn_probe"
    shutil.copytree(root / "world" / "studio_cyc", lawn)
    m = json.loads((lawn / "block.json").read_text(encoding="utf-8"))
    m.update(id="lawn_probe", groundType="grass", hasFoliage=False, windDefault=2.0, studio=False)
    (lawn / "block.json").write_text(json.dumps(m), encoding="utf-8")
    return Catalog.load(root)


def test_a_rechecked_script_re_resolves_system_output_and_keeps_only_real_pins(tmp_path):
    # review fix 2: `engine check` then compile_scene checks the same script twice; the first pass's
    # resolved values must not come back as pins (a world change must re-resolve sink and wind).
    from engine.physics.contact import sink_m
    cat = _cat_with_lawn(tmp_path, [CONTACT])
    first = check(_script(), _p("sports_car"), cat).script
    again = check(first, _p("sports_car"), cat)
    assert again.script["realism"] == first["realism"] and again.script["wind"] == first["wind"]
    assert "wind_from_script" not in [i.code for i in again.issues]
    moved = copy.deepcopy(first)
    moved["world"] = {"id": "lawn_probe", "params": {}}
    r = check(moved, _p("sports_car"), cat)
    want = 1000.0 * sink_m("grass", _p("sports_car").sizeM[2])
    assert r.script["realism"][0]["params"]["sinkMm"] == pytest.approx(want) and want > 0
    assert r.script["wind"]["params"]["speedMs"] == 2.0
    pinned = copy.deepcopy(_script())
    pinned["realism"] = [{"kind": "realism", "id": "contact_ground", "params": {"sinkMm": 1.0}}]
    pinned = check(pinned, _p("sports_car"), cat).script
    pinned["world"] = {"id": "lawn_probe", "params": {}}
    assert check(pinned, _p("sports_car"), cat).script["realism"][0]["params"]["sinkMm"] == 1.0   # a real pin stays


def test_an_auto_param_the_resolver_cannot_compute_keeps_its_default(tmp_path):
    # review fix 12: a manifest naming an autoParam AUTO does not produce must not crash check()
    odd = _manifest("odd_block", {"placement": ["ground"]},
                    {"x": {"type": "number", "min": 0, "max": 1, "default": 0.5}}, auto=["x"])
    cat = _cat(tmp_path, [odd])
    r = check(_script(), _p("toycar"), cat)
    assert r.ok and r.script["realism"][0]["params"] == {"x": 0.5}


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
