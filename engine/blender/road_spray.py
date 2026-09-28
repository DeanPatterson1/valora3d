"""tyre_spray and dust_kick, the Blender side (phase 6 Task 106), on the shared GN point sim (engine/blender/
gn_sim.py). Runs inside Blender only; the maths (emitters on the rolling contacts through the drive's pose
function, rates, sizes) is engine/physics/road_spray.py.

Step: gravity, a per-point linear drag (grains light, puffs heavy: puff x puffDrag + (1 - puff) x drag) toward the
shared wind (valora_wind), and the ground (z = 0) with almost no bounce. No shell collision: the particles are born
at the tyres, inside the car's closed shell, so a push-out would throw them onto the body; they fly back and down,
away from it. Post: grains are points (droplets / grit, at least MIN_R_M in radius so they read at 540p); puffs
become a volume (Points to Volume) that swells with age (mist / dust billow)."""
import bpy

from engine.blender import gn_sim as G
from engine.physics import road_spray as R

MIN_R_M = {"spray": 0.0025, "dust": 0.0015}     # (eng, G6) render radius floor of a grain (1 cm/px on a car at 540p)
PUFF_GROW = 2.0                                  # a puff's radius grows (1 + GROW x age / life) x
PUFF_DENSITY = {"spray": 12.0, "dust": 20.0}     # (eng, G6) volume density: a 20 cm puff at 0.6 was invisible (clip 1)


def step(kind):
    k = R.SPRAY if kind == "spray" else R.DUST

    def _step(t, h):
        p0, v0 = t.position(), t.attr("velocity", "FLOAT_VECTOR")
        puff = t.attr("puff")
        drag = t.math("ADD", t.math("MULTIPLY", puff, k["puffDrag"] - k["drag"]), k["drag"])
        air = t.vec(0.0, 0.0, 0.0)
        ng = bpy.data.node_groups.get("valora_wind")
        if ng is not None:
            air = t.group(ng, Position=p0).outputs["Wind"]
        g = t.vec(0.0, 0.0, -9.81)
        g = t.vmath("SCALE", g, scale=t.math("SUBTRACT", 1.0, t.math("MULTIPLY", puff, 0.85)))   # a puff barely falls
        acc = t.vmath("ADD", g, t.vmath("SCALE", t.vmath("SUBTRACT", air, v0), scale=drag))
        v1 = t.vmath("ADD", v0, t.vmath("SCALE", acc, scale=h))
        p1 = t.vmath("ADD", p0, t.vmath("SCALE", v1, scale=h))
        p1, v1 = G.collide_ground(t, p1, v1, 0.0, 0.05, 0.9)
        G.commit(t, p1, v1)
    return _step


def _grain_material(kind):
    name = f"valora_{kind}_grain"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if kind == "spray":
        sh.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        sh.inputs["Roughness"].default_value = 0.25
        sh.inputs["IOR"].default_value = 1.333
        sh.inputs["Transmission Weight"].default_value = 0.4   # a sub-pixel droplet reads by its sheen, not its refraction
    else:
        sh.inputs["Base Color"].default_value = (0.24, 0.19, 0.13, 1.0)
        sh.inputs["Roughness"].default_value = 0.9
    return m


def _puff_material(kind):
    name = f"valora_{kind}_puff"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (0.86, 0.88, 0.9, 1.0) if kind == "spray" else (0.55, 0.46, 0.35, 1.0)
    pv.inputs["Density"].default_value = 1.0
    nt.links.new(pv.outputs[0], out.inputs["Volume"])
    return m


def group(kind, emitter, time_scale):
    def post(t):
        pts = t.geometry
        is_puff = t.math("GREATER_THAN", t.attr("puff"), 0.5)
        # grains: the points themselves, puffs removed
        dg = t.node("GeometryNodeDeleteGeometry", domain="POINT")
        t.feed(dg.inputs["Geometry"], pts)
        t.feed(dg.inputs["Selection"], is_puff)
        t.geometry = dg.outputs["Geometry"]
        rad = t.node("GeometryNodeSetPointRadius")
        t.feed(rad.inputs["Points"], t.geometry)
        t.feed(rad.inputs["Radius"], t.math("MAXIMUM", t.math("MULTIPLY", t.attr("size"), 0.5), MIN_R_M[kind]))
        t.geometry = rad.outputs["Points"]
        G.material(t, _grain_material(kind))
        grains = t.geometry
        # puffs: a volume, each puff a sphere that swells with age
        dp = t.node("GeometryNodeDeleteGeometry", domain="POINT")
        t.feed(dp.inputs["Geometry"], pts)
        t.feed(dp.inputs["Selection"], t.math("SUBTRACT", 1.0, is_puff))
        pv = t.node("GeometryNodePointsToVolume")
        t.feed(pv.inputs["Points"], dp.outputs["Geometry"])
        pv.inputs["Density"].default_value = PUFF_DENSITY[kind]
        if hasattr(pv, "resolution_mode"):
            pv.resolution_mode = "VOXEL_SIZE"
        vs = next((s for s in pv.inputs if s.name == "Voxel Size"), None)
        if vs is not None:
            vs.default_value = 0.012 if kind == "spray" else 0.02
        grow = t.math("ADD", 1.0, t.math("MULTIPLY", t.math("DIVIDE", t.attr("age"), t.attr("life")), PUFF_GROW))
        t.feed(pv.inputs["Radius"], t.math("MULTIPLY", t.math("MULTIPLY", t.attr("size"), 0.5), grow))
        sm = t.node("GeometryNodeSetMaterial")
        t.feed(sm.inputs["Geometry"], pv.outputs["Volume"])
        sm.inputs["Material"].default_value = _puff_material(kind)
        j = t.node("GeometryNodeJoinGeometry")
        t.ng.links.new(grains, j.inputs[0])
        t.ng.links.new(sm.outputs["Geometry"], j.inputs[0])
        t.geometry = j.outputs[0]
    return G.ensure_point_sim(f"valora_sim_{'tyre_spray' if kind == 'spray' else 'dust_kick'}", spawn=emitter,
                              forces={}, collide={}, attrs=("puff",), post=post, substeps=2, time_scale=time_scale,
                              step=step(kind))
