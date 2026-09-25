"""Droplets and drips on the subject (plan Task 66; render-studio rain_atmosphere.drips generalised). Pure.

Beads (FL-03): real-size flattened hemispheres (sizeMm across) scattered on the subject's surface where it
faces up (zone up_facing: estimated normal n.up > shape.UP_DOT) or anywhere (zone all), covering COVER x
density of that surface (eng). Drips (FL-20): emitters on the subject's low edges (shape.low_edges); each
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
COVER = 0.25           # (eng) share of the selected surface the beads cover at density 1
MAX_BEADS = 30000      # (eng) instance cap, by cost
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


def bead_density(size_mm, density):
    """Beads per m2 of selected surface: COVER x density of it, each a disc of diameter sizeMm."""
    r = size_mm / 2000.0
    return COVER * density / (math.pi * r * r)


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
