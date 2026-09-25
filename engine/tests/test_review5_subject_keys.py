"""Review chunk5 #3, #4, #11: the keys the compiler puts on valora_motion (engine/compiler/subject_keys), checked
as Blender will interpolate them (subject_keys.evaluate: linear between keys, CONSTANT after a hold)."""
import copy
import json
import math
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.compiler import subject_keys as SK
from engine.compiler.tiers import SHUTTER
from engine.motion_path import apply, pivot, pose_fn, subject_pose
from engine.profile import SubjectProfile
from engine.tests.shape_profiles import _cylinder_points, _profile
from engine.tests.test_director_package import _p

FIX = Path(__file__).parent / "fixtures"
T3 = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))
CAT = Catalog.load()


def _script(bid, params):
    s = copy.deepcopy(T3)
    defaults = {k: v["default"] for k, v in CAT.get("motion", bid)["params"].items() if "default" in v}
    s["subject"]["motion"] = {"id": bid, "params": {**defaults, **params}}
    for sh in s["shots"]:
        cam = CAT.get("camera", sh["camera"]["id"])["params"]
        sh["camera"]["params"] = {**{k: v["default"] for k, v in cam.items() if "default" in v}, **sh["camera"]["params"]}
    return s


def _keyed(s, p):
    keys, quat = SK.subject_keys(s, p, CAT)
    return keys, quat, SK.key_values(keys, p, quat)


# ---- #3: bounce contacts are keyed exactly -----------------------------------------------------------------

def test_drop_settle_bounces_reach_the_ground_at_every_contact_and_never_turn_back_above_it():
    p = _p("sneaker")
    s = _script("drop_settle", {"bounces": 2})
    prm, fps = s["subject"]["motion"]["params"], s["format"]["fps"]
    cs = CAT.motion_module("drop_settle").contacts(prm, p)
    keys, quat, vals = _keyed(s, p)
    frames = [k.frame for k in keys]
    pv = pivot(p)                                     # the pivot's height is the path's height exactly
    z = lambda f: SK.transform(SK.evaluate(vals, f, quat), pv)[2]  # noqa: E731
    for c in cs:
        fc = 1.0 + c * fps
        assert any(abs(f - fc) < 1e-6 for f in frames), (c, fc)      # a key on the contact itself
        assert z(fc) == pytest.approx(0.0, abs=1e-9)
    # between contacts the keyed height rises then falls: no turn back above the ground (a local minimum > 0)
    for a, b in zip(cs, cs[1:]):
        fa, fb = 1.0 + a * fps, 1.0 + b * fps
        hs = [z(fa + (fb - fa) * j / 400) for j in range(401)]
        top = max(range(len(hs)), key=hs.__getitem__)
        assert all(x <= y + 1e-12 for x, y in zip(hs[:top], hs[1:top + 1])), (a, b)
        assert all(x >= y - 1e-12 for x, y in zip(hs[top:], hs[top + 1:])), (a, b)
        assert hs[top] > 0.0
    # and the keyed arc stays on the ballistic one (checked at 1/8 frames through the whole drop)
    tol = SK.KEY_TOL * p.longest
    for j in range(int(8 * (1 + cs[0] * fps - 4)), int(8 * (1 + cs[-1] * fps + 2))):
        f = j / 8
        want = subject_pose(s, p, CAT, (f - 1) / fps).offset[2]
        assert abs(z(f) - want) <= tol + 1e-12, (f, z(f), want)


def test_integer_frame_keys_alone_turn_the_bounce_back_above_the_ground():
    """The defect itself (what the compiler keyed before): a contact between two frames is interpolated as a
    V whose bottom is a positive key."""
    p = _p("sneaker")
    s = _script("drop_settle", {"bounces": 2})
    prm, fps = s["subject"]["motion"]["params"], s["format"]["fps"]
    c = CAT.motion_module("drop_settle").contacts(prm, p)[0]
    lo = math.floor(1 + c * fps)
    assert 1 + c * fps - lo > 1e-3                       # the contact falls between frames
    h = [subject_pose(s, p, CAT, (f - 1) / fps).offset[2] for f in (lo, lo + 1)]
    assert min(h) > 0.0                                  # both neighbouring keys above the ground


