"""Wet ground (plan Task 65; port of render-studio rain_scene.wet_asphalt / wet_detail, generalised). Pure.

Wet stone is darker and smoother than dry: albedo x albedo_factor(wetness) (1 -> 0.6 at full wetness) and
roughness x roughness_factor(wetness) (1 -> 0.1). Standing water fills where a summed height noise is below
the level puddle_threshold(puddles), and `puddles` is the share of open ground under water: the level is the
height field's measured quantile at that share (PUDDLE_HEIGHT_Q), so 0 is dry, 1 floods everything and the level
rises with the param (review chunk3 #2: 1 - puddles flooded 85% of the ground at the default 0.4 and 100% at 0;
render-studio's "roughly a third" is puddles 0.33 here).
Inside a puddle the water is optically flat (PUDDLE_ROUGH) so it mirrors like glass. Every number marked (eng)
is in the calibration register (Task 65 look-check)."""
import math

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
TYRE_FILM_M = (0.06, 0.42)   # (eng, round 10) round each tyre's contact point: a flat water film (full inside the
#                              first radius, gone by the second) that mirrors the tyre where it meets the road
#                              (owner's r9 review: the tyre sat on matte asphalt; v04 f_08: the wet road mirrors
#                              the tyre right at its contact line)
TYRE_FILM_ROUGH = 0.03       # (eng) its coat roughness at full strength (a thin film, not a pool)
APRON_DEPTH = 0.12      # (eng) extra standing-water depth under the subject's posed footprint (render-studio apron)
RIPPLE_REACH = 0.45     # (eng) a rain ripple grows to 0.45 lattice cells over its period (stays in its cell) ...
RIPPLE_MAX_R_M = 0.05   # ... and never past 50 mm radius: real rain rings are 20-100 mm across (critique mat-v2 #3)
RIPPLE_WAVE_M = 0.010   # ripple ring wavelength (m): several fading crests inside one ring
RIPPLE_HEIGHT_M = 0.00015   # crest height: 0.05-0.3 mm on level water (a 0.75 mm crest read raised and rubbery)
RING_FIELD_PEAK = 0.5   # the ring fields' peak value (wave x envelope x 0.5); the bump distance turns it to metres
DRIP_HZ = 0.25          # (eng) slow drip rings on calm puddles after the rain ...
DRIP_SPREAD, DRIP_AMP = 0.06, 0.2   # (eng) ... only near a few cell centres, faint (first look-check: 0.25 / 1.0
                                    # read as a choppy sea at pocket-watch scale)


# realism audit #15 (render-studio rain_scene.wet_asphalt, rain_scene.py:137-237): the scan's height roughens the
# shores, saturated banks and pool beds darken, and the scan's roughness drives both the wet stone and the film.
SCAN_HEIGHT_K = 0.10            # height-field units per unit of the scanned displacement (render-studio .10)
DAMP_BAND = (-0.075, 0.0)       # water depth over which a pool's bank goes from damp to saturated
DEEP_BAND = (0.02, 0.16)        # depth over which a pool's bed darkens
PUDDLE_DISP_M = (0.002, 0.008)  # round 6: a pool is a real 2-8 mm depression (shore to bed, by DEEP_BAND), not a
#                                 painted coat: the asphalt steps down into it and the shore catches the light. Adaptive
#                                 subdivision near the camera only (1 px dicing): +17% render time on the courtyard hero
#                                 (look-check dbg_r6_court, 128 spp, 15.6 -> 18.2 s). None under the subject's apron,
#                                 where the tyres stand
DISP_PIXEL = 1.0                # adaptive dicing rate, px
BANK_ALBEDO = 0.40 / 0.56       # saturated bank vs damp stone (render-studio .56 -> .40)
BED_ALBEDO = 0.62               # pool bed
STONE_ROUGH_SCAN = (0.34, 0.62)   # wet aggregate roughness from the scanned roughness
FILM_ROUGH_SCAN = (0.07, 0.20)    # water-film roughness from the scanned roughness
FILM_SATURATED = 0.55           # a saturated film is this much smoother
FILM_RELIEF = (0.46, 0.24)      # how much of the stone's relief the film keeps, damp -> saturated
COAT_ROUGH_FLOOR = 0.004        # standing water: optically flat (render-studio .004)
# Round 11 (owner's r10 review: "the pavement is too glossy and curated"): real wet ground dries unevenly - wheel
# tracks, crowns and sheltered patches go damp-matte between the saturated lows. (eng) A coarse drying noise
# (DRY_SCALE_M patches, DRY_BAND of it) takes up to DRY_MAX of the film away there: the film's weight drops by
# DRY_MAX, its roughness rises by DRY_ROUGH and the stone lightens back toward dry by DRY_ALBEDO. Never inside a
# pool, on a pool's bank or in a tyre's water film.
DRY_SCALE_M = 1.6
DRY_BAND = (0.46, 0.62)
DRY_MAX = 0.7
DRY_ROUGH = 0.22
DRY_ALBEDO = 0.55


