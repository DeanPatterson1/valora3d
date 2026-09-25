"""Droplets and drips on the subject (plan Task 66; render-studio rain_atmosphere.drips generalised). Pure.

Beads (FL-03): render-studio's mixed populations (render_materials.add_water_beads, ModVision
tools/render-studio/render_materials.py:136-225) on the subject's surface where it faces up (zone up_facing:
n.up > shape.UP_DOT) or anywhere (zone all): mist, small and large domes, merged pools and gravity runoff
streaks (bead_kind / bead_dims), each with its own width, length and height (a varying contact angle),
gathered into irregular wet clusters (patch_factor) at CANDIDATES_M2 x density candidates per m2. Drips (FL-20): emitters on the subject's low edges (shape.low_edges); each
swells for HANG_FRAC of its seeded period, lets go and falls under gravity until the ground (z = 0), where it
is gone until the next cycle. The lifecycle is a function of time alone (METHODS R1).

A drip that lets go leaves the subject (review chunk3 #5): drip_events lists every cycle that touches the clip
with the emitter's world position and velocity at its detach time (from engine.motion_path, the pose the
compiler keys), and drip_at flies it ballistically from there. While it hangs it rides the subject."""
import math
import random

from engine.physics import shape

G = 9.81
HANG_FRAC = 0.4        # render-studio: a drop hangs for 40% of its period
SWELL_EXP = 0.6        # render-studio: fills fast, then hangs
MAX_BEADS = 60000      # render-studio BEAD_LIMIT (render_materials.py:133); an instance cap, by cost
CANDIDATES_M2 = 9000.0  # render-studio: bead candidates per m2 of up-facing lacquer (render_materials.py:159)
BEAD_REF_MM = 1.5      # the sizeMm at which render-studio's absolute radii apply (the block default)

# bead kinds (the GN tree stores the code in valora_kind; render-studio numbers them 3 / 0 / 0 / 1 / 2)
MIST, SMALL, LARGE, MERGED, RUNOFF = 0, 1, 2, 3, 4
BEAD_KINDS = (MIST, SMALL, LARGE, MERGED, RUNOFF)
KIND_EDGES = (0.34, 0.84, 0.965, 0.985)   # render_materials.py:192-212: the chance thresholds
RUNOFF_NZ = 0.94       # render_materials.py:212: runoff only where the panel slopes (n.z < .94)
LIFT = 0.22            # render_materials.py:219: the bead centre sits 0.22 x height above the paint
SAG_R_MM = 2.2         # render_materials.py:204: above this radius a drop sags (height x .78)
DISTORT = 0.12         # render_materials.py:262: smooth radial distortion of the unit prototype (+-12%)
PATCH_BROAD_M, PATCH_FINE_M = 8.5, 37.0   # render_materials.py:180-183: cluster noise frequencies (1/m)
REF_LONGEST_M = 4.5    # render-studio tuned its bead field on a ~4.5 m car
MAX_CLOSEUP = 50.0     # (eng) the most a small subject densifies and tightens its bead field
MAX_DRIPS = 40         # (eng) drip emitters at density 1
PERIOD_S = (1.2, 3.4)  # (eng) render-studio period range at car scale (hang + fall + ring always fit)


def fall_time(h):
    return math.sqrt(2.0 * max(h, 0.0) / G)


def drip_state(t, period, phase, h):
    """(state, size 0..1, drop metres below the emitter): swell -> fall -> gone, one cycle per period."""
    since = ((t / period + phase) % 1.0) * period
    hang = HANG_FRAC * period
    if since < hang:
        return "swell", (since / hang) ** SWELL_EXP, 0.0
    fall = since - hang
    drop = 0.5 * G * fall * fall
    if drop < h:
        return "fall", 1.0, drop
    return "gone", 0.0, h


def zone_samples(profile, zone):
    ss = shape.samples(profile)
    return shape.up_facing(ss) if zone == "up_facing" else list(ss)


def size_scale(size_mm):
    """Every bead dimension scales with sizeMm; 1 at BEAD_REF_MM (render-studio's absolute sizes)."""
    return size_mm / BEAD_REF_MM


