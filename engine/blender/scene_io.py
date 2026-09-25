"""The ONE GLB import (runs inside Blender). Ingest and the compiler both use it, with the same
importer settings, so the compiler's placed bounds can equal the SubjectProfile's."""
import bpy


RESERVED = "valora_"   # every engine-made datablock name and custom property starts with this
_ID_KINDS = ("objects", "meshes", "materials", "node_groups", "images", "textures", "actions", "armatures",
             "cameras", "lights", "curves", "collections", "shape_keys", "worlds")


def _reserved(name):
    return isinstance(name, str) and name.lower().startswith(RESERVED)


def _strip_reserved_props(idb):
    for k in [k for k in idb.keys() if _reserved(k)]:
        del idb[k]


def reserve_engine_names(before):
    """An upload can never claim an engine name (review chunk1 #1). The engine finds its own datablocks by
    name (valora_motion, valora_wind_field, valora_wind, valora_rz_*...) and custom properties
    (valora_ground, valora_block, scene valora_*): an imported datablock named valora_* is renamed upload_*
    and every valora_* custom property the importer copied from glTF extras is dropped, on the new
    datablocks and on the scene. `before` = {kind: set of pointers} taken before the import."""
    renamed = []
    for kind in _ID_KINDS:
        coll = getattr(bpy.data, kind, None)
        if coll is None:
            continue
        for idb in [i for i in coll if i.as_pointer() not in before.get(kind, ())]:
            if _reserved(idb.name):
                old = idb.name
                idb.name = "upload_" + old
                renamed.append(old)
            _strip_reserved_props(idb)
            data = getattr(idb, "data", None) if kind == "objects" else None
            if data is not None and hasattr(data, "keys"):
                _strip_reserved_props(data)
    _strip_reserved_props(bpy.context.scene)   # a factory-reset scene has none: every valora_* key is the upload's
    return renamed


def import_subject(glb):
    """Factory-reset the file, import the GLB, drop any cameras/lights it carried, and reserve the
    engine's names (reserve_engine_names). Returns (new_objects, mesh_objects).
    Every model reaches Blender's importer through here, so the upload preflight is re-run on the exact path
    imported: a job.json/argv naming a file never preflighted, or one swapped after the host-side check, is
    refused (IngestRejected) before bpy opens it or any file it would reference."""
    from engine.ingest.run import preflight
    preflight(glb)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before = set(bpy.data.objects)
    ids = {k: {i.as_pointer() for i in getattr(bpy.data, k)} for k in _ID_KINDS if hasattr(bpy.data, k)}
    # disable_bone_shape: otherwise every rigged import gains the importer's 2 m 'Icosphere'
    # bone-display mesh, which ingest measured as subject geometry and the compiler rendered.
    bpy.ops.import_scene.gltf(filepath=str(glb), disable_bone_shape=True)
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.type in ("CAMERA", "LIGHT")]:
        new.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    reserve_engine_names(ids)
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
    are left out: a walk that travels (root motion) still has a seamless limb cycle. Root travel is its
    own fact (root_travel -> profile rootMotion) and play_clip loops such a clip in place (loop_in_place)."""
    start, end = action.frame_range
    return all(abs(fc.evaluate(start) - fc.evaluate(end)) <= tol * max(1.0, abs(fc.evaluate(start)))
               for fc in _curves(action, slot) if not fc.data_path.endswith("location"))


def _root_owner(ad):
    """The Object an animation_data belongs to (None for shape-key data: it carries no root)."""
    idb = ad.id_data
    return idb if isinstance(idb, bpy.types.Object) else None


def _root_bones(obj):
    """Names of an armature's parentless bones (the ones that carry a walk's root motion)."""
    if obj is None or obj.type != "ARMATURE":
        return []
    return [b.name for b in obj.data.bones if b.parent is None]


def _root_points(obj):
    """World positions of what carries root motion: the object's origin and its root bones' heads."""
    pts = [obj.matrix_world.translation.copy()]
    pts += [obj.matrix_world @ obj.pose.bones[n].head for n in _root_bones(obj)]
    return pts


def root_travel(scene, ad, action, slot):
    """Horizontal (world XY) distance the clip's roots end from where they start, evaluated with the clip
    as the owner's only animation. A walk with root motion travels; an in-place cycle returns (review P1).
    Restores the owner's animation and the frame."""
    import math
    return math.hypot(*root_shift(scene, ad, action, slot))


