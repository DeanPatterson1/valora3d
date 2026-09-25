"""Review fix: a foreground card is built from the posed camera profile the camera itself is solved against,
and stays clear of the subject's live posed bounds (between lens and subject) for the whole shot. Pure."""
import copy

import pytest

from engine.checker import BOX_MARGIN
from engine.foreground_plan import plan_foreground
from engine.geometry import _basis, box_corners, point_in_box
from engine.motion_path import camera_profile, pose_fn, posed_profile, shot_t
from engine.script import validate_and_repair
from engine.tests.camera_helpers import CAT, T3, defaults, path_module, sample
from engine.tests.test_director_package import _p

MOD = path_module("profile_slide")
SLIDE = sample("profile_slide")


def _script(index, drive):
    s = copy.deepcopy(T3)
    s["world"], s["lighting"] = {"id": "night_street", "params": {}}, {"id": "rim_neon", "params": {}}
    s["subject"]["motion"] = {"id": "drive", "params": dict(drive)}
    s["shots"][index]["camera"] = {"id": "profile_slide", "params": {**defaults("profile_slide"), "foreground": True}}
    return validate_and_repair(s, CAT)[0]


# parked 22 m down the lane before the shot / driving through the shot
PARKED = (2, {"path": "straight", "accel": "cruise", "speedKmh": 40.0, "facing": "forward", "startS": 0.0, "driveS": 2.0})
DRIVING = (0, {"path": "straight", "accel": "cruise", "speedKmh": 20.0, "facing": "forward", "startS": 0.0, "driveS": 3.0})


@pytest.mark.parametrize("index,drive", [PARKED, DRIVING])
def test_card_follows_the_posed_camera_profile_and_clears_the_live_subject(index, drive):
    p = _p("sports_car")
    s = _script(index, drive)
    sh, fps = s["shots"][index], s["format"]["fps"]
    pose_at = pose_fn(s, p, CAT)
    cards = dict(plan_foreground(s, p, CAT, outdoor=True))
    assert set(cards) == {index}
    card = cards[index]
    cam_prof = camera_profile(sh, p, lambda t: pose_at(t, index), "anchor", 0.5, fps)
    assert cam_prof.center != pytest.approx(p.center, abs=0.5)                # the subject really is displaced
    assert card == MOD.foreground(sh["camera"]["params"], cam_prof, True)      # the camera's own profile
    assert card != MOD.foreground(sh["camera"]["params"], p, True)             # not the rest profile
    for k in range(21):
        u = k / 20
        cam = SLIDE(sh["camera"]["params"], cam_prof, u)
        live = posed_profile(p, pose_at(shot_t(sh, u, fps), index))
        fwd, _, _ = _basis(cam)
        depth = lambda q: sum((a - b) * f for a, b, f in zip(q, cam.position, fwd))  # noqa: E731
        near = min(depth(c) for c in box_corners(live.boundsMin, live.boundsMax))
        assert all(0.0 < depth(c) < near for c in card["corners"]), k
        assert not any(point_in_box(c, live.boundsMin, live.boundsMax, BOX_MARGIN)
                       for c in card["corners"] + [card["center"]]), k


def test_card_is_dropped_when_the_live_subject_would_cross_it():
    """A subject driving across the lens (toward the camera) would pass through the card: no card."""
    p = _p("sports_car")
    s = _script(0, DRIVING[1])
    sh = s["shots"][0]
    cards = dict(plan_foreground(s, p, CAT, outdoor=True, pose_override=_toward_camera(s, p, sh)))
    assert cards == {}


def _toward_camera(s, p, sh):
    """A synthetic pose_at that moves the subject from its mid-shot pose onto the lens over the shot."""
    from engine.motion_path import IDENTITY
    from dataclasses import replace
    mid = SLIDE(sh["camera"]["params"], p, 0.5)
    gx, gy = mid.position[0] - p.center[0], mid.position[1] - p.center[1]
    a, b = sh["startS"], sh["endS"]

    def pose_at(t, shot=None):
        k = min(max((t - (a + b) / 2) / ((b - a) / 2), 0.0), 1.0)
        return replace(IDENTITY, offset=(gx * k, gy * k, 0.0))
    pose_at.per_shot = False
    return pose_at


def test_static_subject_and_studio_unchanged():
    p = _p("sports_car")
    s = copy.deepcopy(T3)
    s["world"] = {"id": "night_street", "params": {}}
    s["shots"][2]["camera"] = {"id": "profile_slide", "params": {**defaults("profile_slide"), "foreground": True}}
    s = validate_and_repair(s, CAT)[0]
    prm = s["shots"][2]["camera"]["params"]
    assert dict(plan_foreground(s, p, CAT, outdoor=True)) == {2: MOD.foreground(prm, p, True)}
    assert plan_foreground(s, p, CAT, outdoor=False) == []
