"""Ground-cover conformity (TAXONOMY CD-07, HF-06 static; METHODS §2.1 CD-07). Stacked after foliage_sway
(resolver ORDER), in world space on every valora_foliage object:

- pressed: no foliage point stays above the subject's underside. A hidden heightfield of the underside
  (valora_rz_underside: a grid in placed space, the lowest subject surface above each grid point, built once
  from the evaluated subject) is parented to the realism offset, so it follows every move, yaw, sink and
  settle of the subject; each point is ray-cast up to it from below, and a blade (mesh island) with any
  point under it lies wholly CLEAR_M under the lowest underside its points meet (review
  item 3: grass under a car's floor stands up to the floor, a round plush presses only its base; review
  item 2: the footprint travels with a translating subject instead of freezing at frame 1).
- lean: blades rooted within MARGIN_FRAC x longest of the subject's placed box lean away from it, strongest
  at its edge, by leanFrac x len x u^2, keeping their length (engine/physics/sway.bend_point, review item 4)
  together with the sway foliage_sway already applied (its valora_sway_disp).

The subject's sink into the cover is contact_ground's sinkMm. Grass staying parted behind a moving subject
(HF-06 dynamic) waits for phase-5 drive: here it stands up again once the subject has passed."""
MARGIN_FRAC = 0.15    # lean-away ring width, x the subject's longest side (eng)
GRID_N = 96           # underside heightfield cells along the subject's longest side (eng)
GROW_FRAC = 0.02      # the pressed footprint reaches 2% of the longest side past the silhouette (eng)
CLEAR_M = 0.001       # a pressed point sits 1 mm under the underside (eng; the grid is linear between samples)
NO_HIT = 1.0e6        # "no underside above this point" in the per-blade minimum
UNDERSIDE = "valora_rz_underside"


def _underside(ctx, offset):
    """The subject's underside as a grid mesh in placed space, parented to the realism offset: the height
    of the first subject surface a ray from below meets at each grid point, see-through holes inside the
    silhouette filled and the silhouette grown by GROW_FRAC x longest (engine/physics/contact.underside_fill:
    lowest neighbour, so thin or coarse blades near an edge or a gap are still pressed). None if the subject
    has no faces."""
    import bpy
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from engine.physics.contact import underside_fill, underside_floor
    prof = ctx.profile
    inv = offset.matrix_world.inverted()
    deps = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in ctx.meshes:
        ev = o.evaluated_get(deps)
        me = ev.to_mesh()
        try:
            m = inv @ ev.matrix_world
            base = len(verts)
            verts += [m @ v.co for v in me.vertices]
            polys += [[base + i for i in p.vertices] for p in me.polygons]
        finally:
            ev.to_mesh_clear()
    if not polys:
        return None
    bvh = BVHTree.FromPolygons(verts, polys)
    lo, hi = np.array(prof.boundsMin[:2], float), np.array(prof.boundsMax[:2], float)
    step = max(prof.longest / GRID_N, 1e-6)
    grow = max(1, int(np.ceil(GROW_FRAC * prof.longest / step)))
    lo, hi = lo - (grow + 1) * step, hi + (grow + 1) * step
    nx, ny = (int(np.ceil((hi - lo)[k] / step)) + 1 for k in range(2))
    z0 = prof.boundsMin[2] - 1.0 - prof.sizeM[2]
    z = np.full((nx, ny), np.nan)
    for i in range(nx):
        for j in range(ny):
            hit = bvh.ray_cast(Vector((lo[0] + i * step, lo[1] + j * step, z0)), Vector((0.0, 0.0, 1.0)))
            if hit[0] is not None:
                z[i, j] = hit[0].z
    # a thin downward feature (a lip, a tyre shoulder) can fall between the rays: every subject vertex also
    # lowers the four grid points around it, so the grid is never above any vertex of the subject
    V = np.array([tuple(v) for v in verts])
    ci = np.clip(np.floor((V[:, :2] - lo) / step).astype(int), 0, [nx - 2, ny - 2])
    low = np.full((nx, ny), np.inf)
    for di in (0, 1):
        for dj in (0, 1):
            np.minimum.at(low, (ci[:, 0] + di, ci[:, 1] + dj), V[:, 2])
    z = np.where(np.isfinite(low) & ~(z <= low), low, z)
    z = underside_floor(underside_fill(z, grow))
    ok = ~np.isnan(z)
    idx = -np.ones((nx, ny), int)
    idx[ok] = np.arange(int(ok.sum()))
    pts = [(lo[0] + i * step, lo[1] + j * step, float(z[i, j])) for i, j in zip(*np.nonzero(ok))]
    faces = [(idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1])
             for i in range(nx - 1) for j in range(ny - 1)
             if ok[i, j] and ok[i + 1, j] and ok[i + 1, j + 1] and ok[i, j + 1]]
    me = bpy.data.meshes.new(UNDERSIDE)
    me.from_pydata(pts, [], [tuple(int(v) for v in f) for f in faces])
    ob = bpy.data.objects.new(UNDERSIDE, me)
    ctx.scene.collection.objects.link(ob)
    ob.parent = offset            # placed space: follows motion, yaw, sink, settle and squash
    ob.hide_render = True
    for flag in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(ob, flag, False)
    return ob


