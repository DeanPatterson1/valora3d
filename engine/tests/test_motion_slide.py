"""Task 76: slide_in (pure)."""
import math

import pytest

from engine.checker import check
from engine.motion_path import horizontal_travel
from engine.tests.motion_helpers import CAT, defaults, module, script
from engine.tests.test_director_package import _p

SLIDE = module("slide_in")


def test_the_slide_is_continuous_and_stops_at_its_mark():
    p = _p("sneaker")
    prm = defaults("slide_in")
    ts = [k / 240 for k in range(0, 2401)]
    xs = [SLIDE.sample(prm, p, t, 10.0).offset[0] for t in ts]
    assert max(abs(a - b) for a, b in zip(xs, xs[1:])) < 0.01 * p.longest          # no jumps
    end = prm["startS"] + prm["durationS"]
    assert SLIDE.sample(prm, p, end, 10.0).offset == pytest.approx((0.0, 0.0, 0.0))
    v = lambda t: (SLIDE.sample(prm, p, t + 1e-4, 10.0).offset[0] - SLIDE.sample(prm, p, t - 1e-4, 10.0).offset[0]) / 2e-4  # noqa: E731
    assert abs(v(end - 1e-3)) < 0.01 * p.longest                                  # velocity 0 at the stop
    assert v(prm["startS"] + 1e-3) > v(prm["startS"] + prm["durationS"] / 2) > 0   # decelerating
    assert SLIDE.flags(prm) == {"translates": True, "stops": True}


def test_the_studio_keeps_the_slide_short():
    p = _p("sneaker")
    r = check(script("slide_in", {"distanceFrac": 2.0}), p, CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    assert "motion_travel_capped" in {i.code for i in r.issues}
    prm = r.script["subject"]["motion"]["params"]
    travel = horizontal_travel(lambda t: SLIDE.sample(prm, p, t, 10.0), 0.0, 10.0)
    assert travel <= 0.2 * p.longest + 1e-9


def test_outdoors_the_drive_lane_caps_it():
    p = _p("sports_car")
    lane = CAT.get("world", "night_street")["driveLaneM"]
    r = check(script("slide_in", {"distanceFrac": 3.0}, world="night_street", lighting="rim_neon"), p, CAT)
    prm = r.script["subject"]["motion"]["params"]
    travel = horizontal_travel(lambda t: SLIDE.sample(prm, p, t, 10.0), 0.0, 10.0)
    assert travel <= lane + 1e-9
    assert travel == pytest.approx(min(3.0 * p.longest, lane), rel=1e-3)


def test_a_late_slide_settles_before_the_end():
    p = _p("sneaker")
    r = check(script("slide_in", {"startS": 8.0, "durationS": 3.0}), p, CAT)
    assert r.ok
    prm = r.script["subject"]["motion"]["params"]
    assert prm["startS"] + prm["durationS"] <= 10.0 - 0.8 + 1e-9
    assert "motion_ends_unsettled" in {i.code for i in r.issues}


def test_direction_sets_where_it_comes_from():
    p = _p("sneaker")
    prm = {**defaults("slide_in"), "directionDeg": 90.0}
    x, y, _ = SLIDE.sample(prm, p, 0.0, 10.0).offset
    assert abs(x) < 1e-9 and y == pytest.approx(-prm["distanceFrac"] * p.longest)   # comes from -y, travels +y
    assert math.isclose(SLIDE.sample(prm, p, 0.0, 10.0).yaw, 0.0)                     # it does not turn
