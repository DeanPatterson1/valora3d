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


_BLIP = ("from engine.motion_path import IDENTITY, SubjectPose\n\n"
         "def sample(params, profile, t, duration):\n"
         "    # a 20 ms excursion that falls between two of the 24 sweep samples of a 10 s clip\n"
         "    return SubjectPose(offset=(0.5, 0.0, 0.0)) if 5.0 < t < 5.02 else IDENTITY\n")


def _motion_catalog(tmp_path, files):
    import json
    import shutil
    root = tmp_path / "blocks"
    shutil.copytree(Catalog.load().root, root, ignore=shutil.ignore_patterns("__pycache__"))
    d = root / "motion" / "blip"
    d.mkdir()
    m = json.loads((root / "motion" / "static" / "block.json").read_text(encoding="utf-8"))
    (d / "block.json").write_text(json.dumps({**m, "id": "blip", "directorSelectable": False}), encoding="utf-8")
    for name, text in files.items():
        (d / name).write_text(text, encoding="utf-8")
    return Catalog.load(root)


def test_a_brief_excursion_between_samples_still_counts_as_moving(tmp_path):
    """Review chunk1 #2: sampling cannot prove a pose function is static; a path.py is moving unless it
    declares still(params)."""
    from engine.motion_path import SWEEP_SAMPLES, _times
    assert all(not 5.0 < t < 5.02 for t in _times(0.0, 10.0, SWEEP_SAMPLES))   # the blip hides between samples
    cat = _motion_catalog(tmp_path, {"path.py": _BLIP})
    assert is_moving(_script({"id": "blip", "params": {}}), _p("pocket_watch"), cat)


def test_still_is_the_explicit_identity_contract(tmp_path):
    cat = _motion_catalog(tmp_path, {"path.py": _BLIP + "\ndef still(params):\n    return params.get('amp', 1) == 0\n"})
    p = _p("pocket_watch")
    assert not is_moving(_script({"id": "blip", "params": {"amp": 0}}), p, cat)
    assert is_moving(_script({"id": "blip", "params": {"amp": 1}}), p, cat)
    assert Catalog.load().motion_still("static", {}) and Catalog.load().motion_still("play_clip", {})


# --- review amendment 77: a pose may carry its own pivot and a quaternion ---------------------------------

def test_quaternion_and_pivot_poses_round_trip():
    import math as _m

    import pytest

    from engine.motion_path import (SubjectPose, apply, euler_matrix, pose_quat, quat_matrix, rotation_matrix,
                                    unapply)
    from engine.tests.test_director_package import _p
    p = _p("pocket_watch")
    e = SubjectPose(offset=(0.1, -0.2, 0.05), yaw=0.7, pitch=-0.3, roll=0.4)
    assert rotation_matrix(e) == euler_matrix(0.7, -0.3, 0.4)
    q = SubjectPose(offset=e.offset, quat=pose_quat(e))                     # the same rotation as a quaternion
    for pt in ((0.01, 0.02, 0.03), (-0.03, 0.0, 0.05)):
        assert apply(pt, q, p) == pytest.approx(apply(pt, e, p), abs=1e-12)
    ax, th = (0.6, 0.8, 0.0), 1.9                                            # an arbitrary axis, about a pivot
    r = SubjectPose(offset=(0.3, 0.0, 0.0), pivot=(0.0, 0.0, 0.033),
                    quat=(_m.cos(th / 2), *(_m.sin(th / 2) * a for a in ax)))
    for pt in ((0.01, 0.02, 0.03), (0.0, 0.0, 0.033)):
        assert unapply(apply(pt, r, p), r, p) == pytest.approx(pt, abs=1e-12)
    assert apply((0.0, 0.0, 0.033), r, p) == pytest.approx((0.3, 0.0, 0.033))   # the pivot only translates
    m = quat_matrix(r.quat)
    assert [sum(m[i][j] * ax[j] for j in range(3)) for i in range(3)] == pytest.approx(list(ax))   # the axis is fixed
