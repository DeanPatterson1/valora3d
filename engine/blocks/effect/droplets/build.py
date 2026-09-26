"""droplets: water beads and drips on the subject (render-studio rain_atmosphere.drips generalised; maths in
engine/physics/droplets.py).

render-studio found drip emitters by ray-casting the car. Here the beads live on a SEPARATE object that reads
each upload mesh through Object Info (evaluated, so a moving or deformed subject carries its beads), scatters
points on faces whose normal faces up (zone up_facing) or on all faces, and instances render-studio's mixed
bead populations (mist, small and large domes, merged pools, runoff streaks; render_materials.py:136-289) as
smooth, slightly distorted water domes aligned to the surface normal. The upload gets no modifier, so its evaluated mesh (and the
checker's bounds) are untouched. Drip emitters sit on the subject's low edges (shape.low_edges, placed space,
posed through valora_realism_offset every frame while it hangs); each swells, lets go at its detach pose and
falls ballistically to z = 0 on a seeded period, as a function of time alone (METHODS R1). The detach state is
where the drip HUNG: finalize() runs after every realism block is keyed (sink, tyre deflection, a settle's
overshoot or squash) and re-samples each drip's release position and velocity from the keyed motion and
offset curves at its release frame (review chunk5 #10: a correction read at the current frame drifted when a
settle moved the offset mid-fall)."""
UP_NZ = 0.7            # = engine/physics/shape.UP_DOT


PROTOTYPES = 4          # (eng) smooth distorted bead prototypes, one picked per bead


def _water(bpy, name):
    from engine.blender import weather_nodes as wn
    m = wn.water(name)
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Roughness"].default_value = 0.015       # clean water 0.01-0.03, IOR 1.333, no absorption (mat-v2)
    sh.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    return m


