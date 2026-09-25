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
    assert r["filter_width"] == 1.95 and r["adaptive_threshold"] == 0.025
    assert r["adaptive_min_samples"] == 24
    # the declared defaults already exceed the film's total/diffuse/glossy; they are pinned, not raised
    assert (r["max_bounces"], r["diffuse_bounces"], r["glossy_bounces"]) == (12, 4, 4)
    assert r["sample_clamp_direct"] == 0.0 and r["caustics_reflective"] and r["caustics_refractive"]
    assert r["denoiser"] == "OPENIMAGEDENOISE" and r["denoising_prefilter"] == "ACCURATE"
    assert r["denoising_input_passes"] == "RGB_ALBEDO_NORMAL"


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
