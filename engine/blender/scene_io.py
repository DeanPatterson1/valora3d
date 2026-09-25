"""The ONE GLB import (runs inside Blender). Ingest and the compiler both use it, with the same
importer settings, so the compiler's placed bounds can equal the SubjectProfile's."""
import bpy


def import_subject(glb):
    """Factory-reset the file, import the GLB, drop any cameras/lights it carried.
    Returns (new_objects, mesh_objects)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before = set(bpy.data.objects)
    # disable_bone_shape: otherwise every rigged import gains the importer's 2 m 'Icosphere'
    # bone-display mesh, which ingest measured as subject geometry and the compiler rendered.
    bpy.ops.import_scene.gltf(filepath=str(glb), disable_bone_shape=True)
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.type in ("CAMERA", "LIGHT")]:
        new.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    scene = bpy.context.scene  # the fps the clips were measured at; the compiler's timing changes it later
    scene["valora_import_fps"] = scene.render.fps / scene.render.fps_base
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


def _curves(action, slot):
    """F-curves of `action` (only the channels bound to `slot`, when given)."""
    curves = []
    if hasattr(action, "layers"):  # Blender 4.4+ layered actions
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    if slot is None or bag.slot == slot:
                        curves += list(bag.fcurves)
    else:
        curves = list(action.fcurves)
    return curves


def seamless(action, slot, tol=1e-3):
    """Whether the clip's last pose matches its first, so a loop has no visible snap. Location channels
    are left out: a walk that travels (root motion) still has a seamless limb cycle."""
    start, end = action.frame_range
    return all(abs(fc.evaluate(start) - fc.evaluate(end)) <= tol * max(1.0, abs(fc.evaluate(start)))
               for fc in _curves(action, slot) if not fc.data_path.endswith("location"))


def _key_times(action, slot):
    """Keyframe times of `action` (only the channels bound to `slot`, when given)."""
    curves = _curves(action, slot)
    times = {float(k.co[0]) for fc in curves for k in fc.keyframe_points}
    if not times:
        times = {float(action.frame_range[0]), float(action.frame_range[1])}
    return times


def animation_clips(scene, max_times=64, objects=None):
    """Every animation that can move geometry: (anim_data, action, slot, sorted key times).
    Sources: each object's active action and all its NLA strips, and shape-key animation on
    mesh data. Times are the actual keyframe times (a peak between evenly spaced frames would
    be missed), thinned evenly to max_times. `objects` limits the owners to the imported subject
    (the compiler's scene also holds the set, camera and rig); scene order is kept either way, so
    clip order matches ingest's."""
    allowed = None if objects is None else {o.as_pointer() for o in objects}
    owners, seen = [], set()
    for o in scene.objects:
        if allowed is not None and o.as_pointer() not in allowed:
            continue
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


def subject_actions(clips, fps):
    """The clips play_clip can index: one entry per action (a glTF animation driving several owners is
    ONE clip), in animation_clips order, kept by engine.clips.clip_kept - the same dedupe and filter
    ingest applies (blender_extract + measure._clips)."""
    from engine.clips import clip_kept
    out = []
    for _ad, action, _slot, _t in clips:
        if action not in out:
            out.append(action)
    return [a for a in out if clip_kept(a.frame_range[0], a.frame_range[1], fps)]


def rest_animation(scene, objs, frame=1):
    """Pose the subject at `frame` and take every imported animation off it, so a motion that is not
    play_clip renders the pose ingest measured, all video long (an active imported action would play
    once and hold its last pose). Returns the subject's clips as animation_clips listed them BEFORE
    silencing (silencing drops the active actions from that listing) and records them on the scene."""
    import json
    clips = animation_clips(scene, objects=objs)
    scene.frame_set(frame)
    for ad, _action, _slot, _t in clips:
        ad.action = None
        ad.use_nla = False
        for tr in ad.nla_tracks:
            tr.mute = True
    for o in objs:  # owners without a listed clip (an empty action) are silenced too
        for idb in (o, getattr(getattr(o, "data", None), "shape_keys", None)):
            ad = getattr(idb, "animation_data", None) if idb is not None else None
            if ad is not None:
                ad.action, ad.use_nla = None, False
    scene["valora_clips"] = json.dumps([
        {"owner": [type(ad.id_data).__name__, ad.id_data.name], "action": a.name,
         "slot": getattr(s, "identifier", "") if s is not None else ""} for ad, a, s, _t in clips])
    return clips


def rested_clips(scene):
    """rest_animation's record, resolved back to (anim_data, action, slot, None)."""
    import json
    out = []
    for c in json.loads(scene.get("valora_clips", "[]")):
        kind, name = c["owner"]
        idb = (bpy.data.shape_keys if kind == "Key" else bpy.data.objects).get(name)
        action = bpy.data.actions.get(c["action"])
        if idb is None or action is None or idb.animation_data is None:
            continue
        slot = next((s for s in getattr(action, "slots", []) if s.identifier == c["slot"]), None)
        out.append((idb.animation_data, action, slot, None))
    return out


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
