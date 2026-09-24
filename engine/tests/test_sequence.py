import copy
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict({**json.loads((FIX / "profile_car.json").read_text()), "detailPoints": [
    {"kind": "emissive", "point": [2.25, 0.6, 0.7], "normal": [1, 0, 0], "score": 3.0}]})
T3 = json.loads((FIX / "script_t3.json").read_text())


def _codes(r, sev):
    return {i.code for i in r.issues if i.severity == sev}


def test_t3_fixture_passes_the_sequence_stage():
    r = check(T3, CAR, CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]


def test_manifest_templates_name_real_cameras():
    m = CAT.get("edit", "sequence")
    for fam, slots in m["templates"].items():
        assert slots[0]["purpose"] == "hook" and slots[-1]["purpose"] == "hero", fam
        for slot in slots:
            for cam in slot["cameras"]:
                assert CAT.get("camera", cam) is not None, (fam, cam)


def test_too_few_shots_no_detail_bad_ending():
    s = copy.deepcopy(T3)
    s["shots"] = [dict(T3["shots"][0], endS=2.0), dict(T3["shots"][4], startS=2.0, endS=10.0)]
    codes = _codes(check(s, CAR, CAT), "error")
    assert {"seq_shot_count", "seq_no_detail", "seq_shot_length"} <= codes


def test_jump_cut_is_repaired_by_rotating_the_next_shot():
    s = copy.deepcopy(T3)
    s["shots"][2]["camera"]["params"].update({"startAzimuthDeg": -100, "sweepDeg": 20})
    s["shots"][3] = {"startS": 5.5, "endS": 7.0, "purpose": "motion", "focus": "subject",
                     "camera": {"id": "arc_orbit", "params": {"startAzimuthDeg": -80, "sweepDeg": 10, "lensMm": 70, "elevationDeg": 8}}}
    s["shots"][1]["camera"]["params"]["move"] = "push"  # keep one detail shot
    r = check(s, CAR, CAT)
    assert "jump_cut_rotated" in _codes(r, "repaired"), [i.to_dict() for i in r.issues]


def test_ending_without_stillness_is_settled():
    s = copy.deepcopy(T3)
    s["shots"][4]["camera"]["params"]["settleFrac"] = 0.0
    r = check(s, CAR, CAT)
    assert r.ok and "ending_settled" in _codes(r, "repaired")
    assert r.script["shots"][4]["camera"]["params"]["settleFrac"] >= 1.0 / 3.0


def test_missing_purposes_are_inferred():
    s = copy.deepcopy(T3)
    for sh in s["shots"]:
        sh.pop("purpose")
    r = check(s, CAR, CAT)
    assert r.ok and [sh["purpose"] for sh in r.script["shots"]] == ["hook", "detail", "motion", "detail", "hero"]
