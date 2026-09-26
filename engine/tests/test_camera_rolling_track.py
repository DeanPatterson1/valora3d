"""Task 84: rolling_track (camera-car, CATALOG-GAPS rank 5) + owner decision (b): real-speed drives."""
import copy
import math

import pytest

from engine.camera_context import ShotContext, Track, camera_sampler
from engine.checker import check
from engine.director.axes import _opener_ok
from engine.geometry import box_corners, frame_stats
from engine.motion_path import pose_fn, posed_profile
from engine.script import validate_and_repair
from engine.tests.camera_helpers import CAT, T3, defaults, sample
from engine.tests.test_director_package import _p

TRACK_CAM = sample("rolling_track")
# 40 km/h for the hook's 2 s (22 m: inside night_street's 30 m lane); the car is on its mark before the detail
# shots (a moving car in a detail shot is refused, Chunk 5)
DRIVE = {"path": "straight", "accel": "cruise", "speedKmh": 40.0, "facing": "forward", "startS": 0.0, "driveS": 2.0}


def drive_script(camera="rolling_track", params=None, index=0, drive=None, world="night_street"):
    s = copy.deepcopy(T3)
    s["world"], s["lighting"] = {"id": world, "params": {}}, {"id": "rim_neon", "params": {}}
    s["subject"]["motion"] = {"id": "drive", "params": dict(drive or DRIVE)}
    if world == "night_street":           # script_t3's arcs shoot from the road, not behind the pavement slab
        from engine.tests.test_growth_floor import _road_side
        _road_side(s)
    s["shots"][index]["camera"] = {"id": camera, "params": dict(params or {})}
    return s


def _params(sh):
    return {**defaults(sh["camera"]["id"]), **sh["camera"]["params"]}


def _ready(s, p):
    s = validate_and_repair(s, CAT)[0]
    return s, pose_fn(s, p, CAT), s["format"]["fps"]


def _straight_along(p):
    """The drive's straight-line direction (xy unit) as the path samples it."""
    s, pose_at, _ = _ready(drive_script(), p)
    a, b = pose_at(0.0).offset, pose_at(2.0).offset
    n = math.hypot(b[0] - a[0], b[1] - a[1])
    return ((b[0] - a[0]) / n, (b[1] - a[1]) / n)


def test_side_mode_holds_a_constant_offset_in_the_heading_frame():
    p = _p("sports_car")
    s, pose_at, fps = _ready(drive_script(), p)
    sh = s["shots"][0]
    sh["startS"], sh["endS"] = 0.5, 2.0
    prm = _params(sh)
    tr = Track(pose_at, p, sh, fps)
    hx, hy = _straight_along(p)
    offs = []
    for k in range(11):
        u = k / 10
        pose = TRACK_CAM(prm, p, u, ctx=ShotContext(1.5, 0.5, tr))
        c = tr.at(tr.t(u) - prm["lagS"]).center                     # the pose at t - lag
        rel = (pose.position[0] - c[0], pose.position[1] - c[1])
        offs.append((rel[0] * hx + rel[1] * hy, rel[0] * -hy + rel[1] * hx))  # (along, across) the heading
        assert pose.target == pytest.approx(c, abs=1e-9)
    assert all(o == pytest.approx(offs[0], abs=1e-9) for o in offs)
    assert abs(offs[0][0]) < 1e-9 and abs(offs[0][1]) == pytest.approx(prm["distance"] * p.radius)


@pytest.mark.parametrize("mode,sign", [("lead", 1.0), ("tail", -1.0)])
def test_lead_and_tail_sit_ahead_and_behind(mode, sign):
    p = _p("sports_car")
    s, pose_at, fps = _ready(drive_script(params={"mode": mode}), p)
    sh = s["shots"][0]
    sh["startS"], sh["endS"] = 0.2, 1.8
    tr = Track(pose_at, p, sh, fps)
    hx, hy = _straight_along(p)
    prm = _params(sh)
    pose = TRACK_CAM(prm, p, 0.5, ctx=ShotContext(1.6, 0.2, tr))
    c = tr.at(tr.t(0.5) - prm["lagS"]).center
    along = (pose.position[0] - c[0]) * hx + (pose.position[1] - c[1]) * hy
    assert along == pytest.approx(sign * prm["distance"] * p.radius, abs=1e-9)


