"""Pure gas facts (phase 6 Tasks 111 and 113, lane S): the Mantaflow presets our own CC0 VDB library is baked
from, the interactive smoke_sim domain sizing, and playback retiming. Every number is (eng) until the owner
grades G9 / G10; they sit in the Task 123 calibration register.

Budget (the plan's table, gas row): resolution_max <= 160, <= 180 frames, bake cap 60 min, cache cap 4 GB,
RAM 6-10 GB. This box shares its RAM with other Blender jobs, so the library stays at preview-tier resolution
(<= 128 except the wide tyre-smoke billow) with no noise upres: the grade is at 540p preview, and a
final-tier look re-bakes a preset at a higher res (the bake key moves with the preset)."""
import math

LIBRARY_FPS = 30         # the library is simulated at 30 fps: a 30 fps clip plays it 1:1 (no stepped retime)
RES_CAP = 160            # plan: resolution_max <= 160 for gas
FRAMES_CAP = 180
SMOKE_SIM_SPAN = 3.0     # smoke_sim's domain is at most 3 x the subject's longest side (plan T113)

# name -> domain size (x, y, z metres; base centre at the bake origin), resolution_max, frames, and the sources.
# A source: kind (SMOKE | FIRE | BOTH), centre (x, y, z), radius, temperature, density, fuel, velocity (m/s,
# the initial velocity of what it emits), and the frame range it emits over (None: the whole bake).
PRESETS = {
    "plume_soft": {
        "size": (2.0, 2.0, 4.0), "res": 128, "frames": 150, "vorticity": 0.15, "dissolve": 90,
        "sources": [{"kind": "SMOKE", "centre": (0.0, 0.0, 0.06), "radius": 0.28, "temperature": 1.0,
                     "density": 0.8, "velocity": (0.0, 0.0, 0.4), "frames": None}],
        "colour": (0.72, 0.72, 0.72), "use": "a soft ground smoke plume, 2 m wide",
    },
    "chimney_thin": {
        "size": (0.6, 0.6, 2.4), "res": 128, "frames": 150, "vorticity": 0.05, "dissolve": 60,
        "sources": [{"kind": "SMOKE", "centre": (0.0, 0.0, 0.05), "radius": 0.05, "temperature": 1.6,
                     "density": 1.0, "velocity": (0.0, 0.0, 1.0), "frames": None}],
        "colour": (0.8, 0.8, 0.8), "use": "a thin rising column (a chimney, a vent), 0.6 m wide",
    },
    "campfire": {
        "size": (1.2, 1.2, 2.0), "res": 128, "frames": 150, "vorticity": 0.2, "dissolve": 45,
        "sources": [{"kind": "BOTH", "centre": (0.0, 0.0, 0.05), "radius": 0.18, "temperature": 2.0,
                     "density": 0.35, "fuel": 1.2, "velocity": (0.0, 0.0, 0.3), "frames": None}],
        "colour": (0.35, 0.33, 0.32), "use": "fire plus its smoke, a campfire 1.2 m wide",
    },
    "tyre_smoke_burst": {
        "size": (6.0, 4.0, 2.5), "res": 160, "frames": 150, "vorticity": 0.25, "dissolve": 120,
        "sources": [{"kind": "SMOKE", "centre": (-0.8, y, 0.25), "radius": 0.3, "temperature": 0.25,
                     "density": 1.0, "velocity": (-2.5, 0.0, 0.3), "frames": (1, 75)} for y in (-0.8, 0.8)],
        "colour": (0.82, 0.82, 0.82), "use": "a wide low billow from two rear tyres, 6 m long",
    },
    "_probe": {        # test-only (engine/tests/test_gas_blender.py): seconds to bake, never in "all"
        "size": (1.0, 1.0, 1.5), "res": 24, "frames": 12, "vorticity": 0.1, "dissolve": None,
        "sources": [{"kind": "BOTH", "centre": (0.0, 0.0, 0.05), "radius": 0.2, "temperature": 1.5,
                     "density": 1.0, "fuel": 1.0, "velocity": (0.0, 0.0, 0.5), "frames": (1, 8)}],
        "colour": (0.7, 0.7, 0.7), "use": "test probe",
    },
    "dust_billow": {
        "size": (4.0, 4.0, 2.0), "res": 128, "frames": 120, "vorticity": 0.2, "dissolve": 90,
        "sources": [{"kind": "SMOKE", "centre": (0.0, 0.0, 0.1), "radius": 0.6, "temperature": 0.15,
                     "density": 0.9, "velocity": (0.0, 0.0, 1.2), "frames": (1, 20)}],
        "colour": (0.62, 0.55, 0.45), "use": "a dust billow off loose ground, 4 m wide",
    },
}


