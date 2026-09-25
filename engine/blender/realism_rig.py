"""The subject hierarchy every realism block builds on, and the helpers they share (runs inside Blender).

    valora_motion             motion blocks keyframe this (translate / yaw)
     └ valora_realism_offset  realism keyframes this (ground sink, tyre deflection, landing settle, squash)
        └ valora_subject      the compiler's placement (static scale + location)
           └ the upload's own objects

Placed space P = the local space of valora_realism_offset: placed metres, before motion and realism.
SubjectProfile points (wheels, contacts, dangling parts) are in P. Drivers are empties whose keyed
location carries a value per frame; Geometry Nodes read them with Object Info, so every frame
evaluates on its own (METHODS R1).

World contract (every world with hasFoliage: true): tag the foliage mesh objects valora_foliage and write
two point attributes, valora_sway (0 at the root .. 1 at the tip) and valora_sway_len (the stem length in
metres); tag the floor valora_ground. No world animates its own foliage (foliage_sway and ground_conform
do)."""
import bpy
import numpy as np

MOTION, OFFSET = "valora_motion", "valora_realism_offset"
TYRE, SPIN, UNSPRUNG = "valora_tyre", "valora_spin", "valora_unsprung"
SWAY, SWAY_LEN = "valora_sway", "valora_sway_len"
SWAY_PIVOT, SWAY_TIP = "valora_sway_pivot", "valora_sway_tip"   # dangling parts only (object space)
GROUND_TAG, FOLIAGE_TAG = "valora_ground", "valora_foliage"


def build_rig(scene, root):
    motion = bpy.data.objects.new(MOTION, None)
    offset = bpy.data.objects.new(OFFSET, None)
    for o in (motion, offset):
        scene.collection.objects.link(o)
    offset.parent = motion
    root.parent = offset
    bpy.context.view_layer.update()
    return motion, offset


def rig():
    return bpy.data.objects[MOTION], bpy.data.objects[OFFSET]


def fcurves(action):
    """F-curves of an action, for Blender 5 layered actions and legacy ones (moved from blender_main)."""
    if hasattr(action, "layers"):
        return [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves]
    return list(action.fcurves)


def driver(name):
    """An empty whose keyed location carries per-frame values for node trees; never rendered."""
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(ob)
        ob.hide_render = True
    return ob


def key_series(obj, path, index, frames, values):
    """Keys obj.<path>[index] = values[i] at frames[i], linear between keys."""
    for f, v in zip(frames, values):
        getattr(obj, path)[index] = v
        obj.keyframe_insert(path, index=index, frame=f)
    for c in fcurves(obj.animation_data.action):
        if c.data_path == path and c.array_index == index:
            for kp in c.keyframe_points:
                kp.interpolation = "LINEAR"


def motion_track(scene):
    """(positions, yaws) of valora_motion for frames 1..frame_end, from its F-curves (no depsgraph)."""
    motion, _ = rig()
    ad = motion.animation_data
    curves = {(c.data_path, c.array_index): c for c in fcurves(ad.action)} if ad and ad.action else {}

    def ev(path, i, f, default):
        c = curves.get((path, i))
        return float(c.evaluate(f)) if c else float(default)

    frames = range(1, scene.frame_end + 1)
    pos = [tuple(ev("location", k, f, motion.location[k]) for k in range(3)) for f in frames]
    yaw = [ev("rotation_euler", 2, f, motion.rotation_euler[2]) for f in frames]
    return pos, yaw


def placed_points(obj):
    """(n, 3) vertices of obj's own mesh in placed space at the current frame."""
    _, offset = rig()
    m = np.array(offset.matrix_world.inverted() @ obj.matrix_world)
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]


def write_attr(obj, name, values, kind="INT"):
    """A per-vertex attribute on obj's own mesh (a mesh shared with another object is copied first)."""
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    a = obj.data.attributes.get(name) or obj.data.attributes.new(name, kind, "POINT")
    if kind == "FLOAT_VECTOR":
        a.data.foreach_set("vector", np.asarray(values, np.float32).ravel())
        return
    a.data.foreach_set("value", values.astype(np.int32 if kind == "INT" else np.float32))


