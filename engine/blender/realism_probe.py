"""Compile-probe measurements (research/physics/BLOCKS.md §5 [C]): evaluated geometry at <= 3 frames,
no rendering. Pass/fail lives in engine/physics/probes.py (report-only until calibrated)."""
import bpy
import numpy as np
from mathutils import Vector

from engine.blender.realism_rig import FOLIAGE_TAG, SWAY, TYRE, UNSPRUNG, rig

FLAT_TOL_M = 0.0005   # a tyre vertex within 0.5 mm of the tyre's lowest point is on the patch
FOLIAGE_Z = 0.003     # a foliage vertex below 3 mm (world z) lies pressed on the ground
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
    out, f0 = {}, scene.frame_current
    motion, _ = rig()
    for f in list(frames)[:3]:
        scene.frame_set(f)
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
        rec["sway"] = _sway(scene, deps)
        rec["foliageInSubject"] = _foliage_in_subject(scene, deps, offset, profile)
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


def _sway(scene, deps):
    """Mean rest -> evaluated world displacement of every swaying tip vertex (valora_sway >= 0.9; GN keeps
    the attribute and the vertex order): wind_coherent (BLOCKS §5) reads its direction."""
    disp, cnt = np.zeros(3), 0
    for o in [o for o in scene.objects if o.type == "MESH" and o.data.attributes.get(SWAY) is not None]:
        sw = np.empty(len(o.data.vertices), np.float32)
        o.data.attributes[SWAY].data.foreach_get("value", sw)
        rest = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", rest)
        m = np.array(o.matrix_world)
        rest = rest.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        cur = _evaluated(o, deps)
        tip = sw >= 0.9
        disp += (cur[tip] - rest[tip]).sum(axis=0)
        cnt += int(tip.sum())
    return {"n": cnt, "meanDisp": (disp / cnt).tolist() if cnt else [0.0, 0.0, 0.0]}


def _foliage_in_subject(scene, deps, offset, profile):
    """Evaluated foliage points above FOLIAGE_Z (world z; the sink lifts pressed blades a few mm in placed
    space) that fall inside the subject's placed bounds. Points are sampled along every edge
    (EDGE_SAMPLES), not just at vertices: a three-vertex blade taller than the subject has no vertex
    inside it though its stem runs straight through."""
    from engine.geometry import point_in_box
    inv = np.array(offset.matrix_world.inverted())
    s = np.linspace(0.0, 1.0, EDGE_SAMPLES)[:, None, None]
    n = 0
    for o in [o for o in scene.objects if o.type == "MESH" and o.get(FOLIAGE_TAG)]:
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
        up = pts[pts[:, 2] > FOLIAGE_Z]
        placed = up @ inv[:3, :3].T + inv[:3, 3]
        n += sum(point_in_box(tuple(p), profile.boundsMin, profile.boundsMax, 0.0) for p in placed)
    return int(n)
