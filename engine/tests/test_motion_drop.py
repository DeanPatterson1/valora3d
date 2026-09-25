"""Task 74: drop_settle, analytic bounces (pure)."""
import math

import pytest

from engine.checker import check
from engine.motion_path import posed_bounds
from engine.tests.motion_helpers import CAT, defaults, module, script
from engine.tests.test_director_package import _p

MOD = module("drop_settle")
PATH = MOD.sample
PARAMS = defaults("drop_settle")
FPS = 30


def test_height_at_start_is_height_frac_of_the_subject():
    p = _p("sneaker")
    assert MOD.height(PARAMS, p, PARAMS["startS"]) == pytest.approx(PARAMS["heightFrac"] * p.sizeM[2])
    assert PATH(PARAMS, p, PARAMS["startS"], 10.0).offset[2] == pytest.approx(PARAMS["heightFrac"] * p.sizeM[2])


def test_first_contact_is_real_gravity_slowed_by_time_scale():
    p = _p("sneaker")
    h = PARAMS["heightFrac"] * p.sizeM[2]
    want = PARAMS["startS"] + math.sqrt(2 * h / 9.81) / PARAMS["timeScale"]
    first = next(t / (4 * FPS) for t in range(1, 40 * FPS) if MOD.height(PARAMS, p, t / (4 * FPS)) <= 0.02 * h)
    assert abs(first - want) <= 1.0 / FPS
    assert MOD.contacts(PARAMS, p)[0] == pytest.approx(want)


@pytest.mark.parametrize("bounces", [1, 2, 3])
def test_each_bounce_peaks_at_h_e_to_the_2n(bounces):
    p = _p("sneaker")
    prm = {**PARAMS, "bounces": bounces}
    h, e = prm["heightFrac"] * p.sizeM[2], prm["restitution"]
    cs = MOD.contacts(prm, p)
    for n in range(1, bounces + 1):
        mid = (cs[n - 1] + cs[n]) / 2
        assert MOD.height(prm, p, mid) == pytest.approx(h * e ** (2 * n), rel=1e-9)


def test_nothing_ever_goes_below_the_ground():
    for model in ("sneaker", "pocket_watch", "vintage_microscope"):
        p = _p(model)
        prm = {**PARAMS, "tiltDeg": 12.0, "bounces": 3}
        for k in range(0, 10 * FPS * 4):
            lo, _ = posed_bounds(p, PATH(prm, p, k / (4 * FPS), 10.0))
            assert lo[2] >= -1e-9, (model, k, lo)


def test_at_rest_after_the_last_contact_with_no_tilt():
    p = _p("sneaker")
    end = MOD.rest_s(PARAMS, p, 10.0)
    assert end == pytest.approx(PARAMS["startS"] + MOD.total_s(PARAMS, p))
    for t in (end, end + 0.5, 9.9):
        pose = PATH(PARAMS, p, t, 10.0)
        assert pose.offset == (0.0, 0.0, 0.0) and pose.pitch == 0.0


def _drop(params=None, duration=10):
    return script("drop_settle", params, duration)


def test_flags_make_landing_settle_apply():
    r = check(_drop(), _p("sneaker"), CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    assert "landing_settle" in [x["id"] for x in r.script["realism"]]


def test_a_late_drop_is_moved_earlier_to_settle_before_the_end():
    p = _p("sneaker")
    late = {"startS": 8.0, "heightFrac": 1.5, "timeScale": 0.3, "bounces": 3, "restitution": 0.5}
    assert MOD.rest_s({**PARAMS, **late}, p, 10.0) > 9.2
    r = check(_drop(late), p, CAT)
    assert r.ok
    iss = [i for i in r.issues if i.code == "motion_ends_unsettled"]
    assert iss and iss[0].severity == "repaired"
    prm = r.script["subject"]["motion"]["params"]
    assert prm["startS"] < 8.0 and MOD.rest_s(prm, p, 10.0) <= 10.0 - 0.8 + 1e-9


def test_a_car_does_not_drop_in():
    r = check(_drop(), _p("sports_car"), CAT)
    assert not r.ok and ("subject_size_unsupported", "subject.motion.id") in {(i.code, i.path) for i in r.issues}
