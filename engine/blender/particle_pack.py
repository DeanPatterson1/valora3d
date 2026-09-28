"""The particle pack's Blender side (phase 6 Task 105): node groups, steps and materials for sparks, confetti and
bubbles on the shared GN point sim (engine/blender/gn_sim.py), and the stateless embers effect. Runs inside
Blender only. The maths (spawn, sizes, rise speeds, blackbody cooling) is engine/physics/particle_pack.py.

bake(ctx) and build(ctx) of each block call group(...) with the same arguments except the emitter and the proxy:
the bake's zone simulates; the build's zone (no emitter, no proxy) only reads the disk cache (SimInCompile)."""
import bpy

from engine.blender import gn_sim as G
from engine.physics import particle_pack as P


def _principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def _attr(nt, name):
    n = nt.nodes.new("ShaderNodeAttribute")
    n.attribute_type = "GEOMETRY"
    n.attribute_name = name
    return n


def _math(nt, op, a, b=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for s, v in zip(n.inputs, (a, b)):
        if v is None:
            continue
        if hasattr(v, "is_output"):
            nt.links.new(v, s)
        else:
            s.default_value = v
    return n.outputs[0]


# ------------------------------------------------------------------------------------------------- sparks

def spark_material(gain=1.0):
    """Emission = Blackbody(T) x (T / 2000 K)^4 x gain, with T = temp x exp(-COOL x age / life)."""
    m = bpy.data.materials.get("valora_spark") or bpy.data.materials.new("valora_spark")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    bb = nt.nodes.new("ShaderNodeBlackbody")
    frac = _math(nt, "DIVIDE", _attr(nt, "age").outputs["Fac"], _attr(nt, "life").outputs["Fac"])
    temp = _math(nt, "MULTIPLY", _attr(nt, "temp").outputs["Fac"],
                 _math(nt, "EXPONENT", _math(nt, "MULTIPLY", frac, -P.SPARK_COOL)))
    nt.links.new(temp, bb.inputs["Temperature"])
    nt.links.new(bb.outputs[0], em.inputs["Color"])
    strength = _math(nt, "MULTIPLY", _math(nt, "POWER", _math(nt, "DIVIDE", temp, 2000.0), 4.0), SPARK_GAIN * gain)
    strength = _math(nt, "MULTIPLY", strength, _math(nt, "DIVIDE", _attr(nt, "size").outputs["Fac"],
                                                     _math(nt, "MAXIMUM", _attr(nt, "w").outputs["Fac"], 1e-5)))
    nt.links.new(strength, em.inputs["Strength"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


SPARK_GAIN = 3.0e4       # (eng, G5) emission strength at 2000 K: a 2000 K bead radiates ~ sigma T^4 = 9e5 W/m^2, orders
#                          above a lit studio surface; 3e4 keeps a sub-pixel, motion-blurred 0.5 mm bead a visible streak


SPARK_MIN_W_M = 0.0015    # (eng) rendered streak width floor: a 0.5 mm bead is sub-pixel at 540p; emission x size / w


def streaks(t, fps, mat, min_w=SPARK_MIN_W_M):
    """Each point becomes a thin emissive streak along its velocity, as long as the camera's shutter sees it move
    (|v| x SHUTTER / fps, centred on the point like the compiler's centred shutter), `w` = max(size, min_w) wide.
    The streak mesh drops its velocity so Cycles never blurs it twice; the points stay in the output at zero
    radius, carrying position and velocity for simProbe (R7)."""
    from engine.compiler.tiers import SHUTTER
    pts = t.geometry
    v = t.attr("velocity", "FLOAT_VECTOR")
    w = t.math("MAXIMUM", t.attr("size"), min_w)
    t.store("w", w)
    ln = t.math("ADD", t.math("MULTIPLY", t.vmath("LENGTH", v), SHUTTER / float(fps)), w)
    cyl = t.node("GeometryNodeMeshCylinder")
    cyl.inputs["Vertices"].default_value = 6
    cyl.inputs["Radius"].default_value = 0.5
    cyl.inputs["Depth"].default_value = 1.0
    from engine.blender import weather_nodes as wn
    al = t.node("FunctionNodeAlignRotationToVector", axis="Z")
    t.feed(al.inputs["Vector"], v)
    wn.instance(t, cyl.outputs["Mesh"], t.vec(w, w, ln), rotation=al.outputs[0], material=mat)
    rm = t.node("GeometryNodeRemoveAttribute")
    t.feed(rm.inputs["Geometry"], t.geometry)
    rm.inputs["Name"].default_value = "velocity"
    streak = rm.outputs["Geometry"]
    t.geometry = streak
    keep_points(t, pts)


def keep_points(t, pts):
    """Join the sim's points, at zero radius (never rendered), to t.geometry: the point-cloud object's evaluated
    data stays the simulated points, so simProbe reads their positions and velocity."""
    rz = t.node("GeometryNodeSetPointRadius")
    t.feed(rz.inputs["Points"], pts)
    rz.inputs["Radius"].default_value = 0.0
    j = t.node("GeometryNodeJoinGeometry")
    t.ng.links.new(rz.outputs["Points"], j.inputs[0])
    t.ng.links.new(t.geometry, j.inputs[0])
    t.geometry = j.outputs[0]


def sparks_group(emitter, proxy, time_scale, fps=24):
    def post(t):
        streaks(t, fps, spark_material())
    return G.ensure_point_sim("valora_sim_sparks", spawn=emitter,
                              forces={"gravity": (0.0, 0.0, -9.81), "drag": P.SPARK_DRAG, "wind": 0.2},
                              collide={"proxy": proxy, "ground": 0.0, "restitution": P.SPARK_BOUNCE[0],
                                       "friction": P.SPARK_BOUNCE[1]},
                              attrs=("temp",), post=post, substeps=3, time_scale=time_scale)


# ------------------------------------------------------------------------------------------------- confetti

CONFETTI_FLUTTER = 2.5     # (eng) m/s^2 sideways flutter at full fall speed
CONFETTI_SPIN_STOP_MS = 0.25   # below this speed a card lies flat and stops turning


def confetti_step(forces, collide):
    """Drag toward the wind, gravity, a sideways flutter A sin(spin x age + phase) that fades as the card slows,
    and an integrated tumble angle `ang` (stops when the card rests)."""
    def step(t, h):
        p0, v0 = t.position(), t.attr("velocity", "FLOAT_VECTOR")
        age, ph, spin = t.attr("age"), t.attr("phase"), t.attr("spin")
        k = float(forces["drag"])
        air = t.vec(0.0, 0.0, 0.0)
        ng = bpy.data.node_groups.get("valora_wind")
        if ng is not None and forces.get("wind", 0.0):
            air = t.vmath("SCALE", t.group(ng, Position=p0).outputs["Wind"], scale=float(forces["wind"]))
        speed = t.vmath("LENGTH", v0)
        moving = t.smoothstep(0.0, CONFETTI_SPIN_STOP_MS, speed)
        arg = t.math("ADD", t.math("MULTIPLY", age, spin), ph)
        fl = t.math("MULTIPLY", moving, CONFETTI_FLUTTER)
        flutter = t.vec(t.math("MULTIPLY", fl, t.math("SINE", arg)), t.math("MULTIPLY", fl, t.math("COSINE", t.math("MULTIPLY", arg, 0.7))), 0.0)
        acc = t.vmath("ADD", t.vmath("ADD", t.vec(0.0, 0.0, -9.81), flutter),
                      t.vmath("SCALE", t.vmath("SUBTRACT", air, v0), scale=k))
        v1 = t.vmath("ADD", v0, t.vmath("SCALE", acc, scale=h))
        p1 = t.vmath("ADD", p0, t.vmath("SCALE", v1, scale=h))
        e, mu = collide["restitution"], collide["friction"]
        if collide.get("proxy") is not None:
            p1, v1 = G.collide_proxy(t, G._obj_geo(t, collide["proxy"]), p0, p1, v1, h, e, mu)
        p1, v1 = G.collide_ground(t, p1, v1, 0.0, e, mu)
        t.store("ang", t.math("ADD", t.attr("ang"), t.math("MULTIPLY", t.math("MULTIPLY", spin, moving), h)))
        t.store("tilt", moving)
        G.commit(t, p1, v1)
    return step


def confetti_material():
    m = bpy.data.materials.get("valora_confetti") or bpy.data.materials.new("valora_confetti")
    m.use_nodes = True
    nt = m.node_tree
    sh = _principled(m)
    nt.links.new(_attr(nt, "colour").outputs["Color"], sh.inputs["Base Color"])
    metal = _attr(nt, "metal").outputs["Fac"]
    nt.links.new(metal, sh.inputs["Metallic"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    nt.links.new(metal, rough.inputs["Value"])
    rough.inputs["To Min"].default_value, rough.inputs["To Max"].default_value = 0.55, 0.22   # paper -> foil
    nt.links.new(rough.outputs["Result"], sh.inputs["Roughness"])
    if "Sheen Weight" in sh.inputs:
        sh.inputs["Sheen Weight"].default_value = 0.2
    return m


def confetti_group(emitter, proxy, time_scale):
    forces = {"drag": P.CONFETTI_DRAG, "wind": 1.0}
    collide = {"proxy": proxy, "restitution": 0.05, "friction": 0.8}

    def post(t):
        # a thin card (1 x 0.6 x 0.01 of size), turned by the tumble angle, laid flat as it stops (tilt -> 0)
        card = t.node("GeometryNodeMeshCube")
        card.inputs["Size"].default_value = (1.0, 0.6, 0.02)
        ang, tilt, ph = t.attr("ang"), t.attr("tilt"), t.attr("phase")
        rot = t.node("FunctionNodeEulerToRotation")
        t.feed(rot.inputs[0], t.vec(t.math("MULTIPLY", t.math("SINE", ang), tilt),
                                   t.math("MULTIPLY", t.math("COSINE", t.math("MULTIPLY", ang, 0.8)), tilt), ph))
        size = t.attr("size")
        from engine.blender import weather_nodes as wn
        pts = t.geometry
        wn.instance(t, card.outputs["Mesh"], t.vec(size, size, size), rotation=rot.outputs[0],
                    material=confetti_material())
        keep_points(t, pts)
    return G.ensure_point_sim("valora_sim_confetti", spawn=emitter, forces=forces, collide=collide,
                              attrs=("colour", "metal", "phase", "spin", "ang", "tilt"), post=post, substeps=2,
                              time_scale=time_scale, step=confetti_step(forces, collide))


# ------------------------------------------------------------------------------------------------- bubbles

BUBBLE_ZIG_MS = 0.02      # (eng) sideways speed amplitude of a zig-zagging small bubble
BUBBLE_ZIG_HZ = 6.0


def bubble_step(t, h):
    """Rise at the stored speed (velocity z), plus a zig-zag for small bubbles: x' = A cos(w age + phase)."""
    import math
    v0 = t.attr("velocity", "FLOAT_VECTOR")
    _, _, vz = t.xyz(v0)
    arg = t.math("ADD", t.math("MULTIPLY", t.attr("age"), 2 * math.pi * BUBBLE_ZIG_HZ), t.attr("phase"))
    amp = t.math("MULTIPLY", t.attr("zig"), BUBBLE_ZIG_MS)
    v1 = t.vec(t.math("MULTIPLY", amp, t.math("COSINE", arg)), t.math("MULTIPLY", amp, t.math("SINE", arg)), vz)
    G.commit(t, t.vmath("ADD", t.position(), t.vmath("SCALE", v1, scale=h)), v1)


BUBBLE_RIM = 6.0      # (eng, G5) the silvery total-internal-reflection rim, as emission on grazing angles


def bubble_material():
    """An air bubble in water: a clear transmissive sphere with IOR 1 / 1.333, plus the silvery rim real bubbles
    show from total internal reflection. At preview the path runs out of transmission bounces (glass wall, drink,
    bubble: 8) before that reflection resolves, so the rim is added as a faint emission on grazing angles
    (Layer Weight facing^1.5 x BUBBLE_RIM)."""
    m = bpy.data.materials.get("valora_bubble") or bpy.data.materials.new("valora_bubble")
    m.use_nodes = True
    nt = m.node_tree
    sh = _principled(m)
    sh.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    sh.inputs["Roughness"].default_value = 0.0
    sh.inputs["IOR"].default_value = 1.0 / 1.333
    sh.inputs["Transmission Weight"].default_value = 1.0
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.3
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(_math(nt, "MULTIPLY", _math(nt, "POWER", lw.outputs["Facing"], 1.5), BUBBLE_RIM), em.inputs["Strength"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(sh.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m


def bubbles_group(emitter, time_scale):
    def post(t):
        grow = t.math("ADD", 1.0, t.math("MULTIPLY", t.math("DIVIDE", t.attr("age"), t.attr("life")), P.BUBBLE_GROW))
        n = t.node("GeometryNodeSetPointRadius")
        t.feed(n.inputs["Points"], t.geometry)
        t.feed(n.inputs["Radius"], t.math("MULTIPLY", t.math("MULTIPLY", t.attr("size"), 0.5), grow))
        t.geometry = n.outputs["Points"]
        G.material(t, bubble_material())
    return G.ensure_point_sim("valora_sim_bubbles", spawn=emitter, forces={}, collide={},
                              attrs=("phase", "zig"), post=post, substeps=1, time_scale=time_scale, step=bubble_step)


def drink(name, centre, radius, z0, z1, block):
    """The liquid the bubbles rise in: a closed cylinder of water inside the container (radius x 0.92, clear of a glass wall), from the
    floor to the fill line, tagged with the block. Water: IOR 1.333, faint absorption."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=64, radius1=radius * 0.92, radius2=radius * 0.92,
                          depth=z1 - z0)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (centre[0], centre[1], (z0 + z1) / 2)
    ob["valora_block"] = f"{block}:drink"     # not the sim's own tag: simProbe reads only the simulated points
    m = bpy.data.materials.get("valora_drink") or bpy.data.materials.new("valora_drink")
    m.use_nodes = True
    sh = _principled(m)
    sh.inputs["Base Color"].default_value = (0.97, 0.99, 1.0, 1.0)
    sh.inputs["Roughness"].default_value = 0.0
    sh.inputs["IOR"].default_value = 1.333
    sh.inputs["Transmission Weight"].default_value = 1.0
    me.materials.append(m)
    return ob
