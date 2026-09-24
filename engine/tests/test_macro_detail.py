import copy
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import DETAIL_CENTER, SAMPLES_PER_SHOT, check
from engine.geometry import project
from engine.profile import SubjectProfile
from engine.targets import resolve_target

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
_CAR = json.loads((FIX / "profile_car.json").read_text())
LAMP = {"kind": "emissive", "point": [2.25, 0.6, 0.7], "normal": [1, 0, 0], "score": 3.0}
CAR = SubjectProfile.from_dict({**_CAR, "detailPoints": [LAMP]})
BASE = json.loads((FIX / "script_valid.json").read_text())


def _macro(**shot):
    s = copy.deepcopy(BASE)
    s["shots"][1] = {"startS": 5, "endS": 10, "focus": "subject",
                     "camera": {"id": "macro_detail", "params": {}}, **shot}
    return s


def _codes(r, sev):
    return {i.code for i in r.issues if i.severity == sev}


def test_macro_on_a_detail_point_passes_and_keeps_it_centred():
    r = check(_macro(target={"detail": 0}), CAR, CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
    shot = r.script["shots"][1]
    sample = CAT.load_camera_path("macro_detail")
    tgt = resolve_target(shot, CAR, [])
    for k in range(SAMPLES_PER_SHOT):
        x, y, depth = project(sample(shot["camera"]["params"], CAR, k / (SAMPLES_PER_SHOT - 1), tgt),
                              tgt.point, "9:16")
        assert depth > 0 and max(abs(x), abs(y)) <= DETAIL_CENTER


def test_missing_target_defaults_to_the_best_detail_point():
    r = check(_macro(), CAR, CAT)
    assert r.ok and "detail_target_defaulted" in _codes(r, "repaired")
    assert r.script["shots"][1]["target"] == {"detail": 0}


def test_unknown_targets_are_errors():
    assert "unknown_target" in _codes(check(_macro(target={"detail": 3}), CAR, CAT), "error")
    assert "unknown_target" in _codes(check(_macro(target={"marker": "nope"}), CAR, CAT), "error")


def test_marker_target_works():
    s = _macro(target={"marker": "lamp"})
    s["markers"] = [{"id": "lamp", "anchor": {"space": "placed", "point": LAMP["point"], "normal": [1, 0, 0]},
                     "text": "macro on the headlight"}]
    assert check(s, CAR, CAT).ok


def test_too_close_macro_is_pushed_out_of_the_subject_margin():
    s = _macro(target={"detail": 0})
    s["shots"][1]["camera"]["params"] = {"distance": 0.1}
    r = check(s, CAR, CAT)
    assert r.ok and "camera_distance_adjusted" in _codes(r, "repaired")
