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
COVER_DENSITY = 170.0                   # (eng) cover tufts per m^2 inside the blade disc (round 10: 90, the r9 foreground
                                        # showed black soil between stringy blades)
COVER_MIN_W = 0.5                       # (eng) a cover tuft is never narrower than this (x the grass height): a
                                        # cut tuft is trampled flat, not a thin stub
COVER_PAD_M = 0.12                      # (eng) cover keeps this far outside the subject's footprint
# ground contact (round 3; outside critique of the r4 field: 0.15-0.3 m transition, half the obstruction)
SIGHT_AIM_K = 0.10                      # (eng) the subject corridor aims this share up its bounds (round 6: 0.05
#                                         cut a lane to the sills; blades now reach the tyres' lower tenth)
TYRE_PAD_M = 0.04                       # (eng) the pressed patch reaches this past the tread's sides (round 8: 0.05
#                                         hid the tyre's contact, owner's r7 grade)
TYRE_PATCH_K = 0.55                     # (eng) ... and this x the radius fore and aft of the contact point (was 0.55)
TRAMPLE_RAMP_M = 0.25                   # (eng) from pressed flat to standing, metres past the patch (round 6: 0.25
#                                         left a bald ring, 0.15 buried the contact again; the wider patch now
#                                         carries the pressing and the ramp is back at 0.25)
TRAMPLE_FLOOR = 0.06                    # (eng) a pressed stem stands this share of its height (it lies down)
WHEEL_AIM_K, WHEEL_SIGHT_K = 0.4, 1.0   # (eng) tyre corridors: aim x radius up the tyre, half-width x radius
#                                         (round 6: 0.35; round 11 0.5 -> 0.4, owner's r10 review "the car sits on
#                                         the grass, not in it": blades cross the tyre's bottom again)
WEDGE_AIM_K = 0.12                      # (eng) the subject wedge: nothing between a camera and the subject's
WEDGE_PAD_M = 0.05                      # footprint (+ pad) stands above the line to this share of its height
TRAMPLE_DENSITY = 140.0                 # (eng) flattened stems per m^2 under the body and the tyre patches
TRAMPLE_SEED = 0x7A4E                   # their own stream: they never move the blades
FAR_GROW_MAX = 1.6                      # (eng) a far tuft grows at most this much (r4: 2 m stalks at 100 m)
# round 8 (owner's r7 grade: "dense, stiff, uniform stems overwhelm the car, hide tyre contact, feel miniature"):
PATCH_DENSITY = 0.12                    # (eng) worn / open patches per m^2 of the blade disc ...
PATCH_R_M = (0.4, 1.4)                  # (eng) ... each this radius ...
PATCH_DEPTH = (0.35, 0.8)               # (eng) ... cutting the blades at its centre by this share, fading to its edge
PATCH_THIN = 0.7                        # (eng) and dropping this share of the stems at full strength (open ground)
PATCH_SEED = 0x9A7C                     # their own stream: the patches never move a blade
FORE_R_M = 4.5                          # (eng) round each camera the grass is trodden (the crew stood there): ...
FORE_FLOOR = 0.15                        # (eng) ... this share of its height at the camera, standing by FORE_R_M


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


def _wedge_cap(x, y, c, cz, box, aim, k=1.0):
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
    z = max(0.0, cz + (aim - cz) / t0 - SIGHT_CLEAR_M)
    if k != 1.0 and math.hypot(dx, dy) * (t0 - 1.0) < WEDGE_RAGGED_M:   # round 12: within reach of the body
        z *= k                                                         # the cut is ragged, not a clean line
    return z


def sight_cap(x, y, lines, half_w, tyre_k=1.0):
    """The tallest a blade at (x, y) may stand so no camera's sight line to the subject passes through it
    (inf when it is in no corridor). tyre_k (round 12) scales a tyre corridor's line within TYRE_TUFT_R_M of the
    tyre: a ragged edge of blades across the tyre's foot instead of one straight cut."""
    cap = math.inf
    for line in lines:
        if line[0] == "wedge":
            cap = min(cap, _wedge_cap(x, y, line[1], line[2], line[3], line[4], tyre_k))
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
        z = max(0.0, az + t * (bz - az) - SIGHT_CLEAR_M)
        if len(line) > 4 and tyre_k != 1.0 and math.hypot(x - bx, y - by) < TYRE_TUFT_R_M:
            z *= tyre_k
        cap = min(cap, z)
    return cap


def open_patches(profile, seed, radius):
    """[(x, y, r, depth)] worn patches in the blade disc (round 8), outside the subject's footprint."""
    rng = random.Random(seed ^ PATCH_SEED)
    (cx, cy), hx, hy = _frame(profile)
    out = []
    for _ in range(int(PATCH_DENSITY * math.pi * radius * radius)):
        r, a = radius * math.sqrt(rng.random()), rng.uniform(0.0, math.tau)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        pr, dp = rng.uniform(*PATCH_R_M), rng.uniform(*PATCH_DEPTH)
        if abs(x - cx) <= hx and abs(y - cy) <= hy:
            continue
        out.append((x, y, pr, dp))
    return out


