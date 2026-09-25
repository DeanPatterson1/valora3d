"""Compile-probe measurements (research/physics/BLOCKS.md §5 [C]): evaluated geometry at <= 3 frames,
no rendering. Pass/fail lives in engine/physics/probes.py (report-only until calibrated)."""
import bpy
import numpy as np
from mathutils import Vector

from engine.blender.realism_rig import FOLIAGE_TAG, SPIN, SWAY, SWAY_LEN, SWAY_PIVOT, TYRE, UNSPRUNG, rig

FLAT_TOL_M = 0.0005   # a tyre vertex within 0.5 mm of the tyre's lowest point is on the patch
UNDER_TOL_M = 0.0005  # a foliage point up to 0.5 mm above the subject's underside is not inside it
CLEAR_OF_BOX = 0.05   # stretch is read on blades wholly 5% of the longest side clear of the subject's box
COVER_Z = 0.0005      # a foliage point at most 0.5 mm above the world ground is in the cover the subject sank into
EDGE_SAMPLES = 9      # points per foliage edge, both ends included (foliageInSubject)


def _world(ev, me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    m = np.array(ev.matrix_world)
    return co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]


def sample_wind(points, frame):
    """Wind vectors (m/s) of the scene's valora_wind group at points, at one frame (tests and wind_coherent)."""
    from engine.blender.gn import Tree, add_modifier
    scene = bpy.context.scene
    me = bpy.data.meshes.new("valora_wind_probe")
    me.from_pydata([tuple(p) for p in points], [], [])
    ob = bpy.data.objects.new("valora_wind_probe", me)
    scene.collection.objects.link(ob)
    t = Tree("valora_wind_probe")
    t.store("w", t.group(bpy.data.node_groups["valora_wind"], Position=t.position()).outputs["Wind"], "FLOAT_VECTOR")
    add_modifier(ob, t.finish(), "probe")
    f0 = scene.frame_current
    scene.frame_set(frame)
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.to_mesh()
    w = np.empty(len(m.vertices) * 3)
    m.attributes["w"].data.foreach_get("vector", w)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    scene.frame_set(f0)
    return w.reshape(-1, 3).tolist()


def realism_probe(scene, meshes, profile, frames):
    out, f0, isl_cache = {}, scene.frame_current, {}
    motion, _ = rig()
    for f in list(frames)[:3]:
        whole = int(np.floor(f))       # a probe frame may be a subframe (a centred shutter samples n + 0.5)
        scene.frame_set(whole, subframe=float(f) - whole)
        deps = bpy.context.evaluated_depsgraph_get()
        zmin, tyres, cos = np.inf, {}, []
        acc = {"body": 0.0, "nb": 0, "uns": 0.0, "nu": 0}
        for o in meshes:
            ev = o.evaluated_get(deps)
            me = ev.to_mesh()
            try:
                if not len(me.vertices):
                    continue
                co = _world(ev, me)
                zmin = min(zmin, float(co[:, 2].min()))
                cos.append(co)
                u = me.attributes.get(UNSPRUNG)
                un = np.zeros(len(me.vertices), np.int32)
                if u is not None:
                    u.data.foreach_get("value", un)
                acc["body"] += float(co[un == 0, 2].sum())
                acc["nb"] += int((un == 0).sum())
                acc["uns"] += float(co[un > 0, 2].sum())
                acc["nu"] += int((un > 0).sum())
                a = me.attributes.get(TYRE)
                if a is not None and profile.wheels:
                    t = np.empty(len(me.vertices), np.int32)
                    a.data.foreach_get("value", t)
                    for i in np.unique(t[t > 0]):
                        tyres.setdefault(int(i) - 1, []).append(co[t == i])
            finally:
                ev.to_mesh_clear()
        fwd = motion.matrix_world.to_3x3() @ Vector((profile.vehicle or {}).get("forwardAxis", [0.0, 1.0, 0.0]))
        rec = {"minZ": zmin, "tyres": {}}
        low = np.vstack([c[c[:, 2] <= zmin + FLAT_TOL_M] for c in cos]) if cos else np.empty((0, 3))
        rec["footprintM"] = float(max(np.ptp(low[:, 0]), np.ptp(low[:, 1]))) if len(low) >= 3 else 0.0
        rec["bodyMeanZ"] = acc["body"] / acc["nb"] if acc["nb"] else None
        rec["unsprungMeanZ"] = acc["uns"] / acc["nu"] if acc["nu"] else None
        rec["drivers"] = {o.name: list(o.location) for o in scene.objects if o.name.startswith("valora_rz_")}
        _, offset = rig()
        rec["offset"] = {"loc": list(offset.location), "scale": list(offset.scale)}
        for i, pts in sorted(tyres.items()):
            p = np.vstack(pts)
            lo = float(p[:, 2].min())
            flat = p[p[:, 2] <= lo + FLAT_TOL_M]
            along = flat @ np.array(fwd)
            rec["tyres"][str(i)] = {"minZ": lo, "flatN": int(len(flat)),
                                    "flatLenM": float(along.max() - along.min()) if len(flat) else 0.0}
        spin = _spin_verts(meshes, deps, motion)
        if spin:
            rec["wheelVerts"] = spin
        rec["sway"] = _sway(scene, deps)
        rec["rigidMaxDispM"] = _rigid_disp(meshes, deps)
        dust = _dust(profile)
        if dust is not None:
            rec["dust"] = dust
        rec["foliageInSubject"] = _foliage_in_subject(scene, deps, meshes)
        if any(o.get(FOLIAGE_TAG) for o in scene.objects):
            rec["conform"] = _conform(scene, deps, offset, profile, isl_cache)
        out[str(f)] = rec
    scene.frame_set(f0)
    return out


