"""Weather compile probe (plan Tasks 64-69): report-only facts about the stateless weather objects, read from
the evaluated scene at <= 3 probe frames, no render. Runs inside Blender.

For every point-emitting weather object (rain, snow, droplets; their points before the instancing modifier):
the point count, how many lie inside the posed subject bounds (placed space through valora_realism_offset,
the no_particles_in_subject probe), whether a `velocity` attribute is present (METHODS R7), a hash of the
positions (the stateless proof compares it across fresh loads), and the count before the shelter delete."""
import hashlib

import bpy
import numpy as np

from engine.blender.realism_rig import rig
from engine.blender.weather_nodes import SHELTER

# object name -> (block, the instancing modifier to switch off so the points are read)
POINT_OBJECTS = {"valora_rain": ("effect/rain", "valora_rain_drops"),
                 "valora_snow": ("effect/snow", "valora_snow_flakes"),
                 "valora_droplets": ("effect/droplets", "valora_droplets_beads")}


def _points(ob, inst):
    mod = ob.modifiers.get(inst)
    if mod is not None:
        mod.show_viewport = False
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    try:
        n = len(me.vertices)
        co = np.empty(n * 3)
        me.vertices.foreach_get("co", co)
        m = np.array(ev.matrix_world)
        pts = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        vel = me.attributes.get("velocity")
        has_vel = vel is not None and vel.data_type == "FLOAT_VECTOR"
    finally:
        ev.to_mesh_clear()
        if mod is not None:
            mod.show_viewport = True
    return pts, has_vel


def _inside(pts, profile):
    if not len(pts):
        return 0
    _, offset = rig()
    inv = np.array(offset.matrix_world.inverted())
    P = pts @ inv[:3, :3].T + inv[:3, 3]
    lo, hi = np.array(profile.boundsMin), np.array(profile.boundsMax)
    return int(np.all((P > lo) & (P < hi), axis=1).sum())


def _digest(pts):
    return hashlib.sha256(np.round(pts, 6).astype(np.float64).tobytes()).hexdigest()[:16]


def _shelter_nodes(ob):
    for mod in ob.modifiers:
        ng = getattr(mod, "node_group", None)
        if ng is not None and SHELTER in ng.nodes:
            yield ng.nodes[SHELTER]


def point_probe(ob, inst, profile, frames):
    out = {"frames": {}}
    for f in list(frames)[:3]:
        bpy.context.scene.frame_set(int(f))
        pts, has_vel = _points(ob, inst)
        out["frames"][str(f)] = {"n": int(len(pts)), "inside": _inside(pts, profile), "velocity": bool(has_vel),
                                 "hash": _digest(pts)}
    nodes = list(_shelter_nodes(ob))
    if nodes and frames:
        bpy.context.scene.frame_set(int(list(frames)[0]))
        for n in nodes:
            n.mute = True
        out["preShelter"] = int(len(_points(ob, inst)[0]))
        for n in nodes:
            n.mute = False
    return out


def _on_surface(ob, inst, meshes):
    """droplets: the farthest bead centre from the evaluated subject surface (m) and the lowest bead normal z."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in meshes:
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        base = len(verts)
        verts += [eo.matrix_world @ v.co for v in me.vertices]
        polys += [[base + i for i in pl.vertices] for pl in me.polygons]
        eo.to_mesh_clear()
    bvh = BVHTree.FromPolygons(verts, polys)
    pts, _ = _points(ob, inst)
    far = max((bvh.find_nearest(Vector(q))[3] for q in pts), default=0.0)
    mod = ob.modifiers.get(inst)
    mod.show_viewport = False
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    a = me.attributes.get("valora_n")
    nz = None
    if a is not None and len(me.vertices):
        n = np.empty(len(me.vertices) * 3, np.float32)
        a.data.foreach_get("vector", n)
        nz = float(n.reshape(-1, 3)[:, 2].min())
    ev.to_mesh_clear()
    mod.show_viewport = True
    return {"surfaceMaxM": float(far), "minNz": nz}


def weather_probe(scene, profile, frames, meshes=()):
    f0, sub0 = scene.frame_current, scene.frame_subframe
    out = {}
    for name, (block, inst) in POINT_OBJECTS.items():
        ob = bpy.data.objects.get(name)
        if ob is not None:
            out[block.split("/")[1]] = point_probe(ob, inst, profile, frames)
    ob = bpy.data.objects.get("valora_droplets")
    if ob is not None and meshes and frames:
        scene.frame_set(int(list(frames)[0]))
        out["droplets"].update(_on_surface(ob, POINT_OBJECTS["valora_droplets"][1], meshes))
    cover = bpy.data.objects.get("valora_snow_cover")
    if cover is not None and "snow" in out:        # the layer lies on up-facing faces only (Task 67)
        from engine.physics.snow import UP_DOT
        ev = cover.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        nz = [pl.normal.z for pl in me.polygons]
        area = sum(pl.area for pl in me.polygons)
        up = sum(pl.area for pl in me.polygons if pl.normal.z > UP_DOT)
        out["snow"].update({"coverFaces": len(nz), "coverMinNz": float(min(nz)) if nz else None,
                            "coverUpShare": up / area if area else None})
        ev.to_mesh_clear()
    out["verdicts"] = verdicts(out)
    scene.frame_set(f0, subframe=sub0)
    return out


def verdicts(out):
    """Report-only verdicts (spec §4.8: thresholds calibrate before they gate): falling weather keeps out of
    the posed subject (droplets sit on it by design) and every point-emitting falling object carries velocity."""
    from engine.physics.probes import PARTICLE_TOL, particles_inside_share, velocity_present
    falling = {k: v for k, v in out.items() if k in ("rain", "snow")}
    res = {}
    for k, v in falling.items():
        fr = v["frames"]
        share = particles_inside_share({f: r["inside"] for f, r in fr.items()}, {f: r["n"] for f, r in fr.items()})
        res[k] = {"noParticlesInSubject": share <= PARTICLE_TOL, "insideShare": share}
    res["velocityPresent"] = velocity_present({k: all(r["velocity"] for r in v["frames"].values())
                                               for k, v in falling.items()})
    return res
