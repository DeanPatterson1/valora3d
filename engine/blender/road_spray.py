"""tyre_spray and dust_kick, the Blender side (phase 6 Task 106), on the shared GN point sim (engine/blender/
gn_sim.py). Runs inside Blender only; the maths (emitters on the rolling contacts through the drive's pose
function, rates, sizes) is engine/physics/road_spray.py.

Step: gravity, a per-point linear drag (grains light, puffs heavy: puff x puffDrag + (1 - puff) x drag) toward the
shared wind (valora_wind), and the ground (z = 0) with almost no bounce. No shell collision: the particles are born
at the tyres, inside the car's closed shell, so a push-out would throw them onto the body; they fly back and down,
away from it. Each particle carries its own drag `k` and gravity share `fall` (engine/physics/road_spray: grains
ballistic, fine mist carried by the air, puffs barely falling).
Post: grains and the fine mist are real-size shutter streaks (a width floor that is one 540p pixel's worth at the preview
tier and scales down with the render's short side, so a 1080p frame is not full of 5 mm beads); spray is a clear
water droplet, dust a translucent mote that glows when the sun is behind it; puffs become a volume (Points to
Volume) that swells with age, its density broken by a 3D noise so the billow reads as wisps, not spheres
(hero pass 2026-09-28: the lane clips' puffs were uniform spheres and read as blobs)."""
import bpy

from engine.blender import gn_sim as G
from engine.physics import road_spray as R

MIN_R_M = {"spray": 0.0025, "dust": 0.0015}     # (eng, G6) render radius floor of a grain at 540p (1 cm/px on a car)
FINE_MIN_R_M = {"spray": 0.0008, "dust": 0.0008}   # (eng) the fine mist floor at 540p: one streak stands for many real droplets
PUFF_NOISE_SCALE = {"spray": 7.0, "dust": 4.5}   # (eng) wisps per metre of the billow's density noise
PUFF_ANISO = {"spray": 0.45, "dust": 0.6}        # forward scattering: backlit mist and dust glow
PUFF_GROW = {"spray": 2.0, "dust": 3.5}         # a puff's radius grows (1 + GROW x age / life) x: dust billows out
DUST_TRANSLUCENT = 0.5                           # (eng) share of a mote's light that comes through it (backlit glow)
STREAK_SIDES = 4                                 # a droplet streak is far thinner than a pixel: 4 sides is plenty
PUFF_DENSITY = {"spray": 20.0, "dust": 30.0}     # (eng, G6) volume density before the noise mask (clip 1: 0.6 invisible;
                                                 # the lane's uniform 12 / 20 spheres read as blobs; the
                                                 # mask keeps ~1/5 of it: 9 / 14 were invisible at final)


EXTRAS = ("puff", "fine", "k", "fall")          # the per-particle attributes the emitter carries
PUFF_MASK = (0.42, 0.72)                         # (eng) noise Fac mapped to 0..1 density: below 0.42 clear air


def step(kind):
    k = R.SPRAY if kind == "spray" else R.DUST

    def _step(t, h):
        p0, v0 = t.position(), t.attr("velocity", "FLOAT_VECTOR")
        drag = t.attr("k")
        air = t.vec(0.0, 0.0, 0.0)
        ng = bpy.data.node_groups.get("valora_wind")
        if ng is not None:
            air = t.group(ng, Position=p0).outputs["Wind"]
        g = t.vec(0.0, 0.0, -9.81)
        g = t.vmath("SCALE", g, scale=t.attr("fall"))                  # a puff barely falls, mist drifts down
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
        sh.inputs["Transmission Weight"].default_value = 0.15  # a sub-pixel droplet reads by its sheen, not its refraction
    else:
        sh.inputs["Base Color"].default_value = (0.24, 0.19, 0.13, 1.0)
        sh.inputs["Roughness"].default_value = 0.9
    return m


