import math

import pytest

from engine.physics import sway, wind


def test_direction_is_where_the_air_goes_world_azimuth_ccw_from_x():
    x, y, z = wind.vector(90.0, 4.0)
    assert (x, y, z) == pytest.approx((0.0, 4.0, 0.0), abs=1e-9)


@pytest.mark.parametrize("speed,force", [(0.0, 0), (0.8, 1), (3.0, 2), (7.0, 4), (13.0, 6), (20.0, 7)])
def test_beaufort(speed, force):
    assert wind.beaufort(speed) == force


def test_gust_envelope_and_calm():
    assert wind.envelope(4.0, 0.3) == pytest.approx((2.8, 5.2))
    assert wind.envelope(4.0, 1.0)[0] == 0.0
    assert wind.is_calm(0.2) and not wind.is_calm(0.8)


def test_bend_grows_with_speed_squared_and_is_capped():
    assert sway.bend_frac(0.0, 0.4) == 0.0
    assert sway.bend_frac(2.0, 0.4) == pytest.approx(0.02 * 4 * 0.68)
    assert sway.bend_frac(14.0, 0.0) == pytest.approx(math.tan(math.radians(25)))
    assert sway.tip_offset(0.5, 0.2, 2.0, 0.4) == pytest.approx(sway.bend_frac(2.0, 0.4) * 0.2 * 0.25)
