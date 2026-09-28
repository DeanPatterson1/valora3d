"""rigid_scatter's pure layout (phase 6 Task 100; METHODS RB-05, R4/R5): real piece sizes, the pile cap, the
spawn points, and the small helpers the bake uses to write rigid_keys rows.

- Piece sizes are REAL (a coffee bean is 11 mm on a watch and on a car): scale cues never scale with the subject.
- The pile covers at most PILE_COVER of its zone's area (count_for), so a small subject gets a small handful.
- spawn() places the pieces in 3D by seeded dart throwing (a Poisson-disc set: no two bounding spheres overlap,
  jitter included) in a column over the zone, starting SPAWN_MARGIN above the subject's top plus `drop` x its
  height. Every zone therefore starts outside bounds x 1.1 (the checker's sim_spawn_in_subject margin), and
  `around` / `behind` pieces fall onto the ground annulus / wedge instead of the subject.
  - onto: a disc of RADIUS_FRAC x longest over the subject's centre (its top and the ground next to it);
  - around: engine.physics.sim_facts.pile_zone (1.05-1.6 x the footprint radius);
  - behind: the same annulus, cut to a +-BEHIND_HALF_DEG wedge on the side away from the hero camera.
Every number marked (eng) is in the plan's calibration register (G1 owner grade; KE decay)."""
import math
import random

from engine.physics.sim_facts import pile_zone

PIECES = ("beans", "coffee_beans", "ice", "gems", "coins", "pills", "candies", "pebbles")
PIECE_SIZE_M = {"beans": 0.015, "coffee_beans": 0.011, "ice": 0.025, "gems": 0.012, "coins": 0.024,
                "pills": 0.012, "candies": 0.018, "pebbles": 0.02}
ZONES = ("onto", "around", "behind")
RADIUS_FRAC = 0.6          # the onto disc, x longest (= the manifest's spawnZone.radiusFrac)
PILE_COVER = 0.6           # (eng) the pile covers <= 60% of its zone's area
BEHIND_HALF_DEG = 35.0     # (eng) the behind wedge's half angle
SPAWN_MARGIN = 0.10        # = engine.weather_rules.SPAWN_MARGIN
JITTER = (0.85, 1.15)      # seeded per-piece size jitter
# Bake cost (measured 2026-09-28, coffee beans on the sneaker, 60 substeps / 20 iterations, collide-LOD hulls, other
# lanes baking on the same box): 150 x 124 frames 57.5 s, 300 x 124 155.9 s, 500 x 124 581.1 s (a deep pile's
# contacts grow much faster than the count; 500 x 240 ran > 28 min before the collide LOD and was killed).
# bake_s ~ max over COST of a x n^p x frames (two power laws through the three points). count_for caps n so the
# estimate stays under BAKE_CAP_S x COST_SAFETY (the budget table's 5 min for rigid_scatter; the fit runs ~25% low
# on a busy box).
COST = ((3.41e-4, 1.44), (5.41e-07, 2.576))
BAKE_CAP_S, COST_SAFETY = 300.0, 0.65   # 0.8 let a capped 500 x 240 ask (255 pieces) bake 298.3 s
PACK = 0.25                # (eng) target spawn density x d^3: well under dart throwing's ~0.7 saturation
TRIES = 60


def piece_size_m(pieces):
    return PIECE_SIZE_M[pieces]


def min_spacing(pieces):
    """The closest two spawn points may be: two jittered bounding spheres just touching, plus 5%."""
    return piece_size_m(pieces) * JITTER[1] * 1.05


def zone_area(profile, zone):
    if zone == "onto":
        r = RADIUS_FRAC * profile.longest
        return math.pi * r * r
    z = pile_zone(profile)
    ring = math.pi * (z["outerM"] ** 2 - z["innerM"] ** 2)
    return ring if zone == "around" else ring * BEHIND_HALF_DEG / 180.0


def estimate_s(n, frames):
    return max(a * n ** p for a, p in COST) * frames


def cost_cap(frames):
    """The most pieces whose bake over `frames` frames stays under BAKE_CAP_S x COST_SAFETY."""
    return min(int((BAKE_CAP_S * COST_SAFETY / (a * frames)) ** (1.0 / p)) for a, p in COST)