def closeup(longest_m):
    """How much closer than a car a subject of this size is filmed (>= 1): a small subject is framed close, so
    its bead field is denser per m2 and its wet clusters tighter (the car's look, scaled to the frame)."""
    return min(MAX_CLOSEUP, max(1.0, REF_LONGEST_M / max(1e-4, longest_m)))


def bead_density(size_mm, density, longest_m=REF_LONGEST_M):
    """Bead candidates per m2 of selected surface (before the cluster mask): render-studio's 9000 / m2 at
    density 1 on a car, fewer as the beads grow (same wetted share), denser on a small subject (closeup)."""
    return CANDIDATES_M2 * density / size_scale(size_mm) ** 2 * closeup(longest_m)


def patch_freqs(longest_m):
    """(broad, fine) cluster-noise frequencies (1/m): render-studio's on a car, tighter on a small subject."""
    c = closeup(longest_m)
    return PATCH_BROAD_M * c, PATCH_FINE_M * c


def bead_cap_density(longest_m):
    """The density cap that keeps a subject of this size under MAX_BEADS (by cost)."""
    return MAX_BEADS / max(1e-4, longest_m ** 2)


def patch_factor(broad, fine):
    """Share of candidates kept (render_materials.py:180-184): nested irregular patches (broad / fine are
    0..1 noise values) make wet clusters separated by calmer paint, with a 4% floor of stray beads."""
    cluster = max(0.0, min(1.0, (broad - 0.30) / 0.40)) ** 2.2
    return 0.04 + 0.92 * cluster * (0.45 + 0.55 * fine)


def bead_kind(u, nz):
    """The population of a bead from one uniform u and the surface normal z (render_materials.py:188-212):
    34% mist, 50% small domes, 12.5% large pooled drops, 3.5% merged; the top 1.5% run off as streaks where
    the panel slopes (n.z < RUNOFF_NZ), else they stay merged pools."""
    a, b, c, d = KIND_EDGES
    if u < a:
        return MIST
    if u < b:
        return SMALL
    if u < c:
        return LARGE
    if u >= d and nz < RUNOFF_NZ:
        return RUNOFF
    return MERGED


def bead_dims(kind, r, k=1.0):
    """(width, length, height) half-extents in metres of the unit-sphere prototype for one bead, from four
    uniforms r (render_materials.py:193-216), scaled by k = size_scale(sizeMm). height / width is the
    contact angle's shape: 0.5-0.74 (a waxed lacquer's high contact angle), x .78 for drops over SAG_R_MM
    (gravity flattens them). Length is along the downhill direction (merged pools and runoff stretch)."""
    r1, r2, r3, r4 = r
    if kind == MIST:
        radius = 0.00025 + r1 * 0.00035
    elif kind == SMALL:
        radius = 0.0007 + r1 ** 2 * 0.0017
    elif kind == RUNOFF:
        return (k * (0.00028 + r1 * 0.00037), k * (0.003 + r2 * 0.009), k * (0.00010 + r3 * 0.00012))
    else:                                      # LARGE and MERGED (a merged pool is a large drop that joined)
        radius = 0.0022 + r1 ** 2.6 * 0.0058
    width = radius * (0.86 + r2 * 0.26)
    length = radius * (0.85 + r3 * 0.45)
    height = radius * (0.50 + r4 * 0.24) * (1.0 if radius < SAG_R_MM / 1000.0 else 0.78)
    if kind == MERGED:
        width, length, height = width * 1.25, length * (1.6 + r3 * 0.9), height * 0.8
    return (k * width, k * length, k * height)


def contact_angle_deg(width, height):
    """The contact angle of a bead prototype (unit sphere scaled (w, ., h), centre LIFT x h above the paint),
    read as a spherical cap: 2 atan(cap height / footprint radius)."""
    cap = (1.0 + LIFT) * height
    foot = width * math.sqrt(1.0 - LIFT * LIFT)
    return math.degrees(2.0 * math.atan2(cap, foot))


