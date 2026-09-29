"""Rain as analytic streams (METHODS FL-01, PT-04 pattern; plan Task 64). Pure; stdlib only.

Each drop i has a seeded base point in a lattice box and falls along one direction at one speed:
position(t) = base + dir * speed * t, wrapped into a box that follows the camera, so frame N needs no frame
N-1 (METHODS R1). Fall speed by drop size (Atlas et al. fit), slant from the one wind field (perMs 1.0: the
drop drifts with the air), streak length = speed x shutter time (180 deg at 24 fps -> 1/48 s). The box and
the counts are sized here so the Blender builder and its tests agree on every number.

Every number marked (eng) is in the plan's calibration register (Task 64 look-check)."""
import math

INTENSITY = {  # (eng) mm/h and drop size by preset; render counts come from rate x box volume
    "drizzle": {"rateMmH": 1.0, "dropSizeMm": 0.8},
    "steady": {"rateMmH": 4.0, "dropSizeMm": 2.0},
    "downpour": {"rateMmH": 25.0, "dropSizeMm": 3.0},
}
MAX_DROPS = 60000          # (eng) instance cap per clip, by cost
DROPS_PER_MM_H_M3 = 90.0   # (eng) visible streak density per (mm/h x m^3); calibrated by the look-check
BOX_FAR_K = 1.5            # (eng) the box spans 1.5 x the farthest camera distance ...
BOX_MIN_M, BOX_CAP_M = 1.0, 30.0      # (eng) ... at least 1 m, at most 30 m across
BOX_H_MIN_M, BOX_H_CAP_M = 1.0, 12.0  # (eng) box height: 1.5 x the subject height or half the side
NEAR_FRAC = 0.1            # (eng) no drop closer to the camera than 10% of the nearest camera distance
IMPACT_LIFE_S = 0.15       # (eng) a ground crown lives 0.15 s (3-4 frames at 24 fps; plan: 3-8 frames)
IMPACT_CAP = 4000          # (eng) crowns alive at once, by cost
SENSOR_HALF_MM = 18.0      # engine/geometry.SENSOR_MM / 2 (the long side)
VISIBLE_SIZE_K = 2.3       # (eng) render-studio rain_look 'rain_size': a true 1 mm drop is a third of a pixel at
                           # 1080p and vanishes against an overcast sky, so drops render 2.3x their radius
GLOW = 1.1                 # (eng) render-studio 'rain_glow' at our default backlight: emission on airborne water,
                           # the only rain brightness the film's indirect clamp cannot cap
# Round 5 (critique mat-v2 #3): the streaks read as an overlay. Their whole contribution (glow and the rain-only
# backlight) is cut to STREAK_SHARE, and to DETAIL_STREAK_SHARE in a close detail shot (25-50% there), switched
# per shot at the cuts.
STREAK_SHARE = 0.32        # round 9 (owner's r8 grade: "the rain streaks still read as an effect layer"; was 0.5): with
#                            the body beaded the scene reads wet on its own, and a filmed drizzle shows a few faint
#                            streaks against dark trees, not a curtain
STREAK_SIZE = (0.3, 1.0)   # round 8 (owner's r7 grade: "rain streaks less uniformly prominent"): each drop's visible
#                            radius x a per-drop random in this range, so a few streaks read and most recede
DETAIL_STREAK_SHARE = 0.22   # round 9 (was 0.35)


def streak_share(detail):
    """The share of the film's streak brightness a shot keeps."""
    return DETAIL_STREAK_SHARE if detail else STREAK_SHARE


RATE_RANGE_MM_H = (0.1, 50.0)   # the manifest's zeroOrMin .. max: an explicit rate outside it is not rain
SIZE_RANGE_MM = (0.5, 4.0)      # physical raindrops: < 0.5 mm is drizzle mist, > 4 mm breaks up (manifest zeroOrMin)