def patch_strength(x, y, patches):
    """0 (none) .. depth: how worn the ground is at (x, y), smooth to 0 at a patch's radius."""
    s = 0.0
    for px, py, pr, dp in patches:
        d = math.hypot(x - px, y - py)
        if d < pr:
            t = d / pr
            s = max(s, dp * (1.0 - t * t * (3.0 - 2.0 * t)))
    return s


def fore_factor(x, y, cameras):
    """Height factor near the cameras: FORE_FLOOR at a camera's foot, 1 by FORE_R_M (a trodden foreground)."""
    f = 1.0
    for c in cameras:
        d = math.hypot(x - c[0], y - c[1])
        if d < FORE_R_M:
            t = d / FORE_R_M
            f = min(f, FORE_FLOOR + (1.0 - FORE_FLOOR) * t * t * (3.0 - 2.0 * t))
    return f


CLUMP_WAVES = ((0.55, 0.45), (1.9, 0.35), (4.3, 0.20))   # (eng, round 9) wavelength m, weight: clumps, drifts, swathes
CLUMP_RANGE = (0.45, 1.0)  # (eng) the blade height factor they span (never taller than the ask): a meadow is never one even pile


def clump_factor(x, y, seed):
    """Height factor (CLUMP_RANGE) of the grass at (x, y): three seeded plane-wave pairs at clump / drift / swathe
    scale, so tall clumps stand beside short, thin ground (round 9, owner: "the field grass is uniform stems").
    A function of position alone: it draws nothing from the blade stream."""
    k = random.Random(seed ^ 0xC1A3)
    v, tot = 0.0, 0.0
    for lam, w in CLUMP_WAVES:
        for _ in range(2):
            a, ph = k.uniform(0.0, math.pi), k.uniform(0.0, math.tau)
            v += w * math.cos(math.tau / lam * (x * math.cos(a) + y * math.sin(a)) + ph)
            tot += w
    t = 0.5 + 0.5 * v / tot                                 # 0..1, bunched round 0.5
    t = min(1.0, max(0.0, 0.5 + 1.6 * (t - 0.5)))           # spread toward the ends
    lo, hi = CLUMP_RANGE
    return lo + (hi - lo) * t


# Round 12 (owner's r11 review: "same detail everywhere"): a real meadow is patchy at several scales at once. The
# plane-wave clumps above are regular; meadow() is seeded value noise (random lattice, smooth interpolation) summed
# over three octaves, contrast-stretched to 0..1. Low ground (< BARE_HI) is bare or short, trodden grass; the species
# field decides where a stand is live green or dry straw; the lodge field lays whole patches over (wind / rain
# lodging). All are functions of position alone: they draw nothing from any random stream. (eng)
MEADOW_OCTAVES = ((0.8, 0.30), (2.6, 0.40), (7.5, 0.30))   # wavelength m, weight
MEADOW_SEED, SPECIES_SEED, LODGE_SEED = 0x3EAD, 0x5BEC, 0x10D6
MEADOW_HEIGHT = (0.32, 0.12, 0.55)      # height factor at meadow 0 (bare) .. full by the ramp (lo, hi)
BARE_HI, BARE_DROP = 0.2, 0.6          # under BARE_HI a plant is dropped with up to BARE_DROP odds (open soil)
SPECIES_M = 3.2                         # species stands: live green here, dry straw there
LODGE_M, LODGE_T = 1.8, 0.7             # lodged patches: where the lodge field passes LODGE_T ...
LODGE_DEG = (32.0, 68.0)                # ... the plants lie over this far, downwind
TILT_DEG = 14.0                         # elsewhere a plant leans up to this, mostly downwind
FORE_THIN = 0.22                        # round the cameras (fore_factor) up to this share of the plants is gone
TYRE_TUFT = (0.55, 1.9)                 # a plant in a tyre corridor stands this x the line's height (irregular edge)
TYRE_TUFT_M = 0.07                      # ... varying at this scale (a few blades cross the tyre, most do not)


def _hash01(ix, iy, s):
    """A stable uniform in [0, 1) for an integer lattice point and a seed."""
    h = (ix * 0x27D4EB2D ^ iy * 0x165667B1 ^ s * 0x9E3779B1) & 0xFFFFFFFF
    h = ((h ^ (h >> 15)) * 0x2C1B3C6D) & 0xFFFFFFFF
    h = ((h ^ (h >> 12)) * 0x297A2D39) & 0xFFFFFFFF
    return ((h ^ (h >> 15)) & 0xFFFFFF) / float(0x1000000)


