"""debris_float's pure float (phase 6 Task 101; RB-07, METHODS M-KIN): pieces hang in a shell around the subject
and drift, bob and spin analytically, so there is no bake (bake.method "none") and any frame is a function of
time alone.

- drift: a constant velocity of DRIFT_FRAC (1-5%) of the subject's longest side per second (RB-07);
- spin: SPIN_DEG_S (5-20 deg/s) about a seeded axis, from a seeded start rotation;
- bob: BOB_FRAC x longest vertically at BOB_HZ, each piece on its own phase;
- the shell: SHELL x the subject's bounding radius around its centre, ELEV_DEG in elevation.
layout() rejects any piece whose path (SAMPLES samples over the clip) meets the subject's bounds x 1.1 inflated by
the piece's half size, the floor, or another piece, so path_through_subject(layout(...)) is 0 by construction;
layout checks a denser superset of those samples. The same function is the gate a checker rule reuses for sims (registry patch)."""
import math
import random

DRIFT_FRAC = (0.01, 0.05)
SPIN_DEG_S = (5.0, 20.0)
BOB_FRAC = 0.01           # (eng)
BOB_HZ = (0.15, 0.35)     # (eng)
SHELL = (1.25, 1.9)       # (eng) x profile.radius
ELEV_DEG = (-20.0, 50.0)  # (eng)
SIZE_JITTER = (0.7, 1.3)  # (eng)
MARGIN = 0.10             # = engine.weather_rules.SPAWN_MARGIN
SAMPLES = 12
TRIES = 4000
PIECES = ("pebbles", "gems", "shards", "leaves_dry")


def _unit(rng):
    z = rng.uniform(-1, 1)
    a = rng.uniform(0, 2 * math.pi)
    r = math.sqrt(1 - z * z)
    return [r * math.cos(a), r * math.sin(a), z]


def _quat(rng):
    u1, u2, u3 = rng.random(), rng.random(), rng.random()
    a, b = math.sqrt(1 - u1), math.sqrt(u1)
    return [b * math.cos(2 * math.pi * u3), a * math.sin(2 * math.pi * u2), a * math.cos(2 * math.pi * u2),
            b * math.sin(2 * math.pi * u3)]


def position(piece, t):
    o, v = piece["origin"], piece["velocity"]
    bob = piece["bob"] * math.sin(2 * math.pi * piece["bobHz"] * t + piece["phase"])
    return (o[0] + v[0] * t, o[1] + v[1] * t, o[2] + v[2] * t + bob)


def _qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw]


def rotation(piece, t):
    """(w, x, y, z): the start rotation turned by spinDegS x t about the piece's axis."""
    ang = math.radians(piece["spinDegS"] * t)
    s = math.sin(ang / 2)
    ax = piece["axis"]
    return _qmul([math.cos(ang / 2), ax[0] * s, ax[1] * s, ax[2] * s], piece["q0"])


def _in_subject(p, profile, pad):
    c, h = profile.center, profile.half
    return all(abs(p[i] - c[i]) <= h[i] * (1 + MARGIN) + pad for i in range(3))


def _times(duration_s, n=SAMPLES):
    return [duration_s * k / (n - 1) for k in range(n)]


def path_through_subject(layout, profile, duration_s):
    """How many pieces' paths meet the subject's bounds x 1.1 (inflated by the piece's half size) at any of
    SAMPLES times over the clip."""
    ts = _times(duration_s)
    return sum(1 for x in layout if any(_in_subject(position(x, t), profile, x["size"] / 2) for t in ts))


def layout(params, profile, seed, duration_s):
    rng = random.Random(seed)
    L, R0 = profile.longest, profile.radius
    ts = _times(duration_s, 4 * SAMPLES - 3)        # a superset of the gate's 12 samples, dense enough for pairs
    out, paths = [], []
    for _ in range(int(params["count"])):
        for _ in range(TRIES):
            size = params["sizeFrac"] * L * rng.uniform(*SIZE_JITTER)
            r = R0 * rng.uniform(*SHELL)
            el = math.radians(rng.uniform(*ELEV_DEG))
            az = rng.uniform(0, 2 * math.pi)
            c = profile.center
            origin = [c[0] + r * math.cos(el) * math.cos(az), c[1] + r * math.cos(el) * math.sin(az),
                      c[2] + r * math.sin(el)]
            d = _unit(rng)
            speed = L * rng.uniform(*DRIFT_FRAC)
            x = {"origin": origin, "velocity": [v * speed for v in d], "size": size,
                 "spinDegS": rng.uniform(*SPIN_DEG_S) * rng.choice((-1, 1)), "axis": _unit(rng), "q0": _quat(rng),
                 "phase": rng.uniform(0, 2 * math.pi), "bob": BOB_FRAC * L, "bobHz": rng.uniform(*BOB_HZ)}
            path = [position(x, t) for t in ts]
            if any(p[2] - size / 2 < 0 or _in_subject(p, profile, size / 2) for p in path):
                continue
            if any(math.dist(p, q) < (size + y["size"]) / 2 for y, other in zip(out, paths) for p, q in zip(path, other)):
                continue
            out.append(x)
            paths.append(path)
            break
        else:
            raise RuntimeError("debris_float: could not place every piece clear of the subject and each other")
    return out
