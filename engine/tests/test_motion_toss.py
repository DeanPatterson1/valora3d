"""Task 78: toss_tumble about a stable principal axis (pure)."""
import math

import pytest

from engine.checker import check
from engine.motion_path import apply, rotation_matrix
from engine.motion_rules import peak_rate_deg_s
from engine.physics import shape
from engine.tests.motion_helpers import CAT, defaults, module, script
from engine.tests.test_director_package import _p

TOSS = module("toss_tumble")


def _air(prm, p):
    return TOSS.air_s(prm, p)


def test_the_arc_peaks_at_arc_height_and_lands_in_the_rest_pose():
    p = _p("sneaker")
    prm = defaults("toss_tumble")
    T, H = _air(prm, p), prm["arcHeightFrac"] * p.sizeM[2]
    t0 = prm["startS"]
    mid = TOSS.sample(prm, p, t0 + T / 2, 10.0)
    plan = TOSS._plan(prm, p)
    # at the apex the centroid is H up (plus any lift the turned body needs to clear its own footprint)
    assert mid.offset[2] >= H - 1e-9
    assert T == pytest.approx(2 * math.sqrt(2 * H / 9.81) / prm["timeScale"])
    end = TOSS.sample(prm, p, t0 + T, 10.0)
    R = rotation_matrix(end)
    err = math.degrees(math.acos(max(-1.0, min(1.0, (R[0][0] + R[1][1] + R[2][2] - 1) / 2))))
    assert err < 1.0 and end.offset == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    assert TOSS.sample(prm, p, 9.9, 10.0) == end                              # holds
    assert plan["c"] == pytest.approx(tuple(sum(s["p"][i] for s in shape.samples(p)) / len(shape.samples(p))
                                            for i in range(3)))


def test_the_spin_axis_is_a_stable_principal_axis():
    for model in ("sneaker", "pocket_watch", "vintage_microscope"):
        p = _p(model)
        ax = TOSS.stable_axis(defaults("toss_tumble"), p)
        axes = shape.principal_axes(shape.samples(p))
        dots = [abs(sum(ax[i] * a[i] for i in range(3))) for a in axes]
        assert max(dots[0], dots[2]) == pytest.approx(1.0, abs=1e-9) and dots[1] < 1.0 - 1e-6, model
        prm = defaults("toss_tumble")
        pose = TOSS.sample(prm, p, prm["startS"] + _air(prm, p) / 3, 10.0)
        R = rotation_matrix(pose)
        assert [sum(R[i][j] * ax[j] for j in range(3)) for i in range(3)] == pytest.approx(list(ax), abs=1e-9)


def test_nothing_goes_below_the_ground():
    p = _p("sneaker")
    prm = {**defaults("toss_tumble"), "spins": 2}
    step = max(1, len(p.surfaceSamples) // 300)
    for k in range(0, 601):
        pose = TOSS.sample(prm, p, k / 60, 10.0)
        low = min(apply(q, pose, p)[2] for q in p.surfaceSamples[::step])
        assert low >= -1e-3 * p.longest, (k, low)


def test_spin_rate_cap_lowers_spins_then_slows_time():
    p = _p("sneaker")
    r = check(script("toss_tumble", {"spins": 3}), p, CAT)
    prm = r.script["subject"]["motion"]["params"]
    assert "spin_rate_cap" in {i.code for i in r.issues}
    assert prm["spins"] < 3 and float(prm["spins"]).is_integer()
    peak = peak_rate_deg_s(lambda t: TOSS.sample(prm, p, t, 10.0), 0.0, 10.0)
    assert peak <= 360.0 + 1e-6


def test_a_car_is_not_tossed():
    r = check(script("toss_tumble"), _p("sports_car"), CAT)
    assert ("subject_size_unsupported", "subject.motion.id") in {(i.code, i.path) for i in r.issues}


def test_flags():
    assert TOSS.flags({}) == {"translates": True, "lands": True, "stops": True}