# ---- #4: fast turns never interpolate backward --------------------------------------------------------------

def _pencil():
    """A 20 cm pencil-thin rod (r 4 mm) lying on its side: its roll turns ~340 degrees a frame at 30 fps."""
    return SubjectProfile.from_dict(_profile(_cylinder_points(0.004, 0.20, "x"), [{"class": "matte", "share": 1.0}],
                                             "small-object"))


def test_a_fast_roll_keys_its_quaternion_the_paths_way_round():
    p = _pencil()
    s = _script("roll", {"distanceFrac": 4.0})
    mod = CAT.motion_module("roll")
    assert mod.supports(s["subject"]["motion"]["params"], p)[0]
    fps, prm = s["format"]["fps"], s["subject"]["motion"]["params"]
    turn = lambda f: mod.turn_angle(prm, p, (f - 1) / fps, 10.0)  # noqa: E731
    per_frame = max(abs(turn(f + 1) - turn(f)) for f in range(1, 300))
    assert per_frame > math.pi                           # the case the review names: > 180 degrees between frames
    keys, quat, vals = _keyed(s, p)
    assert quat
    for a, b in zip(keys, keys[1:]):
        assert abs(turn(b.frame) - turn(a.frame)) <= SK.KEY_MAX_TURN + 1e-9, (a.frame, b.frame)
    # evaluated as Blender will: the probe points follow the path's turn at every 1/8 frame
    pts, tol = SK.probe_points(p), 0.05 * p.longest
    for j in range(8, 8 * 120):
        f = j / 8
        got = SK.evaluate(vals, f, quat)
        pose = subject_pose(s, p, CAT, (f - 1) / fps)
        for q in pts:
            assert math.dist(SK.transform(got, q), apply(q, pose, p)) <= tol, (f, q)


def test_a_fast_roll_keyed_once_a_frame_would_turn_backward():
    """The defect: hemisphere-corrected per-frame quaternions take the short way, i.e. backward."""
    p = _pencil()
    s = _script("roll", {"distanceFrac": 4.0})
    fps = s["format"]["fps"]
    frames = [float(f) for f in range(0, 302)]
    keys = [SK.SubjectKey(f, 0, subject_pose(s, p, CAT, (f - 1) / fps)) for f in frames]
    vals = SK.key_values(keys, p, True)
    worst = 0.0
    for j in range(8, 8 * 120):
        f = j / 8
        got, pose = SK.evaluate(vals, f, True), subject_pose(s, p, CAT, (f - 1) / fps)
        worst = max(worst, max(math.dist(SK.transform(got, q), apply(q, pose, p)) for q in SK.probe_points(p)))
    assert worst > 0.5 * p.longest


# ---- #11: drive perShot ----------------------------------------------------------------------------------

def test_drive_manifest_has_per_shot_off_by_default():
    assert CAT.get("motion", "drive")["params"]["perShot"] == {"type": "bool", "default": False}


def _drive(per_shot):
    s = _script("drive", {"startS": 0.2, "driveS": 1.2, "speedKmh": 40.0, "path": "arc_left"})
    if per_shot is not None:
        s["subject"]["motion"]["params"]["perShot"] = per_shot
    return s


def test_per_shot_drive_restarts_at_every_shot_and_off_is_clip_time():
    p = _p("sports_car")
    on, off, bare = _drive(True), _drive(False), _drive(None)
    sample = CAT.load_motion_path("drive")
    prm = off["subject"]["motion"]["params"]
    for t in [x / 7 for x in range(0, 70)]:
        assert subject_pose(off, p, CAT, t) == subject_pose(bare, p, CAT, t) == sample(prm, p, t, 10.0)
    for sh in on["shots"]:
        a, b = sh["startS"], sh["endS"]
        for x in (0.0, 0.1, 0.5, 0.9 * (b - a)):
            assert subject_pose(on, p, CAT, a + x) == sample(prm, p, (a + x) - a, b - a)
    # the shot may be pinned: just before a cut the incoming shot's own drive has not started
    assert subject_pose(on, p, CAT, 2.0 - 1e-3, 1) == sample(prm, p, -1e-3, 1.5)


