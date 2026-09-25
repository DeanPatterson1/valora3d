"""Phase 5 Task 56: one pose function for checker and compiler (pure)."""
import math

from engine.catalog import Catalog
from engine.motion_path import (IDENTITY, SubjectPose, camera_profile, horizontal_travel, is_moving, posed_markers,
                                posed_profile, subject_pose, swept_bounds)
from engine.tests.test_director_package import _p


def _script(motion, dur=10.0, shots=((0, 5), (5, 10))):
    return {"format": {"durationS": dur, "fps": 30, "aspect": "9:16"}, "subject": {"placement": "ground", "motion": motion},
            "shots": [{"startS": a, "endS": b, "camera": {"id": "low_hero_push", "params": {}}} for a, b in shots]}


def test_static_and_play_clip_are_identity():
    cat, p = Catalog.load(), _p("pocket_watch")
    for m in ({"id": "static", "params": {}}, {"id": "play_clip", "params": {}}):
        for t in (0.0, 3.3, 10.0):
            assert subject_pose(_script(m), p, cat, t) == IDENTITY
        assert not is_moving(_script(m), p, cat)


def test_posed_profile_moves_bounds_and_centre():
    p = _p("sports_car")
    q = posed_profile(p, SubjectPose(offset=(2.0, 0.0, 0.0), yaw=0.0))
    assert math.isclose(q.center[0], p.center[0] + 2.0) and math.isclose(q.boundsMax[0], p.boundsMax[0] + 2.0)
    r = posed_profile(p, SubjectPose(offset=(0.0, 0.0, 0.0), yaw=math.pi / 2))
    assert math.isclose(r.boundsMax[0] - r.boundsMin[0], p.boundsMax[1] - p.boundsMin[1], rel_tol=1e-6)
    assert posed_profile(p, IDENTITY) is p


def test_posed_profile_moves_detail_points_and_turns_their_normals():
    p = _p("pocket_watch")
    q = posed_profile(p, SubjectPose(offset=(1.0, 0.0, 0.0), yaw=math.pi))
    d0, e0 = p.detailPoints[0], q.detailPoints[0]
    cx, cy = p.center[0], p.center[1]
    assert math.isclose(e0["point"][0], 2 * cx - d0["point"][0] + 1.0, abs_tol=1e-9)
    assert math.isclose(e0["point"][1], 2 * cy - d0["point"][1], abs_tol=1e-9)
    assert math.isclose(e0["normal"][0], -d0["normal"][0], abs_tol=1e-9)
    assert p.detailPoints[0] == d0            # the source profile is untouched


def test_posed_markers_move_anchor_points():
    p = _p("pocket_watch")
    mk = [{"id": "a", "anchor": {"space": "placed", "point": [0.01, 0.0, 0.05], "normal": [0, 0, 1]}}]
    out = posed_markers(mk, p, SubjectPose(offset=(0.5, 0.0, 0.0)))
    assert math.isclose(out[0]["anchor"]["point"][0], 0.51) and mk[0]["anchor"]["point"][0] == 0.01
    assert posed_markers(mk, p, IDENTITY) is mk


def test_anchor_camera_uses_mid_shot_pose_subject_camera_uses_live_pose():
    p = _p("sports_car")
    pose = lambda t: SubjectPose(offset=(t, 0.0, 0.0), yaw=0.0)  # noqa: E731
    shot = {"startS": 2.0, "endS": 6.0}
    assert math.isclose(camera_profile(shot, p, pose, follows="anchor", u=0.0).center[0], p.center[0] + 4.0)
    assert math.isclose(camera_profile(shot, p, pose, follows="subject", u=0.25).center[0], p.center[0] + 3.0)
    # with fps, u follows the timeline's frame-aligned span (the shot's last frame is u = 1)
    got = camera_profile(shot, p, pose, follows="subject", u=1.0, fps=10).center[0]
    assert math.isclose(got, p.center[0] + 5.9)


def test_swept_bounds_cover_every_pose():
    p = _p("pocket_watch")
    lo, hi = swept_bounds(p, lambda t: SubjectPose(offset=(0.1 * t, 0.0, 0.0), yaw=0.0), 0.0, 10.0)
    assert math.isclose(hi[0], p.boundsMax[0] + 1.0, rel_tol=1e-6) and math.isclose(lo[0], p.boundsMin[0])


def test_horizontal_travel_ignores_turning_in_place():
    assert horizontal_travel(lambda t: SubjectPose(yaw=t), 0.0, 10.0) == 0.0
    got = horizontal_travel(lambda t: SubjectPose(offset=(0.3 * t, 0.4 * t, 5.0)), 0.0, 10.0)
    assert math.isclose(got, 5.0)
