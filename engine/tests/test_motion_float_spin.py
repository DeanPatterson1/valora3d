"""Task 75: float_drift and plinth_spin (pure)."""
import copy
import math

import pytest

from engine.checker import check
from engine.motion_rules import peak_rate_deg_s
from engine.tests.motion_helpers import CAT, defaults, module, script
from engine.tests.realism_catalog import catalog_with_fixtures
from engine.tests.test_director_package import _p

FLOAT, SPIN = module("float_drift"), module("plinth_spin")


def test_float_stays_inside_its_bob_band_and_turns_slowly():
    p = _p("pocket_watch")
    prm = defaults("float_drift")
    h = p.sizeM[2]
    lo, hi = (prm["liftFrac"] - prm["bobFrac"]) * h, (prm["liftFrac"] + prm["bobFrac"]) * h
    for k in range(0, 1201):
        pose = FLOAT.sample(prm, p, k / 120, 10.0)
        assert lo - 1e-12 <= pose.offset[2] <= hi + 1e-12
        assert abs(pose.pitch) <= math.radians(2.0) and abs(pose.roll) <= math.radians(2.0)
    fast = {**prm, "yawDegS": 20.0}
    assert peak_rate_deg_s(lambda t: FLOAT.sample(fast, p, t, 10.0), 0.0, 10.0) <= 20.0 + 1.0   # + the tiny sway
    assert FLOAT.flags(prm) == {}


def test_a_ground_float_script_is_repaired_to_float():
    r = check(script("float_drift"), _p("pocket_watch"), CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    assert r.script["subject"]["placement"] == "float"
    assert [(i.code, i.severity) for i in r.issues if i.code == "placement_for_motion"] == [("placement_for_motion", "repaired")]
    assert "contact_ground" not in [x["id"] for x in r.script["realism"]]      # floating: no ground realism


def test_a_ground_contact_motion_never_floats():
    r = check(script("drop_settle", placement="float"), _p("sneaker"), CAT)
    assert not r.ok and "motion_needs_ground" in {i.code for i in r.issues}


def test_spin_turns_once_inside_its_window_under_the_cap():
    p = _p("sneaker")
    prm = defaults("plinth_spin")
    t0, t1 = SPIN.window(prm, p, 10.0)
    assert (t0, t1) == (prm["startS"], prm["startS"] + prm["turnS"])
    assert SPIN.sample(prm, p, t1, 10.0).yaw == pytest.approx(math.radians(prm["turnDeg"]))
    assert SPIN.sample(prm, p, 9.9, 10.0).yaw == pytest.approx(math.radians(prm["turnDeg"]))   # holds after
    assert SPIN.sample(prm, p, t0, 10.0).yaw == 0.0
    at = lambda t: SPIN.sample(prm, p, t, 10.0)                                  # noqa: E731
    assert peak_rate_deg_s(at, 0.0, t0) == 0.0 and peak_rate_deg_s(at, t1, 10.0) == 0.0     # 0 outside
    assert peak_rate_deg_s(at, 0.0, 10.0) <= 45.0 + 1e-6
    assert SPIN.sample(prm, p, 5.0, 10.0).offset[2] == pytest.approx(SPIN.plinth_height(p))   # on the plinth


def test_the_spin_rate_cap_lowers_the_turn():
    p = _p("sneaker")
    r = check(script("plinth_spin", {"turnDeg": 180.0, "turnS": 3.0}), p, CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    iss = [i for i in r.issues if i.code == "spin_rate_cap"]
    assert iss and iss[0].severity == "repaired"
    prm = r.script["subject"]["motion"]["params"]
    assert prm["turnDeg"] < 180.0
    assert peak_rate_deg_s(lambda t: SPIN.sample(prm, p, t, 10.0), 0.0, 10.0) <= 45.0 + 1e-6


def test_no_params_make_a_plinth_spin_a_constant_360_turntable():
    """Every corner of the param space: never a full turn, never a constant rate over the clip."""
    p, spec = _p("sneaker"), CAT.get("motion", "plinth_spin")["params"]
    for turn in (spec["turnDeg"]["min"], spec["turnDeg"]["max"]):
        for ts in (spec["turnS"]["min"], spec["turnS"]["max"]):
            for st in (spec["startS"]["min"], spec["startS"]["max"]):
                r = check(script("plinth_spin", {"turnDeg": turn, "turnS": ts, "startS": st}), p, CAT)
                prm = r.script["subject"]["motion"]["params"]
                total = math.degrees(SPIN.sample(prm, p, 10.0, 10.0).yaw)
                assert total < 360.0
                rates = [abs(SPIN.sample(prm, p, k / 10 + 0.1, 10.0).yaw - SPIN.sample(prm, p, k / 10, 10.0).yaw)
                         for k in range(100)]
                assert max(rates) - min(rates) > 1e-6            # the rate changes: eased, then held
    assert "turntable" not in CAT.selectable_ids("camera")


def test_spin_needs_a_moving_camera(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = script("plinth_spin")
    assert check(copy.deepcopy(s), _p("sneaker"), cat).ok                  # the default shots all move
    locked = copy.deepcopy(s)
    for sh in locked["shots"]:
        if sh["startS"] < 7.0:                                             # every shot during the turn [1, 7]
            sh["camera"] = {"id": "turntable", "params": {"sweepDeg": 40.0}}
            sh.pop("target", None)
    r = check(locked, _p("sneaker"), cat)
    assert "spin_needs_camera_move" in {i.code for i in r.issues if i.severity == "error"}
