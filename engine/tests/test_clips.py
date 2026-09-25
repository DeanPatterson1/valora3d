"""Pure play_clip helpers (engine/clips.py): which clips exist, which one a prompt means, how the NLA
strips cover the video."""
import itertools
import math

import pytest

from engine.clips import MAX_NLA_REPEAT, MIN_CLIP_S, choose_clip, clip_kept, resolve_mode, strip_plan
from engine.script import DURATION_RANGE, FPS


def _clips(*names, durs=None):
    durs = durs or [2.0] * len(names)
    return [{"index": i, "nameHint": n, "durationS": d} for i, (n, d) in enumerate(zip(names, durs))]


def _ask(text):
    return {"ask": text, "capability": "motion.character_clip", "source": "prompt"}


def test_choose_clip_by_ask_stem_then_longest_then_lowest_index():
    assert choose_clip([_ask("walks")], _clips("Idle", "Walk")) == 1
    assert choose_clip([_ask("character runs")], _clips("Idle", "Walk", "Run_Fast")) == 2
    assert choose_clip([_ask("dancing")], _clips("Idle", "Dance01", "dance02")) == 1   # first match
    assert choose_clip([_ask("walks")], _clips("Anim_0")) == 0
    assert choose_clip([_ask("waving")], _clips("A", "B", "C", durs=[1.0, 3.0, 3.0])) == 1  # longest, tie -> low
    assert choose_clip([], _clips("A", "B", durs=[1.0, 2.0])) == 1
    assert choose_clip([{"ask": "rain", "capability": "weather.rain"}], _clips("Rain", "B", durs=[1.0, 2.0])) == 1
    assert choose_clip([_ask("walks")], []) == 0


def test_clip_kept_drops_clips_shorter_than_the_floor():
    assert MIN_CLIP_S == pytest.approx(0.25)
    assert clip_kept(1.0, 25.0, 24.0) and not clip_kept(1.0, 2.0, 24.0) and not clip_kept(1.0, 25.0, 0.0)


def test_resolve_mode():
    assert resolve_mode("auto", True) == "loop" and resolve_mode("auto", None) == "loop"
    assert resolve_mode("auto", False) == "pingpong"
    for m in ("loop", "once", "pingpong"):
        assert resolve_mode(m, False) == m


def test_strip_plan_never_exceeds_blender_repeat_max_and_covers_the_video():
    """Every durationS/fps/speed/offset/clip length the checker admits (clips >= MIN_CLIP_S at 24-60 fps)."""
    assert MAX_NLA_REPEAT == 1000.0          # NlaStrip.repeat hard_max, Blender 5.0.1 (probed 2026-09-24)
    durs = [DURATION_RANGE[0], 10, DURATION_RANGE[1]]
    for dur, fps, speed, off, clip_s, clip_fps, mode in itertools.product(
            durs, FPS, (0.5, 1.0, 1.5), (0.0, 10.0), (MIN_CLIP_S, 0.5, 3.0, 40.0), (24.0, 60.0),
            ("loop", "once", "pingpong")):
        clip_frames = clip_s * clip_fps
        scale = fps / clip_fps / speed
        loop = clip_frames * scale
        video, offset = dur * fps + 2, off * fps
        segs = strip_plan(loop, video, offset, mode)
        assert all(0 < r <= MAX_NLA_REPEAT for _, r, _ in segs)
        assert segs[0][0] == pytest.approx(1 - offset)
        for (s0, r0, _), (s1, _r, _) in zip(segs, segs[1:]):
            assert s1 == pytest.approx(s0 + r0 * loop)       # contiguous, no gap or overlap
        end = segs[-1][0] + segs[-1][1] * loop
        if mode == "once":
            assert len(segs) == 1 and segs[0][1] == 1.0
        else:
            assert end >= 1 + video - 1e-6, (dur, fps, speed, off, clip_s, mode)
        if mode == "pingpong":
            assert [rev for _, _, rev in segs] == [k % 2 == 1 for k in range(len(segs))]
            assert all(r == 1.0 for _, r, _ in segs)


def test_strip_plan_splits_a_loop_past_the_repeat_max():
    segs = strip_plan(1.0, 2500.0, 0.0, "loop")
    assert len(segs) >= 3 and all(r <= MAX_NLA_REPEAT for _, r, _ in segs)
    assert math.fsum(r for _, r, _ in segs) >= 2500.0


def test_only_clips_measured_with_the_current_clip_map_count():
    # independent review P1: a profile measured before the short-clip filter can index a different action
    # for the same clip number; its clips are unavailable (re-ingest), never silently replayed
    from engine.clips import CLIP_MAP_VERSION, clips_current
    ok = {"index": 0, "fps": 24.0, "clipMapVersion": CLIP_MAP_VERSION}
    assert clips_current([ok, {**ok, "index": 1}])
    assert not clips_current([])
    assert not clips_current([{k: v for k, v in ok.items() if k != "clipMapVersion"}])
    assert not clips_current([ok, {**ok, "clipMapVersion": CLIP_MAP_VERSION - 1}])


