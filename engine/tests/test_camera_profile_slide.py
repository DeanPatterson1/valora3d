"""Task 83: profile_slide (lateral truck at a profile angle, optional foreground card), pure."""
import math

import pytest

from engine.checker import BOX_MARGIN, check
from engine.director.axes import _opener_ok
from engine.easing import ease, settle
from engine.geometry import _basis, box_corners, point_in_box, project
from engine.tests.camera_helpers import CAT, bearing_rate, defaults, path_module, sample, script_with
from engine.tests.test_director_package import _p

SLIDE = sample("profile_slide")
MOD = path_module("profile_slide")


def _long(p):
    return (1.0, 0.0) if p.sizeM[0] >= p.sizeM[1] else (0.0, 1.0)


def _exact(prm, p, u):
    """The Task 83 formula: a truck along the long axis L at angleDeg from it, target shifted in parallel."""
    cx, cy, cz = p.center
    lx, ly = _long(p)
    s = 1.0 if prm["side"] == "right" else -1.0
    a = math.radians(prm["angleDeg"])
    dx, dy = math.cos(a) * lx - s * math.sin(a) * ly, math.cos(a) * ly + s * math.sin(a) * lx
    k = ease(prm["easing"], settle(u, prm["settleFrac"]))
    o = (k - 0.5) * prm["slideFrac"] * p.longest
    d = prm["distance"] * p.radius
    z = max(0.03, prm["heightFrac"] * p.sizeM[2])
    return ((cx + d * dx + o * lx, cy + d * dy + o * ly, z), (cx + o * lx, cy + o * ly, cz))


@pytest.mark.parametrize("model", ["sports_car", "sneaker", "pocket_watch"])
@pytest.mark.parametrize("u", [0.0, 0.5, 1.0])
def test_path_matches_its_formula(model, u):
    p, prm = _p(model), defaults("profile_slide")
    pose = SLIDE(prm, p, u)
    pos, tgt = _exact(prm, p, u)
    assert pose.position == pytest.approx(pos, abs=1e-12) and pose.target == pytest.approx(tgt, abs=1e-12)


@pytest.mark.parametrize("angle,side", [(90.0, "right"), (60.0, "left"), (120.0, "right")])
def test_moves_parallel_to_the_long_axis_and_keeps_its_angle(angle, side):
    p = _p("sports_car")
    prm = {**defaults("profile_slide"), "angleDeg": angle, "side": side}
    lx, ly = _long(p)
    a, b = SLIDE(prm, p, 0.0), SLIDE(prm, p, 1.0)
    mv = [q - r for q, r in zip(b.position, a.position)]
    assert abs(mv[0] * ly - mv[1] * lx) < 1e-12 and mv[2] == 0.0                  # parallel to L
    assert math.hypot(mv[0], mv[1]) == pytest.approx(prm["slideFrac"] * p.longest)
    for u in (0.0, 0.3, 0.7, 1.0):
        q = SLIDE(prm, p, u)
        vx, vy = q.position[0] - q.target[0], q.position[1] - q.target[1]
        ang = math.degrees(math.acos((vx * lx + vy * ly) / math.hypot(vx, vy)))
        assert ang == pytest.approx(angle, abs=1e-9)                                # the angle is preserved


def test_no_foreground_by_default_or_in_the_studio():
    p = _p("sports_car")
    assert MOD.foreground(defaults("profile_slide"), p) is None
    assert MOD.foreground({**defaults("profile_slide"), "foreground": True}, p, outdoor=False) is None


@pytest.mark.parametrize("model", ["sports_car", "sneaker", "mid_century_lounge_chair"])
@pytest.mark.parametrize("dist", [1.6, 4.0, 8.0])
def test_the_foreground_card_sits_between_camera_and_subject(model, dist):
    p = _p(model)
    prm = {**defaults("profile_slide"), "foreground": True, "distance": dist}
    card = MOD.foreground(prm, p)
    assert card is not None                                              # present on every eval subject here
    corners = card["corners"]
    for c in corners + [card["center"]]:
        assert not point_in_box(c, p.boundsMin, p.boundsMax, BOX_MARGIN)
    subj = box_corners(p.boundsMin, p.boundsMax)
    for k in range(21):
        pose = SLIDE(prm, p, k / 20)
        fwd, _, _ = _basis(pose)
        depth = lambda q: sum((a - b) * f for a, b, f in zip(q, pose.position, fwd))  # noqa: E731
        near = min(depth(c) for c in subj)
        assert all(0.0 < depth(c) < near for c in corners), k


def test_the_foreground_moves_at_least_twice_the_subject_parallax():
    p = _p("sports_car")
    prm = {**defaults("profile_slide"), "foreground": True}
    card = MOD.foreground(prm, p)
    a, b = SLIDE(prm, p, 0.0), SLIDE(prm, p, 1.0)
    shift = lambda q: project(b, q, "9:16")[0] - project(a, q, "9:16")[0]  # noqa: E731
    subj = p.center
    assert abs(shift(card["center"])) >= 2.0 * abs(shift(subj)) and abs(shift(subj)) > 0   # F-C08 / P-C10


def test_bearing_rate_hook_rule_checker_and_settle():
    for model in ("sports_car", "pocket_watch"):
        assert bearing_rate("profile_slide", _p(model)) <= 80.0
    assert _opener_ok(CAT.get("camera", "profile_slide"))
    r = check(script_with("profile_slide", {}), _p("sports_car"), CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    p = _p("sports_car")
    prm = {**defaults("profile_slide"), "settleFrac": 0.25}
    assert SLIDE(prm, p, 0.8) == SLIDE(prm, p, 1.0)