def _tree(ctx, offset, underside, margin):
    from engine.blender import gn
    from engine.blender.realism_rig import SWAY, SWAY_LEN
    from engine.blender.sway_nodes import SWAY_DISP, bend_point
    prof = ctx.profile
    t = gn.Tree("valora_rz_ground_conform")
    mw = t.object_transform(t.self_object())
    wp = t.point(t.position(), mw)
    u, ln = t.attr(SWAY), t.attr(SWAY_LEN)
    u_len = t.math("MULTIPLY", u, ln)
    d1 = t.attr(SWAY_DISP, "FLOAT_VECTOR")                       # foliage_sway's horizontal move (or 0)
    rest = t.vmath("SUBTRACT", wp, bend_point(t, u_len, d1))     # the point before any sway
    om = t.object_transform(offset)
    rx, ry, _ = t.xyz(t.point(rest, t.invert(om)))               # the blade's root in placed space
    lo, hi = prof.boundsMin, prof.boundsMax
    dx = t.math("MAXIMUM", t.math("MAXIMUM", t.math("SUBTRACT", float(lo[0]), rx), t.math("SUBTRACT", rx, float(hi[0]))), 0.0)
    dy = t.math("MAXIMUM", t.math("MAXIMUM", t.math("SUBTRACT", float(lo[1]), ry), t.math("SUBTRACT", ry, float(hi[1]))), 0.0)
    dist = t.math("SQRT", t.math("ADD", t.math("MULTIPLY", dx, dx), t.math("MULTIPLY", dy, dy)))
    cx, cy = float(0.5 * (lo[0] + hi[0])), float(0.5 * (lo[1] + hi[1]))
    out_p = t.vec(t.math("SUBTRACT", rx, cx), t.math("SUBTRACT", ry, cy), 0.0)
    td = t.node("FunctionNodeTransformDirection")
    t.feed(td.inputs["Direction"], out_p)
    t.feed(td.inputs["Transform"], om)
    out_w = t.vmath("NORMALIZE", t.vmath("MULTIPLY", td.outputs[0], t.vec(1.0, 1.0, 0.0)))
    near = t.math("MULTIPLY", t.math("GREATER_THAN", dist, 1e-6),
                  t.math("SUBTRACT", 1.0, t.smoothstep(0.0, margin, dist)))   # 0 inside the box, 1 at its edge
    lean = t.math("MULTIPLY", t.math("MULTIPLY", near, ctx.params["leanFrac"]),
                  t.math("MULTIPLY", ln, t.math("MULTIPLY", u, u)))
    d = t.vmath("ADD", d1, t.vmath("SCALE", out_w, scale=lean))
    new = t.vmath("ADD", rest, bend_point(t, u_len, d))
    # pressed: ray from well below the subject straight up to the underside heightfield (foliage-local space)
    info = t.node("GeometryNodeObjectInfo", transform_space="RELATIVE")
    t.feed(info.inputs["Object"], underside)
    nx_, ny_, nz_ = t.xyz(new)
    z0 = t.math("SUBTRACT", t.math("MINIMUM", nz_, 0.0), 2.0 * prof.sizeM[2] + 1.0)
    inv = t.invert(mw)
    rc = t.node("GeometryNodeRaycast")
    t.feed(rc.inputs["Target Geometry"], info.outputs["Geometry"])
    t.feed(rc.inputs["Source Position"], t.point(t.vec(nx_, ny_, z0), inv))
    up = t.node("FunctionNodeTransformDirection")
    t.feed(up.inputs["Direction"], t.vec(0.0, 0.0, 1.0))
    t.feed(up.inputs["Transform"], inv)
    t.feed(rc.inputs["Ray Direction"], t.vmath("NORMALIZE", up.outputs[0]))
    t.feed(rc.inputs["Ray Length"], t.math("MULTIPLY", t.math("SUBTRACT", nz_, z0),
                                           t.vmath("LENGTH", up.outputs[0])))
    hz = t.xyz(t.point(rc.outputs["Hit Position"], mw))[2]
    hit = rc.outputs["Is Hit"]
    far = t.math("ADD", t.math("MULTIPLY", hz, hit), t.math("MULTIPLY", NO_HIT, t.math("SUBTRACT", 1.0, hit)))
    # a blade (mesh island) with any point under the subject lies wholly under the lowest underside it meets:
    # clamping point by point let a blade straddling the silhouette run its stem through the subject
    isl = t.node("GeometryNodeInputMeshIsland").outputs["Island Index"]
    mm = t.node("GeometryNodeFieldMinAndMax", data_type="FLOAT", domain="POINT")
    t.feed(mm.inputs["Value"], far)
    t.feed(mm.inputs["Group ID"], isl)
    low = mm.outputs["Min"]
    pressed = t.vec(nx_, ny_, t.math("MINIMUM", nz_, t.math("SUBTRACT", low, CLEAR_M)))
    t.set_position(t.point(t.switch_vec(t.math("LESS_THAN", low, 0.5 * NO_HIT), new, pressed), inv))
    return t.finish()