def value_noise(x, y, seed, lam):
    """Smooth value noise in [0, 1] at wavelength lam metres (a random value per lattice point, smoothstepped)."""
    u, v = x / lam, y / lam
    ix, iy = math.floor(u), math.floor(v)
    fx, fy = u - ix, v - iy
    sx, sy = fx * fx * (3.0 - 2.0 * fx), fy * fy * (3.0 - 2.0 * fy)
    a, b = _hash01(ix, iy, seed), _hash01(ix + 1, iy, seed)
    c, d = _hash01(ix, iy + 1, seed), _hash01(ix + 1, iy + 1, seed)
    return (a + (b - a) * sx) * (1.0 - sy) + (c + (d - c) * sx) * sy


def meadow(x, y, seed):
    """0 (bare) .. 1 (lush): three octaves of value noise, stretched so both ends occur."""
    v = sum(w * value_noise(x, y, seed ^ MEADOW_SEED ^ (i * 0x51), lam) for i, (lam, w) in enumerate(MEADOW_OCTAVES))
    return min(1.0, max(0.0, 0.5 + 1.7 * (v - 0.5)))


def meadow_height(v):
    """Height factor (never above 1) for meadow value v: short, trodden ground low, full stands high."""
    lo, a, b = MEADOW_HEIGHT
    t = min(1.0, max(0.0, (v - a) / (b - a)))
    return lo + (1.0 - lo) * t * t * (3.0 - 2.0 * t)


def meadow_drop(x, y, seed, v, fore=1.0):
    """True when the plant at (x, y) is left out: bare soil in the low meadow, fewer stems round a camera."""
    p = BARE_DROP * max(0.0, 1.0 - v / BARE_HI) if v < BARE_HI else 0.0
    if fore < 1.0:
        p = max(p, FORE_THIN * (1.0 - (fore - FORE_FLOOR) / (1.0 - FORE_FLOOR)))
    return _hash01(int(math.floor(x * 1000.0)), int(math.floor(y * 1000.0)), seed ^ 0xD209) < p


def species(x, y, seed):
    """0 (live green) .. 1 (dry straw): the stand a plant belongs to, 0..1 across SPECIES_M-sized drifts."""
    v = 0.65 * value_noise(x, y, seed ^ SPECIES_SEED, SPECIES_M) + 0.35 * value_noise(x, y, seed ^ SPECIES_SEED ^ 7,
                                                                                       SPECIES_M / 3.1)
    return min(1.0, max(0.0, 0.5 + 2.2 * (v - 0.5)))


def lodge(x, y, seed, wind_deg, pick):
    """(tilt_deg, toward_deg) of a plant: lying over downwind in a lodged patch, else a small lean mostly downwind."""
    v = value_noise(x, y, seed ^ LODGE_SEED, LODGE_M)
    r1, r2 = _hash01(int(pick * 1e6), 3, seed), _hash01(int(pick * 1e6), 5, seed)
    toward = wind_deg + (r2 - 0.5) * 70.0
    if v > LODGE_T:
        k = min(1.0, (v - LODGE_T) / (1.0 - LODGE_T) * 1.6)
        return LODGE_DEG[0] + (LODGE_DEG[1] - LODGE_DEG[0]) * k * (0.6 + 0.4 * r1), toward
    return TILT_DEG * r1, toward + (r1 - 0.5) * 120.0


WEDGE_RAGGED_M = 0.8                    # (eng) the wedge's cut takes the same ragged multiplier this close to the body
TYRE_TUFT_R_M = 0.7                     # (eng) ... only this close to the tyre (the corridor's far end)
TRACK_LEN_M = (3.5, 6.0)                # (eng) the wheels' way in: flattened lanes behind the rear wheels ...
TRACK_FLOOR = 0.42                      # ... pressed to this share of the height (bent over, not flat) ...
TRACK_PAD_M = 0.03                      # ... as wide as the tread + this either side, fading out along its length


def wheel_tracks(profile):
    """[(start xy, back unit xy, half width, length)]: a lane behind each rear wheel (the axle with the bigger
    tyres, else the one toward -forwardAxis), running back from its contact patch: the way the car drove in."""
    ws = _wheels(profile)
    if len(ws) < 2:
        return []
    fwd = (getattr(profile, "vehicle", None) or {}).get("forwardAxis") or (0.0, 1.0, 0.0)
    n = math.hypot(fwd[0], fwd[1]) or 1.0
    fx, fy = fwd[0] / n, fwd[1] / n
    along = [c[0] * fx + c[1] * fy for c, *_ in ws]
    mid = sum(along) / len(along)
    front = [w for w, a in zip(ws, along) if a > mid]
    back = [w for w, a in zip(ws, along) if a <= mid]
    if not front or not back:
        return []
    rf, rb = (sum(w[1] for w in g) / len(g) for g in (front, back))
    if rf > 1.02 * rb:                                       # the bigger tyres are the rear axle
        back, fx, fy = front, -fx, -fy
    L = TRACK_LEN_M[0] + (TRACK_LEN_M[1] - TRACK_LEN_M[0]) * _hash01(len(ws), int(1000 * profile.longest), 11)
    return [((c[0] - fx * TYRE_PATCH_K * r, c[1] - fy * TYRE_PATCH_K * r), (-fx, -fy), 0.5 * wd + TRACK_PAD_M, L)
            for c, r, wd, _ in back]


