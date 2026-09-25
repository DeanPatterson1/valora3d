"""golden_field layout, pure (phase 5 Task 71).

An open field around the subject (placed metres, ground at z = 0):
- the field is `extent` = max(EXTENT_MIN_M, EXTENT_K x longest) square; real blades (the foliage contract,
  hand-off H6) grow within `bladeRadius` = max(BLADE_R_MIN_M, BLADE_R_K x longest) of the subject, at a
  seeded density, capped at BLADE_CAP; farther out the grass is the ground texture;
- a clearing: no blade root inside the subject's footprint; within CLEAR_IN x the footprint the blades are
  CLEAR_FLOOR (20%) of their height, rising to full height by CLEAR_OUT x (the subject is not buried);
- with `track`, a flattened dirt track runs along the subject's longer horizontal axis (the drive lane),
  as wide as the subject + margin, with no blades on it;
- a far treeline/hill silhouette card ring at the field's edge (seeded heights);
- every draw comes from random.Random(seed): the layout is a pure function of its arguments.
Numbers marked (eng) are in the calibration register."""
import math
import random

EXTENT_MIN_M, EXTENT_K = 40.0, 10.0     # plan: field extent = max(40 m, 10 x longest)
BLADE_R_MIN_M, BLADE_R_K = 4.0, 2.5     # (eng) real blades out to this radius; beyond, the ground texture
BLADE_CAP = 60000                       # plan: 60k blades in view
DENSITY = {"grass": 160.0, "wheat": 110.0, "wildflowers": 140.0}   # (eng) blades per m^2
FLOWER_SHARE = 0.08                     # (eng) wildflowers: share of stems with a flower head
CLEAR_IN, CLEAR_OUT, CLEAR_FLOOR = 1.2, 2.0, 0.2   # plan 1.2 x footprint to 20%; (eng) full height by 2 x
HEIGHT_JITTER = (0.6, 1.2)              # (eng) blade height x grassHeightM
BLADE_W = 0.012                         # (eng) blade base width (real size, the courtyard's)
TRACK_MARGIN_K, TRACK_MARGIN_M = 0.15, 0.10         # the courtyard's exclusion margin (eng)
EDGE_TAPER = 0.25                       # (eng) the outer quarter of the blade disc tapers toward the ground
EDGE_FLOOR = 0.35                       # (eng) ... to this share of the height at the disc's edge
SIGHT_W_MIN, SIGHT_W_K = 0.25, 0.3      # (eng) sight corridor half-width: max(0.25 m, 0.3 x longest)
SIGHT_CLEAR_M = 0.02                    # (eng) blades in a corridor stay this far under the sight line
HORIZON_SEGMENTS = 48                   # (eng) silhouette card ring segments
HORIZON_H = (0.02, 0.07)                # (eng) silhouette height as a share of the ring radius


def _frame(profile):
    cx, cy = profile.center[0], profile.center[1]
    hx, hy = max(profile.half[0], 1e-4), max(profile.half[1], 1e-4)
    return (cx, cy), hx, hy


def clear_factor(q):
    """Blade height factor at normalised footprint distance q (1 = the footprint's edge, box norm)."""
    if q <= CLEAR_IN:
        return CLEAR_FLOOR
    if q >= CLEAR_OUT:
        return 1.0
    return CLEAR_FLOOR + (1.0 - CLEAR_FLOOR) * (q - CLEAR_IN) / (CLEAR_OUT - CLEAR_IN)


def track_rect(profile):
    """(x0, y0, x1, y1) of the dirt track along the subject's longer horizontal axis, through the field."""
    (cx, cy), hx, hy = _frame(profile)
    extent = max(EXTENT_MIN_M, EXTENT_K * profile.longest)
    m = TRACK_MARGIN_K * profile.longest + TRACK_MARGIN_M
    if hy >= hx:
        return (cx - hx - m, cy - extent / 2, cx + hx + m, cy + extent / 2)
    return (cx - extent / 2, cy - hy - m, cx + extent / 2, cy + hy + m)


