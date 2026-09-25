"""Window rooms with depth (interior mapping) - the pure maths the room shader mirrors."""
import math

import pytest

from engine import interior_mapping as I


def test_straight_on_view_sees_the_back_wall():
    s, hit = I.room_hit(0.6, 0.8, (0.0, 0.0, 1.0), 1.2, 1.6)
    assert s == "back" and hit == pytest.approx((0.6, 0.8, I.ROOM_DEPTH_M))


def test_oblique_views_find_side_wall_ceiling_and_floor():
    w, h = 1.2, 1.6
    assert I.room_hit(0.6, 0.8, (1.0, 0.0, 0.2), w, h)[0] == "side"      # looking along the facade
    assert I.room_hit(0.6, 0.8, (0.0, 1.0, 0.3), w, h)[0] == "ceiling"    # from the street below
    assert I.room_hit(0.6, 0.8, (0.0, -1.0, 0.3), w, h)[0] == "floor"     # from above


def test_hits_lie_on_the_room_box():
    w, h = 1.2, 1.6
    (x0, x1), (y0, y1), (z0, z1) = I.bounds(w, h)
    for d in [(0.3, 0.2, 1.0), (-0.9, 0.1, 0.4), (0.1, 0.9, 0.2), (0.2, -0.8, 0.5)]:
        s, (x, y, z) = I.room_hit(0.5, 0.7, d, w, h)
        on = {"back": abs(z - z1) < 1e-6, "side": min(abs(x - x0), abs(x - x1)) < 1e-6,
              "ceiling": abs(y - y1) < 1e-6, "floor": abs(y - y0) < 1e-6}[s]
        assert on and x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6 and 0 <= z <= z1 + 1e-6


def test_the_ceiling_near_the_lamp_is_the_brightest_surface():
    w, h = 1.2, 1.6
    lamp = I.lamp_at(w, h, 0.5)
    ceil = I.brightness("ceiling", (lamp[0], lamp[1] + 0.15, lamp[2]), lamp)
    back = I.brightness("back", (0.6, 0.5, I.ROOM_DEPTH_M), lamp)
    floor = I.brightness("floor", (0.6, -I.ROOM_SILL_M, 1.0), lamp)
    assert ceil > back > floor > I.AMBIENT


def test_local_direction_frame():
    t, n_out = (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)                         # a facade facing -y
    assert I.local_dir((0.0, 1.0, 0.0), t, n_out) == pytest.approx((0.0, 0.0, 1.0))   # into the room
    assert I.parallax_shift(I.ROOM_DEPTH_M, 45.0) == pytest.approx(I.ROOM_DEPTH_M)
    assert I.parallax_shift(1.0, 0.0) == 0.0 and math.isfinite(I.parallax_shift(1.0, 80.0))
