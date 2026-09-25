"""Task 64: rain maths (pure)."""
import math

import pytest

from engine.physics import rain as R


def test_fall_speed_matches_render_studio():
    assert R.fall_speed(2.0) == pytest.approx(6.5, abs=0.05)            # render-studio's 6.5 m/s
    assert R.fall_speed(0.8) < R.fall_speed(2.0) < R.fall_speed(3.0) < 9.65
    assert R.fall_speed(0.01) == 0.5                                      # floor


def test_streak_length_is_speed_times_the_shutter():
    assert R.streak_len(6.5) == pytest.approx(0.108, abs=5e-4)           # METHODS' 11 cm example


def test_drop_position_is_periodic_in_the_box_height():
    d, v, h = R.slant_vector((0.0, 0.0), 6.5), 6.5, 3.0
    a = R.drop_position((0.0, 0.0, 3.0), 0.2, 0.7, d, v, h)
    b = R.drop_position((0.0, 0.0, 3.0), 0.2, 0.7 + h / v, d, v, h)
    assert a == pytest.approx(b, abs=1e-9)


def test_counts_grow_with_intensity_and_cap():
    box = 10.0 * 10.0 * 4.0 / 100.0                                       # 4 m3
    counts = [R.drop_count(R.INTENSITY[k]["rateMmH"], box) for k in ("drizzle", "steady", "downpour")]
    assert counts[0] < counts[1] < counts[2]
    assert R.drop_count(50.0, 1e6) == R.MAX_DROPS


def test_slant_follows_the_wind():
    assert R.slant_vector((0.0, 0.0), 6.5) == pytest.approx((0.0, 0.0, -1.0))
    d = R.slant_vector((6.5, 0.0), 6.5)
    assert math.degrees(math.atan2(d[0], -d[2])) == pytest.approx(45.0)
    assert R.slant_deg(6.5, 6.5) == pytest.approx(45.0)


def test_shelter_is_the_footprint():
    lo, hi = (-1.0, -2.0, 0.0), (1.0, 2.0, 1.2)
    assert R.sheltered((0.5, 1.9), lo, hi) and not R.sheltered((1.2, 0.0), lo, hi, margin=0.1)
    assert R.sheltered((1.05, 0.0), lo, hi, margin=0.1)


def test_intensity_presets_and_explicit_values():
    assert R.resolve({"intensity": "drizzle", "rateMmH": 0.0, "dropSizeMm": 0.0}) == (1.0, 0.8)
    assert R.resolve({"intensity": "downpour", "rateMmH": 12.0, "dropSizeMm": 0.0}) == (12.0, 3.0)


def test_box_covers_the_view_and_the_subject():
    side, h = R.box_size(4.5, 1.3, 8.0, 35.0)
    assert side >= 1.5 * 8.0 and side >= 1.5 * (2 * 8.0 * 18 / 35) - 1e-9 and h >= 1.5 * 1.3
    assert R.box_size(0.07, 0.05, 0.4, 100.0) == (R.BOX_MIN_M, R.BOX_H_MIN_M)       # a watch: the 1 m floor
    assert R.box_size(30.0, 5.0, 60.0, 24.0) == (R.BOX_CAP_M, R.BOX_H_CAP_M)


def test_impacts_scale_with_rate_and_area():
    a = R.impact_slots(4.0, 2.0, 1.0)
    assert 30 <= a <= 50                                                  # ~265 drops/m2/s x 0.15 s
    assert R.impact_slots(25.0, 3.0, 1.0) > a and R.impact_slots(4.0, 2.0, 1e6) == R.IMPACT_CAP
