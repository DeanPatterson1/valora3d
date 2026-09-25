"""Phase 5 Task 59 (hand-off H4): one wind, a calibration per consumer (pure)."""
import math

from engine.catalog import Catalog
from engine.physics import sway
from engine.physics.wind_calibration import (coherent, consumer_value, ff_seed, force_field_strength, perms,
                                             rain_slant_deg)


def test_rain_slant_matches_wind_over_fall_speed():
    assert math.isclose(rain_slant_deg(0.0, 6.5), 0.0)
    assert math.isclose(rain_slant_deg(6.5, 6.5), 45.0, rel_tol=1e-6)


def test_every_wind_driven_block_declares_a_calibration():
    cat = Catalog.load()
    for kind in ("effect", "realism"):
        for bid in cat.ids(kind):
            ph = cat.get(kind, bid).get("physics") or {}
            if ph.get("windDriven"):
                assert ph.get("windCalibration"), f"{kind}/{bid} reads wind but declares no calibration"


def test_declared_calibrations_are_todays_constants_so_nothing_changes_look():
    cat = Catalog.load()
    cal = lambda kind, bid: cat.get(kind, bid)["physics"]["windCalibration"]  # noqa: E731
    assert cal("effect", "haze_volume")["perMs"] == 1.0          # wisps advect with the full mean wind
    assert cal("realism", "shaft_dust")["perMs"] == 1.0          # motes drift with the full mean wind
    assert cal("realism", "foliage_sway")["perMs"] == sway.DRAG_K
    assert cal("realism", "dangling_sway")["perMs"] == sway.DRAG_K
    assert perms(cat, "effect", "haze_volume") == 1.0 and perms(cat, "effect", "nope", default=0.5) == 0.5


def test_consumer_value_is_linear_in_speed_and_zero_when_calm():
    cal = {"unit": "m/s drift", "perMs": 0.6}
    assert consumer_value(cal, 0.0) == 0.0 and math.isclose(consumer_value(cal, 5.0), 3.0)


def test_force_field_strength_is_monotonic_and_seed_in_range():
    s = [force_field_strength(v) for v in (0, 2, 5, 10, 14)]
    assert s == sorted(s) and s[0] == 0.0
    assert all(1 <= ff_seed(k) <= 128 for k in (0, 1, 127, 128, 10 ** 9))


def test_coherent_is_within_45_degrees_of_the_wind_when_it_blows():
    assert coherent([1.0, 0.1, 0.0], 0.0, 3.0) == {"angleDeg": 5.71, "ok": True}
    assert coherent([0.0, -1.0, 0.0], 0.0, 3.0)["ok"] is False
    assert coherent([0.0, 0.0, 0.0], 0.0, 1.0) == {"angleDeg": None, "ok": None}   # below 1.5 m/s: not judged
