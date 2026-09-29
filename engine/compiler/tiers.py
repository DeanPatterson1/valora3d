"""Render tiers (spec §4.7). `keyframes` exists for tests and eval only. Preview = composition and
motion in minutes. Final = the paid clip. Sample counts are (eng): the final default follows the
engine survey's measured 192 spp baseline, and the spec's open question 2 (price per clip) may
change it."""
from engine.geometry import aspect_wh

SHUTTER = 0.5  # 180 degrees, centred (TIERS T2-05)

# Final sampling (2026-09-29 render-cost lane, golden_field 1080p x 3 frames, OIDN on): 256 spp / adaptive .01 is
# indistinguishable from the old 1024 / .005 (PSNR 49.4 dB to the same scene rendered at 1024, the same as two seeds of
# 1024 against each other: 49.6 dB) at 1/3.2 of the time. 128 / .02 (47.1 dB) and 64 / .03 (45.7 dB) also held; they are
# one edit away here. Adaptive sampling is what stops early, so the cap only matters for the hard pixels.
FINAL_SAMPLES = 256
FINAL_THRESHOLD = 0.01

TIERS = {
    "keyframes": {"shortSide": 144, "samples": 4, "denoise": True, "passes": True},
    "preview": {"shortSide": 540, "samples": 16, "denoise": True, "passes": True, "lodScaled": False},
    "final": {"shortSide": 1080, "samples": FINAL_SAMPLES, "denoise": True, "passes": False},
}
# Final is the clean benchmark (critique mat-v2 #1, 2026-09-25): the 192 spp film recipe left speckle the OIDN
# pass could not hold, and the grain on top of it hid detail. Adaptive sampling stops most pixels far below the
# cap; a close detail (a headlight: the frame's long side spans < CLOSEUP_FIELD_M at the target) gets
# CLOSEUP_SAMPLES, where the critique saw the grain first.
CLOSEUP_FIELD_M = 1.2
CLOSEUP_SAMPLES = 2048


SEED = 20260915   # render-studio rain_look.LOOK['seed']: one fixed noise seed, never animated
RECIPE_KEYS = ("samples", "adaptive_min_samples", "adaptive_threshold", "max_bounces", "diffuse_bounces",
               "glossy_bounces", "transmission_bounces", "transparent_max_bounces", "volume_bounces",
               "sample_clamp_direct", "sample_clamp_indirect", "caustics_reflective", "caustics_refractive",
               "filter_width", "seed", "use_animated_seed", "denoiser", "denoising_prefilter",
               "denoising_input_passes", "denoising_quality")
# Final = render-studio's rain film (rain_look.py:97-113, render_snapshot.py:237-251): 24 transparent bounces,
# indirect clamp 5, 1.95 px filter, adaptive threshold .025. Total/diffuse/glossy/transmission keep the Cycles
# 5.0 declared values (12/4/4) or the film's (transmission 8); they are PINNED here, not raised, so a Blender
# upgrade cannot move them. Cheaper tiers trade bounces and the noise threshold, never the optics (filter).
_BASE = {"max_bounces": 12, "diffuse_bounces": 4, "glossy_bounces": 4, "transmission_bounces": 8,
         "transparent_max_bounces": 24, "volume_bounces": 0, "sample_clamp_direct": 0.0,
         "sample_clamp_indirect": 5.0, "caustics_reflective": True, "caustics_refractive": True,
         "filter_width": 1.95, "seed": SEED, "use_animated_seed": False, "denoiser": "OPENIMAGEDENOISE",
         "denoising_prefilter": "ACCURATE", "denoising_input_passes": "RGB_ALBEDO_NORMAL",
         "denoising_quality": "HIGH"}
_PER_TIER = {"final": {"adaptive_threshold": FINAL_THRESHOLD, "adaptive_min_samples": 64},
             "preview": {"adaptive_threshold": 0.05, "transparent_max_bounces": 16},
             "keyframes": {"adaptive_threshold": 0.1, "max_bounces": 8, "transmission_bounces": 6,
                           "transparent_max_bounces": 8}}


def cycles_recipe(tier):
    """Every Cycles setting a render depends on, for one tier (KeyError for an unknown tier)."""
    t = TIERS[tier]
    r = {**_BASE, "samples": t["samples"], "adaptive_min_samples": max(1, t["samples"] // 8), **_PER_TIER[tier]}
    return {k: r[k] for k in RECIPE_KEYS}


def frame_samples(tier, *, detail, field_m):
    """The sample cap for one frame: a final-tier detail shot whose frame spans < CLOSEUP_FIELD_M (long side, at
    the target) gets CLOSEUP_SAMPLES."""
    n = TIERS[tier]["samples"]
    if tier == "final" and detail and field_m is not None and field_m < CLOSEUP_FIELD_M:
        return max(n, CLOSEUP_SAMPLES)
    return n


def resolution(aspect, short_side):
    """Width and height that are both even (video encoders need it), keep the aspect exactly
    (w * ah == h * aw) and never fall below short_side: the smallest k with k * min(aw, ah) >=
    short_side, k even whenever aw or ah is odd (4:5 at 540 -> 544 x 680)."""
    w, h = aspect_wh(aspect)
    step = 1 if w % 2 == 0 and h % 2 == 0 else 2
    k = -(-short_side // (min(w, h) * step)) * step
    return w * k, h * k


def _apply_override():
    """Experiment hook: VALORA_TIER_OVERRIDE='{"final": {"samples": 256, "adaptive_threshold": 0.01}}' patches the
    tier table for one process (and the Blender child it spawns, which inherits the environment). Unset in
    production; never write it into a job."""
    import json
    import os
    raw = os.environ.get("VALORA_TIER_OVERRIDE")
    if not raw:
        return
    for tier, kv in json.loads(raw).items():
        for k, v in kv.items():
            (TIERS[tier] if k in TIERS[tier] else _PER_TIER[tier] if k in _PER_TIER[tier] else _BASE)[k] = v


_apply_override()
