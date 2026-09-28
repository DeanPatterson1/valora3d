"""Play an OpenVDB sequence on a Volume object (phase 6 Task 110, lane S): smoke plumes, steam, fire and the
interactive smoke_sim cache all read through place_vdb.

Placement. A sequence carries its native facts (engine/assets manifest `native`, or a bake report): widthM, the
domain's width it was simulated in, and baseM, the point of the bake scene that is the plume's base (x, y
centre, z floor) in the VDB's own space. Mantaflow writes its grids with the domain's MIN corner at the
origin (measured: a 2 m domain's grids span 0..2 on every axis), so a domain whose base centre sat at the bake
origin has baseM = (width / 2, depth / 2, 0). The Volume object is scaled uniformly by engine/physics/vdb.scale_factor (x3 guard, GS-01),
rotated about z at the base, and its base lands on `anchor`.

Time (the measured 5.0.1 rule, formats.gas_vdb): file = scene_frame - frame_start + 1 + frame_offset, CLIP empty
outside frame_duration. A retime keys frame_offset per render frame (engine/physics/vdb.offset_keys, CONSTANT);
velocity_scale follows the retime so motion blur matches the playback (R7).

Shading: Principled Volume on the 'density' grid; with flame=True the 'flame' grid drives a blackbody emission
(FLAME_K) through Emission Strength. Every node is found by type; nothing touches the upload."""
import bpy

from engine.physics import vdb as V

FLAME_K = (900.0, 1750.0)        # (eng, G9) flame 0 -> 1 maps onto this blackbody range
FLAME_GAIN = 12.0                # (eng, G9) emission strength at flame 1 (per unit density)


def _socket(node, *names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    return None


def volume_material(name, *, color=(0.8, 0.8, 0.8), density=1.0, flame=False, flame_gain=FLAME_GAIN,
                    absorption=(0.0, 0.0, 0.0), anisotropy=0.0):
    """A Principled Volume reading the sequence's grids: 'density' x density; flame=True adds blackbody emission
    from the 'flame' grid. Reuses a material of the same name."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (*color[:3], 1.0)
    vol.inputs["Density"].default_value = float(density)
    s = _socket(vol, "Density Attribute")
    if s is not None:
        s.default_value = "density"
    vol.inputs["Anisotropy"].default_value = float(anisotropy)
    s = _socket(vol, "Absorption Color")
    if s is not None:
        s.default_value = (*absorption[:3], 1.0)
    if flame:
        a = nt.nodes.new("ShaderNodeAttribute")
        a.attribute_name = "flame"
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.clamp = True
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = FLAME_K
        nt.links.new(a.outputs["Fac"], mr.inputs["Value"])
        bb = nt.nodes.new("ShaderNodeBlackbody")
        nt.links.new(mr.outputs["Result"], bb.inputs["Temperature"])
        nt.links.new(bb.outputs[0], vol.inputs["Emission Color"])
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = float(flame_gain)
        nt.links.new(a.outputs["Fac"], mul.inputs[0])
        nt.links.new(mul.outputs[0], vol.inputs["Emission Strength"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return m


def place_vdb(seq, *, anchor, scale_m=None, start_frame=1, retime=1.0, rotate_deg=0.0, first_file=1,
              velocity=True, name="valora_vdb", block=None, material=None):
    """A Volume object playing `seq` ({"files": [paths in order], "native": {"widthM", "baseM"}}), its first
    shown file (first_file) at render frame start_frame, advancing `retime` files per render frame. scale_m is
    the plume's width in the scene (None: native size). Returns the object; its ["valora_vdb"] records the play
    (files, start, span, scale, retime) for probes."""
    import math
    files = [str(f) for f in seq["files"]]
    native = seq.get("native") or {}
    k = 1.0 if scale_m is None else V.scale_factor(float(native["widthM"]), float(scale_m))
    retime = V.clamp_retime(retime)
    n = len(files)
    vol = bpy.data.volumes.new(name)
    vol.filepath = files[0]
    vol.is_sequence = True
    start, span = V.play_range(int(start_frame), retime, n, first_file)
    vol.frame_start = start
    vol.frame_duration = span
    vol.sequence_mode = "CLIP"
    keys = V.offset_keys(start, retime, n, first_file)
    vol.frame_offset = keys[0][1]
    if len(keys) > 1:
        for f, off in keys:
            vol.frame_offset = off
            vol.keyframe_insert("frame_offset", frame=f)
        from engine.blender.realism_rig import fcurves
        for c in fcurves(vol.animation_data.action):
            for kp in c.keyframe_points:
                kp.interpolation = "CONSTANT"
    if velocity:
        # velocity_grid defaults to 'velocity' (Mantaflow's name). Never assign it here: the setter checks the
        # grids loaded NOW, and before a frame is evaluated there are none, so it clears the name (measured).
        vol.velocity_unit = "FRAME"
        vol.velocity_scale = V.velocity_scale(retime)
    else:
        vol.velocity_grid = ""
    ob = bpy.data.objects.new(name, vol)
    bpy.context.scene.collection.objects.link(ob)
    base = native.get("baseM") or (0.0, 0.0, 0.0)
    a = math.radians(rotate_deg)
    ca, sa = math.cos(a), math.sin(a)
    bx, by, bz = (k * c for c in base)                       # the base point after scaling, before rotation
    ob.scale = (k, k, k)
    ob.rotation_euler = (0.0, 0.0, a)
    ob.location = (anchor[0] - (ca * bx - sa * by), anchor[1] - (sa * bx + ca * by), anchor[2] - bz)
    vol.materials.append(material or volume_material(f"{name}_mat"))
    if block:
        ob["valora_block"] = block
    ob["valora_vdb"] = {"files": n, "start": start, "span": span, "scale": k, "retime": retime,
                        "firstFile": first_file}
    return ob


def grids_at(ob, frame):
    """[(grid name, data type)] and the file the Volume shows at `frame` (probes and tests)."""
    import os
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    g = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.grids
    g.load()
    return {"file": os.path.basename(g.frame_filepath) if len(g) else None,
            "grids": sorted((x.name, x.data_type) for x in g)}
