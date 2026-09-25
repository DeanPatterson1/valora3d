"""The wind-bend deformers (engine/physics/sway in nodes). Both work in world space (Object Info of the
object itself) and read the shared valora_wind group. Stateless.

sway_tree: foliage. Each vertex moves bend_frac(|w|) * len * u^2 along the horizontal wind, plus a small
perpendicular flutter (a cantilever stem: the root stays, the tip moves most).
pivot_tree: dangling parts. A rigid rotation about the part's pivot (keeps the strap's length)."""
import math

from engine.physics import sway as SW


def _bend(t, wx, wy, stiffness):
    v2 = t.math("ADD", t.math("MULTIPLY", wx, wx), t.math("MULTIPLY", wy, wy))
    return t.math("MINIMUM", math.tan(math.radians(SW.MAX_BEND_DEG)),
                  t.math("MULTIPLY", v2, SW.DRAG_K * (1.0 - 0.8 * stiffness)))


def sway_tree(name, stiffness, flutter):
    import bpy
    from engine.blender import gn
    from engine.blender.realism_rig import SWAY, SWAY_LEN
    t = gn.Tree(name)
    m = t.object_transform(t.self_object())
    wp = t.point(t.position(), m)                                                  # world position
    wind = t.group(bpy.data.node_groups["valora_wind"], Position=wp).outputs["Wind"]
    wx, wy, _ = t.xyz(wind)
    bend = _bend(t, wx, wy, stiffness)
    u = t.attr(SWAY)
    reach = t.math("MULTIPLY", t.math("MULTIPLY", bend, t.attr(SWAY_LEN)), t.math("MULTIPLY", u, u))
    dirn = t.vmath("NORMALIZE", t.vec(wx, wy, 0.0))
    fac, _ = t.noise(t.vmath("ADD", t.vmath("SCALE", wp, scale=20.0),
                             t.vec(0.0, 0.0, t.math("MULTIPLY", t.time(), 6.0))))
    jitter = t.math("MULTIPLY", t.math("MULTIPLY", reach, 0.2 * flutter),
                    t.math("SUBTRACT", t.math("MULTIPLY", fac, 2.0), 1.0))
    dx, dy, _ = t.xyz(dirn)
    perp = t.vec(t.math("MULTIPLY", dy, -1.0), dx, 0.0)
    disp = t.vmath("ADD", t.vmath("SCALE", dirn, scale=reach), t.vmath("SCALE", perp, scale=jitter))
    t.set_position(t.point(t.vmath("ADD", wp, disp), t.invert(m)))
    return t.finish()


def pivot_tree(name, stiffness, flutter):
    """Dangling parts (engine/physics/sway.swing_point in nodes): every tagged vertex turns rigidly about its
    part's pivot by atan(bend_frac) in the plane of the part and the wind, the wind sampled at the pivot so
    a whole part turns as one. Flutter scales the angle by 1 +/- 0.2 x flutter (noise in time), still a
    rotation, so the part never stretches. Untagged vertices (valora_sway_len 0) get angle 0."""
    import bpy
    from engine.blender import gn
    from engine.blender.realism_rig import SWAY_LEN, SWAY_PIVOT, SWAY_TIP
    t = gn.Tree(name)
    m = t.object_transform(t.self_object())
    wp = t.point(t.position(), m)
    pw = t.point(t.attr(SWAY_PIVOT, "FLOAT_VECTOR"), m)
    tw = t.point(t.attr(SWAY_TIP, "FLOAT_VECTOR"), m)
    wind = t.group(bpy.data.node_groups["valora_wind"], Position=pw).outputs["Wind"]
    wx, wy, _ = t.xyz(wind)
    theta = t.math("ARCTANGENT", _bend(t, wx, wy, stiffness))
    fac, _ = t.noise(t.vmath("ADD", t.vmath("SCALE", pw, scale=20.0),
                             t.vec(0.0, 0.0, t.math("MULTIPLY", t.time(), 6.0))))
    theta = t.math("MULTIPLY", theta, t.math("ADD", 1.0, t.math("MULTIPLY", 0.2 * flutter,
                                                                 t.math("SUBTRACT", t.math("MULTIPLY", fac, 2.0), 1.0))))
    theta = t.math("MINIMUM", theta, math.radians(SW.MAX_BEND_DEG))   # flutter never passes the cap
    k = t.vmath("CROSS_PRODUCT", t.vmath("SUBTRACT", tw, pw), t.vmath("NORMALIZE", t.vec(wx, wy, 0.0)))
    klen = t.vmath("LENGTH", k)
    live = t.math("MULTIPLY", t.math("GREATER_THAN", klen, 1e-9), t.math("GREATER_THAN", t.attr(SWAY_LEN), 0.0))
    axis = t.switch_vec(live, t.vec(0.0, 0.0, 1.0), t.vmath("NORMALIZE", k))
    turned = t.vmath("ADD", pw, t.rotate(t.vmath("SUBTRACT", wp, pw), axis, t.math("MULTIPLY", theta, live)))
    t.set_position(t.point(turned, t.invert(m)))
    return t.finish()
