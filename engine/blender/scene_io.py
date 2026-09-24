"""The ONE GLB import (runs inside Blender). Ingest and the compiler both use it, with the same
importer settings, so the compiler's placed bounds can equal the SubjectProfile's."""
import bpy


def import_subject(glb):
    """Factory-reset the file, import the GLB, drop any cameras/lights it carried.
    Returns (new_objects, mesh_objects)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.type in ("CAMERA", "LIGHT")]:
        new.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    return new, [o for o in new if o.type == "MESH"]


def world_bounds(meshes, depsgraph):
    """Per-axis (min, max) numpy arrays over evaluated world-space vertices. Ingest and the
    compiler's placement guard (Task 19) share it, so they measure the same thing."""
    import numpy as np
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for obj in meshes:
        ev = obj.evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        n = len(mesh.vertices)
        if n:
            co = np.empty(n * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", co)
            m = np.array(ev.matrix_world, dtype=np.float64)
            w = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
            lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
        ev.to_mesh_clear()
    return lo, hi


def _key_times(action, slot):
    """Keyframe times of `action` (only the channels bound to `slot`, when given)."""
    curves = []
    if hasattr(action, "layers"):  # Blender 4.4+ layered actions
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    if slot is None or bag.slot == slot:
                        curves += list(bag.fcurves)
    else:
        curves = list(action.fcurves)
    times = {float(k.co[0]) for fc in curves for k in fc.keyframe_points}
    if not times:
        times = {float(action.frame_range[0]), float(action.frame_range[1])}
    return times


def animation_clips(scene, max_times=64):
    """Every animation that can move geometry: (anim_data, action, slot, sorted key times).
    Sources: each object's active action and all its NLA strips, and shape-key animation on
    mesh data. Times are the actual keyframe times (a peak between evenly spaced frames would
    be missed), thinned evenly to max_times."""
    owners, seen = [], set()
    for o in scene.objects:
        ids = [o]
        key = getattr(getattr(o, "data", None), "shape_keys", None)
        if key is not None:
            ids.append(key)
        for idb in ids:
            if idb.animation_data is not None and idb.as_pointer() not in seen:
                seen.add(idb.as_pointer())
                owners.append(idb.animation_data)
    clips, done = [], set()
    for ad in owners:
        cands = [(ad.action, getattr(ad, "action_slot", None))] if ad.action else []
        for track in ad.nla_tracks:
            cands += [(st.action, getattr(st, "action_slot", None)) for st in track.strips if st.action]
        for action, slot in cands:
            k = (ad.as_pointer(), action.as_pointer(), slot.as_pointer() if slot is not None else 0)
            if k in done:
                continue
            done.add(k)
            t = sorted(_key_times(action, slot))
            if len(t) > max_times:
                t = [t[round(j * (len(t) - 1) / (max_times - 1))] for j in range(max_times)]
            clips.append((ad, action, slot, t))
    return clips


def posed_bounds(scene, meshes, max_times=64):
    """(lo, hi, posed, animated): world bounds unioned over every clip's key poses, each clip
    evaluated alone as the active action (NLA off for its owner). Restores the scene afterwards.
    Rigs swing out of their rest bounds; framing the rest pose alone would crop them."""
    import math
    import numpy as np
    clips = animation_clips(scene, max_times)
    f0, sub0 = scene.frame_current, scene.frame_subframe
    lo, hi = world_bounds(meshes, bpy.context.evaluated_depsgraph_get())
    for ad, action, slot, times in clips:
        saved = (ad.action, getattr(ad, "action_slot", None), ad.use_nla)
        ad.action = action
        if slot is not None and getattr(ad, "action_slot", slot) != slot:
            ad.action_slot = slot
        ad.use_nla = False
        for t in times:
            scene.frame_set(int(math.floor(t)), subframe=t - math.floor(t))
            flo, fhi = world_bounds(meshes, bpy.context.evaluated_depsgraph_get())
            lo, hi = np.minimum(lo, flo), np.maximum(hi, fhi)
        ad.action = saved[0]
        if saved[0] is not None and saved[1] is not None:
            ad.action_slot = saved[1]
        ad.use_nla = saved[2]
    scene.frame_set(f0, subframe=sub0)
    return lo, hi, bool(clips), bool(clips)