def _evaluated(o, deps):
    ev = o.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        return _world(ev, me)
    finally:
        ev.to_mesh_clear()


SPIN_VERTS = 24       # wheel vertices recorded per wheel (wheelVerts)


def _spin_verts(meshes, deps, motion):
    """{wheel index: up to SPIN_VERTS evaluated spin-tagged vertices, in the motion empty's local space}:
    the path's own move is taken out, so two frames differ only where a wheel turned (or a deformer moved it)."""
    inv = np.array(motion.matrix_world.inverted())
    out = {}
    for o in meshes:
        a = o.data.attributes.get(SPIN)
        if a is None or not len(o.data.vertices):
            continue
        tag = np.empty(len(o.data.vertices), np.int32)
        a.data.foreach_get("value", tag)
        cur = _evaluated(o, deps)
        if len(cur) != len(tag):
            continue
        loc = cur @ inv[:3, :3].T + inv[:3, 3]
        for i in np.unique(tag[tag > 0]):
            have = out.setdefault(str(int(i) - 1), [])
            idx = np.flatnonzero(tag == i)
            idx = idx[np.linspace(0, len(idx) - 1, min(len(idx), SPIN_VERTS)).astype(int)]
            have += loc[idx].tolist()[:SPIN_VERTS - len(have)]
    return out


def _sway(scene, deps):
    """Mean rest -> evaluated world displacement of every swaying tip vertex (valora_sway >= 0.9; GN keeps
    the attribute and the vertex order): wind_coherent (BLOCKS §5) reads its direction."""
    disp, cnt, stretch, angle = np.zeros(3), 0, 0.0, 0.0
    for o in [o for o in scene.objects if o.type == "MESH" and o.data.attributes.get(SWAY) is not None]:
        sw = np.empty(len(o.data.vertices), np.float32)
        o.data.attributes[SWAY].data.foreach_get("value", sw)
        rest = _rest(o)
        cur = _evaluated(o, deps)
        tip = sw >= 0.9
        disp += (cur[tip] - rest[tip]).sum(axis=0)
        cnt += int(tip.sum())
        if o.data.attributes.get(SWAY_PIVOT) is not None:     # dangling parts: rigid about the pivot
            piv = np.empty(len(o.data.vertices) * 3, np.float32)
            o.data.attributes[SWAY_PIVOT].data.foreach_get("vector", piv)
            ln = np.empty(len(o.data.vertices), np.float32)
            o.data.attributes[SWAY_LEN].data.foreach_get("value", ln)
            m = np.array(o.matrix_world)
            pw = piv.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
            on = ln > 0
            a, b = rest[on] - pw[on], cur[on] - pw[on]
            ra, rb = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1)
            stretch = max(stretch, float((np.abs(rb - ra) / ln[on]).max()))
            far = ra > 0.5 * ln[on]
            if far.any():
                cos = (a[far] * b[far]).sum(axis=1) / (ra[far] * rb[far])
                angle = max(angle, float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))).max()))
    return {"n": cnt, "meanDisp": (disp / cnt).tolist() if cnt else [0.0, 0.0, 0.0],
            "maxStretchFrac": stretch, "maxAngleDeg": angle}


