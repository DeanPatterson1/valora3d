"""Pure placement and timing for library smoke and fire (phase 6 Task 112, lane S: smoke_plume, fire; T113
tyre_smoke). A library sequence (tools/bake_vdb_library.py) keeps its physical size (x3 guard, engine/physics/vdb)
and sits OUTSIDE the subject's bounds x 1.1 (the effects' spawn_in_subject margin), on the ground.

Timing: a plume should already be rising when the clip opens, so play starts at a seeded file inside the
sequence's developed part (SETTLED_FRAC..), and the play is fitted to the clip: if the clip needs more files than
remain, the start moves earlier, then the retime slows (never below vdb.MIN_RETIME)."""
import math

from engine.physics import vdb as V

MARGIN = 1.1             # the subject's bounds x 1.1: nothing spawns inside (weather_rules.spawn_in_subject)
GAP_FRAC = 0.15          # (eng) extra clearance, x the plume width, between the bounds and the plume's edge
SETTLED_FRAC = 0.3       # (eng) the first 30% of a sequence is the plume forming: a clip opens after it
JITTER_DEG = 15.0        # (eng) seeded yaw jitter of a placement about its nominal direction
SPREAD_DEG = {"behind": 0.0, "around": 70.0, "side": 90.0}


def _unit(x, y):
    n = math.hypot(x, y)
    return (x / n, y / n) if n > 1e-9 else (1.0, 0.0)


def footprint_radius(profile):
    return math.hypot(profile.half[0], profile.half[1]) * MARGIN


def anchors(profile, camera, width_m, placement="behind", count=1, rng=None):
    """[(x, y, z)] ground anchors (the plume's base centre) for `count` plumes: 'behind' the subject as the
    camera sees it, 'around' it (fanned up to +-SPREAD), or to one 'side'; each plume's edge clears the bounds
    x MARGIN by GAP_FRAC x width. Seeded yaw jitter when rng is given."""
    c = profile.center
    bx, by = _unit(c[0] - camera[0], c[1] - camera[1])          # camera -> subject, continued past it
    base = math.atan2(by, bx)
    dist = footprint_radius(profile) + width_m * (0.5 + GAP_FRAC)
    spread = math.radians(SPREAD_DEG[placement])
    out = []
    for i in range(count):
        if placement == "side":
            a = base + spread * (1 if i % 2 == 0 else -1)
        elif count == 1:
            a = base
        else:
            a = base - spread + 2 * spread * i / (count - 1)
        if rng is not None:
            a += math.radians(rng.uniform(-JITTER_DEG, JITTER_DEG))
        out.append((c[0] + dist * math.cos(a), c[1] + dist * math.sin(a), 0.0))
    return out


def clear_of_subject(profile, anchor, width_m):
    """True when a plume of width_m at anchor stays outside the subject's bounds x MARGIN (in plan view)."""
    lo = [c - h * MARGIN for c, h in zip(profile.center, profile.half)]
    hi = [c + h * MARGIN for c, h in zip(profile.center, profile.half)]
    r = width_m / 2
    return (anchor[0] + r < lo[0] or anchor[0] - r > hi[0] or anchor[1] + r < lo[1] or anchor[1] - r > hi[1])


def fit_play(n_files, clip_frames, retime, rng=None, settled_frac=SETTLED_FRAC):
    """(first_file, retime) so that clip_frames render frames play inside the sequence: start at a seeded file
    in the developed part; move the start earlier if the clip needs more files; then slow the retime."""
    retime = V.clamp_retime(retime)
    need = int(math.ceil((clip_frames - 1) * retime)) + 1
    lo = max(1, int(settled_frac * n_files))
    first = lo if rng is None else rng.randint(lo, max(lo, lo + n_files // 10))
    if first + need - 1 > n_files:
        first = max(1, n_files - need + 1)
    if need > n_files:
        retime = max(V.MIN_RETIME, (n_files - 1) / max(1, clip_frames - 1))
    return first, retime


def wind_drift(wind, per_ms, seconds):
    """(dx, dy) metres a plume drifts downwind over `seconds` (per_ms: the block's windCalibration)."""
    if not wind or wind.get("speedMs", 0.0) <= 0:
        return (0.0, 0.0)
    a = math.radians(wind.get("directionDeg", 0.0))
    s = wind["speedMs"] * per_ms * seconds
    return (s * math.cos(a), s * math.sin(a))


# --- flicker (fire) -----------------------------------------------------------------------------------------

FLICKER_HZ = (5.0, 12.0)     # LM-08 / GS-06: a real flame's light flickers at 5-12 Hz
FLICKER_DEPTH = 0.35         # (eng) +-35% about the mean


def flicker(frames, fps, rng, depth=FLICKER_DEPTH):
    """[energy multiplier per frame] (mean 1): a sum of three seeded sines in FLICKER_HZ plus a little seeded
    noise, so the light never pulses on one clean beat."""
    comps = [(rng.uniform(*FLICKER_HZ), rng.uniform(0, 2 * math.pi), w) for w in (0.5, 0.3, 0.2)]
    out = []
    for f in range(frames):
        t = f / fps
        s = sum(w * math.sin(2 * math.pi * hz * t + ph) for hz, ph, w in comps)
        out.append(max(0.2, 1.0 + depth * (s + 0.3 * rng.uniform(-1, 1))))
    return out