def drip_emitters(profile, density, seed):
    """[(placed point, period, phase)] on the low edges, seeded; at most MAX_DRIPS x density, highest first."""
    edges = sorted(shape.low_edges(shape.samples(profile)), key=lambda s: -s["p"][2])
    n = min(len(edges), int(round(MAX_DRIPS * density)))
    rng = random.Random(seed)
    pick = sorted(rng.sample(range(len(edges)), n)) if n else []
    lo, hi = PERIOD_S
    return [(list(edges[i]["p"]), rng.uniform(lo, hi) + fall_time(edges[i]["p"][2]), rng.random()) for i in pick]


def _rotation(pose):
    from engine.motion_path import rotation_matrix as rm
    return rm(pose)


def _emit_world(p, pose_at, profile, t):
    from engine.motion_path import apply
    return apply(p, pose_at(t), profile)


def drip_events(emitters, pose_at, profile, t_end, t_start=0.0, dt=1e-3):
    """Every drip cycle (script seconds) that is alive somewhere in [t_start, t_end]: {p (placed), t0 (starts to
    swell), td (lets go), pd (world position at td), vd (world velocity at td, m/s), rd / rdd (the pose's
    rotation at td and its time derivative, rows), tl (lands at z = 0)}. The cycles are the periodic ones
    drip_state walks (start = (k - phase) x period); the pose at td comes from the motion path, so a moving or
    turning subject throws its drips instead of carrying them. pd / vd are the motion path's alone: the
    compiled drip's are re-sampled where it HUNG, from the keyed motion and realism offset curves at its release
    frame (droplets build finalize; review chunk5 #10); detach_state is that for an offset shift d held still:
    pd + rd d, vd + rdd d."""
    out = []
    for p, period, phase in emitters:
        hang = HANG_FRAC * period
        k = math.floor(t_start / period + phase) - 1
        while True:
            t0 = (k - phase) * period
            if t0 > t_end:
                break
            td = t0 + hang
            pd = _emit_world(p, pose_at, profile, td)
            a, b = _emit_world(p, pose_at, profile, td - dt), _emit_world(p, pose_at, profile, td + dt)
            vd = tuple((b[i] - a[i]) / (2 * dt) for i in range(3))
            R = _rotation(pose_at(td))
            Ra, Rb = _rotation(pose_at(td - dt)), _rotation(pose_at(td + dt))
            Rd = [[(Rb[i][j] - Ra[i][j]) / (2 * dt) for j in range(3)] for i in range(3)]
            z0, vz = max(pd[2], 0.0), vd[2]
            tl = td + (vz + math.sqrt(vz * vz + 2.0 * G * z0)) / G
            if tl >= t_start:
                out.append({"p": list(p), "t0": t0, "td": td, "pd": list(pd), "vd": list(vd), "tl": tl,
                            "rd": [list(r) for r in R], "rdd": Rd})
            k += 1
    return out


def detach_state(ev, shift):
    """(position, velocity) at td of a drip whose emitter the realism offset moved by `shift` (placed metres,
    motion-local): the same rigid motion carries the shifted point, so it lets go where it hung."""
    pos = [ev["pd"][i] + sum(ev["rd"][i][j] * shift[j] for j in range(3)) for i in range(3)]
    vel = [ev["vd"][i] + sum(ev["rdd"][i][j] * shift[j] for j in range(3)) for i in range(3)]
    return pos, vel


def drip_at(ev, t, attached=None):
    """(state, size 0..1, world position) of one drip event at script time t. Hanging it rides the subject
    (`attached`, the emitter's world position now); after td it is ballistic from (pd, vd) until z < 0."""
    if t < ev["t0"]:
        return "wait", 0.0, None
    if t < ev["td"]:
        return "swell", ((t - ev["t0"]) / (ev["td"] - ev["t0"])) ** SWELL_EXP, attached
    u = t - ev["td"]
    pos = tuple(ev["pd"][i] + ev["vd"][i] * u for i in range(3))
    pos = (pos[0], pos[1], pos[2] - 0.5 * G * u * u)
    if pos[2] < 0.0:
        return "gone", 0.0, None
    return "fall", 1.0, pos
