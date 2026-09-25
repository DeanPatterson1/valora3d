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


# --- realism pass (audit #19): varied flakes, a smoothed accumulation shell --------------------------------

def test_flake_sizes_vary_and_clumps_are_bigger():
    import random
    rng = random.Random(4)
    singles = [S.flake_size_mm(rng.random(), 6.0, False) for _ in range(4000)]
    clumps = [S.flake_size_mm(rng.random(), 6.0, True) for _ in range(4000)]
    assert min(singles) >= 6.0 * S.SIZE_SPREAD[0] - 1e-9 and max(singles) <= 6.0 * S.SIZE_SPREAD[1] + 1e-9
    assert sorted(singles)[2000] < 6.0 * sum(S.SIZE_SPREAD) / 2 * 0.85   # skewed: most flakes small, a few big
    assert sum(clumps) / len(clumps) > 1.6 * sum(singles) / len(singles)
    assert S.is_clump(S.CLUMP_SHARE - 1e-6) and not S.is_clump(S.CLUMP_SHARE + 1e-6)


def test_flakes_tumble_at_a_bounded_rate():
    a0 = (0.3, 1.0, 2.0)
    w = S.tumble_rate((0.0, 0.5, 1.0))
    assert all(abs(x) <= S.TUMBLE_RAD_S + 1e-12 for x in w) and w[0] == pytest.approx(-S.TUMBLE_RAD_S)
    assert S.tumble(a0, w, 0.0) == a0
    assert S.tumble(a0, w, 2.0) == pytest.approx(tuple(a0[i] + 2.0 * w[i] for i in range(3)))


def test_cover_depth_rolls_off_toward_the_edge_of_the_up_facing_surface():
    full = S.cover_depth_mm(5.0, 1.0, 0.5)
    assert full == pytest.approx(5.0)                                   # flat roof, mean noise: the full depth
    assert S.cover_depth_mm(5.0, S.UP_DOT, 0.5) == pytest.approx(S.MIN_LIFT_MM)   # meets the car at the edge
    ds = [S.cover_depth_mm(5.0, nz, 0.5) for nz in (0.71, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)]
    assert ds == sorted(ds) and ds[-1] - ds[0] > 4.0                    # a rounded, smoothly thinning edge


def test_cover_depth_varies_with_noise_but_stays_positive():
    lo, hi = S.cover_depth_mm(5.0, 1.0, 0.0), S.cover_depth_mm(5.0, 1.0, 1.0)
    assert lo == pytest.approx(5.0 * (1 - S.DEPTH_VAR)) and hi == pytest.approx(5.0 * (1 + S.DEPTH_VAR))
    assert all(S.cover_depth_mm(a, nz, n) >= S.MIN_LIFT_MM for a in (0.1, 5.0, 40.0)
               for nz in (0.7, 0.8, 1.0) for n in (0.0, 0.5, 1.0))


def test_snow_scatters_light_under_its_surface():
    assert 0.005 <= S.SSS_SCALE_M <= 0.05                              # centimetres, not microns
    r, g, b = S.SSS_RADIUS
    assert b > r                                                        # blue travels further: snow's blue shadow
    assert 0.0005 <= S.GRAIN_M <= 0.002                                 # ice grains ~ 1 mm


def test_flake_card_look_is_mostly_soft_discs_some_dendrites():
    assert 0.0 < S.DENDRITE_SHARE < 0.5 and 0.5 < S.FLAKE_OPACITY <= 1.0 and 0.0 < S.FLAKE_TRANSLUCENCY < 0.5


def test_the_shell_thins_to_a_patchy_dusting_then_bare_paint():
    assert S.cover_share(1.0, 0.5) == 1.0 and S.cover_share(1.0, 0.2) == 1.0          # deep: solid snow
    assert S.cover_share(0.0, 0.5) == 0.0 and S.cover_share(0.0, 0.75) == 0.0         # the edge: bare paint
    mid = [S.cover_share(0.4, n / 20) for n in range(21)]
    assert min(mid) == 0.0 and max(mid) == 1.0                                          # patchy between


def test_the_dusting_breaks_up_grain_by_grain():
    assert S.cover_share(0.35, 0.5, 0.0) < S.cover_share(0.35, 0.5, 1.0)
    assert S.cover_share(1.0, 0.0, 0.0) == 1.0 and S.cover_share(0.0, 0.5, 1.0) == 0.0
