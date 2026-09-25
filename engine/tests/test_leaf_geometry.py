"""Fallen-leaf geometry (engine/worlds/leaf_geometry.py), pure: render-studio's LEAF_PROFILE leaves."""
import math
import random

import pytest

from engine.worlds import leaf_geometry as L


def test_profile_is_render_studios_ovate_outline():
    assert L.LEAF_PROFILE[0] == (0.0, 0.0) and L.LEAF_PROFILE[-1] == (1.0, 0.0)      # pointed at both ends
    assert max(h for _, h in L.LEAF_PROFILE) == 1.0
    alongs = [a for a, _ in L.LEAF_PROFILE]
    assert alongs == sorted(alongs)


def test_one_leaf_is_rows_of_three_with_quads_between():
    v, f = L.leaf(xy=(0.0, 0.0), yaw_deg=0.0, half_width=0.02, length=0.08, fold=0.0, curl=0.0, twist=0.0)
    n = len(L.LEAF_PROFILE)
    assert len(v) == 3 * n and len(f) == 2 * (n - 1)
    assert all(len(q) == 4 and max(q) < len(v) for q in f)


def test_flat_leaf_spans_its_length_and_twice_its_half_width():
    v, _ = L.leaf(xy=(1.0, 2.0), yaw_deg=0.0, half_width=0.02, length=0.08, fold=0.0, curl=0.0, twist=0.0)
    xs, ys, zs = zip(*v)
    assert max(xs) - min(xs) == pytest.approx(0.08)
    assert max(ys) - min(ys) == pytest.approx(0.04)
    assert (min(xs) + max(xs)) / 2 == pytest.approx(1.0) and (min(ys) + max(ys)) / 2 == pytest.approx(2.0)
    assert min(zs) == pytest.approx(L.REST_M) and max(zs) == pytest.approx(L.REST_M)


def test_yaw_turns_the_midrib():
    v, _ = L.leaf(xy=(0.0, 0.0), yaw_deg=90.0, half_width=0.01, length=0.1, fold=0.0, curl=0.0, twist=0.0)
    xs, ys, _ = zip(*v)
    assert max(ys) - min(ys) == pytest.approx(0.1)
    assert max(xs) - min(xs) == pytest.approx(0.02)


@pytest.mark.parametrize("seed", range(40))
def test_every_folded_curled_twisted_leaf_rests_on_the_road_never_through_it(seed):
    rng = random.Random(seed)
    fold, curl, twist = L.shape(rng)
    v, _ = L.leaf(xy=(0.0, 0.0), yaw_deg=rng.uniform(0, 360), half_width=0.03, length=0.1,
                  fold=fold, curl=curl, twist=twist)
    zs = [p[2] for p in v]
    assert min(zs) == pytest.approx(L.REST_M, abs=1e-9)
    assert max(zs) < 0.1 * 0.4 + 0.03                                  # a curled leaf, not a standing one


def test_shape_draws_render_studios_ranges():
    rng = random.Random(1)
    for _ in range(500):
        fold, curl, twist = L.shape(rng)
        assert 0.05 <= fold <= 0.32 and -0.10 <= curl <= 0.28 and -0.10 <= twist <= 0.10


def test_fold_raises_the_edges_above_the_midrib():
    v, _ = L.leaf(xy=(0.0, 0.0), yaw_deg=0.0, half_width=0.02, length=0.08, fold=0.3, curl=0.0, twist=0.0)
    widest = max(range(len(L.LEAF_PROFILE)), key=lambda i: L.LEAF_PROFILE[i][1])
    left, mid, right = v[3 * widest: 3 * widest + 3]
    assert left[2] > mid[2] + 0.004 and right[2] > mid[2] + 0.004


def test_curl_lifts_the_tips():
    v, _ = L.leaf(xy=(0.0, 0.0), yaw_deg=0.0, half_width=0.02, length=0.08, fold=0.0, curl=0.25, twist=0.0)
    tip, centre = v[1], v[3 * 3 + 1]
    assert tip[2] - centre[2] == pytest.approx(0.25 * 0.08 * 1.0, rel=0.05)
    assert math.isclose(v[1][2], v[-2][2])
