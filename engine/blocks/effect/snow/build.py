"""snow: stateless flakes, a snow layer on up-facing surfaces and a white ground coat (maths in
engine/physics/snow.py; the particle box is the rain's, engine/blender/weather_nodes).

Flakes: box_points with a per-flake seeded fall speed and wobble plus the wind drift (perMs 0.9), sheltered by
the posed footprint, instanced as real-size cards (flakeMm) with a `velocity` attribute (the analytic
derivative), so motion blur is right and nothing depends on the frame before. Accumulation: a SEPARATE object
reading each upload mesh through Object Info keeps only faces with n.up > 0.7 and lifts them by the snow depth
(accumulationMm, growing slowly with time); the upload gets no modifier. The ground coat wraps each valora_ground
material's Principled BSDF in one valora_snow group, as wet_surface wraps it. groundType stays the world's:
ground_conform does not switch to snow sink in phase 5 (deferred coupling, in the register)."""
import math

GROUP = "valora_snow"
COAT_FULL_MM = 10.0   # (eng) the ground reads fully white at 10 mm of snow


def _snow_material(bpy):
    m = bpy.data.materials.new("valora_snow")
    m.use_nodes = True
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Base Color"].default_value = (0.92, 0.94, 0.97, 1.0)
    sh.inputs["Roughness"].default_value = 0.75
    sh.inputs["Subsurface Weight"].default_value = 0.3
    return m


def _flakes(bpy, ctx, mat, speed_ms_wind):
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.blender.realism_rig import OFFSET
    from engine.physics import rain as R
    from engine.physics import snow as S
    prof, p = ctx.profile, ctx.params
    far = max((math.dist(q, prof.center) for q in ctx.camera_positions), default=4.0 * prof.radius)
    near = min((math.dist(q, prof.center) for q in ctx.camera_positions), default=far)
    side, height = R.box_size(prof.longest, prof.sizeM[2], far, min(ctx.camera_lenses_mm or [50.0]))
    n = S.flake_count(p["rate"], side * side * height)
    ob = wn.weather_object(ctx.scene, "valora_snow", "effect/snow")
    ob.visible_shadow = False
    t = Tree("valora_snow_points")
    rnd = lambda lo, hi, k: wn.random(t, "FLOAT", lo, hi, ctx.seed + k)  # noqa: E731
    speed = rnd(*S.SPEED_MS, 11)
    amp, f1, f2 = rnd(*S.WOBBLE_A_M, 12), rnd(*S.WOBBLE_HZ, 13), rnd(*S.WOBBLE_HZ, 14)
    p1, p2 = rnd(0.0, 2 * math.pi, 15), rnd(0.0, 2 * math.pi, 16)
    sec = t.time()
    arg1 = t.math("ADD", t.math("MULTIPLY", t.math("MULTIPLY", f1, 2 * math.pi), sec), p1)
    arg2 = t.math("ADD", t.math("MULTIPLY", t.math("MULTIPLY", f2, 2 * math.pi), sec), p2)
    wx, wy = speed_ms_wind
    drift = t.vec(t.math("ADD", t.math("MULTIPLY", sec, wx), t.math("MULTIPLY", amp, t.math("SINE", arg1))),
                  t.math("ADD", t.math("MULTIPLY", sec, wy), t.math("MULTIPLY", amp, t.math("COSINE", arg2))),
                  t.math("MULTIPLY", t.math("MULTIPLY", speed, sec), -1.0))
    # velocity = d(drift)/dt: wind + the wobble's derivative + the fall
    vel = t.vec(t.math("ADD", wx, t.math("MULTIPLY", t.math("MULTIPLY", amp, t.math("MULTIPLY", f1, 2 * math.pi)), t.math("COSINE", arg1))),
                t.math("SUBTRACT", wy, t.math("MULTIPLY", t.math("MULTIPLY", amp, t.math("MULTIPLY", f2, 2 * math.pi)), t.math("SINE", arg2))),
                t.math("MULTIPLY", speed, -1.0))
    wn.box_points(t, n, ctx.seed, side, height, wn.box_centre(t, prof.center[:2]), drift)
    wn.store_vector(t, "velocity", vel)
    t.store("valora_spin", wn.random(t, "FLOAT_VECTOR", (0.0, 0.0, 0.0), (6.3, 6.3, 6.3), ctx.seed + 17), "FLOAT_VECTOR")
    wn.shelter(t, bpy.data.objects[OFFSET], prof.boundsMin, prof.boundsMax, near_m=R.NEAR_FRAC * near)
    add_modifier(ob, t.finish(), "valora_snow_points")
    d = Tree("valora_snow_flakes")
    card = d.node("GeometryNodeMeshGrid")
    card.inputs["Size X"].default_value = card.inputs["Size Y"].default_value = p["flakeMm"] / 1000.0
    card.inputs["Vertices X"].default_value = card.inputs["Vertices Y"].default_value = 2
    wn.instance(d, card.outputs["Mesh"], (1.0, 1.0, 1.0), rotation=d.attr("valora_spin", "FLOAT_VECTOR"), material=mat)
    add_modifier(ob, d.finish(), "valora_snow_flakes")
    return ob, n, side, height


