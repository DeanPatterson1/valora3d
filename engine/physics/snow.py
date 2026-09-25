"""Snow (plan Task 67; METHODS PT-04). Pure; stdlib only.

A flake falls at a seeded speed in SPEED_MS (0.5-1.5 m/s) with a lateral wobble
(A sin(2 pi f t + p), A cos(2 pi f' t + p')), A in WOBBLE_A_M, f in WOBBLE_HZ, and drifts with the air
(windCalibration perMs 0.9: snow follows the wind). Stateless: position(t) = base + drift(t), wrapped in the
camera-following box (engine/blender/weather_nodes). Accumulation thickness is accumulationMm at t = 0 and grows
by rate x t x GROW_MM_S (small, so it stays a function of time), only where n.up > UP_DOT."""
import math
import random

SPEED_MS = (0.5, 1.5)        # PT-04
WOBBLE_A_M = (0.02, 0.06)    # (eng)
WOBBLE_HZ = (0.3, 0.8)       # (eng)
PER_MS = 0.9                 # drift m/s per wind m/s (the manifest's windCalibration)
FLAKES_PER_RATE_M3 = 400.0   # (eng) visible flakes per m3 at rate 1
MAX_FLAKES = 60000           # (eng) instance cap, by cost
GROW_MM_S = 0.05             # (eng) accumulation growth per second at rate 1
UP_DOT = 0.7                 # = shape.UP_DOT

BLIZZARD_MS = 11.0           # (eng) above this wind, snow reads as noise (wind_implausible warning)


def flake_count(rate, box_m3):
    return min(MAX_FLAKES, int(FLAKES_PER_RATE_M3 * rate * box_m3))


def flake(seed, i):
    """The seeded constants of flake i: (speed, (A, f, f2, p, p2))."""
    r = random.Random(f"{seed}:{i}")
    return (r.uniform(*SPEED_MS), (r.uniform(*WOBBLE_A_M), r.uniform(*WOBBLE_HZ), r.uniform(*WOBBLE_HZ),
                                   r.uniform(0.0, 2 * math.pi), r.uniform(0.0, 2 * math.pi)))


def wobble(t, w):
    a, f, f2, p, p2 = w
    return (a * math.sin(2 * math.pi * f * t + p), a * math.cos(2 * math.pi * f2 * t + p2))


def drift(t, speed, w, wind_vec):
    """Displacement from the base point after t seconds (before the box wrap)."""
    wx, wy = wobble(t, w)
    return (PER_MS * wind_vec[0] * t + wx, PER_MS * wind_vec[1] * t + wy, -speed * t)


def accumulation_mm(acc0, rate, t):
    return acc0 + rate * t * GROW_MM_S


def accumulates(nz):
    return nz > UP_DOT


# --- realism pass (audit #19) -------------------------------------------------------------------------------
# Flakes: every flake a textured card of its own size (a few big, most small), turned and tumbling; CLUMP_SHARE
# of them aggregated clumps (several crystals stuck together, bigger). Cover: a smoothed shell whose depth
# rolls off to MIN_LIFT_MM where the surface turns past UP_DOT (the rounded edge: snow slides off a curve)
# and varies with a noise (drifted, lumpy), shaded with ~1 mm ice grain, glints and subsurface scattering.
SIZE_SPREAD = (0.6, 2.0)     # (eng) flake size as a share of flakeMm, skewed small
SIZE_SKEW = 1.8              # (eng) u ** SIZE_SKEW: most flakes small
CLUMP_SHARE = 0.25           # (eng) aggregated clumps among the flakes
CLUMP_SIZE = (1.6, 2.6)      # (eng) a clump's size as a multiple of a single flake's
TUMBLE_RAD_S = 2.5           # (eng) max tumble rate per axis (a flake turns over in ~1-2 s)
MIN_LIFT_MM = 0.3            # (eng) the shell's edge sits this far off the paint (no z-fight)
ROLL_NZ = (UP_DOT, 0.93)     # (eng) depth ramps from 0 to full across this normal-z band (a rounded edge)
DEPTH_VAR = 0.45             # (eng) +-45% depth variation from the drift noise
DEPTH_NOISE_M = (6.0, 22.0)  # (eng) drift / lump noise frequencies (1/m)
SSS_SCALE_M = 0.008          # (eng) snow's subsurface mean free path ~1 cm (less blurs the grain away)
SSS_WEIGHT = 0.85            # (eng)
SSS_RADIUS = (0.85, 1.0, 1.3)  # (eng) per-channel radius: blue scatters furthest
GRAIN_M = 0.0009             # (eng) ice grain size (bump + roughness variation)
GLINT_SHARE = 0.04           # (eng) grains that catch the light as specular glints


