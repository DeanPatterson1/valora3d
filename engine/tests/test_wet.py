"""Task 65: wet ground maths (pure)."""
import pytest

from engine.physics import wet as W


def test_wetness_darkens_and_smooths_linearly():
    assert W.albedo_factor(0.0) == 1.0 and W.albedo_factor(1.0) == pytest.approx(0.6)
    assert W.roughness_factor(0.0) == 1.0 and W.roughness_factor(1.0) == pytest.approx(0.1)
    assert W.albedo_factor(0.5) == pytest.approx(0.8) and W.roughness_factor(0.5) == pytest.approx(0.55)


def test_puddle_threshold_matches_render_studio():
    assert W.puddle_threshold(0.31) == 0.69            # rain_scene.PUDDLE_LEVEL
    assert W.puddle_threshold(0.0) == 1.0 and W.puddle_threshold(1.0) == 0.0


def test_ripples_only_while_it_rains():
    assert W.ripple_mode({"ripples": "auto", "drips": True}, ["rain", "wet_surface"]) == "rain"
    assert W.ripple_mode({"ripples": "off", "drips": True}, ["rain", "wet_surface"]) is None
    assert W.ripple_mode({"ripples": "auto", "drips": True}, ["wet_surface"]) == "drips"
    assert W.ripple_mode({"ripples": "auto", "drips": False}, ["wet_surface"]) is None