def test_the_flyby_passes_closest_at_pass_u():
    p = _p("sports_car")
    for pu in (0.3, 0.5, 0.7):
        s, pose_at, fps = _ready(drive_script(params={"mode": "flyby", "passU": pu}), p)
        sh = s["shots"][0]
        sh["startS"], sh["endS"] = 0.0, 2.0
        tr = Track(pose_at, p, sh, fps)
        prm = _params(sh)
        us = [k / 240 for k in range(241)]
        poses = [TRACK_CAM(prm, p, u, ctx=ShotContext(2.0, 0.0, tr)) for u in us]
        assert len({q.position for q in poses}) == 1                      # anchored
        dist = [math.dist(q.position[:2], tr.at(tr.t(u)).center[:2]) for q, u in zip(poses, us)]
        best = us[dist.index(min(dist))]
        assert best == pytest.approx(pu, abs=1.5 / 240), (pu, best)
        assert all(q.target == pytest.approx(tr.at(tr.t(u)).center, abs=1e-9) for q, u in zip(poses, us))


def test_a_static_subject_is_camera_needs_motion():
    r = check(drive_script(drive=None) | {"subject": {**T3["subject"]}}, _p("sports_car"), CAT)
    bad = [i for i in r.issues if i.code == "camera_needs_motion"]
    assert not r.ok and bad and bad[0].severity == "error" and bad[0].path == "shots[0].camera"


def test_a_slide_in_is_enough_motion():
    s = copy.deepcopy(T3)
    s["subject"]["motion"] = {"id": "slide_in", "params": {}}
    s["shots"][0]["camera"] = {"id": "rolling_track", "params": {}}
    assert "camera_needs_motion" not in {i.code for i in check(s, _p("sneaker"), CAT).issues}


def test_checker_coverage_passes_at_every_sample_at_40_kmh():
    p = _p("sports_car")
    r = check(drive_script(), p, CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    prm = r.script["subject"]["motion"]["params"]
    assert prm["speedKmh"] == 40.0 and "vehicle_speed_cap" not in {i.code for i in r.issues}
    sh = r.script["shots"][0]
    pose_at, fps = pose_fn(r.script, p, CAT), r.script["format"]["fps"]
    cam = camera_sampler(CAT, sh, p, (pose_at, fps))
    from engine.motion_path import shot_t
    for k in range(25):
        u = k / 24
        live = posed_profile(p, pose_at(shot_t(sh, u, fps)))
        st = frame_stats(cam(sh["camera"]["params"], p, u, None), box_corners(live.boundsMin, live.boundsMax),
                         r.script["format"]["aspect"])
        assert st["allInFront"] and st["inFrame"] and st["coverage"] >= 0.25, (u, st)


def test_decision_b_a_tracking_camera_keeps_the_real_speed():
    """Owner decision (b): under anchor cameras the 80 deg/s sweep cap stays (the drive crawls); a drive shot
    from the tracking camera keeps its speed (the cap exempts follow cameras)."""
    p = _p("sports_car")
    anchor = drive_script("low_hero_push", {"distance": 2.0, "azimuthDeg": 90.0})
    tracked = drive_script("rolling_track", {})
    ra, rt = check(anchor, p, CAT), check(tracked, p, CAT)
    va = ra.script["subject"]["motion"]["params"]["speedKmh"]
    vt = rt.script["subject"]["motion"]["params"]["speedKmh"]
    assert va < 40.0 and "vehicle_speed_cap" in {i.code for i in ra.issues}
    capped = [i for i in rt.issues if i.code == "vehicle_speed_cap"]
    assert vt == 40.0 and not capped and rt.ok, [(i.code, i.message) for i in rt.issues if i.severity == "error"]


def test_hook_rule_and_manifest_contract():
    m = CAT.get("camera", "rolling_track")
    assert m["follows"] == "subject" and m["requiresMotion"] == ["translates"] and m["shotContext"] is True
    assert not _opener_ok(m)                    # a rolled opener must suit any subject; this one needs motion


def test_without_a_track_it_frames_the_rest_pose():
    """A context-free call (no moving subject: the motion rules' lock test) is well defined: beside the rest
    pose along its long axis."""
    p = _p("sports_car")
    prm = defaults("rolling_track")
    pose = TRACK_CAM(prm, p, 0.5)
    assert pose.target == pytest.approx(p.center)
    assert math.hypot(pose.position[0] - p.center[0], pose.position[1] - p.center[1]) == pytest.approx(
        prm["distance"] * p.radius)
