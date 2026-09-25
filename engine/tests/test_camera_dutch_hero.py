"""Task 81: dutch_hero (low hero push + a camera roll), pure; Pose.roll in project/camera_matrix."""
import copy
import math

import pytest

from engine.checker import check
from engine.director.axes import _opener_ok
from engine.geometry import Pose, box_corners, camera_matrix, frame_stats, project
from engine.tests.camera_helpers import CAT, T3, bearing_rate, defaults, sample, script_with
from engine.tests.test_director_package import _p

DUTCH, HERO = sample("dutch_hero"), sample("low_hero_push")


def _shared(prm):
    return {k: v for k, v in prm.items() if k in defaults("low_hero_push")}


@pytest.mark.parametrize("u", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("side,sign", [("right", -1.0), ("left", 1.0)])
def test_it_is_the_low_hero_push_plus_a_roll(u, side, sign):
    p = _p("sports_car")
    prm = {**defaults("dutch_hero"), "rollSide": side}
    a, b = DUTCH(prm, p, u), HERO(_shared(prm), p, u)
    assert (a.position, a.target, a.lens_mm) == (b.position, b.target, b.lens_mm)
    assert a.roll == pytest.approx(sign * math.radians(prm["rollDeg"]))
    assert b.roll == 0.0


def test_a_90_degree_roll_swaps_the_footprint():
    pose = Pose((0.0, -10.0, 0.0), (0.0, 0.0, 0.0), 50.0)
    box = box_corners((-2.0, -0.1, -0.5), (2.0, 0.1, 0.5))            # wide and short, seen from -Y

    def extent(q):
        pts = [project(q, c, "1:1") for c in box]
        xs, ys = [x for x, _, _ in pts], [y for _, y, _ in pts]
        return max(xs) - min(xs), max(ys) - min(ys)
    w0, h0 = extent(pose)
    w1, h1 = extent(Pose(pose.position, pose.target, pose.lens_mm, math.radians(90.0)))
    assert w0 > 3 * h0 and w1 == pytest.approx(h0, rel=1e-9) and h1 == pytest.approx(w0, rel=1e-9)


def test_roll_zero_is_byte_identical():
    pose = Pose((3.0, -7.0, 1.2), (0.1, 0.2, 0.5), 35.0)
    assert Pose(pose.position, pose.target, pose.lens_mm, 0.0) == pose
    assert camera_matrix(Pose(pose.position, pose.target, pose.lens_mm, 0.0)) == camera_matrix(pose)


def test_camera_matrix_rolls_about_the_view_axis():
    pose = Pose((0.0, -10.0, 1.0), (0.0, 0.0, 1.0), 50.0)
    rolled = Pose(pose.position, pose.target, pose.lens_mm, math.radians(12.0))
    m0, m1 = camera_matrix(pose), camera_matrix(rolled)
    col = lambda m, j: [m[i][j] for i in range(3)]  # noqa: E731
    assert col(m1, 2) == pytest.approx(col(m0, 2), abs=1e-12)                 # -forward unchanged
    dot = sum(a * b for a, b in zip(col(m0, 1), col(m1, 1)))
    assert math.degrees(math.acos(max(-1.0, min(1.0, dot)))) == pytest.approx(12.0, abs=1e-9)


def test_the_roll_changes_what_the_checker_sees():
    """frame_stats uses the rolled footprint: a wide car framed tight in a portrait frame at roll 0 overflows
    at a 20 degree roll (the diagonal is wider)."""
    p = _p("sports_car")
    corners = box_corners(p.boundsMin, p.boundsMax)
    prm = {**defaults("dutch_hero"), "rollDeg": 20.0, "distance": 1.9, "azimuthDeg": 90.0}
    flat = HERO(_shared(prm), p, 1.0)
    tilted = DUTCH(prm, p, 1.0)
    assert frame_stats(flat, corners, "9:16")["coverage"] != frame_stats(tilted, corners, "9:16")["coverage"]


def test_bearing_rate_hook_rule_and_checker():
    assert bearing_rate("dutch_hero", _p("sports_car")) <= 80.0
    assert _opener_ok(CAT.get("camera", "dutch_hero"))
    r = check(script_with("dutch_hero", {}, index=2), _p("sports_car"), CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]


def test_the_settle_holds_the_camera_still():
    p = _p("sports_car")
    prm = {**defaults("dutch_hero"), "settleFrac": 0.2}
    assert DUTCH(prm, p, 0.85) == DUTCH(prm, p, 1.0)


def test_one_dutch_shot_per_clip():
    s = script_with("dutch_hero", {}, index=2)
    s["shots"][3]["camera"] = {"id": "dutch_hero", "params": {"azimuthDeg": -40}}
    s["shots"][3]["purpose"] = "motion"
    r = check(s, _p("sports_car"), CAT)
    bad = [i for i in r.issues if i.code == "camera_max_per_clip"]
    assert not r.ok and bad and bad[0].severity == "error" and bad[0].path == "shots[3].camera"
    assert CAT.get("camera", "dutch_hero")["maxPerClip"] == 1


def test_cameras_without_max_per_clip_are_unlimited():
    s = copy.deepcopy(T3)                                  # two macro_detail and two arc_orbit shots
    assert "camera_max_per_clip" not in {i.code for i in check(s, _p("sports_car"), CAT).issues}