def _dust(profile):
    """PH-03 [C]: shaft_dust motes with a non-zero radius, and how many of them sit inside the subject's
    bounds (+10%). The points modifier is switched off for the read so the evaluated mesh keeps its vertices
    and the radius attribute."""
    dust = bpy.data.objects.get("valora_rz_dust")
    if dust is None:
        return None
    from engine.geometry import point_in_box
    mod = dust.modifiers["valora_rz_dust_points"]
    mod.show_viewport = False
    ev = dust.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    try:
        pts = _world(ev, me)
        rad = np.empty(len(me.vertices), np.float32)
        me.attributes["valora_dust_r"].data.foreach_get("value", rad)
    finally:
        ev.to_mesh_clear()
        mod.show_viewport = True
    vis = pts[rad > 0]
    out = {"visible": int(len(vis)), "visibleInSubject": int(sum(
        point_in_box(tuple(p), profile.boundsMin, profile.boundsMax, 0.10) for p in vis)), "edgeRFrac": None}
    # edgeRFrac stays None (a failing reading, never a passing 0) when the fade record or the edge samples
    # are missing: nothing was measured
    box, full, fade = (bpy.context.scene.get(f"valora_rz_dust_{k}") for k in ("box", "radius_m", "fade_m"))
    if box is not None and full and fade:
        lo, hi = np.array(box[:3]), np.array(box[3:])
        edge = np.minimum(pts - lo, hi - pts).min(axis=1) < 0.1 * fade     # within a tenth of the fade band
        out["edgeN"] = int(edge.sum())
        if edge.any():
            out["edgeRFrac"] = float(rad[edge].max() / full)
    return out


def _rest(o):
    co = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", co)
    m = np.array(o.matrix_world)
    return co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]


def _rigid_disp(meshes, deps):
    """Largest rest -> evaluated move of a subject vertex that no sway tags (a strap's body stays put).
    Only meaningful on subjects without other deformers (tyre, soft_rest)."""
    worst = 0.0
    for o in meshes:
        if not len(o.data.vertices):
            continue
        ln = np.zeros(len(o.data.vertices), np.float32)
        if o.data.attributes.get(SWAY_LEN) is not None:
            o.data.attributes[SWAY_LEN].data.foreach_get("value", ln)
        cur = _evaluated(o, deps)
        if len(cur) != len(ln):
            continue
        still = ln == 0
        if still.any():
            worst = max(worst, float(np.linalg.norm(cur[still] - _rest(o)[still], axis=1).max()))
    return worst


def _subject_bvh(meshes, deps):
    """(world-space BVH of the evaluated subject, its world bounds lo, hi) or (None, None, None)."""
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for o in meshes:
        ev = o.evaluated_get(deps)
        me = ev.to_mesh()
        try:
            m = ev.matrix_world
            base = len(verts)
            verts += [m @ v.co for v in me.vertices]
            polys += [[base + i for i in p.vertices] for p in me.polygons]
        finally:
            ev.to_mesh_clear()
    if not polys:
        return None, None, None
    a = np.array([tuple(v) for v in verts])
    return BVHTree.FromPolygons(verts, polys), a.min(axis=0), a.max(axis=0)


def _foliage_in_subject(scene, deps, meshes):
    """Evaluated foliage points that stand above the subject's underside (UNDER_TOL_M): a ray from below
    the subject straight up to the point meets the subject first. Points are sampled along every edge
    (EDGE_SAMPLES), not just at vertices: a three-vertex blade taller than the subject has no vertex inside
    it though its stem runs straight through. Grass standing under a car's floor is not inside the car
    (review item 3); points in the cover layer (world z <= COVER_Z: contact_ground sinks the subject into it)
    are not counted."""
    fol = [o for o in scene.objects if o.type == "MESH" and o.get(FOLIAGE_TAG)]
    if not fol:
        return 0
    bvh, lo, hi = _subject_bvh(meshes, deps)
    if bvh is None:
        return 0
    s = np.linspace(0.0, 1.0, EDGE_SAMPLES)[:, None, None]
    z0 = float(lo[2]) - 1.0
    n = 0
    for o in fol:
        ev = o.evaluated_get(deps)
        me = ev.to_mesh()
        try:
            cur = _world(ev, me)
            ed = np.empty(len(me.edges) * 2, np.int64)
            me.edges.foreach_get("vertices", ed)
        finally:
            ev.to_mesh_clear()
        ed = ed.reshape(-1, 2)
        pts = (cur[ed[:, 0]][None] * (1.0 - s) + cur[ed[:, 1]][None] * s).reshape(-1, 3)
        box = ((pts[:, 0] >= lo[0]) & (pts[:, 0] <= hi[0]) & (pts[:, 1] >= lo[1]) & (pts[:, 1] <= hi[1])
               & (pts[:, 2] >= lo[2]) & (pts[:, 2] > COVER_Z))
        for x, y, z in pts[box]:
            length = z - z0 - UNDER_TOL_M
            hit = bvh.ray_cast(Vector((x, y, z0)), Vector((0.0, 0.0, 1.0)), length)
            n += hit[0] is not None
    return int(n)