def track_press(x, y, tracks, seed):
    """Height factor from the wheel tracks: TRACK_FLOOR in a lane, recovering along it and at its broken edges."""
    f = 1.0
    for (sx, sy), (bx, by), hw, L in tracks:
        dx, dy = x - sx, y - sy
        a = dx * bx + dy * by
        if not 0.0 <= a <= L:
            continue
        side = abs(-dx * by + dy * bx) - hw * (0.8 + 0.4 * value_noise(x, y, seed ^ 0x7AC, 0.25))
        if side > 0.0:
            continue
        k = (a / L) ** 1.5                                   # fresh at the car, standing again by its end
        f = min(f, TRACK_FLOOR + (1.0 - TRACK_FLOOR) * k)
    return f


def tracks_yaw(x, y, tracks, yaw):
    """A stem in a lane lies along it (back, away from the car), with some scatter from its own yaw."""
    for (sx, sy), (bx, by), hw, L in tracks:
        dx, dy = x - sx, y - sy
        a = dx * bx + dy * by
        if 0.0 <= a <= L and abs(-dx * by + dy * bx) <= 1.2 * hw:
            return math.degrees(math.atan2(by, bx)) + 0.25 * (((yaw + 180.0) % 360.0) - 180.0)
    return yaw


def tyre_tuft(x, y, seed):
    """Multiplier on a tyre corridor's height for the plant at (x, y) (TYRE_TUFT range, ragged at TYRE_TUFT_M)."""
    lo, hi = TYRE_TUFT
    return lo + (hi - lo) * value_noise(x, y, seed ^ 0x77E, TYRE_TUFT_M) ** 1.5


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
    tracks = wheel_tracks(profile)
    patches = open_patches(profile, seed, radius)
    thin = random.Random(seed ^ PATCH_SEED ^ 0x1)       # one draw per blade: the patches' thinning
    cut = 0
    blades = []
    floor = []                                         # round 14: where a plant is left out, the meadow floor
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
        worn = patch_strength(x, y, patches)
        if thin.random() < worn * PATCH_THIN:
            floor.append((x, y, yaw, h, lean, False, pick))
            continue                                   # open ground in a worn patch
        fore, mv = fore_factor(x, y, cameras), meadow(x, y, seed)
        if meadow_drop(x, y, seed, mv, fore):
            floor.append((x, y, yaw, h, lean, False, pick))
            continue                                   # round 12: bare soil, a thinner foreground
        h *= (1.0 - worn) * fore * clump_factor(x, y, seed) * meadow_height(mv)
        edge = r / radius
        if edge > 1.0 - EDGE_TAPER:                    # no carpet edge where the real blades end
            h *= 1.0 - (1.0 - EDGE_FLOOR) * (edge - (1.0 - EDGE_TAPER)) / EDGE_TAPER
        if zones:
            h, lean = _press(h, lean, trample_seeded(x, y, zones, seed))     # round 13: irregular, local
            tk = track_press(x, y, tracks, seed)
            if tk < 1.0:                               # round 12: the wheels' way in, laid over along it
                h, lean = _press(h, max(lean, 0.6), tk)
                yaw = tracks_yaw(x, y, tracks, yaw)
        if lines:
            cap = sight_cap(x, y, lines, half_w, tyre_tuft(x, y, seed) if zones else 1.0)
            if cap < h:
                cut += 1
                h = cap
                if h < 0.005:
                    continue                           # trampled flat: no blade
        blades.append((x, y, yaw, h, lean, flower, pick))
    if lines:                                          # the floor's low cover obeys the sight cuts too
        floor = [(x, y, yaw, min(h, sight_cap(x, y, lines, half_w)), lean, f, pk) for x, y, yaw, h, lean, f, pk in floor]
        floor = [b for b in floor if b[3] >= 0.004]
    hills = [rng.uniform(*HORIZON_H) for _ in range(HORIZON_SEGMENTS)]
    trees = tree_stands(profile, seed, radius, cameras, hero, sun)
    far = far_grass(profile, seed, radius, grass_height_m, lines, half_w, trk, zones, cameras)
    flora = field_flora(profile, seed, radius, crop, lines, half_w, trk, zones)
    flora.update(field_cover(profile, seed, radius, lines, half_w, trk, zones, cameras))   # round 15
    return {"trees": trees, "farGrass": far, "flora": flora, "trample": pressed_stems(profile, seed, grass_height_m, zones),
            "tyres": [list(z[0]) for z in zones], "wheelTracks": [[list(t[0]), list(t[1]), t[2], t[3]] for t in tracks],
            "extent": extent, "bladeRadius": radius, "centre": [cx, cy], "footprint": [hx, hy],
            "clearing": {"in": CLEAR_IN * max(hx, hy), "out": CLEAR_OUT * max(hx, hy)},
            "track": list(trk) if trk else None, "blades": blades, "floor": floor, "patches": patches, "horizon": hills, "sightCut": cut}


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