def _sight_lines(profile, cameras):
    """(camera xy, camera z, subject xy, aim z) per distinct camera position: the line a camera needs clear to
    see the subject's lower body (a tenth of the way up its bounds)."""
    cx, cy, _ = profile.center
    aim = profile.boundsMin[2] + 0.1 * (profile.boundsMax[2] - profile.boundsMin[2])
    seen, out = set(), []
    for c in cameras:
        key = tuple(round(v / 0.1) for v in c)
        if key not in seen:
            seen.add(key)
            out.append(((c[0], c[1]), c[2], (cx, cy), aim))
    return out


def sight_cap(x, y, lines, half_w):
    """The tallest a blade at (x, y) may stand so no camera's sight line to the subject passes through it
    (inf when it is in no corridor)."""
    cap = math.inf
    for (ax, ay), az, (bx, by), bz in lines:
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            continue
        t = ((x - ax) * dx + (y - ay) * dy) / L2
        if not 0.0 <= t <= 1.0:
            continue
        if math.hypot(x - (ax + t * dx), y - (ay + t * dy)) > half_w:
            continue
        cap = min(cap, max(0.0, az + t * (bz - az) - SIGHT_CLEAR_M))
    return cap


def layout(profile, seed, grass_height_m=0.45, crop="grass", track=False, cameras=()):
    """cameras: every camera key position; blades in a camera's sight corridor to the subject are cut below
    the sight line (a low camera looks down a trampled lane, not into a wall of grass)."""
    rng = random.Random(seed)
    (cx, cy), hx, hy = _frame(profile)
    extent = max(EXTENT_MIN_M, EXTENT_K * profile.longest)
    radius = min(extent / 2, max(BLADE_R_MIN_M, BLADE_R_K * profile.longest))
    n = min(BLADE_CAP, int(DENSITY[crop] * math.pi * radius * radius))
    trk = track_rect(profile) if track else None
    lines = _sight_lines(profile, cameras)
    half_w = max(SIGHT_W_MIN, SIGHT_W_K * profile.longest)
    cut = 0
    blades = []
    for _ in range(n):
        r = radius * math.sqrt(rng.random())
        a = rng.uniform(0.0, math.tau)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        yaw, lean = rng.uniform(0.0, 360.0), rng.uniform(0.0, 0.35)
        h = grass_height_m * rng.uniform(*HEIGHT_JITTER)
        flower = crop == "wildflowers" and rng.random() < FLOWER_SHARE
        pick = rng.random()
        q = max(abs(x - cx) / hx, abs(y - cy) / hy)
        if max(abs(x - cx) - BLADE_W, 0.0) <= hx and max(abs(y - cy) - BLADE_W, 0.0) <= hy:
            continue                                   # no root (nor its blade's base) inside the footprint
        if q < CLEAR_OUT:
            yaw = math.degrees(math.atan2(y - cy, x - cx))   # near the subject a blade leans away from it
        if trk and trk[0] <= x <= trk[2] and trk[1] <= y <= trk[3]:
            continue                                   # the track is clear
        h *= clear_factor(q)
        edge = r / radius
        if edge > 1.0 - EDGE_TAPER:                    # no carpet edge where the real blades end
            h *= 1.0 - (1.0 - EDGE_FLOOR) * (edge - (1.0 - EDGE_TAPER)) / EDGE_TAPER
        if lines:
            cap = sight_cap(x, y, lines, half_w)
            if cap < h:
                cut += 1
                h = cap
                if h < 0.005:
                    continue                           # trampled flat: no blade
        blades.append((x, y, yaw, h, lean, flower, pick))
    hills = [rng.uniform(*HORIZON_H) for _ in range(HORIZON_SEGMENTS)]
    return {"extent": extent, "bladeRadius": radius, "centre": [cx, cy], "footprint": [hx, hy],
            "clearing": {"in": CLEAR_IN * max(hx, hy), "out": CLEAR_OUT * max(hx, hy)},
            "track": list(trk) if trk else None, "blades": blades, "horizon": hills, "sightCut": cut}