def test_per_shot_off_keeps_the_camera_keys():
    from engine.compiler.timeline import camera_keys
    p = _p("sports_car")
    assert camera_keys(_drive(False), p, CAT) == camera_keys(_drive(None), p, CAT)


def test_per_shot_cut_keys_hold_between_exposures():
    p = _p("sports_car")
    s = _drive(True)
    fps = s["format"]["fps"]
    keys, quat, vals = _keyed(s, p)
    holds = [k for k in keys if k.hold]
    cuts = [int(round(sh["startS"] * fps)) + 1 for sh in s["shots"][1:]]
    assert [k.frame for k in holds] == [f - 1 + SHUTTER / 2 for f in cuts]
    pts = SK.probe_points(p)
    same = lambda m, pose: max(math.dist(SK.transform(m, q), apply(q, pose, p)) for q in pts)  # noqa: E731
    for i, f in enumerate(cuts, start=1):
        sh = s["shots"][i]
        pre, post = f - 1 + SHUTTER / 2, f - SHUTTER / 2
        assert [k.frame for k in keys if pre - 1e-9 <= k.frame <= post + 1e-9] == [pre, post]
        out_pose = subject_pose(s, p, CAT, (pre - 1) / fps, i - 1)
        in_pose = subject_pose(s, p, CAT, (post - 1) / fps, i)
        assert math.dist(out_pose.offset, in_pose.offset) > 1.0          # the drive really jumps at this cut
        # the outgoing exposure (frame f - 1) sees only the outgoing shot, the incoming (f) only the incoming
        for x in (0.0, 0.25, 0.5, 0.75, 1.0):
            g = pre + (post - pre) * x
            assert same(SK.evaluate(vals, g, quat), out_pose if x < 1.0 else in_pose) < 1e-9, (f, g)
        for x in (0.0, 0.5, 1.0):
            g = post + (f + SHUTTER / 2 - post) * x
            want = subject_pose(s, p, CAT, (g - 1) / fps, i)
            assert same(SK.evaluate(vals, g, quat), want) <= SK.KEY_TOL * p.longest + 1e-9, (f, g)
        assert sh["startS"] == pytest.approx((f - 1) / fps)


def test_a_tracking_camera_reads_its_own_shots_drive():
    from engine.camera_context import Track
    p = _p("sports_car")
    s = _drive(True)
    sh = s["shots"][2]
    tr = Track(pose_fn(s, p, CAT), p, sh, s["format"]["fps"])
    # just before its start the shot's drive still waits at its start: no velocity leaks in from shot 1's run
    assert tr.pose(sh["startS"] - 1e-3) == subject_pose(s, p, CAT, sh["startS"], 2)
    assert tr.pose(sh["startS"] - 1e-3) != subject_pose(s, p, CAT, sh["startS"] - 1e-3)   # shot 1's run, by time


# ---- #13: the shared pose assertion compares the whole transform --------------------------------------------

def test_pose_mismatch_catches_a_missing_plinth_turn():
    """A plinth spin turns about the ground centre (~ the origin): a matrix that carries only the path's
    translation takes the origin to the right place, so a translation-only check passes it; the four-point
    check does not."""
    p = _p("sneaker")
    s = _script("plinth_spin", {})
    prm = s["subject"]["motion"]["params"]
    pose = subject_pose(s, p, CAT, prm["startS"] + prm["turnS"] / 2)
    assert abs(pose.yaw) > 0.5
    o = apply((0.0, 0.0, 0.0), pose, p)
    no_turn = [[1.0, 0.0, 0.0, o[0]], [0.0, 1.0, 0.0, o[1]], [0.0, 0.0, 1.0, o[2]], [0.0, 0.0, 0.0, 1.0]]
    assert math.dist([r[3] for r in no_turn[:3]], o) < 1e-12              # the old translation check: passes
    assert SK.pose_mismatch(no_turn, pose, p) > 0.1 * p.longest            # the new one: fails
    loc, rot = SK.channels(pose, p, False)
    assert SK.pose_mismatch(SK.matrix(loc, rot, False), pose, p) < 1e-12   # the keyed channels: exact
