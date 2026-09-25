"""Wet ground (plan Task 65; port of render-studio rain_scene.wet_asphalt / wet_detail, generalised). Pure.

Wet stone is darker and smoother than dry: albedo x albedo_factor(wetness) (1 -> 0.6 at full wetness) and
roughness x roughness_factor(wetness) (1 -> 0.1). Standing water fills where a summed height noise is below
the level puddle_threshold(puddles) = 1 - puddles, so puddles 0.31 gives render-studio's PUDDLE_LEVEL 0.69.
Inside a puddle the water is optically flat (PUDDLE_ROUGH) so it mirrors like glass. Every number marked (eng)
is in the calibration register (Task 65 look-check)."""

ALBEDO_WET = 0.6        # (eng) albedo factor at wetness 1 (render-studio: wet stone ~half as reflective)
ROUGH_WET = 0.1         # (eng) roughness factor at wetness 1
PUDDLE_ROUGH = 0.02     # (eng) standing water roughness: a mirror
FILM_COAT = (0.62, 0.88)   # (eng) water-film coat weight from damp to saturated (render-studio wet_asphalt)
PUDDLE_SCALE_M = 4.8    # (eng) puddle noise feature size in metres (render-studio macro scale 0.21 / m)
APRON_DEPTH = 0.12      # (eng) extra standing-water depth under the subject's posed footprint (render-studio apron)
RIPPLE_HZ = 2.5         # (eng) ripple ring cycles per second while it rains
DRIP_HZ = 0.25          # (eng) slow drip rings on calm puddles after the rain


def albedo_factor(wetness):
    return 1.0 - (1.0 - ALBEDO_WET) * float(wetness)


def roughness_factor(wetness):
    return 1.0 - (1.0 - ROUGH_WET) * float(wetness)


def puddle_threshold(puddles):
    return round(1.0 - float(puddles), 6)


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