def far_grass(profile, seed, blade_radius, grass_height_m, lines, half_w, trk=None, zones=(), cameras=()):
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
                cap = body_cap(x, y, ((cx, cy), hx, hy))   # round 13: no bare strip round the body - the cover
                if cap <= 0.0:                             # grows to it, pressed low under the overhangs
                    continue
                h *= COVER_K * clear_factor(max(abs(x - cx) / hx, abs(y - cy) / hy))
                h = min(h, cap)
                mv = meadow(x, y, seed)
                if meadow_drop(x, y, seed, mv):
                    continue                           # round 12: the cover is patchy too
                h *= meadow_height(mv)
                if zones:
                    h *= trample_seeded(x, y, zones, seed)
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
            s = min(s, body_cap(x, y, ((cx, cy), hx, hy)) / h0)     # round 13: up to the body, pressed
            if s < 0.15:
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
        if kind == "weeds" and zones:
            pts += near_weeds(profile, seed, lines, half_w, zones)   # round 13: a few more where the camera looks
        out[kind] = pts
    return out


# Round 15 (owner's r14 review: "blocked by assets" - the visible grass was two scanned libraries): the meadow floor
# gets its own species, each in its own patches so the ground changes character across the frame instead of one
# even mix. kind -> (nominal height m, plants per m^2 inside a patch, patch wavelength m, patch threshold, fore x).
# fine = finer bermuda blades, clover = sorrel's trefoil leaves, moss = low cushions on the trodden / bare floor,
# broadleaf = nettle-like weeds standing out of the grass. Instanced (static): none of it counts against the
# swaying foliage mesh's vertex budget. The patch mask is two octaves of value noise, smoothstepped over +-PATCH_EDGE
# around the threshold, so a patch fades out over a hand-span instead of a hard edge (eng).
COVER_KINDS = {"fine": (0.12, 170.0, 2.4, 0.46, 2.6), "clover": (0.05, 50.0, 1.5, 0.55, 1.6),
               "moss": (0.03, 190.0, 1.1, 0.50, 2.4), "broadleaf": (0.16, 5.0, 3.3, 0.55, 1.5)}
COVER_GROW = {"fine": 1.8, "clover": 1.7, "moss": 2.2, "broadleaf": 1.4}   # x the scan's own size: r15a at 1.0 hid
#                                         every cover plant under the blades' shade at sheet size (clover is sparse:
#                                         wood sorrel flowers pink, and at r15b's 120/m^2 they read as confetti)
COVER_SEED = 0xC0BE
COVER_PATCH_EDGE = 0.10
COVER_FORE_M = 3.2                       # round each camera (the frame's foreground) a kind grows fore x denser
COVER_CAP = 120000                       # per kind (instances are cheap; this bounds the layout's own time)


def cover_mask(x, y, seed, kind):
    """0..1: how much of `kind`'s patch covers (x, y) - smooth over COVER_PATCH_EDGE either side of its threshold.
    moss prefers the low (bare / trodden) meadow, fine grass the lusher ground."""
    h0, dens, lam, thr, _ = COVER_KINDS[kind]
    k = sorted(COVER_KINDS).index(kind) + 1
    v = 0.7 * value_noise(x, y, seed ^ COVER_SEED ^ (k * 0x1F3), lam) + \
        0.3 * value_noise(x, y, seed ^ COVER_SEED ^ (k * 0x2A7), lam / 2.9)
    if kind == "moss":
        v += 0.25 * (0.5 - meadow(x, y, seed))
    elif kind == "fine":
        v += 0.15 * (meadow(x, y, seed) - 0.5)
    t = min(1.0, max(0.0, (v - (thr - COVER_PATCH_EDGE)) / (2 * COVER_PATCH_EDGE)))
    return t * t * (3.0 - 2.0 * t)


