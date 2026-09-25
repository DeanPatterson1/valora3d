import random

import pytest

from engine.physics.wheel_mask import half_width, in_wheel_box, island_spins, radial, tyre_mask, tyre_weight

W = {"center": [0.8, 1.3, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "width": 0.14, "tyreBand": [0.6, 1.0]}


def test_half_width_falls_back_when_ingest_found_no_width():
    assert half_width(W) == pytest.approx(0.07)
    assert half_width({**W, "width": None}) == pytest.approx(0.3 * 0.35)


def test_whole_tyre_and_rim_spin_but_an_off_axis_caliper_does_not():
    tyre = ([0.73, 0.95, 0.0], [0.87, 1.65, 0.70], [0.8, 1.3, 0.35])
    caliper = ([0.74, 1.38, 0.43], [0.82, 1.46, 0.51], [0.78, 1.42, 0.47])
    body = ([-0.7, -2.0, 0.2], [0.7, 2.0, 1.1], [0.0, 0.0, 0.65])
    assert island_spins(*tyre, W) and in_wheel_box(*tyre[:2], W)
    assert in_wheel_box(*caliper[:2], W) and not island_spins(*caliper, W)
    assert not in_wheel_box(*body[:2], W)


def test_a_piece_in_the_boxes_corner_is_not_a_wheel_part_when_its_radial_reach_is_known():
    # review fix 1: the square +/-1.05 r box reaches 1.48 r at its corners (sports_car bumper trim was tagged)
    import numpy as np
    trim = ([0.76, 1.58, 0.60], [0.84, 1.64, 0.68])        # up and ahead of the tyre, inside the square box
    pts = np.array([[0.8, 1.58, 0.60], [0.8, 1.64, 0.68]])
    reach = float(radial(pts, W).max())
    assert reach > 1.05 * W["radius"]
    assert in_wheel_box(*trim, W)                            # the legacy square box (ingest islands) takes it
    assert not in_wheel_box(*trim, W, rmax=reach)            # the radial reach rejects it
    tyre_pts = np.array([[0.8, 1.3, 0.0], [0.8, 1.65, 0.35], [0.8, 1.3, 0.70]])
    assert in_wheel_box([0.73, 0.95, 0.0], [0.87, 1.65, 0.70], W, rmax=float(radial(tyre_pts, W).max()))


def test_tyre_band_is_the_rubber_ring_not_the_rim():
    assert tyre_weight([0.8, 1.3, 0.0], W) == 1           # bottom of the tread
    assert tyre_weight([0.8, 1.3, 0.35 - 0.25], W) == 1   # sidewall at 0.71 r
    assert tyre_weight([0.8, 1.3, 0.35 - 0.10], W) == 0   # rim face at 0.29 r
    assert tyre_weight([0.5, 1.3, 0.0], W) == 0           # outside the tyre's width


def test_numpy_mask_matches_the_scalar_rule():
    np = pytest.importorskip("numpy")
    rng = random.Random(1)
    pts = [[0.8 + rng.uniform(-0.2, 0.2), 1.3 + rng.uniform(-0.4, 0.4), rng.uniform(-0.05, 0.75)] for _ in range(3000)]
    got = tyre_mask(np.array(pts), W)
    assert got.tolist() == [bool(tyre_weight(p, W)) for p in pts]
