"""Task 79: drive, the hand-off H5 contract (pure + checker)."""
import math

import pytest

from engine.checker import check
from engine.motion_path import horizontal_travel
from engine.physics import suspension as S
from engine.physics.applies import _auto_suspension
from engine.tests.motion_helpers import CAT, defaults, module, script
from engine.tests.test_director_package import _p

DRIVE = module("drive")
FWD = {**defaults("drive"), "facing": "forward"}          # an explicit nose: the arcs stay arcs


def _track(prm, p, t0=0.0, t1=10.0, n=2000):
    ts = [t0 + (t1 - t0) * k / n for k in range(n + 1)]
    return ts, [DRIVE.sample(prm, p, t, 10.0) for t in ts]


@pytest.mark.parametrize("path", ["straight", "arc_left", "arc_right", "s_curve", "stop"])
def test_heading_is_the_path_tangent(path):
    p = _p("sports_car")
    prm = {**FWD, "path": path}
    fx, fy = DRIVE.forward(prm, p)
    ts, poses = _track(prm, p)
    checked = 0
    for (ta, a), (tb, b) in zip(zip(ts, poses), zip(ts[1:], poses[1:])):
        dx, dy = b.offset[0] - a.offset[0], b.offset[1] - a.offset[1]
        if math.hypot(dx, dy) < 1e-4:
            continue                                                   # waiting or holding
        travel = math.atan2(dy, dx)
        body = math.atan2(fy, fx) + (a.yaw + b.yaw) / 2
        assert abs((travel - body + math.pi) % (2 * math.pi) - math.pi) < 2e-3, (path, ta)
        checked += 1
    assert checked > 100


def test_an_s_curve_turns_smoothly():
    p = _p("sports_car")
    ts, poses = _track({**FWD, "path": "s_curve"}, p)
    yaws = [q.yaw for q in poses]
    assert max(abs(a - b) for a, b in zip(yaws, yaws[1:])) < 0.01
    assert max(yaws) - min(yaws) > 0.1 and abs(yaws[-1] - yaws[0]) < 1e-9   # it turns, and comes back straight


def test_the_speed_never_exceeds_the_set_speed_and_the_stop_is_real():
    p = _p("sports_car")
    for accel in ("cruise", "launch", "brake_to_stop"):
        prm = {**FWD, "accel": accel}
        ts, poses = _track(prm, p)
        v = [math.hypot(b.offset[0] - a.offset[0], b.offset[1] - a.offset[1]) / (tb - ta)
             for (ta, a), (tb, b) in zip(zip(ts, poses), zip(ts[1:], poses[1:]))]
        assert max(v) <= prm["speedKmh"] / 3.6 + 1e-6, accel
    prm = {**FWD, "accel": "brake_to_stop"}
    end = prm["startS"] + prm["driveS"]
    assert DRIVE.sample(prm, p, end, 10.0).offset == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)   # on its mark
    assert DRIVE.speed(prm, prm["driveS"]) == pytest.approx(0.0, abs=1e-9) and DRIVE.flags(prm) == {"translates": True, "stops": True}
    assert DRIVE.flags({**FWD, "path": "stop"})["stops"] and not DRIVE.flags(FWD)["stops"]


def _street(params=None, **kw):
    return script("drive", params, world="night_street", lighting="rim_neon", **kw)


def test_brake_to_stop_rests_before_the_end():
    p = _p("sports_car")
    r = check(_street({"accel": "brake_to_stop", "startS": 6.0, "driveS": 4.0, "facing": "forward"}), p, CAT)
    prm = r.script["subject"]["motion"]["params"]
    assert prm["startS"] + prm["driveS"] <= 10.0 - 0.8 + 1e-6
    assert "motion_ends_unsettled" in {i.code for i in r.issues}


def test_low_nose_confidence_drives_a_straight_side_pass_by():
    p = _p("sports_car")
    r = check(_street({"path": "arc_left"}), p, CAT)                  # facing auto: every eval car's nose is low
    assert r.script["subject"]["motion"]["params"]["path"] == "straight"
    assert ("vehicle_nose_uncertain", "info") in {(i.code, i.severity) for i in r.issues}
    r = check(_street({"path": "arc_left", "facing": "forward"}), p, CAT)
    assert r.script["subject"]["motion"]["params"]["path"] == "arc_left"


def test_the_lane_caps_the_speed_and_the_studio_refuses_the_drive():
    p = _p("sports_car")
    lane = CAT.get("world", "night_street")["driveLaneM"]
    r = check(_street({"speedKmh": 120.0, "driveS": 6.0, "facing": "forward"}), p, CAT)
    prm = r.script["subject"]["motion"]["params"]
    assert "vehicle_speed_cap" in {i.code for i in r.issues} and prm["speedKmh"] < 120.0
    assert DRIVE.lane_distance(prm, p) <= lane + 1e-6
    r = check(script("drive"), p, CAT)
    assert not r.ok and "path_through_world" in {i.code for i in r.issues if i.severity == "error"}


def test_realism_rolls_the_wheels_and_the_body():
    p = _p("sports_car")
    r = check(_street({"facing": "forward"}), p, CAT)
    ids = [x["id"] for x in r.script["realism"]]
    assert "wheel_roll" in ids and "suspension" in ids
    assert p.vehicle["vehicleClass"] == "sport" and S.roll_deg_per_g("sport") == 2.0


def test_a_toy_class_vehicle_does_not_roll():
    assert S.roll_deg_per_g("toy") == 0.0 and S.roll_deg_per_g("offroad") == 6.0 and S.roll_deg_per_g("comfort") == 5.0
    assert "rollDegPerG" not in _auto_suspension(_p("sports_car"), None, {})    # a constant: the baseline is unchanged


def test_a_watch_cannot_drive_and_says_why():
    r = check(_street(), _p("pocket_watch"), CAT)
    iss = [i for i in r.issues if i.code == "motion_needs_profile"]
    assert iss and "wheels" in iss[0].message


def test_driving_in_the_rain_notes_the_missing_spray():
    p = _p("sports_car")
    s = _street({"facing": "forward"})
    s["effects"] = list(s.get("effects", [])) + [{"id": "rain", "params": {}}]
    r = check(s, p, CAT)
    assert ("spray_unavailable", "info") in {(i.code, i.severity) for i in r.issues}


def test_pass_by_is_centred_on_the_mark():
    p = _p("sports_car")
    prm = {**FWD}
    mid = prm["startS"] + prm["driveS"] / 2
    assert DRIVE.sample(prm, p, mid, 10.0).offset == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    travel = horizontal_travel(lambda t: DRIVE.sample(prm, p, t, 10.0), 0.0, 10.0)
    assert travel == pytest.approx(DRIVE.lane_distance(prm, p) / 2, rel=0.02)


def test_the_lane_cap_keeps_the_fastest_speed_that_fits():
    from engine.motion_rules import speed_rule
    p = _p("sports_car")
    s = _street({"speedKmh": 120.0, "driveS": 6.0, "facing": "forward"})
    s["shots"] = []                                        # the lane alone (no camera sweep to judge)
    lane = CAT.get("world", "night_street")["driveLaneM"]
    issues = []
    speed_rule(s, CAT, p, issues)
    prm = s["subject"]["motion"]["params"]
    assert DRIVE.lane_distance(prm, p) <= lane + 1e-9
    assert DRIVE.lane_distance({**prm, "speedKmh": prm["speedKmh"] + 0.01}, p) > lane    # the fastest that fits
    assert [i.code for i in issues] == ["vehicle_speed_cap"]
