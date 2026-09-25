"""Task 67: snow maths (pure)."""
import math

import pytest

from engine.physics import snow as S


def test_fall_speed_is_inside_pt04():
    speeds = [S.flake(3, i)[0] for i in range(200)]
    assert S.SPEED_MS[0] <= min(speeds) and max(speeds) <= S.SPEED_MS[1] and max(speeds) - min(speeds) > 0.5


def test_wobble_is_bounded_by_its_amplitude():
    for i in range(50):
        _, w = S.flake(9, i)
        for k in range(100):
            x, y = S.wobble(k * 0.037, w)
            assert abs(x) <= w[0] + 1e-12 and abs(y) <= w[0] + 1e-12 and w[0] <= S.WOBBLE_A_M[1]


def test_accumulation_only_faces_up():
    assert not S.accumulates(0.7) and not S.accumulates(0.2) and S.accumulates(0.71)
    assert S.accumulation_mm(5.0, 0.4, 0.0) == 5.0 and S.accumulation_mm(5.0, 0.4, 10.0) == pytest.approx(5.2)


def test_flake_count_scales_with_rate():
    assert S.flake_count(0.2, 10.0) < S.flake_count(0.4, 10.0) < S.flake_count(0.8, 10.0)
    assert S.flake_count(1.0, 1e6) == S.MAX_FLAKES


def test_same_seed_same_flakes_at_frame_40():
    t = 39 / 30.0
    a = [S.drift(t, *S.flake(21, i), (1.0, 0.5)) for i in range(20)]
    b = [S.drift(t, *S.flake(21, i), (1.0, 0.5)) for i in range(20)]
    assert a == b and a != [S.drift(t, *S.flake(22, i), (1.0, 0.5)) for i in range(20)]


def test_snow_follows_the_wind():
    dx, dy, dz = S.drift(10.0, 1.0, (0.0, 0.5, 0.5, 0.0, 0.0), (2.0, 0.0))
    assert dx == pytest.approx(0.9 * 2.0 * 10.0) and dz == pytest.approx(-10.0) and math.isclose(dy, 0.0, abs_tol=1e-12)
