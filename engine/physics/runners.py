"""Pure maths for `runners` (phase 6 Task 104, FL-04; engine/blender/runners.py builds the GN step).

A runner is a real-size water drop (1.5-4 mm) on the subject's side below the fill line. Every drop is decided
here, seeded, before Blender simulates anything (engine/physics/gn_sim): where it sits, when it appears, how fast
it runs and its stick-slip schedule (a drop pins on the surface, then lets go: pauses of 0.1-1 s between runs).
Each GN substep then moves it along the tangential gravity g - (g.n)n at its speed x the slope (a vertical wall
runs at full speed, a level top not at all), re-projects it onto the render mesh, and lets it DETACH where the
surface turns away (a convex edge: the surface normal turns by more than acos(EDGE_DOT) in one step) or faces
down (n.z < DETACH_NZ): it becomes a ballistic drip (FL-20) until the ground, where it is gone. Behind a moving
drop a wet streak is left once per frame (the trail points).

Numbers marked (eng) are engineering guesses (calibration register, Task 123)."""
import bisect
import math

from engine.physics import gn_sim

G = 9.81
SKIN_M = 0.0005                 # = engine/blender/gn_sim.SKIN_M: a drop's centre sits this far off the surface
SPEED_CMS = (1.0, 10.0)         # METHODS FL-04: 1-10 cm/s (eng)
SPEED_SPREAD = (0.6, 1.4)       # each drop's speed = the param x U(0.6, 1.4), clamped to SPEED_CMS (eng)
PAUSE_S = (0.1, 1.0)            # METHODS FL-04: stick-slip pauses 0.1-1 s
MOVE_S = (0.3, 1.5)             # (eng) the run between two pauses
SIZE_JITTER = 0.3               # each drop's diameter = dropMm x U(0.7, 1.3) (eng)
SIDE_NZ = 0.5                   # a side face: |n.z| < 0.5 (shape.UP_DOT is 0.7 for up-facing)
SEED_LO = 0.25                  # seeds sit between 0.25 x the height and the fill line, so a drop has room to run
STAGGER = 0.6                   # births spread over the first 60% of the window (eng)
EDGE_DOT = 0.6                  # the normal turns by > 53 degrees in one step: a convex edge -> detach
DETACH_NZ = -0.5                # an underside -> detach
SUBSTEPS = 4
TRAIL_FRAC = 0.35               # a trail streak's width = 0.35 x the drop's diameter (eng)
MOVE_SHARE_MAX = MOVE_S[1] / (PAUSE_S[0] + MOVE_S[1])
BYTES_PER_POINT = 72            # raw attribute bytes per point per frame (12 x 3 vectors + 9 floats), an upper bound
EXTRAS = ("speed", "pause", "move", "phase", "trail", "free", "n")


def _unit(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)


def run_velocity(n, speed, g=G):
    """The run velocity on a surface of unit normal n: the tangential gravity's direction x speed x the slope
    (|g_t| / g = sin of the surface's tilt from level). Level: (0, 0, 0)."""
    gt = gn_sim.tangential_gravity(n, g)
    m = math.sqrt(sum(c * c for c in gt))
    if m < 1e-9 * g:
        return (0.0, 0.0, 0.0)
    k = speed / g                                  # direction (gt / m) x speed x slope (m / g)
    return tuple(c * k for c in gt)


def moving(age, phase, pause, move):
    """Stick-slip: each cycle is `pause` seconds pinned, then `move` seconds running; phase shifts it."""
    return math.fmod(age + phase, pause + move) >= pause


def detaches(n0, n1):
    """A runner lets go where the surface turns away (a convex edge) or faces down."""
    return sum(a * b for a, b in zip(n0, n1)) < EDGE_DOT or n1[2] < DETACH_NZ


def seed_band(fill_z, z_min, height, size):
    """(lo, hi): the heights a runner may start at."""
    return z_min + SEED_LO * height, fill_z - size


def _cross(u, v):
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def seed_runners(verts, tris, normals, *, count, fill_z, z_min, height, first, last, fps, speed_cms, drop_mm, rng,
                 tries=200):
    """The runners as gn_sim particles: count (clamped to 3..30) drops on side triangles (|n.z| < SIDE_NZ) at
    heights in seed_band, area-weighted and seeded; [] when the subject has no side there. verts: [(x, y, z)]
    world metres; tris: [(i, j, k)]; normals: one outward unit normal per triangle."""
    count = max(3, min(30, int(count)))
    size0 = drop_mm / 1000.0
    lo, hi = seed_band(fill_z, z_min, height, size0)
    cand, cum, acc = [], [], 0.0
    for t, n in zip(tris, normals):
        if abs(n[2]) >= SIDE_NZ:
            continue
        a, b, c = (verts[i] for i in t)
        if min(a[2], b[2], c[2]) > hi or max(a[2], b[2], c[2]) < lo:
            continue
        ar = 0.5 * math.sqrt(sum(x * x for x in _cross([q - p for p, q in zip(a, b)], [r - p for p, r in zip(a, c)])))
        if ar <= 0:
            continue
        acc += ar
        cand.append((a, b, c, _unit(n)))
        cum.append(acc)
    if not cand or hi <= lo:
        return []
    out, n_frames = [], last - first + 1
    for _ in range(count):
        for _ in range(tries):
            a, b, c, n = cand[min(len(cand) - 1, bisect.bisect_left(cum, rng.random() * acc))]
            s, r2 = math.sqrt(rng.random()), rng.random()
            w = (1 - s, s * (1 - r2), s * r2)
            p = tuple(w[0] * x + w[1] * y + w[2] * z for x, y, z in zip(a, b, c))
            if lo <= p[2] <= hi:
                break
        else:
            continue
        birth = first + STAGGER * n_frames * rng.random()
        speed = min(SPEED_CMS[1], max(SPEED_CMS[0], speed_cms * (SPEED_SPREAD[0] + (SPEED_SPREAD[1] - SPEED_SPREAD[0]) * rng.random()))) / 100.0
        pause = PAUSE_S[0] + (PAUSE_S[1] - PAUSE_S[0]) * rng.random()
        move = MOVE_S[0] + (MOVE_S[1] - MOVE_S[0]) * rng.random()
        phase = (pause + move) * rng.random()
        size = size0 * (1.0 + SIZE_JITTER * (2.0 * rng.random() - 1.0))
        out.append({"birth": birth, "pos": tuple(x + SKIN_M * k for x, k in zip(p, n)), "vel": (0.0, 0.0, 0.0),
                    "size": size, "life": (last - birth) / fps + 1.0, "speed": speed, "pause": pause,
                    "move": move, "phase": phase, "trail": 0.0, "free": 0.0, "n": n})
    return out


def trail_points(count, frames):
    """The most trail points a bake can hold: one per moving drop per frame."""
    return int(count * frames * MOVE_SHARE_MAX)


def estimate_s(count, frames):
    """Bake seconds for `count` runners over `frames`, from gn_sim's measured rate (every trail point counted
    alive for the whole window, so an upper bound)."""
    return gn_sim.estimate_s(count + trail_points(count, frames), frames, SUBSTEPS)


def cache_mb_max(count, frames):
    """The cache's upper bound in MB: every point alive every frame at BYTES_PER_POINT."""
    return (count + trail_points(count, frames)) * frames * BYTES_PER_POINT / 1e6