def field_cover(profile, seed, blade_radius, lines, half_w, trk=None, zones=(), cameras=()):
    """{kind: [(x, y, yaw_deg, scale)]} the meadow floor's species (COVER_KINDS) in their own patches, out to
    FLORA_R_K x the blade disc and denser round the cameras; body-, sight- and track-capped like the weeds. Low kinds
    (moss, clover) grow into a tyre's pressed ring; the standing ones do not."""
    rng = random.Random(seed ^ COVER_SEED)
    (cx, cy), hx, hy = _frame(profile)
    r0 = FLORA_R_K * blade_radius
    cams = [(c[0], c[1]) for c in cameras]
    out = {}
    for kind in sorted(COVER_KINDS):
        h0, dens, _, _, fore = COVER_KINDS[kind]
        pts = []
        n = min(COVER_CAP, int(dens * fore * math.pi * r0 * r0))
        for _ in range(n):
            r, a = r0 * math.sqrt(rng.random()), rng.uniform(0.0, math.tau)
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            s, yaw, keep = rng.uniform(0.6, 1.4) * COVER_GROW[kind], rng.uniform(0.0, 360.0), rng.random()
            near = any(math.hypot(x - px, y - py) < COVER_FORE_M for px, py in cams)
            if keep >= cover_mask(x, y, seed, kind) * (1.0 if near else 1.0 / fore):
                continue
            s = min(s, body_cap(x, y, ((cx, cy), hx, hy)) / h0)
            if s < 0.2:
                continue
            if trk and trk[0] <= x <= trk[2] and trk[1] <= y <= trk[3]:
                continue
            if zones and h0 > 0.06 and trample(x, y, zones) < 0.5:
                continue
            if lines and h0 > 0.06:
                s = min(s, sight_cap(x, y, lines, half_w) / h0)
                if s < 0.2:
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
    ring = EDGE_STEMS["ringM"]                       # round 13: the grass the body's edge pressed over, just outside
    ex, ey = hx + ring, hy + ring
    for _ in range(int(EDGE_STEMS["density"] * (4.0 * ex * ey - 4.0 * hx * hy))):
        x, y = rng.uniform(cx - ex, cx + ex), rng.uniform(cy - ey, cy + ey)
        if abs(x - cx) <= hx and abs(y - cy) <= hy:
            continue
        yaw = math.degrees(math.atan2(y - cy, x - cx)) + rng.gauss(0.0, 50.0)
        out.append((x, y, yaw, grass_height_m * rng.uniform(0.25, 0.8), rng.random()))
    return out


# Round 13 (owner's r12 review: "remove the bare dirt strip under the front bumper ... grass shorter / pressed where
# needed but never clean exposed ground unless motivated by tyre compression; a real dip under each tyre where the
# weight sits; flattened grass local and irregular round the tyres; the car IN the field, not on top"). (eng)
UNDER = {"inM": 0.30, "capM": 0.03, "slope": 0.9}   # cover and weeds grow to the body: inside the footprint's
#   outer inM (the overhangs, the sill) pressed to capM, under the ride height; outside it capM + slope x distance
EDGE_STEMS = {"ringM": 0.28, "density": 120.0}      # pressed stems in a ring just outside the footprint as well
DIP = {"depthM": 0.028, "reachK": 1.5, "rimM": 0.006, "rimK": 0.8, "noiseM": 0.09}   # each tyre sits in a dip:
#   depthM at an even share of the weight (groundContacts share), reaching reachK x the pressed patch, a low
#   pushed-up rim rimK x the patch beyond it, the edge wandering at noiseM
TRAMPLE_WOBBLE = (0.45, 1.7)            # the pressed ring reaches this x TRAMPLE_RAMP_M, varying round each tyre
TRAMPLE_WOBBLE_M = 0.11                 # ... at this scale (flattened grass is local and irregular, never a ring)
NEAR_WEEDS = {"ringM": 1.4, "density": 5.0, "clump": 0.18}   # a few weeds where the camera looks: round the body


def body_cap(x, y, frame):
    """The tallest a cover tuft / weed at (x, y) may stand near the subject (frame = ((cx, cy), hx, hy)): 0 deep
    under it (nothing grows there), UNDER capM in the footprint's outer inM, rising by slope outside it."""
    (cx, cy), hx, hy = frame
    ax, ay = abs(x - cx), abs(y - cy)
    if ax <= hx and ay <= hy:
        return UNDER["capM"] if min(hx - ax, hy - ay) <= UNDER["inM"] else 0.0
    return UNDER["capM"] + UNDER["slope"] * math.hypot(max(ax - hx, 0.0), max(ay - hy, 0.0))


def trample_seeded(x, y, zones, seed):
    """trample with the ramp's reach wobbling round each tyre (TRAMPLE_WOBBLE at TRAMPLE_WOBBLE_M): the pressed
    grass is local and irregular, flat on the patch, standing again anywhere from 0.45 to 1.7 x the ramp out."""
    d = _zone_dist(x, y, zones)
    lo, hi = TRAMPLE_WOBBLE
    ramp = TRAMPLE_RAMP_M * (lo + (hi - lo) * value_noise(x, y, seed ^ 0x7B0B, TRAMPLE_WOBBLE_M))
    if d >= ramp:
        return 1.0
    t = d / ramp
    return TRAMPLE_FLOOR + (1.0 - TRAMPLE_FLOOR) * t * t * (3.0 - 2.0 * t)


