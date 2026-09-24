import json
from pathlib import Path
from engine.catalog import Catalog
from engine.checker import check
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()


def _load(name):
    return json.loads((FIX / name).read_text())


def _codes(result, severity):
    return {i.code for i in result.issues if i.severity == severity}


def test_valid_script_passes_for_car_and_watch_without_camera_repair():
    # Default distances (4.0 / 5.0 radii) must frame both a wide 4.5 m car and a 6 cm watch
    # in 9:16 as-is. If this fails, raise the block DEFAULT to the value the checker
    # converges to (rounded up) — never loosen MIN_COVERAGE or the in-frame rule.
    for prof in ("profile_car.json", "profile_watch.json"):
        r = check(_load("script_valid.json"), SubjectProfile.from_dict(_load(prof)), CAT)
        assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
        assert "camera_distance_adjusted" not in _codes(r, "repaired"), prof


def test_camera_too_close_is_pushed_out():
    s = _load("script_valid.json")
    s["shots"][1]["camera"]["params"].update({"distance": 1.2, "lensMm": 35})
    r = check(s, SubjectProfile.from_dict(_load("profile_car.json")), CAT)
    assert r.ok
    assert "camera_distance_adjusted" in _codes(r, "repaired")
    assert r.script["shots"][1]["camera"]["params"]["distance"] > 1.2


def test_tiny_subject_far_away_is_pulled_in():
    s = _load("script_valid.json")
    s["shots"][1]["camera"]["params"].update({"distance": 8.0, "lensMm": 18})
    r = check(s, SubjectProfile.from_dict(_load("profile_watch.json")), CAT)
    assert r.ok
    assert r.script["shots"][1]["camera"]["params"]["distance"] < 8.0


def test_subject_outside_supported_size_is_an_error_not_a_repair():
    prof = _load("profile_car.json")
    prof["sizeM"] = [30.0, 10.0, 10.0]
    prof["boundsMin"] = [-15.0, -5.0, 0.0]
    prof["boundsMax"] = [15.0, 5.0, 10.0]
    r = check(_load("script_valid.json"), SubjectProfile.from_dict(prof), CAT)
    assert not r.ok and "subject_size_unsupported" in _codes(r, "error")


def test_unfixable_framing_is_an_error(monkeypatch):
    # 35 mm converges unpatched (see the test above); only the narrowed range makes it fail.
    import engine.checker as chk
    s = _load("script_valid.json")
    s["shots"][1]["camera"]["params"].update({"distance": 1.2, "lensMm": 35})
    real_get = CAT.get

    def narrow(kind, bid):
        m = real_get(kind, bid)
        if kind == "camera" and bid == "arc_orbit":
            m = {**m, "params": {**m["params"], "distance": {**m["params"]["distance"], "max": 1.2}}}
        return m

    monkeypatch.setattr(CAT, "get", narrow)
    r = chk.check(s, SubjectProfile.from_dict(_load("profile_car.json")), CAT)
    assert not r.ok and "framing_unfixable" in _codes(r, "error")


def test_float_placement_world_without_ground_ok_and_structure_errors_propagate():
    s = _load("script_valid.json")
    s["world"]["id"] = "moon"
    r = check(s, SubjectProfile.from_dict(_load("profile_car.json")), CAT)
    assert not r.ok and "unknown_block" in _codes(r, "error")