def ripple_bump_distance():
    """Bump distance (m) that makes a ring field's peak a RIPPLE_HEIGHT_M crest."""
    return RIPPLE_HEIGHT_M / RING_FIELD_PEAK


def ripple_radius_m(cell_m):
    """How far a rain ring grows over its period: RIPPLE_REACH cells, at most RIPPLE_MAX_R_M."""
    return min(RIPPLE_REACH * float(cell_m), RIPPLE_MAX_R_M)


def world_wetness(wetness, effect_ids):
    """The world's own damp sheen, or 0 when wet_surface owns the ground's wetness (never both)."""
    return 0.0 if "wet_surface" in effect_ids else float(wetness)


def stone_roughness(scan_rough, wetness):
    lo, hi = STONE_ROUGH_SCAN
    w = float(wetness)
    return (1.0 - w) * scan_rough + w * (lo + (hi - lo) * scan_rough)


def film_roughness(scan_rough, damp):
    lo, hi = FILM_ROUGH_SCAN
    return (lo + (hi - lo) * scan_rough) * (1.0 + (FILM_SATURATED - 1.0) * damp)


def scan_height_term(height):
    """Zero-mean (0.5 = no change), so the measured puddle quantiles (PUDDLE_HEIGHT_Q) still hold on average."""
    return SCAN_HEIGHT_K * (float(height) - 0.5)


def bank_albedo(damp):
    return 1.0 + (BANK_ALBEDO - 1.0) * damp


def bed_albedo(deep):
    return 1.0 + (BED_ALBEDO - 1.0) * deep


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


POOL_REACH = (0.15, 0.85)   # (eng, round 7) the mirror pool runs from 15% to 85% of the way from the subject's centre
#                             toward the hook camera: a low camera (0.3-0.7 m) sees a 0.3-1.4 m tall car mirrored in the
#                             ground 26-60% of the way out from itself, so this span holds the whole reflection
POOL_ACROSS_K = 0.6         # across the camera's line: semi-axis 0.6 x the subject's longest side (its 3/4 width)
POOL_DEPTH = 0.35           # water depth added over the pool's bed (height-field units): standing water throughout
POOL_SHORE = (0.7, 1.0)     # the pool fades out between these ellipse radii ...
POOL_WOBBLE = 0.6           # ... the shore pushed in and out by the puddle noise (never a drawn ellipse) ...
POOL_FINE_WOBBLE = 0.45     # ... and by the finer patch noise (round 8: the r7 shore read as one smooth oval)
POOL_CALM = 0.65            # round 8 0.85; round 11 0.65 (owner: "faint ripples in the puddle"): the pool keeps 35% ...
POOL_STIR = (0.66, 0.74)    # ... except where a coarse noise passes this band: a few local disturbances
POOL_STIR_SCALE = 0.9       # (1/m) the disturbances' noise scale (patches ~1 m across)


def pool_ellipse(centre, camera, longest):
    """(centre xy, unit axis toward the camera, semi-axis along, semi-axis across) of the one large mirror pool
    between the subject and the camera (placed metres), or None when the camera stands over the subject."""
    dx, dy = camera[0] - centre[0], camera[1] - centre[1]
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return None
    u = (dx / d, dy / d)
    r0, r1 = POOL_REACH
    mid = 0.5 * (r0 + r1) * d
    return ((centre[0] + u[0] * mid, centre[1] + u[1] * mid), u, 0.5 * (r1 - r0) * d, POOL_ACROSS_K * longest)


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
