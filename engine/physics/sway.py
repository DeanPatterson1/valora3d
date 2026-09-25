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