def _count(objs, underside, offset, prof, margin):
    """(blades rooted under the underside at frame 1, blades rooted in the lean ring). A blade is a mesh
    island; its root is its points with valora_sway 0 (world contract, review item 5)."""
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from engine.blender.islands import vertex_islands
    from engine.blender.realism_rig import SWAY
    import bpy
    bvh = BVHTree.FromObject(underside, bpy.context.evaluated_depsgraph_get()) if len(underside.data.polygons) else None
    inv = np.array(offset.matrix_world.inverted())
    lo, hi = prof.boundsMin, prof.boundsMax
    n_in = n_ring = 0
    for o in objs:
        isl = vertex_islands(o)
        a = o.data.attributes.get(SWAY)
        if isl is None or a is None or not len(isl):
            continue
        sw = np.empty(len(o.data.vertices), np.float32)
        a.data.foreach_get("value", sw)
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        mo = np.array(o.matrix_world)
        wp = co.reshape(-1, 3) @ mo[:3, :3].T + mo[:3, 3]
        P = wp @ inv[:3, :3].T + inv[:3, 3]                       # placed space
        root = sw <= 1e-6
        cnt = np.bincount(isl[root], minlength=int(isl.max()) + 1)
        has = cnt > 0
        rx = np.bincount(isl[root], weights=P[root, 0], minlength=len(cnt))[has] / cnt[has]
        ry = np.bincount(isl[root], weights=P[root, 1], minlength=len(cnt))[has] / cnt[has]
        d = np.hypot(np.maximum(np.maximum(lo[0] - rx, rx - hi[0]), 0), np.maximum(np.maximum(lo[1] - ry, ry - hi[1]), 0))
        n_ring += int(((d > 0) & (d < margin)).sum())
        if bvh is not None:
            for x, y in zip(rx, ry):                               # the grid's own space is placed space
                n_in += bvh.ray_cast(Vector((x, y, -1e3)), Vector((0.0, 0.0, 1.0)))[0] is not None
    return n_in, n_ring


def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import FOLIAGE_TAG, record, rig
    prof, scene = ctx.profile, ctx.scene
    objs = [o for o in scene.objects if o.get(FOLIAGE_TAG) and o.type == "MESH"]
    _, offset = rig()
    scene.frame_set(1)
    margin = MARGIN_FRAC * prof.longest
    record("conform_margin_m", margin)
    underside = _underside(ctx, offset) if objs else None
    if underside is None:
        record("conform_pressed_blades", 0)
        record("conform_leaning_blades", 0)
        return
    n_in, n_ring = _count(objs, underside, offset, prof, margin)
    ng = _tree(ctx, offset, underside, margin)
    for o in objs:
        gn.add_modifier(o, ng, "valora_rz_ground_conform")
    record("conform_pressed_blades", n_in)
    record("conform_leaning_blades", n_ring)
    record("conform_underside_faces", len(underside.data.polygons))