def tyre_dips(profile):
    """[(centre xy, axle unit xy, half across, half along, depth m)]: a dip under each tyre, its depth the share of
    the weight that tyre carries (profile groundContacts nearest it; an even share without them)."""
    zones = tyre_zones(profile)
    if not zones:
        return []
    gc = getattr(profile, "groundContacts", None) or []
    out = []
    for c, ax, ha, hl in zones:
        share = 1.0 / len(zones)
        if gc:
            g = min(gc, key=lambda g: math.hypot(g["center"][0] - c[0], g["center"][1] - c[1]))
            share = float(g.get("share", share))
        k = min(1.3, max(0.55, share * len(zones)))          # 1 = an even share
        out.append((c, ax, ha * DIP["reachK"], hl * DIP["reachK"], DIP["depthM"] * k))
    return out


def ground_dz(x, y, dips, seed=0):
    """The ground's height (m; negative in a dip, a few mm up on its rim) at (x, y): a smooth bowl under each tyre,
    its edge wandering with noise, a low pushed-up rim round it, 0 beyond."""
    low, rim = 0.0, 0.0
    for (zx, zy), (ax, ay), ha, hl, depth in dips:
        dx, dy = x - zx, y - zy
        a, b = (dx * ax + dy * ay) / ha, (-dx * ay + dy * ax) / hl
        w = 0.8 + 0.4 * value_noise(x, y, seed ^ 0xD1B, DIP["noiseM"])
        q = math.hypot(a, b) / w
        if q < 1.0:
            s = 1.0 - q * q
            low = min(low, -depth * s * s)
        elif q < 1.0 + DIP["rimK"]:
            rim = max(rim, DIP["rimM"] * math.sin(math.pi * (q - 1.0) / DIP["rimK"]) * depth / DIP["depthM"])
    return low if low < 0.0 else rim


def near_weeds(profile, seed, lines, half_w, zones):
    """[(x, y, yaw, scale)] a few extra weeds round the body (NEAR_WEEDS ring), some in small clumps, each capped by
    the body and the sight lines like any weed: micro-variation where the camera looks, not more grass everywhere."""
    rng = random.Random(seed ^ 0x3EED)
    (cx, cy), hx, hy = _frame(profile)
    R = NEAR_WEEDS["ringM"]
    area = (2 * hx + 2 * R) * (2 * hy + 2 * R) - 4 * hx * hy
    n = int(NEAR_WEEDS["density"] * area)
    h0 = FLORA["weeds"][0]
    out = []
    for _ in range(4 * n):
        if len(out) >= n:
            break
        x, y = rng.uniform(cx - hx - R, cx + hx + R), rng.uniform(cy - hy - R, cy + hy + R)
        if abs(x - cx) <= hx and abs(y - cy) <= hy:
            continue
        pts = [(x, y)]
        if rng.random() < 3 * NEAR_WEEDS["clump"]:
            pts += [(x + rng.gauss(0, NEAR_WEEDS["clump"]), y + rng.gauss(0, NEAR_WEEDS["clump"]))
                    for _ in range(rng.randint(1, 3))]
        for px, py in pts:
            s = min(rng.uniform(0.5, 1.2), body_cap(px, py, ((cx, cy), hx, hy)) / h0)
            if zones and trample(px, py, zones) < 0.5:
                continue
            if lines:
                s = min(s, sight_cap(px, py, lines, half_w) / h0)
            if s >= 0.15:
                out.append((px, py, rng.uniform(0.0, 360.0), s))
    return out[:n]


# Round 10 (owner's r9 review: "the field has no props"): a farm field has a boundary. A weathered post-and-wire
# fence crosses the view FENCE_DIST_M behind the subject as the hook camera sees it, and a line of wooden utility
# poles runs further out; both fade into the aerial haze (golden_field realises them). Human-scale cues, never
# clutter: nothing stands within FENCE_DIST_M of the subject.
FENCE_DIST_M = 38.0                     # (eng) fence line distance behind the subject
FENCE_HALF_M = 48.0                     # (eng) it runs this far either side of the view line
FENCE_STEP_M = (2.3, 2.9)               # (eng) post spacing
FENCE_POST_H = (1.05, 1.3)              # (eng) post height above ground (a stock fence)
FENCE_LEAN_DEG = 4.0                    # (eng) a post leans up to this, any direction (old wood)
FENCE_YAW_DEG = 14.0                    # (eng) the line is never square to the camera
POLE_DIST_M, POLE_STEP_M, POLE_H = 125.0, 48.0, (8.5, 9.5)   # (eng) utility poles, spacing, height
POLE_COUNT = 5
FENCE_SEED = 0xFE7C                     # their own stream: they never move a blade or a tree


