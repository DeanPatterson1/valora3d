import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.compiler.timeline import camera_keys, frame_count, key_frames, shot_u
from engine.geometry import Pose, _basis, camera_matrix, focus_depth
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))
SCRIPT = check(json.loads((FIX / "script_valid.json").read_text()), CAR, CAT).script  # 0-5 s, 5-10 s


def test_camera_matrix_is_a_rotation_whose_minus_z_is_forward():
    pose = Pose((3.0, -4.0, 1.0), (0.0, 0.0, 0.5), 50.0)
    m = camera_matrix(pose)
    cols = [[m[r][c] for r in range(3)] for c in range(3)]
    for i in range(3):
        for j in range(3):
            assert sum(a * b for a, b in zip(cols[i], cols[j])) == pytest.approx(1.0 if i == j else 0.0, abs=1e-12)
    fwd, right, up = _basis(pose)
    assert cols[0] == pytest.approx(list(right)) and cols[1] == pytest.approx(list(up))
    assert [-v for v in cols[2]] == pytest.approx(list(fwd))


def test_frame_count_and_shot_u_hit_both_ends():
    assert frame_count(SCRIPT["format"]) == 300
    sh = SCRIPT["shots"][0]
    assert shot_u(sh, 0.0, 30) == 0.0
    assert shot_u(sh, 5.0 - 1 / 30, 30) == pytest.approx(1.0)  # last frame of the shot reaches u=1


def test_keys_cover_every_frame_plus_blur_margins_and_cut_subframes():
    keys = camera_keys(SCRIPT, CAR, CAT)
    frames = [k.frame for k in keys]
    assert frames == sorted(frames) and len(set(frames)) == len(frames)
    assert len(keys) == 300 + 2 + 2  # frames 0..301, plus two subframe keys for the one cut
    assert frames[0] == 0 and frames[-1] == 301


def test_cut_lands_in_the_closed_shutter_gap():
    keys = camera_keys(SCRIPT, CAR, CAT)
    by = {k.frame: k for k in keys}
    assert by[150.25].shot == 0 and by[150.75].shot == 1
    assert max(k.frame for k in keys if k.shot == 0) == 150.25
    assert min(k.frame for k in keys if k.shot == 1) == 150.75


def test_integer_frame_keys_equal_the_checker_path():
    keys = camera_keys(SCRIPT, CAR, CAT)
    sample = CAT.load_camera_path("low_hero_push")
    p = SCRIPT["shots"][0]["camera"]["params"]
    k1 = next(k for k in keys if k.frame == 1)
    assert k1.pose == sample(p, CAR, 0.0, None)
    k150 = next(k for k in keys if k.frame == 150)
    assert k150.pose == sample(p, CAR, 1.0, None)
    assert k1.focusM > 0 and k1.fstop == p["fstop"]


def test_key_frames_are_few_and_include_the_hook_frame():
    assert key_frames(SCRIPT) == [16, 76, 226, 300]
    assert key_frames(SCRIPT, limit=3) == [16, 226, 300]


def test_focus_depth_is_distance_along_the_view_axis():
    pose = Pose((0.0, -10.0, 0.0), (0.0, 0.0, 0.0), 50.0)
    assert focus_depth(pose, (3.0, 0.0, 2.0)) == pytest.approx(10.0)


def _linear_end_script():
    raw = json.loads((FIX / "script_valid.json").read_text())
    raw["shots"][0]["camera"]["params"]["easing"] = "in_quad"  # still moving at u = 1
    raw["shots"][1]["camera"]["params"].update({"easing": "in_quad", "settleFrac": 0.0})
    return check(raw, CAR, CAT).script


def _lerp_pos(a, b, t):
    return [x + (y - x) * t for x, y in zip(a.pose.position, b.pose.position)]


def test_cut_subframes_follow_the_shutter(monkeypatch):
    import engine.compiler.timeline as tl
    from engine.compiler.tiers import SHUTTER
    frames = {k.frame for k in camera_keys(SCRIPT, CAR, CAT)}
    assert 151 - 1 + SHUTTER / 2 in frames and 151 - SHUTTER / 2 in frames
    monkeypatch.setattr(tl, "SHUTTER", 0.4)
    frames = {k.frame for k in tl.camera_keys(SCRIPT, CAR, CAT)}
    assert 150.2 in frames and 150.8 in frames and 150.25 not in frames


def test_keys_past_a_shot_end_extrapolate_its_motion_instead_of_freezing():
    s = _linear_end_script()
    by = {k.frame: k for k in camera_keys(s, CAR, CAT)}
    # frame 301 (one frame past the clip): the path keeps its last velocity, so frame 300 blurs fully
    assert by[301].pose.position == pytest.approx(_lerp_pos(by[299], by[300], 2.0), abs=1e-9)
    assert by[301].pose.position != pytest.approx(by[300].pose.position, abs=1e-6)
    # the outgoing shot's cut subframe continues shot 0 a quarter frame past its last frame
    assert by[150.25].pose.position == pytest.approx(_lerp_pos(by[149], by[150], 1.25), abs=1e-9)
    # frame 0 continues shot 0 backwards; the incoming subframe continues shot 1 backwards
    assert by[0].pose.position == pytest.approx(_lerp_pos(by[2], by[1], 2.0), abs=1e-9)
    assert by[150.75].pose.position == pytest.approx(_lerp_pos(by[152], by[151], 1.25), abs=1e-9)
