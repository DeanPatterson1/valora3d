"""Phase 6 Task 99: the sim hygiene rules behind compile.json.simProbe (pure). Report-only until the good and bad
fixtures separate on real bakes (PHASING: thresholds before gating); these pin the arithmetic on synthetic good
and bad caches."""
import math

from engine.physics.sim_stats import (INSIDE_MAX, cloth_stretch, inside_verdict, liquid_volume, rigid_verdict,
                                      speeds)

FPS = 30


def _fall(n=60, rest=20):
    """One piece falling then resting: z drops 5 cm/frame for `rest` frames, then holds."""
    return [[(0.0, 0.0, max(0.05, 1.0 - 0.05 * f))] for f in range(n)]


def test_speeds_are_finite_differences_in_metres_per_second():
    s = speeds([[(0, 0, 0)], [(0, 0, 0.1)], [(0, 0, 0.3)]], FPS)
    assert [round(v[0], 6) for v in s] == [3.0, 6.0]


def test_a_settling_rigid_bake_is_stable():
    v = rigid_verdict(_fall(), FPS, max_speed_ms=10)
    assert v["finite"] and v["ok"] and v["keTailRatio"] <= 0.01 and v["maxSpeedMs"] == 1.5


def test_a_nan_frame_is_unstable():
    frames = _fall()
    frames[30] = [(math.nan, 0.0, 0.0)]
    v = rigid_verdict(frames, FPS, max_speed_ms=10)
    assert not v["finite"] and not v["ok"]


def test_an_explosion_is_unstable():
    frames = _fall()
    frames[40] = [(0.0, 0.0, 50.0)]                       # a piece jumps 50 m in one frame
    v = rigid_verdict(frames, FPS, max_speed_ms=10)
    assert v["finite"] and not v["ok"] and v["maxSpeedMs"] > 30


def test_still_moving_at_the_end_is_unstable():
    frames = [[(0.0, 0.0, 1.0 - 0.02 * f)] for f in range(60)]   # never rests
    assert not rigid_verdict(frames, FPS, max_speed_ms=10)["ok"]


def test_points_inside_the_proxy_fail_above_one_in_a_thousand():
    assert inside_verdict([False] * 2000)["ok"]
    assert inside_verdict([True] + [False] * 1999)["ok"]           # 0.05%
    bad = inside_verdict([True] * 3 + [False] * 997)                # 0.3%
    assert not bad["ok"] and bad["share"] > INSIDE_MAX and bad["inside"] == 3


def test_cloth_stretch_and_liquid_volume_rules():
    rest = [1.0, 1.0, 2.0]
    assert cloth_stretch(rest, [1.2, 1.0, 4.0])["ok"]
    assert not cloth_stretch(rest, [3.0, 1.0, 2.0])["ok"]
    assert liquid_volume([1.0, 1.0, 0.9, 0.88])["ok"]
    assert not liquid_volume([1.0, 1.0, 0.7])["ok"]
