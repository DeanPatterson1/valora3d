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


# --- realism audit #15: one wetness owner; scanned relief shapes the shores and the film --------------------

def test_one_owner_for_the_ground_wetness():
    assert W.world_wetness(0.8, ["haze_volume"]) == pytest.approx(0.8)      # the world's own damp sheen
    assert W.world_wetness(0.8, ["wet_surface", "rain"]) == 0.0             # wet_surface owns it: never twice


def test_wet_stone_roughness_follows_the_scan():
    # render-studio wet_asphalt: the scanned roughness mapped to 0.34-0.62 at full wetness (no flat clamp)
    assert W.stone_roughness(0.0, 1.0) == pytest.approx(0.34) and W.stone_roughness(1.0, 1.0) == pytest.approx(0.62)
    assert W.stone_roughness(0.7, 0.0) == pytest.approx(0.7)               # dry: the scan itself
    lo, hi = W.stone_roughness(0.2, 1.0), W.stone_roughness(0.8, 1.0)
    assert hi - lo == pytest.approx(0.28 * 0.6)                            # the scan's variation survives


def test_film_roughness_varies_with_the_scan_and_saturation():
    assert W.film_roughness(0.0, 0.0) == pytest.approx(0.07) and W.film_roughness(1.0, 0.0) == pytest.approx(0.20)
    assert W.film_roughness(1.0, 1.0) == pytest.approx(0.20 * 0.55)        # a saturated film is smoother


def test_scanned_height_is_zero_mean_so_the_puddle_share_holds():
    assert W.scan_height_term(0.5) == 0.0
    assert W.scan_height_term(1.0) == pytest.approx(-W.scan_height_term(0.0)) == pytest.approx(W.SCAN_HEIGHT_K / 2)


def test_banks_and_pool_beds_darken():
    assert W.bank_albedo(0.0) == 1.0 and W.bank_albedo(1.0) == pytest.approx(0.40 / 0.56)
    assert W.bed_albedo(0.0) == 1.0 and W.bed_albedo(1.0) == pytest.approx(0.62)
