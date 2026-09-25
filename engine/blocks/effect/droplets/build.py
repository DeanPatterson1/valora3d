"""droplets: water beads and drips on the subject (render-studio rain_atmosphere.drips generalised; maths in
engine/physics/droplets.py).

render-studio found drip emitters by ray-casting the car. Here the beads live on a SEPARATE object that reads
each upload mesh through Object Info (evaluated, so a moving or deformed subject carries its beads), scatters
points on faces whose normal faces up (zone up_facing) or on all faces, and instances real-size flattened
water hemispheres aligned to the surface normal. The upload gets no modifier, so its evaluated mesh (and the
checker's bounds) are untouched. Drip emitters sit on the subject's low edges (shape.low_edges, placed space,
posed through valora_realism_offset every frame); each swells, lets go and falls under gravity to z = 0 on a
seeded period, as a function of time alone (METHODS R1)."""
UP_NZ = 0.7            # = engine/physics/shape.UP_DOT


def _beads(bpy, ctx, meshes):
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.physics import droplets as D
    p = ctx.params
    ob = wn.weather_object(ctx.scene, "valora_droplets", "effect/droplets")
    t = Tree("valora_droplets_points")
    join = t.node("GeometryNodeJoinGeometry")
    for m in meshes:
        info = t.node("GeometryNodeObjectInfo", transform_space="RELATIVE")
        info.inputs["Object"].default_value = m
        t.feed(join.inputs["Geometry"], info.outputs["Geometry"])
    rm = t.node("GeometryNodeRemoveAttribute")    # the true face normal, not the upload's custom split normals
    t.feed(rm.inputs["Geometry"], join.outputs["Geometry"])
    rm.inputs["Name"].default_value = "custom_normal"
    nz = t.xyz(t.node("GeometryNodeInputNormal").outputs["Normal"])[2]
    sel = t.math("GREATER_THAN", nz, UP_NZ) if p["zone"] == "up_facing" else 1.0
    fac, _ = t.noise(t.position(), scale=1.0 / max(0.01, 0.1 * ctx.profile.longest))
    sel = t.math("MULTIPLY", sel, t.math("GREATER_THAN", fac, 0.35))          # a noise mask: beads gather in patches
    dist = t.node("GeometryNodeDistributePointsOnFaces", distribute_method="RANDOM")
    t.feed(dist.inputs["Mesh"], rm.outputs["Geometry"])
    t.feed(dist.inputs["Selection"], sel)
    dist.inputs["Density"].default_value = min(D.bead_density(p["sizeMm"], p["density"]),
                                               D.MAX_BEADS / max(1e-4, ctx.profile.longest ** 2))
    dist.inputs["Seed"].default_value = int(ctx.seed) % 100000
    t.geometry = wn._vertices(t, dist.outputs["Points"])
    t.store("valora_n", dist.outputs["Normal"], "FLOAT_VECTOR")
    t.store("valora_rot", dist.outputs["Rotation"], "QUATERNION")
    add_modifier(ob, t.finish(), "valora_droplets_points")
    d = Tree("valora_droplets_beads")
    r = p["sizeMm"] / 2000.0
    rot = d.attr("valora_rot", "QUATERNION")
    wn.instance(d, wn.ico(d, 2), (r, r, 0.5 * r), rotation=rot, material=wn.water("valora_droplet_water"))
    add_modifier(ob, d.finish(), "valora_droplets_beads")
    return ob


def _drips(bpy, ctx):
    """Emitters as vertices in placed space with period/phase attributes; the tree poses them through
    valora_realism_offset each frame, then drops them under gravity until z = 0."""
    import numpy as np
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.blender.realism_rig import OFFSET
    from engine.physics import droplets as D
    em = D.drip_emitters(ctx.profile, ctx.params["density"], ctx.seed)
    if not em:
        return None, 0
    me = bpy.data.meshes.new("valora_drips")
    me.from_pydata([e[0] for e in em], [], [])
    for name, vals in (("valora_period", [e[1] for e in em]), ("valora_phase", [e[2] for e in em])):
        me.attributes.new(name, "FLOAT", "POINT").data.foreach_set("value", np.array(vals, np.float32))
    ob = bpy.data.objects.new("valora_drips", me)
    ob["valora_block"] = "effect/droplets"
    ctx.scene.collection.objects.link(ob)
    t = Tree("valora_drips")
    world = t.point(t.position(), t.object_transform(bpy.data.objects[OFFSET]))
    period, phase = t.attr("valora_period"), t.attr("valora_phase")
    since = t.math("MULTIPLY", t.math("FRACT", t.math("ADD", t.math("DIVIDE", t.time(), period), phase)), period)
    hang = t.math("MULTIPLY", period, D.HANG_FRAC)
    fall = t.math("MAXIMUM", t.math("SUBTRACT", since, hang), 0.0)
    drop = t.math("MULTIPLY", t.math("MULTIPLY", fall, fall), 0.5 * D.G)
    wx, wy, wz = t.xyz(world)
    z = t.math("SUBTRACT", wz, drop)
    swell = t.math("POWER", t.math("MINIMUM", t.math("DIVIDE", since, hang), 1.0), D.SWELL_EXP)
    t.set_position(t.vec(wx, wy, z))
    wn.store_vector(t, "velocity", t.vec(0.0, 0.0, t.math("MULTIPLY", fall, -D.G)))
    t.store("valora_size", swell)
    gone = t.node("GeometryNodeDeleteGeometry")
    t.feed(gone.inputs["Geometry"], t.geometry)
    t.feed(gone.inputs["Selection"], t.math("LESS_THAN", z, 0.0))
    t.geometry = gone.outputs["Geometry"]
    r = 1.1 * ctx.params["sizeMm"] / 1000.0                    # a hanging drip is bigger than a bead
    size = t.math("MULTIPLY", t.attr("valora_size"), r)
    stretch = t.math("ADD", 1.15, t.math("MULTIPLY", t.math("MINIMUM", t.math("MULTIPLY", fall, 6.0), 1.0), 0.7))
    wn.instance(t, wn.ico(t, 2), t.vec(size, size, t.math("MULTIPLY", size, stretch)), material=wn.water("valora_drip_water"))
    add_modifier(ob, t.finish(), "valora_drips")
    return ob, len(em)


def build(ctx):
    import bpy
    p = ctx.params
    ob = _beads(bpy, ctx, ctx.meshes)
    drips, n = _drips(bpy, ctx) if p["drips"] else (None, 0)
    ctx.scene["valora_fx_droplets"] = {"zone": p["zone"], "sizeMm": p["sizeMm"], "dripEmitters": n,
                                       "uploadMeshes": len(ctx.meshes)}
    return ob
