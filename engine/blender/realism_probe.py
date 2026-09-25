"""Compile-probe measurements (research/physics/BLOCKS.md §5 [C]): evaluated geometry at <= 3 frames,
no rendering. Pass/fail lives in engine/physics/probes.py (report-only until calibrated)."""
import bpy
import numpy as np
from mathutils import Vector

from engine.blender.realism_rig import TYRE, UNSPRUNG, rig

FLAT_TOL_M = 0.0005   # a tyre vertex within 0.5 mm of the tyre's lowest point is on the patch


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
        zmin, tyres = np.inf, {}
        acc = {"body": 0.0, "nb": 0, "uns": 0.0, "nu": 0}
        for o in meshes:
            ev = o.evaluated_get(deps)
            me = ev.to_mesh()
            try:
                if not len(me.vertices):
                    continue
                co = _world(ev, me)
                zmin = min(zmin, float(co[:, 2].min()))
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
        out[str(f)] = rec
    scene.frame_set(f0)
    return out