def _fine_material(kind):
    """A mist streak: white, opaque (it stands for many droplets scattering the sky); a dust mote: a pale grain lit through
    (partly transmissive), so a low sun behind the cloud makes it glow."""
    name = f"valora_{kind}_fine"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if kind == "spray":      # opaque: a streak stands for many droplets scattering white; refracting streaks
        sh.inputs["Base Color"].default_value = (0.92, 0.94, 0.96, 1.0)   # ghosted the car behind them (hero pass)
        sh.inputs["Roughness"].default_value = 0.35
        sh.inputs["IOR"].default_value = 1.333
    else:                    # a thin mineral grain: diffuse + translucent (lit through, never refracting)
        nt = m.node_tree
        sh.inputs["Base Color"].default_value = (0.62, 0.52, 0.38, 1.0)
        sh.inputs["Roughness"].default_value = 0.8
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
        tr.inputs["Color"].default_value = (0.85, 0.72, 0.52, 1.0)
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = DUST_TRANSLUCENT
        nt.links.new(sh.outputs[0], mix.inputs[1])
        nt.links.new(tr.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def _puff_material(kind):
    """Principled Volume whose density is (the Points to Volume grid) x a 3D noise mask: the billow breaks into
    wisps with soft edges instead of reading as the union of uniform spheres."""
    name = f"valora_{kind}_puff"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (0.86, 0.88, 0.9, 1.0) if kind == "spray" else (0.78, 0.66, 0.50, 1.0)
    pv.inputs["Anisotropy"].default_value = PUFF_ANISO[kind]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "3D"
    nz.inputs["Scale"].default_value = PUFF_NOISE_SCALE[kind]
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.clamp = True
    ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = PUFF_MASK
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Value"])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    nt.links.new(ramp.outputs["Result"], pw.inputs[0])
    pw.inputs[1].default_value = 1.6
    nt.links.new(pw.outputs[0], pv.inputs["Density"])
    nt.links.new(pv.outputs[0], out.inputs["Volume"])
    return m



def streaks(t, floor, mat):
    """Each droplet / grain becomes a thin streak along its velocity, as long as the shutter sees it travel
    (|v| x SHUTTER / fps + w, centred), w = max(size, floor) wide, with the velocity attribute dropped so Cycles
    never blurs it twice; the camera's own motion blur still smears it (a tracking camera sees the spray stream
    past). Hero pass 2026-09-28: the final-tier stills rendered the spray's GN points as sharp round dots (no
    velocity blur on the point cloud), which read as salt, not spray; the sparks already draw streaks this way."""
    from engine.blender import weather_nodes as wn
    from engine.compiler.tiers import SHUTTER
    fps = float(bpy.context.scene.render.fps)
    v = t.attr("velocity", "FLOAT_VECTOR")
    w = t.math("MAXIMUM", t.attr("size"), floor)
    ln = t.math("ADD", t.math("MULTIPLY", t.vmath("LENGTH", v), SHUTTER / fps), w)
    cyl = t.node("GeometryNodeMeshCylinder")
    cyl.inputs["Vertices"].default_value = STREAK_SIDES
    cyl.inputs["Radius"].default_value = 0.5
    cyl.inputs["Depth"].default_value = 1.0
    al = t.node("FunctionNodeAlignRotationToVector", axis="Z")
    t.feed(al.inputs["Vector"], v)
    wn.instance(t, cyl.outputs["Mesh"], t.vec(w, w, ln), rotation=al.outputs[0], material=mat)
    rm = t.node("GeometryNodeRemoveAttribute")
    t.feed(rm.inputs["Geometry"], t.geometry)
    rm.inputs["Name"].default_value = "velocity"
    t.geometry = rm.outputs["Geometry"]


def group(kind, emitter, time_scale):
    def post(t):
        pts = t.geometry
        fl = G.floor_scale()                           # the floors are for 540p; 0.5 x at 1080p
        is_puff = t.math("GREATER_THAN", t.attr("puff"), 0.5)
        is_fine = t.math("GREATER_THAN", t.attr("fine"), 0.5)

        def points(drop, floor, mat):
            dg = t.node("GeometryNodeDeleteGeometry", domain="POINT")
            t.feed(dg.inputs["Geometry"], pts)
            t.feed(dg.inputs["Selection"], drop)
            t.geometry = dg.outputs["Geometry"]
            streaks(t, floor * fl, mat)
            return t.geometry

        # grains: neither puff nor fine; the fine mist: its own floor and material
        grains = points(t.math("MAXIMUM", is_puff, is_fine), MIN_R_M[kind], _grain_material(kind))
        fine = points(t.math("SUBTRACT", 1.0, is_fine), FINE_MIN_R_M[kind], _fine_material(kind))
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
        grow = t.math("ADD", 1.0, t.math("MULTIPLY", t.math("DIVIDE", t.attr("age"), t.attr("life")), PUFF_GROW[kind]))
        t.feed(pv.inputs["Radius"], t.math("MULTIPLY", t.math("MULTIPLY", t.attr("size"), 0.5), grow))
        sm = t.node("GeometryNodeSetMaterial")
        t.feed(sm.inputs["Geometry"], pv.outputs["Volume"])
        sm.inputs["Material"].default_value = _puff_material(kind)
        j = t.node("GeometryNodeJoinGeometry")
        t.ng.links.new(grains, j.inputs[0])
        t.ng.links.new(fine, j.inputs[0])
        rz = t.node("GeometryNodeSetPointRadius")                # the sim's points ride along at radius 0 for simProbe
        t.feed(rz.inputs["Points"], pts)
        rz.inputs["Radius"].default_value = 0.0
        t.ng.links.new(rz.outputs["Points"], j.inputs[0])
        t.ng.links.new(sm.outputs["Geometry"], j.inputs[0])
        t.geometry = j.outputs[0]
    return G.ensure_point_sim(f"valora_sim_{'tyre_spray' if kind == 'spray' else 'dust_kick'}", spawn=emitter,
                              forces={}, collide={}, attrs=EXTRAS, post=post, substeps=2, time_scale=time_scale,
                              step=step(kind))