def test_a_root_motion_clip_loops_in_place_and_says_so():
    # independent review P1: a walk that travels would teleport back each loop; auto/loop plays it in place
    from engine.clips import in_place_line, plays_in_place
    walk = {"index": 1, "seamless": True, "rootMotion": True}
    assert plays_in_place(walk, "auto") and plays_in_place(walk, "loop")
    assert not plays_in_place(walk, "pingpong") and not plays_in_place(walk, "once")
    assert not plays_in_place({**walk, "seamless": False}, "auto")          # auto ping-pongs it: no jump
    assert not plays_in_place({**walk, "rootMotion": False}, "loop")
    assert not plays_in_place({"index": 0}, "loop")                       # unknown: never assumed
    clips = [{"index": 0, "seamless": True}, walk]
    assert in_place_line(clips, {"id": "play_clip", "params": {"clip": 1}}) \
        == "clip 1 walks forward, so it plays in place (a loop would jump back each cycle)"
    assert in_place_line(clips, {"id": "play_clip", "params": {"clip": 1, "mode": "once"}}) is None
    assert in_place_line(clips, {"id": "play_clip", "params": {"clip": 0}}) is None
    assert in_place_line(clips, {"id": "play_clip", "params": {"clip": 9}}) is None
    assert in_place_line(clips, {"id": "static", "params": {}}) is None


def _walker_profile(travel=(1.0, 0.0), seamless=True):
    import json
    from pathlib import Path
    from engine.clips import CLIP_MAP_VERSION
    from engine.profile import SubjectProfile
    d = json.loads((Path(__file__).parent / "fixtures" / "profile_car.json").read_text())
    clip = {"index": 0, "frameStart": 1.0, "frameEnd": 25.0, "fps": 24.0, "durationS": 1.0, "nameHint": "walk",
            "seamless": seamless, "clipMapVersion": CLIP_MAP_VERSION, "rootMotion": True,
            "rootTravelM": list(travel)}
    return SubjectProfile.from_dict({**d, "sizeM": [0.2, 0.2, 0.4], "boundsMin": [-0.1, -0.1, 0.0],
                                     "boundsMax": [0.1, 0.1, 0.4], "animationClips": [clip]})


def _script(mode, duration=6.0, speed=1.0, offset=0.0):
    return {"format": {"durationS": duration, "fps": 30},
            "subject": {"motion": {"id": "play_clip", "params": {"clip": 0, "mode": mode, "speed": speed,
                                                                 "offsetS": offset}}}}


def test_once_and_pingpong_frame_the_swept_travel_loop_stays_in_place():
    from engine.clips import swept_profile
    p = _walker_profile()
    for mode in ("once", "pingpong"):
        s = swept_profile(p, _script(mode))
        assert s.boundsMin == [-0.1, -0.1, 0.0] and s.boundsMax == [1.1, 0.1, 0.4], (mode, s.boundsMax)
        assert s.sizeM == [1.2, 0.2, 0.4]
        assert s.sourceCenter == p.sourceCenter            # placement unchanged: the walk starts where it stands
        assert swept_profile(s, _script(mode)) is s          # never swept twice
    assert swept_profile(p, _script("loop")) is p
    assert swept_profile(p, _script("auto")) is p            # seamless: auto loops in place
    assert swept_profile(_walker_profile(seamless=False), _script("auto")).boundsMax[0] == 1.1  # auto pingpongs
    half = swept_profile(p, _script("once", duration=2.0, speed=0.5))   # 2 s of a 2 s pass... all of it
    assert half.boundsMax[0] == 1.1
    part = swept_profile(p, _script("once", duration=2.0, speed=0.25))  # a 4 s pass, 2 s played: half the travel
    assert abs(part.boundsMax[0] - 0.6) < 1e-9
    back = swept_profile(_walker_profile(travel=(0.0, -2.0)), _script("once"))
    assert back.boundsMin[1] == -2.1 and back.boundsMax[1] == 0.1


def test_no_sweep_without_root_motion_or_a_measured_travel():
    from dataclasses import replace
    from engine.clips import swept_profile
    p = _walker_profile()
    still = replace(p, animationClips=[{**p.animationClips[0], "rootMotion": False}])
    assert swept_profile(still, _script("once")) is still
    old = replace(p, animationClips=[{k: v for k, v in p.animationClips[0].items() if k != "rootTravelM"}])
    assert swept_profile(old, _script("once")) is old
    assert swept_profile(p, {"format": {"durationS": 6.0, "fps": 30}, "subject": {"motion": {"id": "none"}}}) is p