def boundary_props(profile, seed, cameras=()):
    """{"posts": [(x, y, h, lean_x_deg, lean_y_deg, yaw_deg)], "wires": [(post_i, post_j)], "poles": [(x, y, h, yaw_deg)]}
    behind the subject along the first camera's view line (none without a camera)."""
    if not cameras:
        return {"posts": [], "wires": [], "poles": []}
    rng = random.Random(seed ^ FENCE_SEED)
    (cx, cy), _, _ = _frame(profile)
    cam = cameras[0]
    dx, dy = cx - cam[0], cy - cam[1]
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    a = math.radians(rng.uniform(-FENCE_YAW_DEG, FENCE_YAW_DEG))
    px, py = -dy * math.cos(a) - dx * math.sin(a), dx * math.cos(a) - dy * math.sin(a)   # along the line
    fx, fy = cx + dx * FENCE_DIST_M, cy + dy * FENCE_DIST_M
    posts, t = [], -FENCE_HALF_M
    while t <= FENCE_HALF_M:
        x, y = fx + px * t + rng.gauss(0.0, 0.08), fy + py * t + rng.gauss(0.0, 0.08)
        posts.append((x, y, rng.uniform(*FENCE_POST_H), rng.uniform(-FENCE_LEAN_DEG, FENCE_LEAN_DEG),
                      rng.uniform(-FENCE_LEAN_DEG, FENCE_LEAN_DEG), math.degrees(math.atan2(py, px)) + rng.gauss(0, 8)))
        t += rng.uniform(*FENCE_STEP_M)
    wires = [(i, i + 1) for i in range(len(posts) - 1)]
    b = math.radians(rng.uniform(-25.0, 25.0))
    qx, qy = -dy * math.cos(b) - dx * math.sin(b), dx * math.cos(b) - dy * math.sin(b)
    ox, oy = cx + dx * POLE_DIST_M, cy + dy * POLE_DIST_M
    start = rng.uniform(-0.5, 0.5) * POLE_STEP_M - POLE_STEP_M * (POLE_COUNT - 1) / 2
    poles = [(ox + qx * (start + k * POLE_STEP_M), oy + qy * (start + k * POLE_STEP_M), rng.uniform(*POLE_H),
              math.degrees(math.atan2(qy, qx))) for k in range(POLE_COUNT)]
    return {"posts": posts, "wires": wires, "poles": poles}


# Round 11 (owner's r10 review: "the field's horizon is weak, too much empty sky"): a real field's horizon is layered.
# A near hedgerow stands just behind the fence (HEDGE_DIST_M, broken by gaps), under the tree stands and the sky's own
# skyline.
# (eng)
HEDGE_DIST_M = 44.0                     # behind the subject along the hook camera's line (the fence stands at 38 m)
HEDGE_HALF_M = 60.0                     # it runs this far either side of the view line
HEDGE_STEP_M = (1.4, 2.6)               # shrub spacing
HEDGE_H = (1.1, 2.8)                    # shrub height (real metres)
HEDGE_GAP_P = 0.3                       # share of shrubs left out (a hedgerow has gaps; r11a at 0.12 read as a wall)
HEDGE_SEED = 0x4ED6


def horizon_layers(profile, seed, cameras=()):
    """{"hedge": [(x, y, h, yaw_deg, pick)]} behind the subject along the first camera's view line; empty without a
    camera. Its own random stream."""
    if not cameras:
        return {"hedge": []}
    rng = random.Random(seed ^ HEDGE_SEED)
    (cx, cy), _, _ = _frame(profile)
    cam = cameras[0]
    dx, dy = cx - cam[0], cy - cam[1]
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    a = math.radians(rng.uniform(-10.0, 10.0))
    px, py = -dy * math.cos(a) - dx * math.sin(a), dx * math.cos(a) - dy * math.sin(a)
    hx, hy = cx + dx * HEDGE_DIST_M, cy + dy * HEDGE_DIST_M
    hedge, t = [], -HEDGE_HALF_M
    wave = rng.uniform(0.0, math.tau)
    while t <= HEDGE_HALF_M:
        if rng.random() >= HEDGE_GAP_P:
            off = 1.5 * math.sin(t / 17.0 + wave) + rng.gauss(0.0, 0.4)     # a hedgerow wanders a little
            h = rng.uniform(*HEDGE_H) * (0.85 + 0.3 * (0.5 + 0.5 * math.sin(t / 9.0 + 2.0 * wave)))
            hedge.append((hx + px * t + dx * off, hy + py * t + dy * off, h, rng.uniform(0.0, 360.0), rng.random()))
        t += rng.uniform(*HEDGE_STEP_M)
    return {"hedge": hedge}
