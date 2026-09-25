"""The one Blender wind (hand-off H4, METHODS §2.9). Runs inside Blender.

ensure_wind_group: the shared Geometry Nodes group `valora_wind` (Position -> Wind, m/s), built once per
scene; every consumer (rain slant, snow drift, fog drift, foliage sway) calls this, never its own noise.
wind(p, t) = d * s * (1 + gustiness * g) + turbulence * s * h, where d is the unit direction, s the mean
speed, g in [-1, 1] a noise advected downwind at the mean speed (gust fronts travel with the air), and h a
horizontal turbulence vector in [-0.5, 0.5]^2. Time is Scene Time: no frame depends on the one before.

ensure_force_field: one WIND force field empty (`valora_wind_field`) from the same params, so phase-6
consumers (legacy particles, cloth) cannot build a second wind. Its strength is not m/s
(engine/physics/wind_calibration.force_field_strength); its seed is 1-128 (METHODS R3)."""
import math

from engine.physics import wind as W
from engine.physics.wind_calibration import ff_seed, force_field_strength

GROUP, FIELD = "valora_wind", "valora_wind_field"


def ensure_wind_group(params, seed):
    import bpy
    from engine.blender.gn import Tree
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None:
        return ng
    s, g, tb = params["speedMs"], params["gustiness"], params["turbulence"]
    dx, dy, _ = W.vector(params["directionDeg"], 1.0)
    t = Tree(GROUP, inputs=(("Position", "NodeSocketVector"),), outputs=(("Wind", "NodeSocketVector"),))
    pos, sec = t.input("Position"), t.time()
    d = t.vec(dx, dy, 0.0)
    offs = float(seed % 997)                                       # per-clip noise offset (METHODS R3)
    drift = t.vmath("SCALE", d, scale=t.math("MULTIPLY", sec, s))  # how far the air moved since t = 0
    q = t.vmath("SCALE", t.vmath("SUBTRACT", pos, drift), scale=1.0 / W.GUST_WAVELENGTH_M)
    fac, _ = t.noise(t.vmath("ADD", q, t.vec(offs, offs, 0.0)))
    gust = t.math("SUBTRACT", t.math("MULTIPLY", fac, 2.0), 1.0)               # [-1, 1]
    mean = t.vmath("SCALE", d, scale=t.math("MULTIPLY", s, t.math("ADD", 1.0, t.math("MULTIPLY", gust, g))))
    tq = t.vmath("SCALE", t.vmath("SUBTRACT", pos, drift), scale=1.0 / W.TURB_SCALE_M)
    _, col = t.noise(t.vmath("ADD", tq, t.vec(-offs, offs, 0.5)))
    hx, hy, _ = t.xyz(t.vmath("SUBTRACT", col, t.vec(0.5, 0.5, 0.5)))
    turb = t.vmath("SCALE", t.vec(hx, hy, 0.0), scale=tb * s)
    t.output("Wind", t.vmath("ADD", mean, turb))
    return t.finish()


def ensure_force_field(params, seed):
    """A WIND field blows along its object's local +Z: rotate +Z onto the horizontal wind direction."""
    import bpy
    ob = bpy.data.objects.get(FIELD)
    if ob is None:   # a plain new empty has no FieldSettings until an effector is added: use the operator
        vl = bpy.context.view_layer
        was = vl.objects.active
        bpy.ops.object.effector_add(type="WIND", location=(0.0, 0.0, 0.0))
        ob = bpy.context.active_object
        ob.name = FIELD
        ob.select_set(False)
        vl.objects.active = was            # later blocks never see the field as the active object
    ob.hide_render = True
    ob.field.type = "WIND"
    ob.field.strength = force_field_strength(params["speedMs"])
    ob.field.noise = float(params["gustiness"])
    ob.field.seed = ff_seed(int(seed))
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (-math.pi / 2, 0.0, math.radians(params["directionDeg"]) - math.pi / 2)
    ob["valora_block"] = "field/wind"
    return ob
