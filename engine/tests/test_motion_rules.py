"""Chunk 5 shared motion rules (engine/motion_rules.py), written before the motion blocks: each rule on a
TEST ONLY fixture motion, so a rule is proven apart from any one block."""
import copy
import json
import math
import shutil
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.issues import Issue
from engine.motion_path import SubjectPose
from engine.motion_rules import (peak_rate_deg_s, rest_time, spray_rule, strobe_rule, strobes)
from engine.tests.realism_catalog import catalog_with_fixtures
from engine.tests.test_director_package import _p

FIX = Path(__file__).parent / "fixtures"
T3 = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))

_SPIN = '''import math
from engine.motion_path import SubjectPose
def sample(params, profile, t, duration):
    u = min(max((t - params["startS"]) / params["turnS"], 0.0), 1.0)
    return SubjectPose(yaw=math.radians(params["turnDeg"]) * u)
def flags(params):
    return {"stops": True}
'''

_SPIN_PARAMS = {"turnDeg": {"type": "number", "min": 10.0, "max": 180.0, "default": 90.0},
                "turnS": {"type": "number", "min": 0.5, "max": 8.0, "default": 1.0},
                "startS": {"type": "number", "min": 0.0, "max": 8.0, "default": 1.0}}


def _cat(tmp_path, bid="test_rule", params=None, path_src=_SPIN, **extra):
    cat = catalog_with_fixtures(tmp_path)
    d = Path(cat.root) / "motion" / bid
    shutil.copytree(Path(cat.root) / "motion" / "test_glide", d)
    m = json.loads((d / "block.json").read_text(encoding="utf-8"))
    m.update({"id": bid, "params": params or _SPIN_PARAMS, "subjectMotion": {"stops": True}, **extra})
    (d / "block.json").write_text(json.dumps(m), encoding="utf-8")
    (d / "path.py").write_text(path_src, encoding="utf-8")
    return Catalog.load(cat.root)


def _script(bid="test_rule", params=None, placement="ground"):
    s = copy.deepcopy(T3)
    s["subject"] = {"placement": placement, "motion": {"id": bid, "params": dict(params or {})}}
    return s


def _codes(r, sev=None):
    return {i.code for i in r.issues if sev is None or i.severity == sev}


def test_peak_rate_and_rest_time_read_the_pose_track():
    at = lambda t: SubjectPose(yaw=math.radians(30.0) * min(max(t - 1.0, 0.0), 2.0))   # noqa: E731  30 deg/s, 1-3 s
    assert peak_rate_deg_s(at, 0.0, 10.0) == pytest.approx(30.0, rel=1e-3)
    assert rest_time(at, 10.0) == pytest.approx(3.0, abs=2.0 / 120)
    assert rest_time(lambda t: SubjectPose(), 10.0) == 0.0


def test_a_float_motion_repairs_ground_to_float_and_a_ground_motion_never_floats(tmp_path):
    cat = _cat(tmp_path / "f", placement="float")
    r = check(_script(), _p("pocket_watch"), cat)
    assert r.script["subject"]["placement"] == "float" and "placement_for_motion" in _codes(r, "repaired")
    cat = _cat(tmp_path / "g", placement="ground")
    r = check(_script(placement="float"), _p("pocket_watch"), cat)
    assert "motion_needs_ground" in _codes(r, "error") and not r.ok


def test_spin_rate_cap_lowers_the_named_param(tmp_path):
    cat = _cat(tmp_path, rateCap={"degS": 45.0, "repair": [{"param": "turnDeg", "dir": "down"}]})
    r = check(_script(params={"turnDeg": 90.0, "turnS": 1.0}), _p("pocket_watch"), cat)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    assert "spin_rate_cap" in _codes(r, "repaired")
    assert r.script["subject"]["motion"]["params"]["turnDeg"] == pytest.approx(45.0, abs=0.5)


def test_spin_rate_cap_that_cannot_be_met_is_an_error(tmp_path):
    cat = _cat(tmp_path, rateCap={"degS": 45.0, "repair": [{"param": "turnS", "dir": "down"}]})   # wrong way
    r = check(_script(params={"turnDeg": 90.0, "turnS": 1.0}), _p("pocket_watch"), cat)
    assert "motion_too_fast" in _codes(r, "error")
    assert r.script["subject"]["motion"]["params"]["turnS"] == 1.0          # left as it was


def test_an_integer_repair_param_steps_by_one(tmp_path):
    params = {**_SPIN_PARAMS, "turns": {"type": "number", "min": 1, "max": 3, "default": 3}}
    src = _SPIN.replace('math.radians(params["turnDeg"])', '2 * math.pi * params["turns"]')
    cat = _cat(tmp_path, params=params, path_src=src,
               rateCap={"degS": 800.0, "repair": [{"param": "turns", "dir": "down", "integer": True}]})
    r = check(_script(params={"turns": 3, "turnS": 1.0}), _p("pocket_watch"), cat)
    assert r.script["subject"]["motion"]["params"]["turns"] == 2 and "spin_rate_cap" in _codes(r)