def _cover(bpy, ctx, mat):
    """The snow layer on the subject: up-facing faces of the evaluated upload, lifted by the snow depth."""
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.physics import snow as S
    p = ctx.params
    ob = wn.weather_object(ctx.scene, "valora_snow_cover", "effect/snow")
    t = Tree("valora_snow_cover")
    join = t.node("GeometryNodeJoinGeometry")
    for m in ctx.meshes:
        info = t.node("GeometryNodeObjectInfo", transform_space="RELATIVE")
        info.inputs["Object"].default_value = m
        t.feed(join.inputs["Geometry"], info.outputs["Geometry"])
    # the upload's custom (split) normals would make the Normal field a smoothed normal: drop them on this copy so
    # "faces up" is the true face normal (glTF imports carry custom_normal; the upload itself is untouched)
    tri = t.node("GeometryNodeTriangulate")               # planar faces: a non-planar quad has no one normal
    t.feed(tri.inputs["Mesh"], join.outputs["Geometry"])
    rm = t.node("GeometryNodeRemoveAttribute")
    t.feed(rm.inputs["Geometry"], tri.outputs["Mesh"])
    rm.inputs["Name"].default_value = "custom_normal"
    t.geometry = rm.outputs["Geometry"]
    nz = t.xyz(t.node("GeometryNodeInputNormal").outputs["Normal"])[2]
    d = t.node("GeometryNodeDeleteGeometry", domain="FACE")
    t.feed(d.inputs["Geometry"], t.geometry)
    t.feed(d.inputs["Selection"], t.math("LESS_THAN", nz, S.UP_DOT + 1e-4))
    t.geometry = d.outputs["Geometry"]
    # snow depth is measured vertically: lift straight up (a lift along vertex normals folds thin parts)
    depth_m = t.math("MULTIPLY", t.math("ADD", p["accumulationMm"], t.math("MULTIPLY", t.time(), p["rate"] * S.GROW_MM_S)), 0.001)
    t.set_position(t.vmath("ADD", t.position(), t.vec(0.0, 0.0, depth_m)))
    sm = t.node("GeometryNodeSetMaterial")
    t.feed(sm.inputs["Geometry"], t.geometry)
    sm.inputs["Material"].default_value = mat
    t.geometry = sm.outputs["Geometry"]
    add_modifier(ob, t.finish(), "valora_snow_cover")
    return ob


def _ground_group(bpy, coverage):
    ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    for name, kind in (("Color", "NodeSocketColor"), ("Roughness", "NodeSocketFloat")):
        ng.interface.new_socket(name, in_out="INPUT", socket_type=kind)
        ng.interface.new_socket(name, in_out="OUTPUT", socket_type=kind)
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    geo = ng.nodes.new("ShaderNodeNewGeometry")
    noise = ng.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.6
    ng.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    ramp = ng.nodes.new("ShaderNodeMapRange")                  # patchy where thin, solid where deep
    ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.65 - 0.6 * coverage, 0.75 - 0.6 * coverage
    ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = 0.0, 1.0
    ng.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    mix = ng.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    ng.links.new(ramp.outputs["Result"], mix.inputs["Factor"])
    ng.links.new(gi.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (0.9, 0.92, 0.95, 1.0)
    ng.links.new(mix.outputs[2], go.inputs["Color"])
    rough = ng.nodes.new("ShaderNodeMix")
    rough.data_type = "FLOAT"
    ng.links.new(ramp.outputs["Result"], rough.inputs["Factor"])
    ng.links.new(gi.outputs["Roughness"], rough.inputs[2])
    rough.inputs[3].default_value = 0.8
    ng.links.new(rough.outputs[0], go.inputs["Roughness"])
    return ng


def _coat_ground(bpy, coverage):
    from engine.blender.realism_rig import ground_objects
    group, wrapped = _ground_group(bpy, coverage), []
    for ob in ground_objects():
        for mat in {m for m in ob.data.materials if m is not None and m.use_nodes}:
            sh = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if sh is None:
                continue
            nt = mat.node_tree
            g = nt.nodes.new("ShaderNodeGroup")
            g.node_tree, g.name = group, GROUP
            for src, dst in (("Base Color", "Color"), ("Roughness", "Roughness")):
                sock = sh.inputs[src]
                if sock.is_linked:
                    nt.links.new(sock.links[0].from_socket, g.inputs[dst])
                else:
                    g.inputs[dst].default_value = sock.default_value
                nt.links.new(g.outputs[dst], sh.inputs[src])
            wrapped.append(mat.name)
    return sorted(wrapped)


def build(ctx):
    import bpy
    from engine.physics import snow as S
    from engine.physics import wind as W
    from engine.physics.wind_calibration import perms
    p = ctx.params
    w = ctx.scene.get("valora_wind") or {"directionDeg": 0.0, "speedMs": 0.0}
    wind = W.vector(float(w["directionDeg"]), float(w["speedMs"]) * perms(ctx.catalog, "effect", "snow"))
    mat = _snow_material(bpy)
    ob, n, side, height = _flakes(bpy, ctx, mat, wind[:2])
    cover = _cover(bpy, ctx, mat) if p["onSubject"] and p["accumulationMm"] > 0 else None
    ground = _coat_ground(bpy, min(1.0, p["accumulationMm"] / COAT_FULL_MM))
    ctx.scene["valora_fx_snow"] = {"count": n, "side": side, "height": height, "cover": cover is not None,
                                   "groundMaterials": ground, "driftMs": [wind[0], wind[1]],
                                   "accumulationMm": p["accumulationMm"]}
    return ob