def _explicit(v, lo, hi):
    """An explicit value > 0 inside [lo, hi] (a hostile 1e-200 or inf never reaches the maths, review chunk3 #1)."""
    try:
        v = float(v or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(v) or v <= 0.0:
        return 0.0
    return min(max(v, lo), hi)


def resolve(params):
    """(rateMmH, dropSizeMm): an explicit value > 0 wins (held to the physical range), 0 = the intensity preset
    (review amendment 64)."""
    pre = INTENSITY[params.get("intensity", "steady")]
    rate = _explicit(params.get("rateMmH"), *RATE_RANGE_MM_H) or pre["rateMmH"]
    size = _explicit(params.get("dropSizeMm"), *SIZE_RANGE_MM) or pre["dropSizeMm"]
    return rate, size


def fall_speed(d_mm):
    """Terminal velocity (m/s) for a drop of diameter d (mm): 9.65 - 10.3 exp(-0.6 d) (Atlas et al.)."""
    return max(0.5, 9.65 - 10.3 * math.exp(-0.6 * d_mm))


def streak_len(speed, fps=24, shutter=0.5):
    return speed * shutter / fps


def box_size(longest, height, far_m, lens_mm):
    """(side, height) in metres of the square, camera-following rain box: wide enough for the widest view at
    the farthest camera distance, never smaller than 1.5 x the subject."""
    wide = 2.0 * far_m * SENSOR_HALF_MM / max(lens_mm, 1.0)
    side = min(BOX_CAP_M, max(BOX_MIN_M, BOX_FAR_K * far_m, BOX_FAR_K * wide, BOX_FAR_K * longest))
    h = min(BOX_H_CAP_M, max(BOX_H_MIN_M, 1.5 * height, 0.5 * side))
    return side, h


def drop_count(rate_mm_h, box_m3):
    return min(MAX_DROPS, int(DROPS_PER_MM_H_M3 * rate_mm_h * box_m3))


def slant_vector(wind_vec, speed):
    """Unit fall direction including wind drift (wind_vec in m/s, world XY)."""
    x, y, z = wind_vec[0], wind_vec[1], -speed
    n = math.sqrt(x * x + y * y + z * z)
    return (x / n, y / n, z / n)


def velocity(wind_vec, speed):
    """A drop's velocity (m/s): the full wind drift horizontally and the full fall speed down (review chunk3 #3:
    unit slant x fall speed shrank both by the slant's cosine/sine)."""
    return (float(wind_vec[0]), float(wind_vec[1]), -float(speed))


def slant_deg(wind_speed, speed):
    return math.degrees(math.atan2(wind_speed, speed))


def drop_position(spawn, phase, t, fall_dir, speed, box_h):
    """Wrapped analytic position; spawn is the top of the column."""
    s = ((t + phase) * speed) % box_h
    return (spawn[0] + fall_dir[0] * s, spawn[1] + fall_dir[1] * s, spawn[2] + fall_dir[2] * s)


def sheltered(xy, bounds_lo, bounds_hi, margin=0.0):
    """A drop whose column passes over the posed subject's footprint dies at its roof (no rain under a car)."""
    return (bounds_lo[0] - margin <= xy[0] <= bounds_hi[0] + margin) and (bounds_lo[1] - margin <= xy[1] <= bounds_hi[1] + margin)


IMPACT_PERIOD_S = 2 * IMPACT_LIFE_S   # (eng) one impact per lattice cell per period, so a cell's crown is gone
                                     # before its next drop lands
LATTICE_JITTER = 0.5       # (eng) Voronoi randomness of the impact lattice: each cell's feature point stays within
                           # half a cell of its corner, so a sample at the jitter square's middle finds its own point


def impact_lattice(rate_mm_h, drop_mm, side_m, seed):
    """The ONE impact source rain crowns and puddle ripples share (review chunk3 #6): a world-fixed Voronoi lattice
    of cell `cellM` (jitter LATTICE_JITTER, offset by `offset` cells from the seed); each cell's feature point is
    hit once per `periodS` at phase = the cell's Voronoi colour (red), so event age = frac(t / periodS + red).
    Sized so impact_slots crowns are alive at once over the side x side box (same density and cap as before).
    None when nothing lands."""
    slots = impact_slots(rate_mm_h, drop_mm, side_m * side_m)
    if slots <= 0:
        return None
    cells = slots * IMPACT_PERIOD_S / IMPACT_LIFE_S
    cell = side_m / math.sqrt(cells)
    k = int(seed) % 997
    return {"cellM": cell, "periodS": IMPACT_PERIOD_S, "lifeS": IMPACT_LIFE_S, "jitter": LATTICE_JITTER,
            "offset": [round(k * 0.37 % 1000, 6), round(k * 0.61 % 1000, 6)], "across": int(math.ceil(side_m / cell)) + 2}


def clip_box(profile, camera_positions, lenses_mm):
    """(side, height, far, near) of the clip's rain box from the camera keys (the rain builder and wet_surface
    read the same numbers)."""
    far = max((math.dist(q, profile.center) for q in camera_positions), default=4.0 * profile.radius)
    near = min((math.dist(q, profile.center) for q in camera_positions), default=far)
    side, height = box_size(profile.longest, profile.sizeM[2], far, min(lenses_mm or [50.0]))
    return side, height, far, near


def clip_lattice(script, profile, camera_positions, lenses_mm):
    """The script's rain impact lattice, or None (no rain, or nothing lands): the one source rain's
    crowns and wet_surface's ripples share, whichever of the two builds first."""
    from engine.compiler.context import block_seed
    rain = next((e for e in script.get("effects", []) if e.get("id") == "rain"), None)
    if rain is None:                    # impacts off hides the crowns only: the puddles still ripple
        return None
    rate, size = resolve(rain.get("params") or {})
    side = clip_box(profile, camera_positions, lenses_mm)[0]
    return impact_lattice(rate, size, side, block_seed(script["seed"], "effect", "rain") + 7)


def impact_age(t, period, red):
    """An impact's age as a share of its period (0 = the drop just landed), for a cell whose Voronoi colour red is
    `red`: the formula both the crown tree and the ripple shader build."""
    return (t / period + red) % 1.0


def impact_slots(rate_mm_h, drop_mm, area_m2):
    """Ground crowns alive at once: drops landing per m2 per s (rate / drop volume) x life x area, capped."""
    r = drop_mm / 2000.0
    if not (r > 0.0 and math.isfinite(r)) or r ** 3 <= 0.0:
        return 0
    per_m2_s = (rate_mm_h / 3.6e6) / (4.0 / 3.0 * math.pi * r ** 3)
    return min(IMPACT_CAP, int(per_m2_s * IMPACT_LIFE_S * area_m2))
