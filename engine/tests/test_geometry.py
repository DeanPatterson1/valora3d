import math
import pytest
from engine.geometry import Pose, project, frame_stats, box_corners, point_in_box, aspect_wh, _norm, _basis


def test_aspect_parse():
    assert aspect_wh("9:16") == (9, 16)


def test_point_straight_ahead_projects_to_centre():
    pose = Pose(position=(0, -5, 1), target=(0, 0, 1), lens_mm=50)
    x, y, depth = project(pose, (0, 0, 1), "16:9")
    assert abs(x) < 1e-9 and abs(y) < 1e-9 and abs(depth - 5) < 1e-9


def test_point_behind_camera_has_negative_depth():
    pose = Pose(position=(0, -5, 1), target=(0, 0, 1), lens_mm=50)
    assert project(pose, (0, -10, 1), "16:9")[2] < 0


def test_frame_stats_full_box():
    # 1 m cube, 50 mm lens, 16:9. Coverage is set by the short vertical side:
    # vertical half-tan = 0.36 * 9/16 = 0.2025; front face at 5.0 m -> 1/5/0.2025/2 ≈ 0.494
    corners = box_corners((-0.5, -0.5, 0), (0.5, 0.5, 1))
    pose = Pose(position=(0, -5.5, 0.5), target=(0, 0, 0.5), lens_mm=50)
    s = frame_stats(pose, corners, "16:9")
    assert s["allInFront"] and s["inFrame"]
    assert 0.45 < s["coverage"] < 0.55


def test_frame_stats_overflow_when_too_close():
    corners = box_corners((-0.5, -0.5, 0), (0.5, 0.5, 1))
    pose = Pose(position=(0, -0.9, 0.5), target=(0, 0, 0.5), lens_mm=85)
    assert not frame_stats(pose, corners, "9:16")["inFrame"]


def test_point_in_box_with_margin():
    assert point_in_box((0.55, 0, 0.5), (-0.5, -0.5, 0), (0.5, 0.5, 1), margin=0.1)
    assert not point_in_box((0.7, 0, 0.5), (-0.5, -0.5, 0), (0.5, 0.5, 1), margin=0.1)


def test_point_behind_camera_projects_to_nan_not_frame_centre():
    pose = Pose(position=(0, -5, 1), target=(0, 0, 1), lens_mm=50)
    x, y, depth = project(pose, (0, -10, 1), "16:9")
    assert math.isnan(x) and math.isnan(y)
    assert depth < 0


def test_frame_stats_behind_camera_is_overflow_not_zero_coverage():
    # Camera sits inside the box's y-range: some corners are behind it.
    corners = box_corners((-0.5, -0.5, 0), (0.5, 0.5, 1))
    pose = Pose(position=(0, 0.3, 0.5), target=(0, 10, 0.5), lens_mm=50)
    s = frame_stats(pose, corners, "16:9")
    assert s == {"allInFront": False, "inFrame": False, "coverage": math.inf}


def test_norm_zero_vector_raises():
    with pytest.raises(ValueError, match="camera position equals target"):
        _norm((0.0, 0.0, 0.0))


def test_basis_docstring_documents_zup_and_blender_contract():
    doc = _basis.__doc__ or ""
    assert "Z-up" in doc or "Z up" in doc
    assert "0.999" in doc
    assert "TRACK_TO" in doc


def test_ray_box_exit_is_the_distance_to_the_far_face():
    from engine.geometry import ray_box_exit
    lo, hi = (-1.0, -2.0, 0.0), (3.0, 2.0, 1.0)
    assert ray_box_exit((0.0, 0.0, 0.5), (1.0, 0.0, 0.0), lo, hi) == pytest.approx(3.0)
    assert ray_box_exit((0.0, 0.0, 0.5), (0.0, 0.6, 0.8), lo, hi) == pytest.approx(0.5 / 0.8)
    assert ray_box_exit((9.0, 0.0, 0.5), (1.0, 0.0, 0.0), lo, hi) is None  # origin outside


def test_mist_far_reaches_the_farthest_set_corner_from_any_camera():
    from engine.geometry import mist_far
    cams = [(0.0, -5.0, 1.0), (5.0, 0.0, 1.0)]
    corners = box_corners((-20.0, -20.0, 0.0), (20.0, 20.0, 8.0))  # the studio set, not just the subject
    far = mist_far(cams, corners)
    expect = max(math.dist(c, k) for c in cams for k in corners)
    assert far == pytest.approx(expect * 1.01)