def count_for(params, profile, frames=None):
    """The asked count, capped so the settled pile covers <= PILE_COVER of the zone (one layer of size^2 each) and,
    given the bake's frame count, so the bake stays inside its time cap (cost_cap)."""
    s = piece_size_m(params["pieces"])
    cap = math.floor(PILE_COVER * zone_area(profile, params["zone"]) / (s * s))
    if frames:
        cap = min(cap, cost_cap(frames))
    return max(1, min(int(params["count"]), cap))


def _unit(v):
    n = math.hypot(v[0], v[1])
    return (0.0, 1.0) if n < 1e-9 else (v[0] / n, v[1] / n)


def _xy_sampler(profile, zone, behind, rng):
    c = profile.center
    if zone == "onto":
        r = RADIUS_FRAC * profile.longest

        def draw():
            rr, a = r * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
            return c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)
        return draw
    z = pile_zone(profile)
    lo, hi = z["innerM"], z["outerM"]
    bx, by = _unit(behind)
    base = math.atan2(bx, by)                          # angle from +Y, the same convention as the tests
    half = math.radians(BEHIND_HALF_DEG)

    def draw():
        rr = math.sqrt(rng.uniform(lo * lo, hi * hi))
        a = rng.uniform(0, 2 * math.pi) if zone == "around" else base + rng.uniform(-half, half)
        return c[0] + rr * math.sin(a), c[1] + rr * math.cos(a)
    return draw


def spawn(params, profile, seed, behind=(0.0, 1.0), frames=None):
    """count_for(params, profile, frames) non-overlapping spawn points [(x, y, z)], seeded. `behind` is the XY
    direction from the subject away from the hero camera (zone behind)."""
    n = count_for(params, profile, frames)
    d = min_spacing(params["pieces"])
    h = profile.sizeM[2]
    z0 = profile.boundsMax[2] * (1 + SPAWN_MARGIN) + params["drop"] * h
    height = max(0.5 * params["drop"] * h, n * d ** 3 / (PACK * zone_area(profile, params["zone"])))
    rng = random.Random(seed)
    for _ in range(8):                                 # grow the column until every piece fits
        draw = _xy_sampler(profile, params["zone"], behind, rng)
        pts, grid = [], {}
        for _ in range(TRIES * n):
            x, y = draw()
            p = (x, y, rng.uniform(z0, z0 + height))
            cell = tuple(int(math.floor(v / d)) for v in p)
            near = (q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                    for q in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()))
            if any(math.dist(p, q) < d for q in near):
                continue
            pts.append(p)
            grid.setdefault(cell, []).append(p)
            if len(pts) == n:
                return pts
        height *= 1.5
    raise RuntimeError(f"spawn: could not place {n} pieces")


def size_jitter(seed, n):
    rng = random.Random(seed * 31 + 7)
    return [round(rng.uniform(*JITTER), 5) for _ in range(n)]


def random_quat(rng):
    """A uniform random rotation (w, x, y, z) (Shoemake)."""
    u1, u2, u3 = rng.random(), rng.random(), rng.random()
    a, b = math.sqrt(1 - u1), math.sqrt(u1)
    return (b * math.cos(2 * math.pi * u3), a * math.sin(2 * math.pi * u2), a * math.cos(2 * math.pi * u2),
            b * math.sin(2 * math.pi * u3))


def row(loc, quat):
    """One rigid_keys row: x, y, z, qw, qx, qy, qz rounded to 1e-5 (formats.FORMATS['rigid_keys'])."""
    return [round(float(v), 5) + 0.0 for v in (*loc, *quat)]


def continuous_quats(rows):
    """Flip each quaternion onto the same hemisphere as the previous one: LINEAR keys interpolate components, so
    q and -q (the same rotation) between two keys would spin the piece through a wrong path."""
    out, prev = [], None
    for r in rows:
        q = r[3:7]
        if prev is not None and sum(a * b for a, b in zip(prev, q)) < 0:
            q = [(-v) + 0.0 for v in q]
        out.append(list(r[:3]) + list(q))
        prev = q
    return out