def tag_wheels(meshes, wheels):
    """Once per scene: valora_tyre / valora_spin / valora_unsprung per vertex = wheel index + 1 (0 none).
    Uses engine/physics/wheel_mask.py, the same rule ingest used for `separable`."""
    scene = bpy.context.scene
    if scene.get("valora_wheel_tags") is not None:
        return dict(scene["valora_wheel_tags"])
    from engine.blender.islands import summaries, vertex_islands
    from engine.physics.wheel_mask import in_wheel_box, island_spins, radial, tyre_mask
    counts = {"objects": 0, "tyre": 0, "spin": 0, "unsprung": 0}
    reach, off_parts = 0.0, 0
    for o in meshes:
        if not len(o.data.vertices):
            continue
        P = placed_points(o)
        isl = vertex_islands(o)
        pieces = summaries(P, isl, 0, min_n=1) if isl is not None else []
        tyre, spin, unsprung = (np.zeros(len(P), np.int32) for _ in range(3))
        for i, w in enumerate(wheels):
            rho = radial(P, w)
            peak = np.zeros(int(isl.max()) + 1) if pieces else None
            if pieces:
                np.maximum.at(peak, isl, rho)        # each island's reach from this axle (review fix 1)
            for s in pieces:
                if in_wheel_box(s["lo"], s["hi"], w, float(peak[s["id"]])):
                    sel = isl == s["id"]
                    unsprung[sel] = i + 1
                    if island_spins(s["lo"], s["hi"], s["centroid"], w, float(peak[s["id"]])):
                        spin[sel] = i + 1
        for i, w in enumerate(wheels):   # tyre band only on this wheel's own parts (review fix 3)
            tyre[(tyre == 0) & tyre_mask(P, w) & (unsprung == i + 1)] = i + 1
        for i, w in enumerate(wheels):
            sel = unsprung == i + 1
            if sel.any():
                reach = max(reach, float(radial(P[sel], w).max()) / w["radius"])
        off_parts += int(((tyre > 0) & (unsprung != tyre)).sum())
        if tyre.any() or unsprung.any():
            for name, arr in ((TYRE, tyre), (SPIN, spin), (UNSPRUNG, unsprung)):
                write_attr(o, name, arr)
            counts["objects"] += 1
            counts["tyre"] += int((tyre > 0).sum())
            counts["spin"] += int((spin > 0).sum())
            counts["unsprung"] += int((unsprung > 0).sum())
    scene["valora_wheel_tags"] = counts
    record("wheel_unsprung_reach_frac", reach)      # largest wheel-part distance from its axle, x r
    record("wheel_tyre_off_parts", off_parts)       # tyre-band vertices not on a part of the same wheel
    record("wheel_tyre_verts", counts["tyre"])
    return counts


def tag_dangling(meshes, parts):
    """valora_sway (0 at the pivot .. 1 at the tip) and valora_sway_len on every island that lies wholly
    inside a high-confidence dangling part's capsule (pivot -> tip, radius x 1.5 + 2 mm), plus the part's
    pivot and tip in the object's own space (valora_sway_pivot / valora_sway_tip: the swing is a rotation
    about the pivot). Islands that only touch the capsule (the body the strap hangs from) stay rigid.
    Returns (tagged vertices, all vertices)."""
    from engine.blender.islands import summaries, vertex_islands
    _, offset = rig()
    tagged = total = 0
    for o in meshes:
        P = placed_points(o)
        total += len(P)
        isl = vertex_islands(o)
        if isl is None or not len(P):
            continue
        u = np.zeros(len(P), np.float32)
        ln = np.zeros(len(P), np.float32)
        piv = np.zeros((len(P), 3), np.float32)
        tip = np.zeros((len(P), 3), np.float32)
        to_local = np.array(o.matrix_world.inverted() @ offset.matrix_world)   # placed -> object space
        for d in (d for d in parts if d["confidence"] == "high"):
            a, b = np.array(d["pivot"], float), np.array(d["tip"], float)
            ab = b - a
            L = float(np.linalg.norm(ab)) or 1e-9
            s = np.clip((P - a) @ ab / (L * L), 0.0, 1.0)
            dist = np.linalg.norm(P - (a + s[:, None] * ab), axis=1)
            inside = dist <= 1.5 * d["radius"] + 0.002
            la, lb = (to_local[:3, :3] @ v + to_local[:3, 3] for v in (a, b))
            for piece in summaries(P, isl, 0, min_n=1):
                sel = isl == piece["id"]
                if inside[sel].all():
                    u[sel], ln[sel], piv[sel], tip[sel] = s[sel], L, la, lb
        if (ln > 0).any():
            write_attr(o, SWAY, u, "FLOAT")
            write_attr(o, SWAY_LEN, ln, "FLOAT")
            write_attr(o, SWAY_PIVOT, piv, "FLOAT_VECTOR")
            write_attr(o, SWAY_TIP, tip, "FLOAT_VECTOR")
            tagged += int((ln > 0).sum())
    return tagged, total


def ground_objects():
    return [o for o in bpy.context.scene.objects if o.get(GROUND_TAG)]


def record(key, value):
    """A fact a realism block wants in compile.json (plain numbers, bools, strings, lists)."""
    bpy.context.scene[f"valora_rz_{key}"] = value


def records(scene):
    return {k[len("valora_rz_"):]: (scene[k].to_list() if hasattr(scene[k], "to_list") else scene[k])
            for k in scene.keys() if k.startswith("valora_rz_")}