def _beads(bpy, ctx, meshes):
    """render-studio's bead populations (render_materials.add_water_beads, :136-289) as fields: a seeded
    uniform per point picks mist / small / large / merged / runoff (droplets.bead_kind), four more give its
    width, length and height (droplets.bead_dims: a varying contact angle), nested noise gathers them into
    wet clusters (droplets.patch_factor), and each bead instances one of PROTOTYPES smooth, slightly
    distorted unit spheres, Z on the face normal, Y downhill (runoff and merged pools stretch down the
    panel, round beads spin at random), its centre LIFT x height above the paint."""
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.physics import droplets as D
    p = ctx.params
    seed = int(ctx.seed)
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
    # zone all: every face that does not face down (render_materials.py:156, n.z < -0.05 drips instead)
    sel = t.math("GREATER_THAN", nz, UP_NZ if p["zone"] == "up_facing" else -0.05)
    share = sel
    if p["zone"] == "up_facing":   # the wet lower band (droplets.low_band_m): side faces near the road carry beads too
        pz = t.xyz(t.position())[2]
        low = t.math("MULTIPLY", t.math("GREATER_THAN", nz, -0.05), t.math("LESS_THAN", pz, D.low_band_m(ctx.profile)))
        low = t.math("MULTIPLY", low, t.math("SUBTRACT", 1.0, sel))
        share = t.math("ADD", sel, t.math("MULTIPLY", low, D.LOW_SHARE))
        sel = t.math("MAXIMUM", sel, low)
    # nested cluster noise in metres (render_materials.py:180-184): patch = .04 + .92 cluster (.45 + .55 fine)
    fb, ff = D.patch_freqs(ctx.profile.longest)
    broad, _ = t.noise(t.position(), scale=fb)
    fine, _ = t.noise(t.vmath("ADD", t.position(), (13.0, 4.0, 7.0)), scale=ff)
    cluster = t.math("POWER", t.math("MINIMUM", t.math("MAXIMUM", t.math("DIVIDE", t.math("SUBTRACT", broad, 0.30), 0.40), 0.0), 1.0), 2.2)
    patch = t.math("ADD", 0.04, t.math("MULTIPLY", t.math("MULTIPLY", cluster, 0.92),
                                       t.math("ADD", 0.45, t.math("MULTIPLY", fine, 0.55))))
    dist = t.node("GeometryNodeDistributePointsOnFaces", distribute_method="RANDOM")
    t.feed(dist.inputs["Mesh"], rm.outputs["Geometry"])
    t.feed(dist.inputs["Selection"], sel)
    base = min(D.bead_density(p["sizeMm"], p["density"], ctx.profile.longest), D.bead_cap_density(ctx.profile.longest))
    t.feed(dist.inputs["Density"], t.math("MULTIPLY", t.math("MULTIPLY", patch, base), share))
    dist.inputs["Seed"].default_value = seed % 100000
    t.geometry = wn._vertices(t, dist.outputs["Points"])
    t.store("valora_n", dist.outputs["Normal"], "FLOAT_VECTOR")
    # the population, per point, stored so the instancing tree reads captured values
    rnd = lambda k: wn.random(t, "FLOAT", 0.0, 1.0, seed + k)  # noqa: E731
    u, r1, r2, r3, r4, spin_u, proto_u = (rnd(k) for k in (101, 102, 103, 104, 105, 106, 107))
    pnz = t.xyz(t.attr("valora_n", "FLOAT_VECTOR"))[2]
    e0, e1, e2, e3 = D.KIND_EDGES
    ge = lambda a, b: t.math("GREATER_THAN", a, b)  # noqa: E731
    kind = t.math("ADD", t.math("ADD", ge(u, e0), ge(u, e1)),
                  t.math("ADD", ge(u, e2), t.math("MULTIPLY", ge(u, e3), t.math("LESS_THAN", pnz, D.RUNOFF_NZ))))
    k = D.size_scale(p["sizeMm"])
    lerp = lambda r, lo, span: t.math("MULTIPLY_ADD", r, span, lo)  # noqa: E731
    def radius(kind):                                       # droplets.RADIUS_M: lo + r1 ** skew x span
        lo, span, pw = D.RADIUS_M[kind]
        return lerp(r1 if pw == 1.0 else t.math("POWER", r1, pw), lo, span)

    def dome(kind, w_mul=1.0, l_mul=None, h_mul=1.0):       # droplets.bead_dims, as fields
        r = radius(D.LARGE if kind == D.MERGED else kind)
        c0, c1 = D.CAP_RATIO[D.LARGE if kind == D.MERGED else kind]
        w0 = t.math("MULTIPLY", r, lerp(r2, 0.9, 0.2))
        w = t.math("MULTIPLY", w0, w_mul * k)
        ln = t.math("MULTIPLY", r, t.math("MULTIPLY", lerp(r3, 0.9, 0.35), k))
        if l_mul is not None:
            ln = t.math("MULTIPLY", ln, l_mul)
        h = t.math("MULTIPLY", t.math("MULTIPLY", w0, lerp(r4, c0, c1 - c0)), D.CAP_H_PER_W * h_mul * k)
        return t.vec(w, ln, h)

    runoff = t.vec(t.math("MULTIPLY", lerp(r1, 0.00015, 0.0002), k), t.math("MULTIPLY", lerp(r2, 0.003, 0.009), k),
                   t.math("MULTIPLY", lerp(r3, 0.00005, 0.00005), k))
    dims = wn.index_switch(t, kind, [dome(D.MIST), dome(D.SMALL), dome(D.LARGE),
                                     dome(D.MERGED, 1.25, lerp(r3, 1.6, 0.9), 0.8), runoff])
    t.store("valora_kind", kind)
    t.store("valora_dims", dims, "FLOAT_VECTOR")
    round_bead = t.math("LESS_THAN", kind, float(D.MERGED) - 0.5)          # mist / small / large: any direction
    level = t.math("GREATER_THAN", pnz, 0.9998)                            # no downhill on a level face
    spin = t.math("MULTIPLY", t.math("MAXIMUM", round_bead, level), t.math("MULTIPLY", spin_u, 6.283185))
    t.store("valora_rot", wn.surface_frame(t, t.attr("valora_n", "FLOAT_VECTOR"), spin), "QUATERNION")
    t.store("valora_proto", t.math("FLOOR", t.math("MULTIPLY", proto_u, PROTOTYPES - 1e-3)))
    add_modifier(ob, t.finish(), "valora_droplets_points")
    d = Tree("valora_droplets_beads")
    dims = d.attr("valora_dims", "FLOAT_VECTOR")
    lift = d.math("MULTIPLY", d.xyz(dims)[2], D.LIFT)
    d.set_position(d.vmath("ADD", d.position(), d.vmath("SCALE", d.attr("valora_n", "FLOAT_VECTOR"), scale=lift)))
    protos = wn.prototypes(d, [wn.smooth_blob(d, 24, 12, D.DISTORT, variant=v) for v in range(PROTOTYPES)])
    wn.instance_pick(d, protos, d.attr("valora_proto"), dims, rotation=d.attr("valora_rot", "QUATERNION"),
                     material=_water(bpy, "valora_droplet_water"))
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
    wn.instance(d, wn.smooth_blob(d, 20, 12), d.vec(size, size, d.math("MULTIPLY", size, stretch)),
                material=_water(bpy, "valora_drip_water"))
    add_modifier(ob, d.finish(), "valora_drips_drops")
    return ob, len(em), len(evs)


