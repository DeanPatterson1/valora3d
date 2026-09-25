"""perShot drive vs vehicle_speed_cap (follow-up to review chunk5 #11). With perShot every shot replays the
drive window, so the cap must judge each replay: the T3-14 80 deg/s sweep per anchor shot on that shot's own
replay, and the drive lane per replay. Both hold on the shot-aware pose track (motion_path.pose_fn): these pin
it. The lane is judged on the WHOLE window even when a shot cuts its replay short: the mark sits mid-window,
so a cut-short replay still starts the full half-window back from it (a per-shot distance would start the car
outside the lane)."""
import copy
import math

from engine import motion_rules as MR
from engine.catalog import Catalog
from engine.checker import check
from engine.tests.test_director_package import _p
from engine.tests.test_growth_floor import FLOORS

CAT = Catalog.load()


def _resolved(per_shot, **prm):
    make, model = FLOORS["camera/rolling_track"]
    s = make()
    s["subject"]["motion"]["params"].update(perShot=per_shot, **prm)
    p = _p(model)
    r = check(s, p, CAT)
    return r, p


def test_the_sweep_cap_judges_each_anchor_shot_on_its_own_replay():
    r, p = _resolved(True, startS=0.0, driveS=2.0)
    s = copy.deepcopy(r.script)
    s["subject"]["motion"]["params"]["speedKmh"] = 40.0
    whole = MR._bearing_rate(s, CAT, p)
    per = []
    for sh in s["shots"]:
        if (CAT.get("camera", sh["camera"]["id"]) or {}).get("follows", "anchor") != "anchor":
            continue
        one = copy.deepcopy(s)                      # the shot alone, as a clip of its own: its replay on clip time
        a, b = sh["startS"], sh["endS"]
        one["shots"] = [dict(copy.deepcopy(sh), startS=0.0, endS=b - a)]
        one["format"] = dict(one["format"], durationS=b - a)
        one["subject"]["motion"]["params"]["perShot"] = False
        per.append(MR._bearing_rate(one, CAT, p))
    assert per and max(per) > MR.CAMERA_RATE_CAP_DEG_S
    assert math.isclose(whole, max(per), rel_tol=1e-9), (whole, per)
    # without perShot the drive plays once, under the tracking shot only: no anchor shot sees it move
    off = copy.deepcopy(s)
    off["subject"]["motion"]["params"]["perShot"] = False
    assert MR._bearing_rate(off, CAT, p) < max(per)


def test_the_lane_holds_every_replay_even_when_a_shot_cuts_it_short():
    """4 s windows in 2 s shots: each replay is cut at 2 s, yet it starts half a window back from the mark."""
    r, p = _resolved(True, startS=0.0, driveS=4.0, speedKmh=40.0)
    s = r.script
    prm = s["subject"]["motion"]["params"]
    assert any(i.code == "vehicle_speed_cap" for i in r.issues)
    lane = CAT.get("world", s["world"]["id"])["driveLaneM"]
    drive = CAT.motion_module("drive")
    assert drive.lane_distance(prm, p) <= lane + 1e-9
    from engine.motion_path import subject_pose
    fps = s["format"]["fps"]
    for i, sh in enumerate(s["shots"]):
        n = int(round((sh["endS"] - sh["startS"]) * fps))
        reach = max(math.hypot(*subject_pose(s, p, CAT, sh["startS"] + k / fps, i).offset[:2]) for k in range(n))
        assert reach <= lane / 2 + 1e-6, (i, reach, lane)
    # the per-shot distance would have kept 40 km/h (22 m driven per 2 s shot < the 30 m lane), and that
    # replay starts 22 m back from the mark: outside the lane
    fast = copy.deepcopy(s)
    fast["subject"]["motion"]["params"]["speedKmh"] = 40.0
    sh = fast["shots"][0]
    assert drive.travelled(fast["subject"]["motion"]["params"], sh["endS"] - sh["startS"]) < lane
    assert math.hypot(*subject_pose(fast, p, CAT, sh["startS"], 0).offset[:2]) > lane / 2