def _conform(scene, deps, offset, profile, cache):
    """ground_conform facts per frame (review items 4, 13): the largest change of any foliage point's
    distance from its blade root (/ blade length), on blades wholly CLEAR_OF_BOX clear of the subject's box
    (a pressed blade is shortened on purpose); how many blades root in the lean ring and their
    tips' mean outward move (m); the median height of tips whose root is inside the subject's box; the mean
    move vector of the tips of blades rooted outside it (sway and lean, never the press). A blade
    is a mesh island, its root the mean of its valora_sway 0 points (the world contract)."""
    from engine.blender.islands import vertex_islands
    fol = [o for o in scene.objects if o.type == "MESH" and o.get(FOLIAGE_TAG)
           and o.data.attributes.get(SWAY) is not None]
    margin = float(scene.get("valora_rz_conform_margin_m", 0.15 * profile.longest))
    lo, hi = profile.boundsMin, profile.boundsMax
    inv = np.array(offset.matrix_world.inverted())
    rot = np.array(offset.matrix_world)[:3, :3]
    stretch, ring_n, ring_out, inner, outer = 0.0, 0, [], [], np.zeros((0, 3))
    for o in fol:
        if o.name not in cache:
            cache[o.name] = vertex_islands(o)
        isl = cache[o.name]
        if isl is None:
            continue
        nv = len(o.data.vertices)
        sw, ln = np.empty(nv, np.float32), np.empty(nv, np.float32)
        o.data.attributes[SWAY].data.foreach_get("value", sw)
        o.data.attributes[SWAY_LEN].data.foreach_get("value", ln)
        rest, cur = _rest(o), _evaluated(o, deps)
        if len(cur) != nv:
            continue
        root = sw <= 1e-6
        cnt = np.bincount(isl[root], minlength=int(isl.max()) + 1).astype(float)
        cnt[cnt == 0] = np.nan
        rr = np.stack([np.bincount(isl[root], weights=rest[root, k], minlength=len(cnt)) for k in range(3)], 1) / cnt[:, None]
        rc = np.stack([np.bincount(isl[root], weights=cur[root, k], minlength=len(cnt)) for k in range(3)], 1) / cnt[:, None]
        P = rr @ inv[:3, :3].T + inv[:3, 3]
        d = np.hypot(np.maximum(np.maximum(lo[0] - P[:, 0], P[:, 0] - hi[0]), 0),
                     np.maximum(np.maximum(lo[1] - P[:, 1], P[:, 1] - hi[1]), 0))
        outside = d > 0
        Pv = rest @ inv[:3, :3].T + inv[:3, 3]
        dv = np.hypot(np.maximum(np.maximum(lo[0] - Pv[:, 0], Pv[:, 0] - hi[0]), 0),
                      np.maximum(np.maximum(lo[1] - Pv[:, 1], Pv[:, 1] - hi[1]), 0))
        dmin = np.full(len(cnt), np.inf)
        np.minimum.at(dmin, isl, dv)
        free = dmin > CLEAR_OF_BOX * profile.longest            # no point of the blade can be pressed
        v = (~root) & (ln > 0) & free[isl] & ~np.isnan(rr[isl, 0])
        if v.any():
            a = np.linalg.norm(rest[v] - rr[isl[v]], axis=1)
            b = np.linalg.norm(cur[v] - rc[isl[v]], axis=1)
            stretch = max(stretch, float((np.abs(b - a) / ln[v]).max()))
        c = np.array([0.5 * (lo[0] + hi[0]), 0.5 * (lo[1] + hi[1]), 0.0])
        outp = P - c
        outp[:, 2] = 0.0
        outw = outp @ rot.T
        outw[:, 2] = 0.0
        outw /= np.maximum(np.linalg.norm(outw, axis=1, keepdims=True), 1e-12)
        ring = outside & (d < margin)
        tip = sw >= 0.9
        rt = tip & ring[isl]
        ring_n += int(ring.sum())
        ring_out += list(((cur[rt] - rest[rt]) * outw[isl[rt]]).sum(axis=1))
        inner += list(cur[tip & ~outside[isl] & ~np.isnan(rr[isl, 0]), 2])
        ot = tip & free[isl]
        outer = np.vstack([outer, cur[ot] - rest[ot]])
    return {"stretchMax": stretch, "ringN": ring_n,
            "ringMeanOut": float(np.mean(ring_out)) if ring_out else 0.0,
            "innerTipMedianZ": float(np.median(inner)) if inner else None,
            "outerTipMeanDisp": outer.mean(axis=0).tolist() if len(outer) else [0.0, 0.0, 0.0]}
