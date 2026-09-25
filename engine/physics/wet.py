"""Wet ground (plan Task 65; port of render-studio rain_scene.wet_asphalt / wet_detail, generalised). Pure.

Wet stone is darker and smoother than dry: albedo x albedo_factor(wetness) (1 -> 0.6 at full wetness) and
roughness x roughness_factor(wetness) (1 -> 0.1). Standing water fills where a summed height noise is below
the level puddle_threshold(puddles), and `puddles` is the share of open ground under water: the level is the
height field's measured quantile at that share (PUDDLE_HEIGHT_Q), so 0 is dry, 1 floods everything and the level
rises with the param (review chunk3 #2: 1 - puddles flooded 85% of the ground at the default 0.4 and 100% at 0;
render-studio's "roughly a third" is puddles 0.33 here).
Inside a puddle the water is optically flat (PUDDLE_ROUGH) so it mirrors like glass. Every number marked (eng)
is in the calibration register (Task 65 look-check)."""

ALBEDO_WET = 0.6        # (eng) albedo factor at wetness 1 (render-studio: wet stone ~half as reflective)
ROUGH_WET = 0.1         # (eng) roughness factor at wetness 1
PUDDLE_ROUGH = 0.02     # (eng) standing water roughness: a mirror (the coat; x 0.2 inside pools)
STONE_ROUGH_MIN = 0.3   # (eng) wet stone under the film never drops below this (render-studio: 0.34-0.62)
FILM_COAT = (0.62, 0.88)   # (eng) water-film coat weight from damp to saturated (render-studio wet_asphalt)
PUDDLE_SCALE_M = 4.8    # (eng) puddle noise feature size in metres (render-studio macro scale 0.21 / m)
PATCH_SCALE, PATCH_DETAIL, PATCH_AMP = 1.35, 3.0, 0.35   # (eng) the small patch noise summed into the height
PUDDLE_EDGE = 0.022     # (eng) a pool's shore: the mask smoothsteps over this much water depth
# Quantiles of height = macro.Fac + PATCH_AMP * (patch.Fac - 0.5) (share of ground below -> height), measured on
# Blender 5.0.1 2026-09-25 over 250k points of a 400 m grid (engine/tests/test_blocks_phase5_blender.py re-measures
# them). The end points bound the field (macro in [0, 1], patch term +-PATCH_AMP/2, plus the 0.022 smoothstep).
PUDDLE_HEIGHT_Q = ((0.0, -0.2), (0.01, 0.2821), (0.05, 0.3401), (0.1, 0.3743), (0.2, 0.4168), (0.3, 0.4485),
                   (0.4, 0.4756), (0.5, 0.4996), (0.6, 0.5237), (0.7, 0.5509), (0.8, 0.5831), (0.9, 0.6255),
                   (0.95, 0.6602), (0.99, 0.7174), (1.0, 1.2))
APRON_DEPTH = 0.12      # (eng) extra standing-water depth under the subject's posed footprint (render-studio apron)
RIPPLE_HZ = 2.5         # (eng) ripple ring cycles per second while it rains
DRIP_HZ = 0.25          # (eng) slow drip rings on calm puddles after the rain ...
DRIP_SPREAD, DRIP_AMP = 0.06, 0.2   # (eng) ... only near a few cell centres, faint (first look-check: 0.25 / 1.0
                                    # read as a choppy sea at pocket-watch scale)


def albedo_factor(wetness):
    return 1.0 - (1.0 - ALBEDO_WET) * float(wetness)


def roughness_factor(wetness):
    return 1.0 - (1.0 - ROUGH_WET) * float(wetness)


def puddle_threshold(puddles):
    """The water level: the height below which `puddles` (a share of the ground, 0..1) stands under water."""
    p = min(1.0, max(0.0, float(puddles)))
    for (a, ha), (b, hb) in zip(PUDDLE_HEIGHT_Q, PUDDLE_HEIGHT_Q[1:]):
        if p <= b:
            # + half the shore, so the mask's 0.5 contour (not its first wet pixel) sits on the quantile
            return round(ha + (hb - ha) * (p - a) / (b - a) + PUDDLE_EDGE / 2, 6)
    return PUDDLE_HEIGHT_Q[-1][1]


def coat_weight(wetness):
    lo, hi = FILM_COAT
    return lo + (hi - lo) * float(wetness)


def ripple_mode(params, effect_ids):
    """'rain' (impact ripples), 'drips' (slow rings after the rain) or None (calm mirrors)."""
    if params.get("ripples", "auto") == "auto" and "rain" in effect_ids:
        return "rain"
    if params.get("drips", True) and "rain" not in effect_ids:
        return "drips"
    return None
