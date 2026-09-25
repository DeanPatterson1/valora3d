"""Task 65: wet ground maths (pure)."""
import pytest

from engine.physics import wet as W


def test_wetness_darkens_and_smooths_linearly():
    assert W.albedo_factor(0.0) == 1.0 and W.albedo_factor(1.0) == pytest.approx(0.6)
    assert W.roughness_factor(0.0) == 1.0 and W.roughness_factor(1.0) == pytest.approx(0.1)
    assert W.albedo_factor(0.5) == pytest.approx(0.8) and W.roughness_factor(0.5) == pytest.approx(0.55)


def test_more_puddles_raise_the_water_level():                         # review chunk3 #2
    levels = [W.puddle_threshold(k / 20) for k in range(21)]
    assert all(a < b for a, b in zip(levels, levels[1:]))
    assert W.puddle_threshold(0.0) < -W.PATCH_AMP / 2                                       # below the lowest height
    assert W.puddle_threshold(1.0) >= 1.0 + W.PATCH_AMP / 2 + W.PUDDLE_EDGE                       # above the highest + smoothstep
    assert W.puddle_threshold(0.5) == pytest.approx(0.4996 + W.PUDDLE_EDGE / 2)             # the measured median


def test_ripples_only_while_it_rains():
    assert W.ripple_mode({"ripples": "auto", "drips": True}, ["rain", "wet_surface"]) == "rain"
    assert W.ripple_mode({"ripples": "off", "drips": True}, ["rain", "wet_surface"]) is None
    assert W.ripple_mode({"ripples": "auto", "drips": True}, ["wet_surface"]) == "drips"
    assert W.ripple_mode({"ripples": "auto", "drips": False}, ["wet_surface"]) is None
