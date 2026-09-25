"""golden_field plant variants and clumping, pure (art pass round 3, 2026-09-25).

The procedural blades were one 12 mm strip in one colour ramp: at a metre they read as a brown mass of soft
cards. Real meadow grass is a mix of plants: fine 2-4 mm blades, broader leaves, stalks bent over at a node,
seed heads on thin stems, dead brown blades, low weeds; and it grows in clumps 0.3-1.5 m across with gaps
between. VARIANTS lists them (share, width m, height x the blade's layout height, lean, colour class, shape);
variant() deals one from a blade's pick, clump() is a 0..1 clump density from three seeded sine lattices at
0.3-1.5 m wavelengths (kept blades: clump >= a threshold, so gaps open between clumps), and blade() builds a
blade as flat arrays: vertices, polygons, sway parameter u (0 root .. 1 tip) and colour class per polygon.

Colour classes (material slots): 0 green, 1 straw, 2 dark brown, 3 seed head. Numbers are (eng)."""
import math

GREEN, STRAW, BROWN, SEED = 0, 1, 2, 3
# name, share, width (m), height x layout h, lean range, colour, shape
VARIANTS = (           # height x layout h: the layout's height is a ceiling (its sight cuts must hold)
    ("fine_green", 0.24, (0.002, 0.003), (0.62, 0.82), (0.05, 0.30), GREEN, "blade"),
    ("fine_straw", 0.22, (0.002, 0.004), (0.62, 0.85), (0.05, 0.35), STRAW, "blade"),
    ("broad_leaf", 0.12, (0.004, 0.006), (0.45, 0.65), (0.15, 0.45), GREEN, "blade"),
    ("bent_stalk", 0.12, (0.002, 0.003), (0.75, 0.92), (0.45, 0.90), STRAW, "bent"),
    ("seed_head", 0.12, (0.0015, 0.0025), (0.88, 1.0), (0.05, 0.25), STRAW, "seed"),
    ("dead_brown", 0.12, (0.003, 0.005), (0.5, 0.75), (0.30, 0.75), BROWN, "bent"),
    ("low_weed", 0.06, (0.005, 0.006), (0.22, 0.32), (0.40, 0.80), GREEN, "rosette"),
)
SCALE_JITTER = (0.7, 1.3)
CLUMP_WAVES_M = (0.3, 0.7, 1.5)
CLUMP_KEEP = 0.38            # blades keep where clump() >= this: about 60% of the ground, the rest gaps
SEED_HEAD_M = (0.03, 0.06)   # spindle length
SEED_HEAD_W = 0.006          # spindle width at its fattest


def _frac(v):
    return v - math.floor(v)


def variant(pick):
    """Index into VARIANTS for a blade's pick in [0, 1)."""
    acc = 0.0
    total = sum(v[1] for v in VARIANTS)
    for i, v in enumerate(VARIANTS):
        acc += v[1] / total
        if pick < acc:
            return i
    return len(VARIANTS) - 1


def clump(x, y, seed):
    """Clump density in [0, 1] at (x, y): the mean of three products of sines, one per CLUMP_WAVES_M wavelength,
    each lattice rotated and shifted by the seed."""
    s = 0.0
    for i, lam in enumerate(CLUMP_WAVES_M):
        a = _frac(math.sin((seed + 1) * 12.9898 + i * 78.233) * 43758.5453) * math.pi
        px, py = _frac(seed * 0.618 + i * 0.37) * lam, _frac(seed * 0.414 + i * 0.73) * lam
        u = (x * math.cos(a) + y * math.sin(a) + px) * math.tau / lam
        v = (-x * math.sin(a) + y * math.cos(a) + py) * math.tau / lam
        s += 0.5 + 0.5 * math.sin(u) * math.sin(v)
    return s / len(CLUMP_WAVES_M)


def _r(pick, k):
    """A second, third ... uniform from one pick (stable, no rng)."""
    return _frac(math.sin(pick * 91.7 + k * 17.13) * 43758.5453)