def is_clump(u):
    return u < CLUMP_SHARE


def flake_size_mm(u, flake_mm, clump, v=0.5):
    """One flake's card size (mm) from a uniform u (and v, the clump's own spread)."""
    lo, hi = SIZE_SPREAD
    s = flake_mm * (lo + (hi - lo) * u ** SIZE_SKEW)
    if clump:
        s *= CLUMP_SIZE[0] + (CLUMP_SIZE[1] - CLUMP_SIZE[0]) * v
    return s


def tumble_rate(u3):
    """Per-axis tumble rate (rad/s) from three uniforms."""
    return tuple((2.0 * u - 1.0) * TUMBLE_RAD_S for u in u3)


def tumble(angles0, rate, t):
    """Euler angles at time t: stateless, a function of time alone (METHODS R1)."""
    return tuple(a + w * t for a, w in zip(angles0, rate))


def _smoothstep(e0, e1, x):
    u = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return u * u * (3.0 - 2.0 * u)


def cover_depth_mm(acc_mm, nz, noise):
    """Shell depth (mm) at a point whose smooth surface normal has z = nz, with a 0..1 drift noise: the
    accumulation +-DEPTH_VAR, rolled off to MIN_LIFT_MM across ROLL_NZ (a rounded edge), never below it."""
    roll = _smoothstep(ROLL_NZ[0], ROLL_NZ[1], nz)
    d = acc_mm * (1.0 + DEPTH_VAR * (2.0 * noise - 1.0)) * roll
    return max(MIN_LIFT_MM, d)
DENDRITE_SHARE = 0.15        # (eng) flakes drawn as six-armed dendrites (the rest: soft irregular discs)
FLAKE_OPACITY = 0.92         # (eng) a flake's densest part lets a little light through
FLAKE_TRANSLUCENCY = 0.35    # (eng) share of a flake's light that is transmitted (back-lit glow)
DUST_NOISE_M = 22.0          # (eng) the dusting's patch noise (1/m): patches of a few cm
DUST_ROLL_GAIN = 1.5         # (eng) coverage level = roll x gain + (patch noise - .5) x noise gain
DUST_NOISE_GAIN = 1.1
DUST_EDGE = (0.35, 0.6)      # (eng) the level band over which bare paint turns to full snow


def cover_share(roll, noise, grain=0.5):
    """How much of the paint the shell covers (0 bare .. 1 full) at a roll-off `roll` (0 edge .. 1 deep), a 0..1
    patch noise and a 0..1 ice-grain value: full on the deep shell, a patchy grainy dusting as it thins, bare
    at its edge (the snow build's cover shader)."""
    level = roll * DUST_ROLL_GAIN + (noise - 0.5) * DUST_NOISE_GAIN + (grain - 0.5) * DUST_GRAIN_GAIN
    return _smoothstep(DUST_EDGE[0], DUST_EDGE[1], level)
DUST_GRAIN_GAIN = 0.35       # (eng) per-grain jitter of the coverage level: the edge breaks up grain by grain
LUMP_NOISE_M = 35.0          # (eng) the surface's soft lumps (1/m) in the bump
LUMP_BUMP_M = 0.004          # (eng) their height scale (m)
DEPTH_BLUR_ITER = 40          # (eng) neighbour-averaging passes over the shell depth (no cliffs at creases)