RELEASE_DF = 0.05        # (eng) frames: the attached drip's velocity is its motion over the last 0.05 frame
RELEASE_KEY_GAP = 0.01   # (eng) frames: a key closer than this before the release counts as the release itself


def release_window(release, keys, df=RELEASE_DF, gap=RELEASE_KEY_GAP):
    """Frames h over which the attached drip's velocity is read backwards from `release`: RELEASE_DF, shortened
    to stay inside the linear key segment the drip rides at release (a key 0.01-0.05 frame before it). Pure."""
    prev = [k for k in keys if release - df < k < release - gap]
    return release - max(prev) if prev else df


def release_states(points, releases, fps, world_at, keys):
    """[(position, velocity)] at each release frame of a point in placed space riding world_at(frame) (4x4): the
    exact keyed position, and the velocity over release_window() (m/s). Pure (world_at is the caller's)."""
    import numpy as np
    out = []
    for p, fr in zip(points, releases):
        h = release_window(fr, keys)
        q = np.array([p[0], p[1], p[2], 1.0])
        a, b = (world_at(fr - h) @ q)[:3], (world_at(fr) @ q)[:3]
        out.append((b, (b - a) * fps / h))
    return out


def finalize(ctx):
    """After every block is built: each drip's release position / velocity re-sampled from the keyed
    valora_motion and valora_realism_offset curves at its release frame (the realism offset is final now)."""
    import bpy
    import numpy as np
    from engine.blender.realism_rig import MOTION, OFFSET, fcurves, keyed_matrix
    ob = bpy.data.objects.get("valora_drips")
    if ob is None or not len(ob.data.vertices):
        return
    me, fps = ob.data, ctx.scene.render.fps / ctx.scene.render.fps_base
    k = len(me.vertices)
    co = np.empty(k * 3)
    me.vertices.foreach_get("co", co)
    td = np.empty(k, np.float32)
    me.attributes["valora_td"].data.foreach_get("value", td)
    off = bpy.data.objects[OFFSET]
    keys = sorted({kp.co[0] for o in (bpy.data.objects[MOTION], off) if o.animation_data and o.animation_data.action
                   for c in fcurves(o.animation_data.action) for kp in c.keyframe_points})
    # the tree lets go when Scene Time (frame / fps) passes valora_td: that is the release frame
    st = release_states(co.reshape(-1, 3), [float(t) * fps for t in td], fps, lambda f: keyed_matrix(off, f), keys)
    me.attributes["valora_pd"].data.foreach_set("vector", np.array([s[0] for s in st], np.float32).ravel())
    me.attributes["valora_vd"].data.foreach_set("vector", np.array([s[1] for s in st], np.float32).ravel())
    ctx.scene["valora_fx_droplets"]["dripReleases"] = len(st)   # re-sampled after realism


def build(ctx):
    import bpy
    p = ctx.params
    ob = _beads(bpy, ctx, ctx.meshes)
    drips, n, events = _drips(bpy, ctx) if p["drips"] else (None, 0, 0)
    ctx.scene["valora_fx_droplets"] = {"zone": p["zone"], "sizeMm": p["sizeMm"], "dripEmitters": n, "dripEvents": events,
                                       "uploadMeshes": len(ctx.meshes)}
    return ob
