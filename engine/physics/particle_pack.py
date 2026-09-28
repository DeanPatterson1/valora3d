"""Pure maths for the phase-6 particle pack (Task 105): sparks (PT-08), confetti (PT-06), bubbles (PT-10) as GN
point sims (engine/blender/particle_pack.py, on the shared base engine/blender/gn_sim.py), and embers (PT-09) as a
stateless effect (analytic drift + flicker, no bake). Every particle is a seeded dict for gn_sim.emitter_object:
{birth, pos, vel, size, life, ...extras}. Real sizes (METHODS R4/R5): sparks 0.3-0.8 mm, confetti 1-3 cm cards,
bubbles 0.3-4 mm. Every number is (eng) until the G5 grade (the plan's calibration register)."""
import math

from engine.physics.gn_sim import burst_frames, cone_velocity, spawn_frames

# ---------------------------------------------------------------------------------------------- sparks
SPARK_TEMP_K = (1700.0, 2300.0)     # hot steel from a grinder / a scraping chassis (eng)
SPARK_SIZE_M = (0.0003, 0.0008)     # glowing particle diameter
DARK_K = 800.0                      # below this a spark reads as dark (Draper point ~ 798 K)
SPARK_COOL = 1.8                    # temp(age) = T0 x exp(-COOL x age / life): 2000 K -> ~ 330 K (dark) at the end of life
SPARK_DRAG = 1.2                    # 1/s: a 0.5 mm steel bead slows, it does not float
SPARK_BOUNCE = (0.35, 0.25)         # restitution, friction on the ground and the shell


def sparks(params, emitter, first, last, fps, rng):
    """A steady stream from emitter {"point", "normal"} over render frames [first, last]."""
    births = spawn_frames(params["rate"], first, last, fps, rng)
    out = []
    for b in births:
        v = cone_velocity(rng, emitter["normal"], 0.5 * params["speedMs"], 1.5 * params["speedMs"],
                          params["spreadDeg"])
        jit = [0.004 * (rng.random() - 0.5) for _ in range(3)]
        out.append({"birth": b, "pos": tuple(p + j for p, j in zip(emitter["point"], jit)), "vel": v,
                    "size": SPARK_SIZE_M[0] + (SPARK_SIZE_M[1] - SPARK_SIZE_M[0]) * rng.random(),
                    "life": params["lifeS"] * (0.5 + rng.random()),
                    "temp": SPARK_TEMP_K[0] + (SPARK_TEMP_K[1] - SPARK_TEMP_K[0]) * rng.random()})
    return out


def spark_temp(t0, age, life):
    """Blackbody temperature (K) at `age` of a spark born at t0 living `life` seconds (the shader's formula)."""
    return t0 * math.exp(-SPARK_COOL * age / max(life, 1e-6))


# ---------------------------------------------------------------------------------------------- confetti
CONFETTI_SIZE_M = (0.01, 0.03)       # 1-3 cm cards
CONFETTI_DRAG = 15.0                 # 1/s: paper settles at ~ 0.65 m/s (g / k; real confetti 0.3-1 m/s), flutter on top
CONFETTI_BURST_S = 0.8                # a released shower, not a single puff (clip 1 of G5: 0.25 s read as a dump)
CONFETTI_METAL_SHARE = 0.4
PALETTES = {
    "mixed": [(0.85, 0.12, 0.2), (0.1, 0.45, 0.85), (0.95, 0.75, 0.1), (0.15, 0.7, 0.35), (0.95, 0.95, 0.95),
              (0.8, 0.3, 0.75)],
    "gold": [(1.0, 0.77, 0.34), (0.95, 0.85, 0.55), (0.9, 0.65, 0.25)],
    "silver": [(0.92, 0.92, 0.95), (0.8, 0.82, 0.86), (0.97, 0.97, 0.97)],
}


def confetti(params, centre_xy, height, frame, fps, rng, grade_colours=None):
    """One burst: count cards from a disc of radius spreadM at `height`, a small outward/upward kick, colours from
    the palette ("grade": the grade's colours when given, else mixed), ~40% metallic foil."""
    n = int(params["count"])
    births = burst_frames(n, frame, CONFETTI_BURST_S * fps, rng)
    pal = PALETTES.get(params["palette"]) or (grade_colours or PALETTES["mixed"])
    out = []
    for b in births:
        a, r = 2 * math.pi * rng.random(), params["spreadM"] * math.sqrt(rng.random())
        dx, dy = math.cos(a), math.sin(a)
        kick = 0.1 + 0.4 * rng.random()
        out.append({"birth": b, "pos": (centre_xy[0] + r * dx, centre_xy[1] + r * dy, height + 0.1 * (rng.random() - 0.5)),
                    "vel": (kick * dx, kick * dy, 0.5 * rng.random()),
                    "size": CONFETTI_SIZE_M[0] + (CONFETTI_SIZE_M[1] - CONFETTI_SIZE_M[0]) * rng.random(),
                    "life": 60.0,
                    "colour": pal[int(rng.random() * len(pal)) % len(pal)],
                    "metal": 1.0 if rng.random() < CONFETTI_METAL_SHARE else 0.0,
                    "phase": 2 * math.pi * rng.random(), "spin": 4.0 + 10.0 * rng.random()})
    return out


