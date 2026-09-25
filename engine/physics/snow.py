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