def blade(x, y, yaw_deg, h, lean, pick):
    """(verts, polys, u, colour per poly) of one plant rooted at (x, y), `h` its layout height (already cleared
    and sight-cut), `lean` the layout's lean (flattened blades keep theirs: they lie down, whatever the variant).
    Every plant is one island rising from z = 0 (the foliage contract: sway 0 at the root)."""
    vi = variant(pick)
    _, _, wr, hr, lr, colour, shape = VARIANTS[vi]
    w = wr[0] + (wr[1] - wr[0]) * _r(pick, 1)
    k = SCALE_JITTER[0] + (SCALE_JITTER[1] - SCALE_JITTER[0]) * _r(pick, 2)
    flat = lean > 1.0                                         # trampled by the layout: keep it lying down
    hh = h if flat else h * min(1.0, k * (hr[0] + (hr[1] - hr[0]) * _r(pick, 3)))   # never above the layout
    ln = lean if flat else lr[0] + (lr[1] - lr[0]) * _r(pick, 4)
    if shape == "rosette" and not flat:                    # three low leaves splayed round one shared root
        verts, polys, u, cols = _strip(x, y, yaw_deg, hh, ln, w, colour, "blade", 0, pick)
        for j in (1, 2):
            yv = yaw_deg + j * 120.0 + 40.0 * _r(pick, 5 + j)
            v, p, uu, c = _strip(x, y, yv, hh, ln, w, colour, "blade", 0, pick)
            k = len(verts) - 2                                # its verts 2.. land at k + 2 ..; 0, 1 are the root
            verts += v[2:]
            u += uu[2:]
            polys += [tuple(i if i < 2 else i + k for i in q) for q in p]
            cols += c
        return verts, polys, u, cols
    return _strip(x, y, yaw_deg, hh, ln, w, colour, "blade" if flat else shape, 0, pick)


def _strip(x, y, yaw_deg, h, lean, w, colour, shape, base, pick):
    a = math.radians(yaw_deg)
    dx, dy = math.cos(a), math.sin(a)
    px, py = -dy * w / 2, dx * w / 2
    L = 0.0
    if shape == "seed":                                       # the head sits within the plant's height
        L = min(SEED_HEAD_M[0] + (SEED_HEAD_M[1] - SEED_HEAD_M[0]) * _r(pick, 9), 0.3 * h)
        h -= L
    if shape == "bent":                                       # upright to a node, then folded over
        node = (x + 0.1 * lean * h * dx, y + 0.1 * lean * h * dy, 0.6 * h)
        tip = (x + 1.2 * lean * h * dx, y + 1.2 * lean * h * dy, max(0.35 * h, 0.6 * h - 0.5 * lean * h))
    else:
        node = (x + 0.3 * lean * h * dx, y + 0.3 * lean * h * dy, 0.55 * h)
        tip = (x + lean * h * dx, y + lean * h * dy, h)
    verts = [(x - px, y - py, 0.0), (x + px, y + py, 0.0),
             (node[0] + 0.6 * px, node[1] + 0.6 * py, node[2]), (node[0] - 0.6 * px, node[1] - 0.6 * py, node[2]), tip]
    polys = [(base, base + 1, base + 2, base + 3), (base + 3, base + 2, base + 4)]
    u = [0.0, 0.0, node[2] / max(h, 1e-6), node[2] / max(h, 1e-6), 1.0]
    cols = [colour, colour]
    if shape == "seed":                                       # a spindle of seeds on the stem's tip
        tx, ty, tz = tip
        ex, ey = lean * dx, lean * dy                         # carry on along the stem's direction
        n = math.sqrt(ex * ex + ey * ey + 1.0)
        ux, uy, uz = ex / n, ey / n, 1.0 / n
        sx, sy = -dy * SEED_HEAD_W / 2, dx * SEED_HEAD_W / 2
        mid = (tx + 0.45 * L * ux, ty + 0.45 * L * uy, tz + 0.45 * L * uz)
        end = (tx + L * ux, ty + L * uy, tz + L * uz)
        verts += [(mid[0] - sx, mid[1] - sy, mid[2]), (mid[0] + sx, mid[1] + sy, mid[2]), end]
        polys.append((base + 4, base + 5, base + 7, base + 6))      # stem tip, mid pair, end: a diamond
        u += [1.0, 1.0, 1.0]
        cols.append(SEED)
    return verts, polys, u, cols