def test_a_late_motion_starts_earlier_to_settle(tmp_path):
    cat = _cat(tmp_path)
    r = check(_script(params={"turnDeg": 30.0, "turnS": 2.0, "startS": 8.0}), _p("pocket_watch"), cat)
    assert r.ok and "motion_ends_unsettled" in _codes(r, "repaired")
    prm = r.script["subject"]["motion"]["params"]
    assert prm["startS"] + prm["turnS"] <= 10.0 - 0.8 + 1e-3


def test_a_motion_too_long_for_the_clip_shortens_or_errors(tmp_path):
    long_ = {**_SPIN_PARAMS, "turnS": {"type": "number", "min": 0.5, "max": 12.0, "default": 1.0}}
    cat = _cat(tmp_path / "a", params=long_, shorten=[{"param": "turnS", "dir": "down"}])
    r = check(_script(params={"turnDeg": 30.0, "turnS": 10.0, "startS": 3.0}), _p("pocket_watch"), cat)
    prm = r.script["subject"]["motion"]["params"]
    assert "motion_ends_unsettled" in _codes(r, "repaired") and prm["startS"] == 0.0
    assert 9.0 <= prm["turnS"] <= 9.2 + 1e-3                                 # shortened just enough
    cat = _cat(tmp_path / "b", params=long_)                                 # no shorten list
    r = check(_script(params={"turnDeg": 30.0, "turnS": 10.0, "startS": 3.0}), _p("pocket_watch"), cat)
    assert "motion_too_long" in _codes(r, "error") and r.script["subject"]["motion"]["params"]["startS"] == 3.0


def test_a_turn_under_a_locked_or_constant_speed_camera_is_refused(tmp_path):
    cat = _cat(tmp_path, needsCameraMove=True)
    s = _script(params={"turnDeg": 30.0, "turnS": 3.0, "startS": 0.5})
    assert "spin_needs_camera_move" not in _codes(check(copy.deepcopy(s), _p("pocket_watch"), cat))
    s["shots"][0]["camera"] = {"id": "turntable", "params": {"sweepDeg": 30.0}}
    assert "spin_needs_camera_move" in _codes(check(s, _p("pocket_watch"), cat), "error")


def test_strobe_nudges_with_a_short_shutter_and_only_notes_it_with_a_long_one():
    p = _p("sports_car")
    r = sorted(w["radius"] for w in p.wheels)[len(p.wheels) // 2]
    # a speed that strobes for 5 spokes (and no other count) at 30 fps, with a clear speed within 9%
    v = next(x / 10 for x in range(200, 1200) if strobes(x / 10, r, 30) == [5]
             and any(not strobes(x / 10 * (1 + k * 0.03), r, 30) for k in (-3, -2, -1, 1, 2, 3)))
    assert 5 in strobes(v, r, 30)
    s = {"format": {"fps": 30}, "subject": {"motion": {"id": "drive", "params": {"speedKmh": v}}}}
    issues = []
    strobe_rule(s, p, issues, shutter=0.25)
    new = s["subject"]["motion"]["params"]["speedKmh"]
    assert [i.code for i in issues] == ["wheel_strobe"] and new != v and not strobes(new, r, 30)
    assert abs(new / v - 1) <= 0.09 + 1e-9
    clear = {"format": {"fps": 30}, "subject": {"motion": {"id": "drive", "params": {"speedKmh": new}}}}
    issues = []
    strobe_rule(clear, p, issues, shutter=0.25)
    assert issues == [] and clear["subject"]["motion"]["params"]["speedKmh"] == new     # a clear one is untouched
    long_ = {"format": {"fps": 30}, "subject": {"motion": {"id": "drive", "params": {"speedKmh": v}}}}
    issues = []
    strobe_rule(long_, p, issues, shutter=0.5)
    assert [(i.code, i.severity) for i in issues] == [("wheel_strobe_risk", "info")]
    assert long_["subject"]["motion"]["params"]["speedKmh"] == v


def test_spray_is_reported_in_the_wet_only():
    issues = []
    spray_rule({"world": {"id": "night_street", "params": {"wetness": 0.6}}, "effects": []}, issues)
    assert [(i.code, i.severity) for i in issues] == [("spray_unavailable", "info")]
    issues = []
    spray_rule({"world": {"id": "night_street", "params": {"wetness": 0.0}}, "effects": []}, issues)
    assert issues == []
    assert isinstance(Issue("spray_unavailable", "", "", "info"), Issue)


def test_motion_flags_come_from_the_path_when_it_has_them(tmp_path):
    from engine.physics.applies import motion_flags
    cat = catalog_with_fixtures(tmp_path)
    s = _script("test_glide", {"metres": 0.0})
    assert cat.get("motion", "test_glide")["subjectMotion"] == {"translates": True}
    assert motion_flags(s, cat)["translates"] is False                      # path.flags(params) wins
    assert motion_flags(_script("test_glide", {"metres": 2.0}), cat)["translates"] is True
    assert motion_flags(_script("static"), cat) == {}


def test_motions_and_effects_are_size_checked(tmp_path):
    cat = _cat(tmp_path, subjectSizeM=[0.02, 0.05])
    r = check(_script(params={"turnDeg": 30.0}), _p("sneaker"), cat)
    assert ("subject_size_unsupported", "subject.motion.id") in {(i.code, i.path) for i in r.issues}
