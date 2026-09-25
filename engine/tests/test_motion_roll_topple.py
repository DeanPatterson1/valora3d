"""Task 77: roll and topple from shape facts (pure), honest when the shape can't."""
import math

import pytest

from engine.checker import check
from engine.motion_path import apply, posed_bounds, rotation_matrix
from engine.physics import shape
from engine.tests.motion_helpers import CAT, defaults, module, script, synthetic
from engine.tests.test_director_package import _p

ROLL, TOPPLE = module("roll"), module("topple")


def test_roll_is_no_slip_about_the_axis_and_comes_to_rest():
    can = synthetic("can")
    prm = defaults("roll")
    d, w, r, pv = ROLL._geometry(prm, can)
    D = ROLL.distance(prm, can)
    prev = None
    for k in range(0, 1001):
        t = k / 100
        pose = ROLL.sample(prm, can, t, 10.0)
        travel = math.hypot(*pose.offset[:2])
        q = pose.quat
        angle = 2.0 * math.atan2(sum(q[i + 1] * w[i] for i in range(3)), q[0])   # about the roll axis
        assert abs(angle) * r == pytest.approx(travel, rel=0.01, abs=1e-9)      # no slip
        assert rotation_matrix(pose)[2][2] <= 1.0
        c = apply(pv, pose, can)                                  # the axis line only translates, at height r:
        assert c[2] == pytest.approx(r, abs=1e-9)                # so its contact line stays on the ground
        if prev is not None:
            assert travel <= prev + 1e-12                        # it only rolls in
        prev = travel
    assert ROLL.sample(prm, can, ROLL.rest_s(prm, can, 10.0), 10.0).offset == pytest.approx((0.0, 0.0, 0.0))
    assert math.hypot(*ROLL.sample(prm, can, 0.0, 10.0).offset[:2]) == pytest.approx(D)


def test_roll_turns_about_the_roll_axis_vector():
    can = synthetic("can")
    ax = shape.roll_axis(shape.samples(can))["axis"]
    _, w, _, _ = ROLL._geometry(defaults("roll"), can)
    n = math.hypot(ax[0], ax[1])
    assert abs(abs(w[0] * ax[0] / n + w[1] * ax[1] / n) - 1.0) < 1e-9


def test_the_samples_stay_above_ground_while_rolling():
    can = synthetic("can")
    prm = defaults("roll")
    for k in range(0, 501):
        pose = ROLL.sample(prm, can, k / 50, 10.0)
        low = min(apply(p, pose, can)[2] for p in can.surfaceSamples[::7])
        assert low >= -0.02 * 0.033                                # sampled cylinder: 2% of r


def test_a_box_cannot_roll_and_says_why():
    r = check(script("roll"), _p("pocket_watch"), CAT)
    assert not r.ok
    iss = [i for i in r.issues if i.code == "motion_needs_profile"]
    assert iss and "rollAxis" in iss[0].message


def test_the_can_rolls_in_a_world_with_a_lane_and_not_in_the_studio():
    r = check(script("roll", {"startS": 0.2, "distanceFrac": 0.5}, world="rain_courtyard", lighting="hdri_only"),
              synthetic("can"), CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    # the studio allows 0.2 x longest; the shortest roll is 0.5 x longest: honestly refused, never faked
    r = check(script("roll"), synthetic("can"), CAT)
    assert not r.ok and "path_through_world" in {i.code for i in r.issues if i.severity == "error"}


def test_topple_pivots_on_its_edge_and_lands_on_its_side():
    bottle = synthetic("bottle")
    prm = defaults("topple")
    plan = TOPPLE._plan(prm, bottle)
    a, b = plan["edge"]
    for k in range(0, 601):
        pose = TOPPLE.sample(prm, bottle, k / 60, 10.0)
        for e in (a, b):
            assert apply(e, pose, bottle)[2] == pytest.approx(0.0, abs=1e-9)     # the pivot edge stays down
        lo, _ = posed_bounds(bottle, pose)
    end = TOPPLE.rest_s(prm, bottle, 10.0)
    last = TOPPLE.sample(prm, bottle, end, 10.0)
    assert TOPPLE.sample(prm, bottle, 9.9, 10.0) == last                       # at rest
    assert math.degrees(plan["land"]) == pytest.approx(90.0, abs=3.0)          # a cylinder lies on its side
    low = min(apply(p, last, bottle)[2] for p in bottle.surfaceSamples)
    assert low == pytest.approx(0.0, abs=2e-3)


def test_topple_rock_never_goes_through_the_ground():
    bottle = synthetic("bottle")
    prm = {**defaults("topple"), "rock": True}
    for k in range(0, 601):
        pose = TOPPLE.sample(prm, bottle, k / 60, 10.0)
        low = min(apply(p, pose, bottle)[2] for p in bottle.surfaceSamples[::5])
        assert low >= -2e-3


def test_a_squat_camera_cannot_topple():
    # the plan named the watch, but this watch profile stands on its edge (aspect 4.8): it can tip onto its
    # face. camera_01 (aspect 0.36) is the squat subject
    r = check(script("topple"), _p("camera_01"), CAT)
    assert not r.ok
    iss = [i for i in r.issues if i.code == "motion_needs_profile"]
    assert iss and "too squat to tip over" in iss[0].message


def test_the_bottle_topples_and_the_helmet_may():
    r = check(script("topple"), synthetic("bottle"), CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    ok, _ = TOPPLE.supports(defaults("topple"), _p("flighthelmet"))
    assert ok == (TOPPLE.aspect(_p("flighthelmet")) >= TOPPLE.MIN_ASPECT)


def test_a_short_roll_is_short_and_a_long_one_takes_the_plans_four_seconds():
    can = synthetic("can")
    assert ROLL.roll_s(defaults("roll"), can) == pytest.approx(2 * math.sqrt(0.18 / ROLL.A_ROLL))
    big = {**defaults("roll"), "distanceFrac": 1.2 / can.longest if 1.2 / can.longest <= 4 else 4.0}
    assert ROLL.roll_s({**defaults("roll"), "distanceFrac": 4.0}, _p("flighthelmet")) == ROLL.ROLL_MAX_S
    assert ROLL.roll_s(big, can) <= ROLL.ROLL_MAX_S


def test_shape_profiles_are_generated():
    """The synthetic can and bottle are exactly engine/tests/shape_profiles.py's output."""
    import json

    from engine.tests.shape_profiles import OUT, SHAPES
    for name, fn in SHAPES.items():
        assert json.loads((OUT / f"{name}.json").read_text(encoding="utf-8")) == json.loads(json.dumps(fn())), name
