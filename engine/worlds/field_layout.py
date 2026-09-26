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
- art pass (2026-09-25), each from its own seeded stream so the blades never move: `trees`, short treelines
  past every camera and out of every sight line (the first in the hero's background), and `farGrass`,
  static tufts for a trampled cover under the blades and the field out to the horizon, sight-cut like them;
- ground contact (round 3, 2026-09-25): with the subject's wheels known, grass round each tyre's contact patch
  is pressed flat (TRAMPLE_FLOOR of its height, lying down at its full length) and stands again over
  TRAMPLE_RAMP_M; every camera also keeps a narrow corridor to each tyre (aimed WHEEL_AIM_K x its radius up
  it) and the subject corridor aims lower (SIGHT_AIM_K), so the near tyre and bumper are not buried; `trample`
  lists flattened stems lying under the body and the tyres (the ground under a parked car is pressed, not
  bald), from their own stream;
- every draw comes from random.Random(seed): the layout is a pure function of its arguments.
Numbers marked (eng) are in the calibration register."""
import math
import random

EXTENT_MIN_M, EXTENT_K = 40.0, 10.0     # plan: field extent = max(40 m, 10 x longest)
BLADE_R_MIN_M, BLADE_R_K = 4.0, 2.5     # (eng) real blades out to this radius; beyond, the ground texture
BLADE_CAP = 60000                       # plan: 60k blades in view
DENSITY = {"grass": 160.0, "wheat": 110.0, "wildflowers": 140.0}   # (eng) blades per m^2
FLOWER_SHARE = 0.08                     # (eng) wildflowers: share of stems with a flower head
CLEAR_IN, CLEAR_OUT, CLEAR_FLOOR = 1.2, 2.0, 0.4   # plan 1.2 x footprint; (eng) full height by 2 x. Round 6: 40%
#   (was the plan's 20%: a mown ring round the car set it ON the field, real_r5_field_golden)
HEIGHT_JITTER = (0.6, 1.2)              # (eng) blade height x grassHeightM
BLADE_W = 0.012                         # (eng) blade base width (real size, the courtyard's)
TRACK_MARGIN_K, TRACK_MARGIN_M = 0.15, 0.10         # the courtyard's exclusion margin (eng)
EDGE_TAPER = 0.25                       # (eng) the outer quarter of the blade disc tapers toward the ground
EDGE_FLOOR = 0.35                       # (eng) ... to this share of the height at the disc's edge
SIGHT_W_MIN, SIGHT_W_K = 0.25, 0.3      # (eng) sight corridor half-width: max(0.25 m, 0.3 x longest)
SIGHT_CLEAR_M = 0.02                    # (eng) blades in a corridor stay this far under the sight line
HORIZON_SEGMENTS = 48                   # (eng) silhouette card ring segments
HORIZON_H = (0.02, 0.07)                # (eng) silhouette height as a share of the ring radius
TREE_CLUSTERS = (2, 4)                  # (eng) art pass: stands of trees at the field's edge
TREES_PER_CLUSTER = (8, 16)             # (eng) a stand is a short treeline ...
TREE_H = (5.5, 11.0)                    # (eng) tree height, real metres (a tree is not subject-scaled)
TREE_R_MIN_M, TREE_CAM_PAD_M = 18.0, 6.0    # (eng) nearest stand: past the blades, past every camera + pad
TREE_BAND_M = 25.0                      # (eng) stands sit in a 25 m band beyond that
TREE_ALONG_M, TREE_DEPTH_M = 16.0, 4.0  # (eng) ... running +-16 m across the view and +-4 m deep
TREE_HERO_CONE_DEG = 28.0               # (eng) the first stand stands behind the subject as the hero sees it
TREE_CROWN_K = 0.35                     # (eng) crown half-width as a share of tree height (the clearance box)
SUN_PATH_MAX_M = 400.0                  # (eng) a sun path's longest run (a 1.6 degree sun over the tallest tree)
TREE_SEED = 0x7EE5                      # a separate stream: trees never shift the blades
FAR_SEED = 0xFA12                       # the far-grass stream (never shifts the blades or trees)
FLORA_SEED = 0xF10A                     # round 2: weeds and flowers, their own stream
FLORA = {"weeds": (0.06, {"grass": 6.0, "wheat": 3.0, "wildflowers": 6.0}),         # round 3: sparse (r3 frames:
                                                                                     # 14/m^2 of broad leaves read
                                                                                     # as a weed bed, not grass)       # (eng) nominal height,
         "flowers": (0.2, {"grass": 0.8, "wheat": 0.3, "wildflowers": 9.0})}        # per-m^2 per crop
FLORA_R_K = 1.15                        # (eng) weeds and flowers reach a little past the blade disc
FAR_R_OUT_M = 260.0                     # (eng) instanced far grass runs out to here (the haze has it by then)
FAR_DENSITY = 40.0                      # (eng) far tufts per m^2 at the blade disc's edge ...
FAR_FALLOFF = 1.5                       # (eng) ... falling as (r_edge / r)^FAR_FALLOFF
FAR_CAP = 200000                        # (eng) at most this many far tufts (instances: cheap)
FAR_GROW = 0.5                          # (eng) a far tuft is (r / r_edge)^FAR_GROW taller: even screen density
COVER_K = 0.4                           # (eng) inside the blade disc the static cover is this share of the height
COVER_DENSITY = 90.0                    # (eng) cover tufts per m^2 inside the blade disc
COVER_MIN_W = 0.5                       # (eng) a cover tuft is never narrower than this (x the grass height): a
                                        # cut tuft is trampled flat, not a thin stub
COVER_PAD_M = 0.12                      # (eng) cover keeps this far outside the subject's footprint
# ground contact (round 3; outside critique of the r4 field: 0.15-0.3 m transition, half the obstruction)
SIGHT_AIM_K = 0.10                      # (eng) the subject corridor aims this share up its bounds (round 6: 0.05
#                                         cut a lane to the sills; blades now reach the tyres' lower tenth)
TYRE_PAD_M = 0.05                       # (eng) the pressed patch reaches this past the tread's sides
TYRE_PATCH_K = 0.55                     # (eng) ... and this x the radius fore and aft of the contact point
TRAMPLE_RAMP_M = 0.15                   # (eng) from pressed flat to standing, metres past the patch (round 6: 0.25,
#                                         left a bald ring round every tyre; a tyre parts the grass it stands in)
TRAMPLE_FLOOR = 0.06                    # (eng) a pressed stem stands this share of its height (it lies down)
WHEEL_AIM_K, WHEEL_SIGHT_K = 0.5, 1.0   # (eng) tyre corridors: aim x radius up the tyre, half-width x radius
#                                         (round 6: 0.35; blades in front now hide the tyre's bottom ~third)
WEDGE_AIM_K = 0.12                      # (eng) the subject wedge: nothing between a camera and the subject's
WEDGE_PAD_M = 0.05                      # footprint (+ pad) stands above the line to this share of its height
TRAMPLE_DENSITY = 140.0                 # (eng) flattened stems per m^2 under the body and the tyre patches
TRAMPLE_SEED = 0x7A4E                   # their own stream: they never move the blades
FAR_GROW_MAX = 1.6                      # (eng) a far tuft grows at most this much (r4: 2 m stalks at 100 m)


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


def _wheels(profile):
    """[(contact xy, radius, width, axle unit xy)] of the subject's wheels that carry a contact point."""
    out = []
    for w in getattr(profile, "wheels", None) or []:
        c, r = w.get("contact"), w.get("radius")
        if not c or not r:
            continue
        ax = w.get("axis") or (1.0, 0.0, 0.0)
        n = math.hypot(ax[0], ax[1]) or 1.0
        out.append(((c[0], c[1]), float(r), float(w.get("width") or 0.25 * r), (ax[0] / n, ax[1] / n)))
    return out


def tyre_zones(profile):
    """[(centre xy, axle unit xy, half across, half along)]: each tyre's pressed contact patch."""
    return [(c, ax, 0.5 * wd + TYRE_PAD_M, TYRE_PATCH_K * r) for c, r, wd, ax in _wheels(profile)]


def _zone_dist(x, y, zones):
    """Distance (m) from (x, y) to the nearest tyre patch (0 inside it; inf with none)."""
    best = math.inf
    for (zx, zy), (ax, ay), ha, hl in zones:
        dx, dy = x - zx, y - zy
        a, b = abs(dx * ax + dy * ay) - ha, abs(-dx * ay + dy * ax) - hl
        best = min(best, math.hypot(max(a, 0.0), max(b, 0.0)))
    return best


def trample(x, y, zones):
    """Height factor from the tyres: TRAMPLE_FLOOR on a patch, rising (smoothstep) to 1 at TRAMPLE_RAMP_M."""
    d = _zone_dist(x, y, zones)
    if d >= TRAMPLE_RAMP_M:
        return 1.0
    t = d / TRAMPLE_RAMP_M
    return TRAMPLE_FLOOR + (1.0 - TRAMPLE_FLOOR) * t * t * (3.0 - 2.0 * t)


def _press(h, lean, f):
    """(height, lean) of a stem pressed to f of its height: below half height it lies down at its full length."""
    h0, h = h, h * f
    if f < 0.5 and h > 0:
        lean = max(lean, math.sqrt(max(0.0, h0 * h0 - h * h)) / h)
    return h, lean


def _sight_lines(profile, cameras):
    """(camera xy, camera z, target xy, aim z[, half width]) per distinct camera position: the line a camera needs
    clear to see the subject's lower body (SIGHT_AIM_K of the way up its bounds), one per wheel to its tyre
    (WHEEL_AIM_K x the radius up it, in a corridor WHEEL_SIGHT_K x the radius either side), and a
    ("wedge", camera xy, camera z, footprint box, aim z) entry: the whole footprint's width as the camera sees it,
    so a wide subject's ends are not buried where a fixed-width corridor stops short of them."""
    cx, cy, _ = profile.center
    aim = profile.boundsMin[2] + SIGHT_AIM_K * (profile.boundsMax[2] - profile.boundsMin[2])
    wheels = _wheels(profile)
    (fx, fy), hx, hy = _frame(profile)
    box = (fx - hx - WEDGE_PAD_M, fy - hy - WEDGE_PAD_M, fx + hx + WEDGE_PAD_M, fy + hy + WEDGE_PAD_M)
    wedge_aim = profile.boundsMin[2] + WEDGE_AIM_K * (profile.boundsMax[2] - profile.boundsMin[2])
    seen, out = set(), []
    for c in cameras:
        key = tuple(round(v / 0.1) for v in c)
        if key not in seen:
            seen.add(key)
            out.append(((c[0], c[1]), c[2], (cx, cy), aim))
            for (wx, wy), r, _, _ in wheels:
                out.append(((c[0], c[1]), c[2], (wx, wy), WHEEL_AIM_K * r, WHEEL_SIGHT_K * r))
            out.append(("wedge", (c[0], c[1]), c[2], box, wedge_aim))
    return out


def _wedge_cap(x, y, c, cz, box, aim):
    """The tallest a plant at (x, y) may stand without hiding the subject's footprint box from camera c (xy, cz):
    the camera's line to `aim` high on the box's near face, at the plant's share of the way there (inf when the
    ray from the camera through the plant misses the box, or the plant is past the box's near face)."""
    dx, dy = x - c[0], y - c[1]
    t0, t1 = -math.inf, math.inf
    for o, d, lo, hi in ((c[0], dx, box[0], box[2]), (c[1], dy, box[1], box[3])):
        if abs(d) < 1e-12:
            if not lo <= o <= hi:
                return math.inf
            continue
        a, b = (lo - o) / d, (hi - o) / d
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    if t0 > t1 or t0 <= 1.0:
        return math.inf
    return max(0.0, cz + (aim - cz) / t0 - SIGHT_CLEAR_M)


def sight_cap(x, y, lines, half_w):
    """The tallest a blade at (x, y) may stand so no camera's sight line to the subject passes through it
    (inf when it is in no corridor)."""
    cap = math.inf
    for line in lines:
        if line[0] == "wedge":
            cap = min(cap, _wedge_cap(x, y, line[1], line[2], line[3], line[4]))
            continue
        (ax, ay), az, (bx, by), bz = line[:4]
        hw = line[4] if len(line) > 4 else half_w
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            continue
        t = ((x - ax) * dx + (y - ay) * dy) / L2
        if not 0.0 <= t <= 1.0:
            continue
        if math.hypot(x - (ax + t * dx), y - (ay + t * dy)) > hw:
            continue
        cap = min(cap, max(0.0, az + t * (bz - az) - SIGHT_CLEAR_M))
    return cap


def layout(profile, seed, grass_height_m=0.45, crop="grass", track=False, cameras=(), hero=None, sun=None):
    """cameras: every camera key position; blades in a camera's sight corridor to the subject are cut below
    the sight line (a low camera looks down a trampled lane, not into a wall of grass). sun: the unit vector
    toward the world's sun; no tree stands between it and the subject or the ground the cameras see."""
    rng = random.Random(seed)
    (cx, cy), hx, hy = _frame(profile)
    extent = max(EXTENT_MIN_M, EXTENT_K * profile.longest)
    radius = min(extent / 2, max(BLADE_R_MIN_M, BLADE_R_K * profile.longest))
    n = min(BLADE_CAP, int(DENSITY[crop] * math.pi * radius * radius))
    trk = track_rect(profile) if track else None
    lines = _sight_lines(profile, cameras)
    half_w = max(SIGHT_W_MIN, SIGHT_W_K * profile.longest)
    zones = tyre_zones(profile)
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
        if zones:
            h, lean = _press(h, lean, trample(x, y, zones))
        if lines:
            cap = sight_cap(x, y, lines, half_w)
            if cap < h:
                cut += 1
                h = cap
                if h < 0.005:
                    continue                           # trampled flat: no blade
        blades.append((x, y, yaw, h, lean, flower, pick))
    hills = [rng.uniform(*HORIZON_H) for _ in range(HORIZON_SEGMENTS)]
    trees = tree_stands(profile, seed, radius, cameras, hero, sun)
    far = far_grass(profile, seed, radius, grass_height_m, lines, half_w, trk, zones)
    flora = field_flora(profile, seed, radius, crop, lines, half_w, trk, zones)
    return {"trees": trees, "farGrass": far, "flora": flora, "trample": pressed_stems(profile, seed, grass_height_m, zones),
            "tyres": [list(z[0]) for z in zones],
            "extent": extent, "bladeRadius": radius, "centre": [cx, cy], "footprint": [hx, hy],
            "clearing": {"in": CLEAR_IN * max(hx, hy), "out": CLEAR_OUT * max(hx, hy)},
            "track": list(trk) if trk else None, "blades": blades, "horizon": hills, "sightCut": cut}


def sun_paths(profile, cameras, sun):
    """Segments from the subject (its footprint corners on the ground, its roof) and the ground the cameras
    look over (each camera, each camera-subject midpoint) toward the sun, up to the tallest tree's height: a
    tree crown that meets one would shade the subject or its foreground ([] without a sun above the horizon)."""
    if not sun or sun[2] <= 1e-3:
        return []
    (cx, cy), hx, hy = _frame(profile)
    top = profile.boundsMax[2]
    src = [(cx + sx * hx, cy + sy * hy, 0.0) for sx in (-1, 1) for sy in (-1, 1)] + [(cx, cy, top)]
    for c in cameras:
        src += [(c[0], c[1], 0.0), (0.5 * (c[0] + cx), 0.5 * (c[1] + cy), 0.0)]
    out = []
    for p in src:
        L = min(SUN_PATH_MAX_M, (TREE_H[1] + 1.0 - p[2]) / sun[2])
        out.append((p, tuple(p[k] + sun[k] * L for k in range(3))))
    return out


def tree_stands(profile, seed, blade_radius, cameras=(), hero=None, sun=None):
    """[(x, y, height, yaw_deg, pick)] trees in a few short treelines beyond the blades and every camera; with the
    hero camera position given, the first stands in the hero's background (within TREE_HERO_CONE_DEG of its
    view through the subject). A tree whose crown box (TREE_CROWN_K x height either side, full height) meets a
    camera's line to the subject is dropped, and so is one that meets a sun path (sun_paths): at the golden
    sun's 8 degrees an 11 m tree shades 78 m, and real_r6_field_golden stood the whole clearing in tree shadow."""
    from engine.worlds.street_layout import segment_hits
    rng = random.Random(seed ^ TREE_SEED)
    (cx, cy), _, _ = _frame(profile)
    far = max((math.hypot(c[0] - cx, c[1] - cy) for c in cameras), default=0.0)
    r0 = max(TREE_R_MIN_M, 1.5 * blade_radius, far + TREE_CAM_PAD_M)
    aim = [tuple(profile.center)]
    lit = sun_paths(profile, cameras, sun)
    out = []
    back = None if hero is None else math.atan2(cy - hero[1], cx - hero[0])
    for i in range(rng.randint(*TREE_CLUSTERS)):
        a = rng.uniform(0.0, math.tau)
        if i == 0 and back is not None:
            a = back + math.radians(rng.uniform(-TREE_HERO_CONE_DEG, TREE_HERO_CONE_DEG))
        r = r0 + rng.uniform(0.0, TREE_BAND_M)
        sx, sy = cx + r * math.cos(a), cy + r * math.sin(a)
        tx, ty = -math.sin(a), math.cos(a)                     # across the view
        for _ in range(rng.randint(*TREES_PER_CLUSTER)):
            u, w = rng.uniform(-TREE_ALONG_M, TREE_ALONG_M), rng.uniform(-TREE_DEPTH_M, TREE_DEPTH_M)
            x, y = sx + u * tx + w * math.cos(a), sy + u * ty + w * math.sin(a)
            h, yaw = rng.uniform(*TREE_H), rng.uniform(0.0, 360.0)
            if math.hypot(x - cx, y - cy) < r0:
                continue
            w = TREE_CROWN_K * h
            lo, hi = (x - w, y - w, 0.0), (x + w, y + w, h)
            if any(segment_hits(c, q, lo, hi) for c in cameras for q in aim):
                continue
            if any(segment_hits(a0, a1, lo, hi) for a0, a1 in lit):
                continue
            out.append((x, y, h, yaw, rng.random()))
    return out


def far_grass(profile, seed, blade_radius, grass_height_m, lines, half_w, trk=None, zones=()):
    """[(x, y, yaw_deg, height, width)] static tufts (width: the height a tuft's footprint is scaled for): a
    short cover (COVER_K of the height, cleared like the blades, never narrower than COVER_MIN_W) under the
    swaying blades inside the disc at COVER_DENSITY per m^2, then full-height tufts from the disc's edge (at
    FAR_DENSITY per m^2) to FAR_R_OUT_M, the density falling as (edge / r)^FAR_FALLOFF and each
    (r / edge)^FAR_GROW taller, so the field reads as grass to the horizon at an even screen density. The sight cut applies as it does to the
    blades (a tuft in a camera's corridor stays under its line to the subject); the track and the subject's
    footprint stay clear."""
    rng = random.Random(seed ^ FAR_SEED)
    (cx, cy), hx, hy = _frame(profile)
    r0 = blade_radius
    k = 2.0 - FAR_FALLOFF              # inverse-CDF radius for a density ~ r^-falloff on an annulus
    n_out = FAR_DENSITY * r0 ** FAR_FALLOFF * math.tau * (FAR_R_OUT_M ** k - r0 ** k) / k
    n_in = COVER_DENSITY * math.pi * r0 * r0
    scale = min(1.0, FAR_CAP / max(1.0, n_in + n_out))
    out = []
    for inner, n in ((True, int(n_in * scale)), (False, int(n_out * scale))):
        for _ in range(n):
            if inner:
                r = r0 * math.sqrt(rng.random())
            else:
                r = (r0 ** k + rng.random() * (FAR_R_OUT_M ** k - r0 ** k)) ** (1.0 / k)
            a = rng.uniform(0.0, math.tau)
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            h = grass_height_m * rng.uniform(*HEIGHT_JITTER)
            yaw = rng.uniform(0.0, 360.0)
            if inner:
                pad = COVER_PAD_M + 0.5 * h
                if abs(x - cx) <= hx + pad and abs(y - cy) <= hy + pad:
                    continue
                h *= COVER_K * clear_factor(max(abs(x - cx) / hx, abs(y - cy) / hy))
                if zones:
                    h *= trample(x, y, zones)
            else:
                h *= min(FAR_GROW_MAX, (r / r0) ** FAR_GROW)
            if trk and trk[0] <= x <= trk[2] and trk[1] <= y <= trk[3]:
                continue
            w = max(h, COVER_MIN_W * grass_height_m) if inner else h
            if lines:
                h = min(h, sight_cap(x, y, lines, half_w))
                if h < (0.004 if inner else 0.01):          # a cut cover tuft is trampled flat,
                    continue                                   # not removed (round 2: no bald lanes)
            out.append((x, y, yaw, h, w))
    return out


def field_flora(profile, seed, blade_radius, crop, lines, half_w, trk=None, zones=()):
    """{"weeds": [...], "flowers": [...]} of (x, y, yaw_deg, scale): low leafy weeds everywhere under the grass
    (the ground cover a trampled lane still has) and flowering plants at the crop's density, out to FLORA_R_K x
    the blade disc. scale 1 is the plant's own size; in a camera's corridor it shrinks under the sight line
    (a weed flat on the ground stays, nothing stands up into the view); the footprint and the track stay clear."""
    rng = random.Random(seed ^ FLORA_SEED)
    (cx, cy), hx, hy = _frame(profile)
    r0 = FLORA_R_K * blade_radius
    out = {}
    for kind, (h0, dens) in FLORA.items():
        pts = []
        for _ in range(min(FAR_CAP, int(dens[crop] * math.pi * r0 * r0))):
            r, a = r0 * math.sqrt(rng.random()), rng.uniform(0.0, math.tau)
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            s, yaw = rng.uniform(0.7, 1.3), rng.uniform(0.0, 360.0)
            pad = COVER_PAD_M + 0.2 * s
            if abs(x - cx) <= hx + pad and abs(y - cy) <= hy + pad:
                continue
            if trk and trk[0] <= x <= trk[2] and trk[1] <= y <= trk[3]:
                continue
            if zones and trample(x, y, zones) < 0.5:
                continue                                       # nothing stands up in a tyre's pressed ring
            if lines:
                s = min(s, sight_cap(x, y, lines, half_w) / h0)
                if s < 0.15:
                    continue
            pts.append((x, y, yaw, s))
        out[kind] = pts
    return out


def pressed_stems(profile, seed, grass_height_m, zones):
    """[(x, y, yaw_deg, length, pick)] dead stems lying flat under the subject: at TRAMPLE_DENSITY per m^2 over
    its footprint, and twice that on each tyre's patch (the grass the wheels rolled over), each pointing away
    from the centre with some scatter. Empty without wheels (a chair on grass sits in it, it did not drive)."""
    if not zones:
        return []
    rng = random.Random(seed ^ TRAMPLE_SEED)
    (cx, cy), hx, hy = _frame(profile)
    out = []
    areas = [((cx, cy), (1.0, 0.0), hx, hy, 1.0)] + [(c, ax, ha, hl, 2.0) for c, ax, ha, hl in zones]
    for (zx, zy), (ax, ay), ha, hl, k in areas:
        for _ in range(int(TRAMPLE_DENSITY * k * 4.0 * ha * hl)):
            a, b = rng.uniform(-ha, ha), rng.uniform(-hl, hl)
            x, y = zx + a * ax - b * ay, zy + a * ay + b * ax
            yaw = math.degrees(math.atan2(y - cy, x - cx)) + rng.gauss(0.0, 35.0)
            out.append((x, y, yaw, grass_height_m * rng.uniform(0.4, 1.1), rng.random()))
    return out
