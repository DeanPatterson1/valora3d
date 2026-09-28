"""Cloth presets and sizing (phase 6 Task 107; METHODS SC-01, SC-02, SC-05, R4, R5). Pure: engine/blender/cloth.py
applies these to Blender's legacy cloth.

Blender's cloth is not scale-free: `mass` is per VERTEX and every spring, damping and air force is absolute. The
presets are therefore given at a reference vertex spacing (REF_SPACING, the Task 107 calibration strip's), and
`settings(preset, spacing)` scales the vertex mass AND every force-like setting by f = (spacing / REF_SPACING)^2.
Scaling both by f keeps every acceleration a cloth feels from its own springs, damping and gravity unchanged
(a = F / m), while the wind's acceleration (Blender's WIND pushes each face by strength x area) stays
strength x REF_SPACING^2 / mass at any resolution. So one wind field strength means the same wind for a 5 cm
watch cover and a 5 m car cover (engine/physics/wind_calibration.FF_STRENGTH_PER_MS, fitted by
engine/tests/test_cloth_calibration_blender.py).

Every number here is (eng) until the owner grades G7 / G8 (the calibration register, Task 123)."""
import math

REF_SPACING = 0.02          # m between vertices of the calibration strip; presets are Blender values at it
MAX_VERTS = 8000            # the budget table: <= 8k vertices per cloth
SPACING_FRAC = 0.01         # SC-02: vertex spacing about 1% of the subject length
DISTANCE_FRAC = 0.004       # SC-02 / R5: collision distance_min 0.3-0.5% of longest
QUALITY = (8, 12)           # SC-02: quality 8-12 steps per frame

# Blender cloth settings at REF_SPACING (the plan's presets); arealKgM2 is the real fabric weight the drag model
# uses (silk charmeuse ~60 g/m2, satin ~120 g/m2, cotton canvas ~350 g/m2: fabric supplier tables, eng).
PRESETS = {
    "silk": {"mass": 0.15, "tension": 5.0, "compression": 5.0, "shear": 5.0, "bending": 0.05, "air": 1.5,
             "damping": 5.0, "arealKgM2": 0.06},
    "satin": {"mass": 0.25, "tension": 10.0, "compression": 10.0, "shear": 10.0, "bending": 0.2, "air": 1.0,
              "damping": 5.0, "arealKgM2": 0.12},
    "canvas": {"mass": 0.6, "tension": 40.0, "compression": 40.0, "shear": 40.0, "bending": 5.0, "air": 1.0,
               "damping": 10.0, "arealKgM2": 0.35},
}
_FORCES = ("tension", "compression", "shear", "bending", "air", "damping")


def spacing_m(longest):
    return SPACING_FRAC * float(longest)


def distance_min(longest):
    """Collision distance: 0.4% of the subject, never under 0.5 mm (Blender's cloth collision loses contacts
    below it) nor over 3 cm."""
    return min(0.03, max(0.0005, DISTANCE_FRAC * float(longest)))


def grid_dims(width, height, spacing, max_verts=MAX_VERTS):
    """(nx, ny, spacing): vertices across and down a width x height sheet at about `spacing`, coarsened evenly
    until nx * ny <= max_verts. Every sheet has at least 2 x 2 vertices."""
    if width <= 0 or height <= 0 or spacing <= 0:
        raise ValueError("cloth sheet sizes must be positive")
    s = float(spacing)
    while True:
        nx = max(2, int(round(width / s)) + 1)
        ny = max(2, int(round(height / s)) + 1)
        if nx * ny <= max_verts:
            return nx, ny, max(width / (nx - 1), height / (ny - 1))
        s *= math.sqrt(nx * ny / max_verts) * 1.001


def settings(preset, spacing):
    """Blender cloth settings for `preset` at a vertex spacing: mass and every force scaled by
    f = (spacing / REF_SPACING)^2 (see the module docstring)."""
    p = PRESETS[preset]
    f = (float(spacing) / REF_SPACING) ** 2
    out = {k: p[k] * f for k in _FORCES}
    out["mass"] = p["mass"] * f
    out["scale"] = f
    return out


def quality(n_verts, self_collision=False):
    """More steps for bigger and self-colliding sheets, within QUALITY."""
    q = QUALITY[0] + (2 if n_verts > 3000 else 0) + (2 if self_collision else 0)
    return max(QUALITY[0], min(QUALITY[1], q))


# The drag model the wind calibration fits against (Task 107): a strip pinned along its top edge hangs at an
# angle theta from the vertical where tan(theta) = F_drag / W, F_drag = 0.5 rho C_d A v^2 and W = m g.
RHO_AIR = 1.225             # kg/m3 at sea level, 15 C
CD_FLAG = 1.2               # (eng) a flapping flag's drag coefficient (the plan's figure)
G = 9.81


def drag_tan(speed_ms, areal_kg_m2, cd=CD_FLAG):
    """tan(theta) of a hanging strip in a steady wind: drag pressure over weight per area."""
    return 0.5 * RHO_AIR * cd * speed_ms * speed_ms / (areal_kg_m2 * G)


def wind_weight(preset):
    """The cloth's effector weight for wind, relative to silk (the calibration fabric). A preset's Blender weight
    per area is mass / REF_SPACING^2, its real weight arealKgM2; the one field strength is fitted on silk, so
    another fabric's wind response scales by the ratio of those two ratios (canvas ~0.69: heavier cloth,
    less lift, as in the drag model)."""
    p, s = PRESETS[preset], PRESETS["silk"]
    return (p["mass"] / p["arealKgM2"]) / (s["mass"] / s["arealKgM2"])


def drag_angle_deg(speed_ms, areal_kg_m2, cd=CD_FLAG):
    return math.degrees(math.atan(drag_tan(speed_ms, areal_kg_m2, cd)))
