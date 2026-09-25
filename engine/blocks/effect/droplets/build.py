"""droplets: water beads and drips on the subject (render-studio rain_atmosphere.drips generalised; maths in
engine/physics/droplets.py).

render-studio found drip emitters by ray-casting the car. Here the beads live on a SEPARATE object that reads
each upload mesh through Object Info (evaluated, so a moving or deformed subject carries its beads), scatters
points on faces whose normal faces up (zone up_facing) or on all faces, and instances real-size flattened
water hemispheres aligned to the surface normal. The upload gets no modifier, so its evaluated mesh (and the
checker's bounds) are untouched. Drip emitters sit on the subject's low edges (shape.low_edges, placed space,
posed through valora_realism_offset every frame while it hangs); each swells, lets go at its detach pose and
falls ballistically to z = 0 on a seeded period, as a function of time alone (METHODS R1)."""
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
    """One vertex per drip cycle that touches the clip (engine/physics/droplets.drip_events), in placed space,
    with its swell start / detach time (scene seconds) and its world position and velocity at detach. While it
    hangs the tree poses it through valora_realism_offset each frame (it rides the subject); once it lets go it
    flies ballistically from its detach state (review chunk3 #5: a moving or turning subject throws its drips
    instead of carrying them) and is gone below z = 0."""
    import numpy as np
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.blender.realism_rig import OFFSET
    from engine.motion_path import pose_fn
    from engine.physics import droplets as D
    em = D.drip_emitters(ctx.profile, ctx.params["density"], ctx.seed)
    if not em:
        return None, 0, 0
    fps = ctx.script["format"]["fps"]
    dur = float(ctx.script["format"]["durationS"])
    evs = D.drip_events(em, pose_fn(ctx.script, ctx.profile, ctx.catalog), ctx.profile, dur + 2.0 / fps,
                        t_start=-2.0 / fps)
    if not evs:
        return None, len(em), 0
    lead = 1.0 / fps                               # Scene Time (frame / fps) runs 1/fps ahead of script time
    me = bpy.data.meshes.new("valora_drips")
    me.from_pydata([e["p"] for e in evs], [], [])
    for name, vals in (("valora_t0", [e["t0"] + lead for e in evs]), ("valora_td", [e["td"] + lead for e in evs])):
        me.attributes.new(name, "FLOAT", "POINT").data.foreach_set("value", np.array(vals, np.float32))
    for name, key in (("valora_pd", "pd"), ("valora_vd", "vd")):
        me.attributes.new(name, "FLOAT_VECTOR", "POINT").data.foreach_set(
            "vector", np.array([e[key] for e in evs], np.float32).ravel())
    ob = bpy.data.objects.new("valora_drips", me)
    ob["valora_block"] = "effect/droplets"
    ctx.scene.collection.objects.link(ob)
    t = Tree("valora_drips")
    now = t.time()
    t0, td = t.attr("valora_t0"), t.attr("valora_td")
    hanging = t.point(t.position(), t.object_transform(bpy.data.objects[OFFSET]))
    u = t.math("MAXIMUM", t.math("SUBTRACT", now, td), 0.0)
    flown = t.vmath("ADD", t.attr("valora_pd", "FLOAT_VECTOR"), t.vmath("SCALE", t.attr("valora_vd", "FLOAT_VECTOR"), scale=u))
    fx, fy, fz = t.xyz(flown)
    fz = t.math("SUBTRACT", fz, t.math("MULTIPLY", t.math("MULTIPLY", u, u), 0.5 * D.G))
    falling = t.math("GREATER_THAN", now, td)
    t.set_position(t.switch_vec(falling, hanging, t.vec(fx, fy, fz)))
    vx, vy, vz = t.xyz(t.attr("valora_vd", "FLOAT_VECTOR"))
    fall_v = t.vec(vx, vy, t.math("SUBTRACT", vz, t.math("MULTIPLY", u, D.G)))
    wn.store_vector(t, "velocity", t.switch_vec(falling, t.vec(0.0, 0.0, 0.0), fall_v))
    hang = t.math("MAXIMUM", t.math("SUBTRACT", td, t0), 1e-6)
    swell = t.math("POWER", t.math("MINIMUM", t.math("MAXIMUM", t.math("DIVIDE", t.math("SUBTRACT", now, t0), hang), 0.0), 1.0),
                   D.SWELL_EXP)
    t.store("valora_size", swell)
    t.store("valora_fall", u)
    gone = t.node("GeometryNodeDeleteGeometry")
    t.feed(gone.inputs["Geometry"], t.geometry)
    t.feed(gone.inputs["Selection"], t.math("MAXIMUM", t.math("LESS_THAN", now, t0),
                                            t.math("MULTIPLY", falling, t.math("LESS_THAN", fz, 0.0))))
    t.geometry = gone.outputs["Geometry"]
    add_modifier(ob, t.finish(), "valora_drips")
    d = Tree("valora_drips_drops")                 # instancing apart, so the probe reads the drip points
    r = 1.1 * ctx.params["sizeMm"] / 1000.0        # a hanging drip is bigger than a bead
    size = d.math("MULTIPLY", d.attr("valora_size"), r)
    stretch = d.math("ADD", 1.15, d.math("MULTIPLY", d.math("MINIMUM", d.math("MULTIPLY", d.attr("valora_fall"), 6.0), 1.0), 0.7))
    wn.instance(d, wn.ico(d, 2), d.vec(size, size, d.math("MULTIPLY", size, stretch)), material=wn.water("valora_drip_water"))
    add_modifier(ob, d.finish(), "valora_drips_drops")
    return ob, len(em), len(evs)


def build(ctx):
    import bpy
    p = ctx.params
    ob = _beads(bpy, ctx, ctx.meshes)
    drips, n, events = _drips(bpy, ctx) if p["drips"] else (None, 0, 0)
    ctx.scene["valora_fx_droplets"] = {"zone": p["zone"], "sizeMm": p["sizeMm"], "dripEmitters": n, "dripEvents": events,
                                       "uploadMeshes": len(ctx.meshes)}
    return ob