# ---------------------------------------------------------------------------------------------- bubbles
BUBBLE_RISE_MS = ((0.0005, 0.08), (0.002, 0.33))   # (radius m, rise m/s): 8-33 cm/s by size (PT-10)
BUBBLE_ZIGZAG_R = 0.001                             # below 2 mm diameter a bubble zig-zags
BUBBLE_WALL_FRAC = 0.7                              # born inside 70% of the container's inner radius
BUBBLE_GROW = 0.15                                  # radius grows 15% over the rise (lower pressure, CO2 uptake)


def bubble_rise(radius):
    (r0, v0), (r1, v1) = BUBBLE_RISE_MS
    f = min(1.0, max(0.0, (radius - r0) / (r1 - r0)))
    return v0 + f * (v1 - v0)


def bubbles(params, container, z_floor, z_top, first, last, fps, rng):
    """A steady stream of bubbles nucleating on the container floor (z_floor) inside BUBBLE_WALL_FRAC of its
    radius, each living exactly until it reaches z_top at its rise speed. sizeMm is the mean diameter."""
    births = spawn_frames(params["rate"], first, last, fps, rng)
    cx, cy = container["opening"][0], container["opening"][1]
    rmax = container["radiusM"] * BUBBLE_WALL_FRAC
    out = []
    for b in births:
        a, r = 2 * math.pi * rng.random(), rmax * math.sqrt(rng.random())
        d = params["sizeMm"] * 1e-3 * (0.5 + rng.random())
        rise = bubble_rise(d / 2)
        out.append({"birth": b, "pos": (cx + r * math.cos(a), cy + r * math.sin(a), z_floor), "vel": (0.0, 0.0, rise),
                    "size": d, "life": (z_top - z_floor) / rise, "phase": 2 * math.pi * rng.random(),
                    "zig": 1.0 if d / 2 < BUBBLE_ZIGZAG_R else 0.0})
    return out


# ---------------------------------------------------------------------------------------------- embers
EMBER_SIZE_M = (0.0006, 0.002)
EMBER_LIFE_S = (2.0, 5.0)
EMBER_FLICKER_HZ = (5.0, 12.0)


def _hash01(*xs):
    """A deterministic value in [0, 1) from numbers (no random state: embers are stateless)."""
    h = 0
    for x in xs:
        h = (h * 1000003) ^ int(x * 1e6) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    h ^= h >> 15
    return (h & 0xFFFFFF) / float(0x1000000)


def ember_state(i, t, seed, base, spread, rise):
    """Ember i at time t: (position, flicker 0..1, age fraction). Each ember respawns every life seconds at a
    seeded point in the base disc, rises at `rise` m/s with a curl-like sideways sway, and flickers at 5-12 Hz.
    The Blender effect evaluates the same formula as nodes (a function of time alone, METHODS R1)."""
    life = EMBER_LIFE_S[0] + (EMBER_LIFE_S[1] - EMBER_LIFE_S[0]) * _hash01(seed, i, 1)
    off = life * _hash01(seed, i, 2)
    cyc = math.floor((t + off) / life)
    age = (t + off) - cyc * life
    a = 2 * math.pi * _hash01(seed, i, cyc, 3)
    r = spread * math.sqrt(_hash01(seed, i, cyc, 4))
    w = 1.3 + _hash01(seed, i, 5)
    sway = 0.15 * spread
    x = base[0] + r * math.cos(a) + sway * math.sin(w * age + a)
    y = base[1] + r * math.sin(a) + sway * math.cos(0.7 * w * age + a)
    z = base[2] + rise * age
    hz = EMBER_FLICKER_HZ[0] + (EMBER_FLICKER_HZ[1] - EMBER_FLICKER_HZ[0]) * _hash01(seed, i, 6)
    flick = 0.5 + 0.5 * math.sin(2 * math.pi * hz * t + a)
    return (x, y, z), flick, age / life


def _unit(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)
