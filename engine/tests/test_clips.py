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
