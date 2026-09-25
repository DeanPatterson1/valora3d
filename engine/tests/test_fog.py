"""Task 60: ground_fog pure maths (engine/physics/fog.py)."""
import math

import pytest

from engine.physics import fog as F


def test_density_falls_off_monotonically_with_height():
    zs = [0.0, 0.1, 0.2, 0.4, 0.8, 1.6]
    d = [F.fog_density(z, 0.4, 0.4) for z in zs]
    assert d[0] == pytest.approx(0.4 * F.FOG_SIGMA)
    assert all(a > b for a, b in zip(d, d[1:]))
    assert F.fog_density(0.4, 0.4, 0.4) == pytest.approx(d[0] / math.e)
    assert F.fog_density(-1.0, 0.4, 0.4) == pytest.approx(d[0])       # below the ground: the ground value
    assert F.fog_density(0.2, 0.4, 0.0) == 0.0


def test_pocket_is_zero_inside_and_full_outside():
    r = 1.3
    assert F.pocket_weight(0.0, r) == 0.0 and F.pocket_weight(r, r) == 0.0
    assert F.pocket_weight(2 * r, r) == 1.0 and F.pocket_weight(5 * r, r) == 1.0
    mid = [F.pocket_weight(r * (1 + k / 10), r) for k in range(11)]
    assert all(a <= b for a, b in zip(mid, mid[1:])) and mid[5] == pytest.approx(0.5)


def test_mist_is_three_times_higher_and_less_dense():
    assert F.mode_params("fog", 0.4, 0.5) == (0.4, 0.5)
    h, d = F.mode_params("mist", 0.4, 0.5)
    assert h == pytest.approx(1.2) and d == pytest.approx(0.2)


def test_domain_and_pocket_scale_with_the_subject():
    assert F.domain_width(4.5, 12.0) == pytest.approx(F.FOG_EXTENT * 12.0)
    assert F.domain_width(4.5, 2.0) == pytest.approx(F.FOG_EXTENT * 4.5)
    assert F.pocket_radius(2.3) == pytest.approx(F.POCKET * 2.3)
    assert F.domain_height(0.4) == pytest.approx(F.TOP_K * 0.4)