def cells(size, res):
    """Mantaflow's grid: resolution_max along the longest side, the others in proportion (at least 1)."""
    m = max(size)
    return tuple(max(1, int(round(res * s / m))) for s in size)


def voxel_m(size, res):
    return max(size) / res


def base_m(size):
    """The plume's base point in the VDB's own space: Mantaflow writes grids with the domain's min corner at the
    origin (measured, T110), and a preset's domain sits with its base centre on the bake origin."""
    return (size[0] / 2, size[1] / 2, 0.0)


def retime(native_fps, clip_fps, time_scale=1.0):
    """Sequence files per render frame: a sequence simulated at native_fps plays at real speed in a clip at
    clip_fps when it advances native_fps / clip_fps files per frame; time_scale < 1 slows it."""
    return native_fps / clip_fps * time_scale


# --- smoke_sim (T113): the interactive domain ------------------------------------------------------------------

SMOKE_RES_DEFAULT = 96   # (eng) preview-tier resolution for smoke_sim; the manifest param caps at RES_CAP


def smoke_domain(profile, source, span=None, height_frac=1.6, path=None):
    """(lo, hi) of smoke_sim's domain, placed metres: centred on the subject in x/y, from the ground to
    height_frac x the subject's height above its top plus a margin, at most SMOKE_SIM_SPAN x longest wide.
    `path` (a list of placed points the subject passes, a moving subject) widens it along the path within the
    same cap. source 'ground' | 'marker' | 'tyres' only shifts nothing: the domain always holds the subject."""
    span = SMOKE_SIM_SPAN if span is None else min(span, SMOKE_SIM_SPAN)
    L = profile.longest
    c = profile.center
    half = 0.5 * span * L
    lo = [c[0] - half, c[1] - half, 0.0]
    hi = [c[0] + half, c[1] + half, 0.0]
    if path:
        xs, ys = [p[0] for p in path], [p[1] for p in path]
        lo[0], hi[0] = min(lo[0], min(xs) - 0.6 * L), max(hi[0], max(xs) + 0.6 * L)
        lo[1], hi[1] = min(lo[1], min(ys) - 0.6 * L), max(hi[1], max(ys) + 0.6 * L)
        for i in (0, 1):                                   # cap each side at span x longest, about the centre
            mid = (lo[i] + hi[i]) / 2
            w = min(hi[i] - lo[i], span * L)
            lo[i], hi[i] = mid - w / 2, mid + w / 2
    top = profile.boundsMax[2]
    hi[2] = max(top * (1 + height_frac), top + 0.5 * L)
    hi[2] = min(hi[2], span * L)
    return lo, hi


def smoke_cells(lo, hi, res):
    return cells(tuple(h - l for l, h in zip(lo, hi)), res)


def growth_smooth(sums, jump=3.0):
    """sim_stable for gas: the density sum per sampled frame grows or decays without a jump larger than `jump`
    x the median step (a blow-up or an emptied domain). Finite values only."""
    if any(not math.isfinite(s) for s in sums):
        return False
    steps = sorted(abs(b - a) for a, b in zip(sums, sums[1:]))
    if not steps:
        return True
    med = steps[len(steps) // 2] or max(steps) or 1.0
    return max(steps) <= jump * max(med, 1e-9) or max(steps) <= 0.05 * max(abs(s) for s in sums)
