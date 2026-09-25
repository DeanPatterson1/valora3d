"""Wind bend of thin things: grass, stems, straps, cords (TAXONOMY HF-01..03, SC-08, SF-02/03;
METHODS §2.5, §2.11). Aerodynamic drag grows with v^2; a cantilever's tip moves most, its root not at
all (u^2 profile along the length). Stateless: the Blender deformer evaluates this per frame from the
wind field, so no frame depends on the one before."""
import math

MAX_BEND_DEG = 25.0   # nothing bends further than 25 deg in this phase (eng)
DRAG_K = 0.02         # tip displacement per metre of length per (m/s)^2 at stiffness 0 (eng)


def bend_frac(speed, stiffness):
    """Tip displacement / length for wind `speed` (m/s); stiffness 0 (thread) .. 1 (stiff stem)."""
    return min(math.tan(math.radians(MAX_BEND_DEG)), DRAG_K * speed * speed * (1.0 - 0.8 * stiffness))


def tip_offset(u, length, speed, stiffness):
    """Displacement (m) of a point at u in [0, 1] from root to tip."""
    return bend_frac(speed, stiffness) * length * u * u


def pivot_angle(speed, stiffness):
    """Swing angle (radians) of a hanging part about its pivot: the angle whose tangent is bend_frac, so the
    tip moves as far across the wind as the cantilever rule says while the part keeps its length."""
    return math.atan(bend_frac(speed, stiffness))


def swing_point(p, pivot, tip, wind, stiffness):
    """p rotated rigidly about `pivot` by pivot_angle(|wind_xy|), in the plane of the part (pivot -> tip)
    and the horizontal wind, so the part turns downwind (a hanging strap and an upright stem alike). Lengths
    are kept exactly (review fix, Task 21: a plain shear stretched straps ~10% at the 25 deg cap). The
    Blender deformer (engine/blender/sway_nodes.pivot_tree) mirrors this."""
    wx, wy = wind[0], wind[1]
    speed = math.hypot(wx, wy)
    s = [t - q for t, q in zip(tip, pivot)]
    d = (wx / speed, wy / speed, 0.0) if speed > 0 else (0.0, 0.0, 0.0)
    k = (s[1] * d[2] - s[2] * d[1], s[2] * d[0] - s[0] * d[2], s[0] * d[1] - s[1] * d[0])   # s x d
    kn = math.sqrt(sum(c * c for c in k))
    if kn < 1e-12:
        return tuple(p)
    k = tuple(c / kn for c in k)
    th = pivot_angle(speed, stiffness)
    v = [a - b for a, b in zip(p, pivot)]
    kv = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0])
    kdv = sum(a * b for a, b in zip(k, v))
    c, sn = math.cos(th), math.sin(th)
    return tuple(pv + vi * c + kvi * sn + ki * kdv * (1 - c) for pv, vi, kvi, ki in zip(pivot, v, kv, k))
