"""The Cycles recipe is pinned per tier (realism audit #17, #20): nothing a render depends on is left to the
installed Cycles defaults. Final follows render-studio's rain film (rain_look.py:97-113,
render_snapshot.py:237-251)."""
import pytest

from engine.compiler.tiers import RECIPE_KEYS, TIERS, cycles_recipe


@pytest.mark.parametrize("tier", sorted(TIERS))
def test_every_tier_pins_every_recipe_key(tier):
    r = cycles_recipe(tier)
    assert set(r) == set(RECIPE_KEYS)
    assert r["samples"] == TIERS[tier]["samples"]
    assert 1 <= r["adaptive_min_samples"] <= r["samples"]
    assert r["use_animated_seed"] is False and r["seed"] == 20260915


def test_final_is_the_film_recipe():
    r = cycles_recipe("final")
    assert r["transparent_max_bounces"] == 24          # stacked foliage alpha / thin sheets (audit #17)
    assert r["transmission_bounces"] == 8 and r["sample_clamp_indirect"] == 5.0
    assert r["filter_width"] == 1.95
    # the declared defaults already exceed the film's total/diffuse/glossy; they are pinned, not raised
    assert (r["max_bounces"], r["diffuse_bounces"], r["glossy_bounces"]) == (12, 4, 4)
    assert r["sample_clamp_direct"] == 0.0 and r["caustics_reflective"] and r["caustics_refractive"]
    assert r["denoiser"] == "OPENIMAGEDENOISE" and r["denoising_prefilter"] == "ACCURATE"
    assert r["denoising_input_passes"] == "RGB_ALBEDO_NORMAL"


def test_final_is_the_clean_benchmark():
    """Critique mat-v2 #1: a clean frame first (grain is added after, display-referred). 128 max samples (was 1024 / .005, then 256 / .01, until 2026-09-29, see tiers.FINAL_SAMPLES),
    adaptive threshold .02, min 64, one OIDN stage at High quality with albedo + normal, Accurate prefilter."""
    r = cycles_recipe("final")
    assert r["samples"] == 128 and r["adaptive_threshold"] == 0.02 and r["adaptive_min_samples"] == 64
    assert r["denoising_quality"] == "HIGH"


def test_a_close_detail_gets_the_close_up_budget():
    from engine.compiler.tiers import CLOSEUP_FIELD_M, frame_samples
    assert frame_samples("final", detail=True, field_m=0.84) == 2048            # the headlight: 100 mm at 2.33 m
    assert frame_samples("final", detail=True, field_m=1.59) == 128            # the wheel: 85 mm at 3.76 m
    assert frame_samples("final", detail=True, field_m=CLOSEUP_FIELD_M + 0.1) == 128
    assert frame_samples("final", detail=False, field_m=0.5) == 128
    assert frame_samples("preview", detail=True, field_m=0.5) == TIERS["preview"]["samples"]


def test_cheaper_tiers_never_exceed_final():
    f = cycles_recipe("final")
    for tier in ("preview", "keyframes"):
        r = cycles_recipe(tier)
        for k in ("max_bounces", "transparent_max_bounces", "samples", "adaptive_min_samples"):
            assert r[k] <= f[k], (tier, k)
        assert r["adaptive_threshold"] >= f["adaptive_threshold"]
        assert r["filter_width"] == f["filter_width"]     # same optics at every tier: previews judge the look


def test_unknown_tier_is_refused():
    with pytest.raises(KeyError):
        cycles_recipe("ultra")
