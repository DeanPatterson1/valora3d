from engine.geometry import Pose, project, frame_stats, box_corners, point_in_box, aspect_wh


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