def root_shift(scene, ad, action, slot):
    """(dx, dy) world XY end-minus-start of the root that travels furthest over the clip (root_travel's
    vector): the direction a walk played once or ping-ponged covers ground in. Restores animation and frame."""
    obj = _root_owner(ad)
    if obj is None:
        return (0.0, 0.0)
    import math
    saved = (ad.action, getattr(ad, "action_slot", None), ad.use_nla)
    f0, sub0 = scene.frame_current, scene.frame_subframe
    ad.action = action
    if slot is not None and getattr(ad, "action_slot", slot) != slot:
        ad.action_slot = slot
    ad.use_nla = False
    ends = []
    for t in action.frame_range:
        scene.frame_set(int(math.floor(t)), subframe=t - math.floor(t))
        ends.append(_root_points(obj))
    ad.action = saved[0]
    if saved[0] is not None and saved[1] is not None:
        ad.action_slot = saved[1]
    ad.use_nla = saved[2]
    scene.frame_set(f0, subframe=sub0)
    moves = [(b.x - a.x, b.y - a.y) for a, b in zip(*ends)]
    return max(moves, key=lambda m: math.hypot(*m), default=(0.0, 0.0))


def _root_channels(obj, action, slot):
    """[(3x3 world matrix of the channel's local axes, {axis index: fcurve})] for each root location
    channel of `action`: the object's own location and each root bone's pose location."""
    from mathutils import Matrix
    curves = _curves(action, slot)
    out = []
    base = (obj.parent.matrix_world @ obj.matrix_parent_inverse).to_3x3() if obj.parent else Matrix.Identity(3)
    groups = [("location", base)]
    arm = obj.matrix_world.to_3x3()
    groups += [(f'pose.bones["{n}"].location', arm @ obj.data.bones[n].matrix_local.to_3x3())
               for n in _root_bones(obj)]
    for path, m in groups:
        fcs = {fc.array_index: fc for fc in curves if fc.data_path == path}
        if fcs:
            out.append((m, fcs))
    return out


def loop_in_place(ad, action, slot):
    """Take the net horizontal travel out of the clip's root location channels (review P1): each channel's
    world-horizontal end-minus-start is removed along a linear ramp over the clip, so the last pose meets
    the first. Vertical bob and in-cycle sway are kept. Edits `action` in place (the compiler's own import).
    Returns the horizontal travel removed (world units; 0 when there is no root channel)."""
    import math
    from mathutils import Vector
    obj = _root_owner(ad)
    if obj is None:
        return 0.0
    start, end = action.frame_range
    span = max(end - start, 1e-9)
    removed = 0.0
    for m, fcs in _root_channels(obj, action, slot):
        net = Vector([fcs[k].evaluate(end) - fcs[k].evaluate(start) if k in fcs else 0.0 for k in range(3)])
        w = m @ net
        flat = Vector((w.x, w.y, 0.0))
        try:
            corr = m.inverted() @ flat            # the local offsets that make that horizontal move
        except ValueError:                        # a degenerate (zero-scale) channel space moves nothing
            continue
        removed = max(removed, math.hypot(w.x, w.y))
        for k, fc in fcs.items():
            c = corr[k]
            if abs(c) < 1e-12:
                continue
            for kp in fc.keyframe_points:         # a linear ramp keeps Bezier segments exact (affine)
                for pt in (kp.co, kp.handle_left, kp.handle_right):
                    pt[1] -= c * (pt[0] - start) / span
            fc.update()
    return removed


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


def posed_bounds(scene, meshes, max_times=64, in_place=()):
    """(lo, hi, posed, animated): world bounds unioned over every clip's key poses, each clip
    evaluated alone as the active action (NLA off for its owner). Restores the scene afterwards.
    Rigs swing out of their rest bounds; framing the rest pose alone would crop them.
    Clips named in `in_place` (action names: root-motion walks) are measured as play_clip loops them,
    on a copy with loop_in_place applied: the travel box would centre and frame the subject half its
    travel away from where it walks on the spot."""
    import math
    import numpy as np
    clips = animation_clips(scene, max_times)
    f0, sub0 = scene.frame_current, scene.frame_subframe
    lo, hi = world_bounds(meshes, bpy.context.evaluated_depsgraph_get())
    for ad, action, slot, times in clips:
        tmp = None
        if action.name in in_place:
            tmp = action.copy()
            if slot is not None:
                slot = next((s for s in getattr(tmp, "slots", []) if s.identifier == slot.identifier), slot)
            loop_in_place(ad, tmp, slot)
            action = tmp
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
        if tmp is not None:
            bpy.data.actions.remove(tmp)
    scene.frame_set(f0, subframe=sub0)
    return lo, hi, bool(clips), bool(clips)
