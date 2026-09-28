"""Pure maths for the shared Geometry Nodes point sim (phase 6 Task 103; engine/blender/gn_sim.py builds it).

Every particle is decided HERE, on the host side of the maths, before Blender simulates anything: its birth
frame, birth position, birth velocity, size and life come from a seeded random.Random, so a GN sim is fully
determined by (seed, params) and the bake key (METHODS R3). The Blender zone only integrates: it adds the
particles born in each frame, applies gravity / drag / wind, collides with the proxy shell and the ground,
ages them and deletes the dead.

A particle is a dict {"birth": frame (float), "pos": (x, y, z), "vel": (vx, vy, vz), "size": metres,
"life": seconds, ...extras}. Extras are float or 3-vector attributes the block wants on every point
(temperature, colour, a flutter phase); the Blender side stores each one as a point attribute.

GN bakes are ABSOLUTE (engine/bake/window.py): birth frames are render-scene frame numbers, and pre-roll births
may be zero or negative."""
import math

G = 9.81

# Measured: bake seconds per 10k points per 100 frames PER SUBSTEP, from test_gn_sim_blender (5k points onto a
# 64-segment proxy sphere, 60 frames, 2 substeps: 2.25 s, i.e. 7.5 s per 10k/100f -> 3.75 per substep; Blender
# 5.0.1, 2026-09-28, var/probe/gn_sim.json). Its cache was 8.2 MB = 27 bytes per point per frame, so cache_mb's
# 12 x (1 + attrs) bytes is an upper bound. estimate_s scales it; the manifests' estimateS come from it.
BAKE_S_PER_10K_100F = 3.75
MAX_POINTS = 100_000          # the phase-6 GN cap (budget table: GN point sims <= 100k points)
BAKE_OVERHEAD_S = 8.0         # Blender start, subject import, proxy load (measured on the _test_drop bake)


def spawn_frames(rate_per_s, first, last, fps, rng, cap=MAX_POINTS):
    """Birth frames for a steady rate over [first, last] (inclusive, render frames): an exact count of
    round(rate x duration) births, each at a seeded sub-frame time, sorted. Never more than cap."""
    if rate_per_s <= 0 or last < first:
        return []
    dur_f = last - first + 1
    n = min(int(round(rate_per_s * dur_f / fps)), int(cap))
    return sorted(first - 1 + rng.random() * dur_f for _ in range(n))


def burst_frames(count, frame, spread_f, rng, cap=MAX_POINTS):
    """count births spread uniformly over [frame, frame + spread_f) (a burst; spread 0 = all at once)."""
    n = min(int(count), int(cap))
    return sorted(frame + rng.random() * max(0.0, spread_f) for _ in range(n))


def alive_peak(births, lives_s, fps):
    """The most particles alive at once (for the cache estimate): a sweep over birth / death events."""
    ev = []
    for b, life in zip(births, lives_s):
        ev.append((b, 1))
        ev.append((b + life * fps, -1))
    ev.sort()
    cur = best = 0
    for _, d in ev:
        cur += d
        best = max(best, cur)
    return best


def estimate_s(points, frames, substeps=1):
    """Bake seconds for `points` alive over `frames` frames at `substeps`, from the measured rate."""
    return BAKE_OVERHEAD_S + BAKE_S_PER_10K_100F * (points / 1e4) * (frames / 100.0) * max(1, substeps)


def cache_mb(points, frames, attrs=4):
    """Disk MB of a GN point cache: position + `attrs` more float3/float attributes (<= 4 x 12 bytes each),
    per point per frame, uncompressed (the GN bake blobs are raw arrays)."""
    return points * frames * 12 * (1 + attrs) / 1e6


def cone_velocity(rng, axis, speed_lo, speed_hi, half_angle_deg):
    """A seeded velocity inside a cone around the unit-ish axis, speed uniform in [lo, hi]."""
    ax = _unit(axis)
    ca = math.cos(math.radians(half_angle_deg))
    cz = ca + (1.0 - ca) * rng.random()                  # uniform over the cap's solid angle
    sz = math.sqrt(max(0.0, 1.0 - cz * cz))
    phi = 2 * math.pi * rng.random()
    u, v = _basis(ax)
    d = tuple(cz * a + sz * (math.cos(phi) * b + math.sin(phi) * c) for a, b, c in zip(ax, u, v))
    s = speed_lo + (speed_hi - speed_lo) * rng.random()
    return tuple(s * x for x in d)


def triangle_samples(verts, tris, n, rng):
    """n seeded points on a triangle mesh, area-weighted: [(point, triangle index)]. verts: [(x, y, z)],
    tris: [(i, j, k)]. The per-triangle normal is the caller's (it knows the winding)."""
    if n <= 0 or not tris:
        return []
    areas, acc = [], 0.0
    for a, b, c in tris:
        acc += _area(verts[a], verts[b], verts[c])
        areas.append(acc)
    if acc <= 0:
        return []
    out = []
    for _ in range(int(n)):
        x = rng.random() * acc
        lo, hi = 0, len(areas) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if areas[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        a, b, c = (verts[i] for i in tris[lo])
        r1, r2 = rng.random(), rng.random()
        s = math.sqrt(r1)
        w = (1 - s, s * (1 - r2), s * r2)
        out.append((tuple(w[0] * p + w[1] * q + w[2] * r for p, q, r in zip(a, b, c)), lo))
    return out


def tangential_gravity(n, g=G):
    """g - (g . n) n for gravity (0, 0, -g) and a unit normal n: the downhill pull along a surface."""
    gn = -g * n[2]
    return (-gn * n[0], -gn * n[1], -g - gn * n[2])


def _area(a, b, c):
    u = [q - p for p, q in zip(a, b)]
    v = [r - p for p, r in zip(a, c)]
    x = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return 0.5 * math.sqrt(sum(t * t for t in x))


def _unit(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)


def _basis(ax):
    t = (1.0, 0.0, 0.0) if abs(ax[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _unit((ax[1] * t[2] - ax[2] * t[1], ax[2] * t[0] - ax[0] * t[2], ax[0] * t[1] - ax[1] * t[0]))
    v = (ax[1] * u[2] - ax[2] * u[1], ax[2] * u[0] - ax[0] * u[2], ax[0] * u[1] - ax[1] * u[0])
    return u, v
