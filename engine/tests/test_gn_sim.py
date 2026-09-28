"""Phase 6 Task 103: the pure maths of the shared GN point sim (engine/physics/gn_sim.py)."""
import math
import random

import pytest

from engine.physics import gn_sim as S


def test_spawn_frames_is_an_exact_seeded_count_inside_the_window():
    a = S.spawn_frames(120, -11, 48, 24, random.Random(3))
    assert len(a) == round(120 * 60 / 24) == 300
    assert a == sorted(a) and -12 <= a[0] and a[-1] <= 48
    assert a == S.spawn_frames(120, -11, 48, 24, random.Random(3))           # seeded
    assert a != S.spawn_frames(120, -11, 48, 24, random.Random(4))
    assert len(S.spawn_frames(1e9, 1, 100, 24, random.Random(0))) == S.MAX_POINTS
    assert S.spawn_frames(0, 1, 10, 24, random.Random(0)) == []


def test_burst_frames_spread():
    b = S.burst_frames(50, 10, 2, random.Random(1))
    assert len(b) == 50 and 10 <= min(b) and max(b) < 12
    assert set(S.burst_frames(5, 7, 0, random.Random(1))) == {7}


def test_alive_peak_counts_overlap():
    assert S.alive_peak([0, 0, 30], [1.0, 1.0, 1.0], 24) == 2      # the third is born after both die (24 f)
    assert S.alive_peak([0, 5, 10], [1.0, 1.0, 1.0], 24) == 3


def test_estimate_and_cache_scale_linearly():
    assert S.estimate_s(1e4, 100) == pytest.approx(S.BAKE_OVERHEAD_S + S.BAKE_S_PER_10K_100F)
    assert S.estimate_s(2e4, 200, substeps=2) == pytest.approx(S.BAKE_OVERHEAD_S + 8 * S.BAKE_S_PER_10K_100F)
    assert S.cache_mb(1000, 100, attrs=4) == pytest.approx(6.0)


def test_cone_velocity_speed_and_angle():
    rng = random.Random(9)
    for _ in range(200):
        v = S.cone_velocity(rng, (0, 0, 2), 3, 15, 20)
        s = math.sqrt(sum(c * c for c in v))
        assert 3 - 1e-9 <= s <= 15 + 1e-9
        assert math.degrees(math.acos(v[2] / s)) <= 20 + 1e-6


def test_triangle_samples_are_area_weighted_and_on_the_mesh():
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (10, 0, 0), (13, 0, 0), (10, 3, 0)]
    tris = [(0, 1, 2), (3, 4, 5)]                  # areas 0.5 and 4.5
    pts = S.triangle_samples(verts, tris, 4000, random.Random(2))
    share = sum(1 for _, t in pts if t == 1) / len(pts)
    assert abs(share - 0.9) < 0.03
    for p, t in pts:
        assert p[2] == 0 and (p[0] >= 10 if t else p[0] + p[1] <= 1 + 1e-9)


def test_tangential_gravity_is_downhill_and_tangent():
    n = (math.sqrt(0.5), 0, math.sqrt(0.5))
    g = S.tangential_gravity(n)
    assert abs(sum(a * b for a, b in zip(g, n))) < 1e-12 and g[2] < 0
    assert S.tangential_gravity((1, 0, 0)) == pytest.approx((0, 0, -S.G))     # a vertical wall: full g
    assert S.tangential_gravity((0, 0, 1)) == pytest.approx((0, 0, 0))        # a flat top: none
