"""Realise engine/lighting/location_key per shot: one area key and one dark flag, re-rigged at every cut.

The key is light-linked to the subject alone, so it shapes the car's reflections and fill without pooling on the
set or showing as a bright rectangle in the puddles. The flag is invisible to the camera and answers only rays
shorter than its reach (Light Path > Ray Length): the windshield's reflection rays meet it, a puddle a few metres
off does not, so it never reads as a black rectangle in the wet ground (look-check real_rw_court_r2_az90).
Values switch at the same subframes the camera cuts on (timeline: f - SHUTTER / 2), CONSTANT between."""
import bpy
from mathutils import Vector

from engine.color import kelvin_to_rgb
from engine.compiler.tiers import SHUTTER
from engine.lighting.location_key import FLAG, shot_rigs

KEY_NAME, FLAG_NAME, SHEEN_NAME = "valora_location_key", "valora_location_flag", "valora_street_sheen"
SHEEN_KELVIN = 4200.0        # (eng) a street lamp's white LED / metal halide
KEY_KELVIN = 6500.0          # the overcast's own colour: the key reads as a brighter patch of the same sky
REACH_PROP = "valora_reach"
FAR = (0.0, 0.0, -1000.0)    # a shot without a flag parks it below the ground


def set_ups(ctx):
    """Per shot: the camera at the shot's middle integer frame (detail target kept)."""
    fps = ctx.script["format"]["fps"]
    out = []
    for i, sh in enumerate(ctx.script["shots"]):
        mid = (sh["startS"] + sh["endS"]) / 2 * fps + 1
        ks = [k for k in ctx.camera_keys if k.shot == i and float(k.frame).is_integer()]
        if not ks:
            continue
        k = min(ks, key=lambda k: abs(k.frame - mid))
        out.append({"shot": i, "frame": int(round(sh["startS"] * fps)) + 1, "detail": k.target is not None,
                    "position": tuple(k.pose.position), "target": k.target})
    return out


def _switch_frames(rigs):
    """The frame each rig takes over: frame 0 for the first, the cut subframe for the rest."""
    return [0.0 if j == 0 else r["frame"] - SHUTTER / 2 for j, r in enumerate(rigs)]


def _constant(idblock):
    ad = idblock.animation_data
    if ad is None or ad.action is None:
        return
    from engine.blender.realism_rig import fcurves
    for c in fcurves(ad.action):
        for kp in c.keyframe_points:
            kp.interpolation = "CONSTANT"


def _aim(ob, facing, axis):
    ob.rotation_euler = Vector(facing).to_track_quat(axis, "Y").to_euler()


def _flag_material():
    m = bpy.data.materials.new(FLAG_NAME)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    a = FLAG["albedo"]
    bsdf.inputs["Base Color"].default_value = (a, a, a, 1.0)
    bsdf.inputs["Roughness"].default_value = FLAG["roughness"]
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    lp = nt.nodes.new("ShaderNodeLightPath")
    reach = nt.nodes.new("ShaderNodeAttribute")
    reach.attribute_type, reach.attribute_name = "OBJECT", REACH_PROP
    far = nt.nodes.new("ShaderNodeMath")
    far.operation = "GREATER_THAN"
    nt.links.new(lp.outputs["Ray Length"], far.inputs[0])
    nt.links.new(reach.outputs["Fac"], far.inputs[1])
    gone = nt.nodes.new("ShaderNodeMath")
    gone.operation, gone.use_clamp = "ADD", True
    nt.links.new(far.outputs[0], gone.inputs[0])
    nt.links.new(lp.outputs["Is Camera Ray"], gone.inputs[1])
    # feather (round 6): clear toward the edge. The quad spans -0.5..0.5 in object space; the flag's opacity is
    # smoothstep over each axis's |coord| from (1 - feather) / 2 to 1/2, multiplied, so the glass sees a gradient
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    lo = (1.0 - FLAG["feather"]) * 0.5
    opaque = None
    for axis in ("X", "Y"):
        ab = nt.nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        nt.links.new(sep.outputs[axis], ab.inputs[0])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.interpolation_type = "SMOOTHSTEP"
        nt.links.new(ab.outputs[0], mr.inputs["Value"])
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = lo, 0.5
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.0, 0.0
        if opaque is None:
            opaque = mr.outputs[0]
        else:
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            nt.links.new(opaque, mul.inputs[0])
            nt.links.new(mr.outputs[0], mul.inputs[1])
            opaque = mul.outputs[0]
    edge = nt.nodes.new("ShaderNodeMath")
    edge.operation = "SUBTRACT"
    edge.inputs[0].default_value = 1.0
    nt.links.new(opaque, edge.inputs[1])
    gone2 = nt.nodes.new("ShaderNodeMath")
    gone2.operation, gone2.use_clamp = "MAXIMUM", True
    nt.links.new(gone.outputs[0], gone2.inputs[0])
    nt.links.new(edge.outputs[0], gone2.inputs[1])
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(gone2.outputs[0], mix.inputs["Fac"])
    nt.links.new(bsdf.outputs[0], mix.inputs[1])
    nt.links.new(clear.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def _orient(ob, facing, axis):
    """An area light emitting along `facing` (its -Z) with its long side (X) along `axis`."""
    from mathutils import Matrix
    z = -Vector(facing).normalized()
    x = Vector(axis) - Vector(axis).dot(z) * z
    x = x.normalized() if x.length > 1e-9 else z.orthogonal().normalized()
    y = z.cross(x)
    ob.rotation_euler = Matrix((x, y, z)).transposed().to_euler()


def build(ctx, block, watts=None, detail_watts=None, ev=0.0, sheen=False):
    """Key + flag for every shot; returns (objects, facts). `ev` scales the keys (a lighting block's exposure).
    sheen (after dark, round 7): every full-frame shot also gets its street-light strip (location_key.SHEEN),
    parked at zero where a shot has none."""
    from engine.blender.lights import link_to
    rigs = shot_rigs(ctx.profile, set_ups(ctx), sheen=sheen)
    if not rigs:
        return [], {}
    if watts is not None or detail_watts is not None:
        from engine.lighting import location_key as LK
        s2 = LK.scale(ctx.profile) ** 2
        for r in rigs:
            w = detail_watts if r["detail"] else watts
            if w is not None:
                r["key"]["watts"] = w * s2
    if ev:
        for r in rigs:
            r["key"]["watts"] *= 2.0 ** ev
    ld = bpy.data.lights.new(KEY_NAME, "AREA")
    ld.shape = "RECTANGLE"
    ld.color = kelvin_to_rgb(KEY_KELVIN)
    key = bpy.data.objects.new(KEY_NAME, ld)
    ctx.scene.collection.objects.link(key)
    key.visible_camera = False
    me = bpy.data.meshes.new(FLAG_NAME)
    me.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
    me.materials.append(_flag_material())
    flag = bpy.data.objects.new(FLAG_NAME, me)
    ctx.scene.collection.objects.link(flag)
    flag.visible_camera = flag.visible_shadow = False
    for f, r in zip(_switch_frames(rigs), rigs):
        k = r["key"]
        key.location = k["center"]
        _aim(key, k["facing"], "-Z")                 # area lights emit along -Z
        ld.size, ld.size_y, ld.energy = k["sizeX"], k["sizeY"], k["watts"]
        key.keyframe_insert("location", frame=f)
        key.keyframe_insert("rotation_euler", frame=f)
        for path in ("size", "size_y", "energy"):
            ld.keyframe_insert(data_path=path, frame=f)
        g = r["flag"]
        if g is None:
            flag.location, flag.scale, flag[REACH_PROP] = FAR, (1.0, 1.0, 1.0), 0.0
        else:
            flag.location, flag.scale, flag[REACH_PROP] = g["center"], (g["sizeX"], g["sizeY"], 1.0), g["reachM"]
            _aim(flag, g["facing"], "Z")
        for path in ("location", "rotation_euler", "scale", f'["{REACH_PROP}"]'):
            flag.keyframe_insert(data_path=path, frame=f)
    lit = [key]
    if sheen and any(r["sheen"] for r in rigs):
        sd = bpy.data.lights.new(SHEEN_NAME, "AREA")
        sd.shape = "RECTANGLE"
        sd.color = kelvin_to_rgb(SHEEN_KELVIN)
        strip = bpy.data.objects.new(SHEEN_NAME, sd)
        ctx.scene.collection.objects.link(strip)
        strip.visible_camera = False
        for f, r in zip(_switch_frames(rigs), rigs):
            g = r["sheen"]
            if g is None:
                strip.location, sd.size, sd.size_y, sd.energy = FAR, 1.0, 1.0, 0.0
            else:
                strip.location = g["center"]
                _orient(strip, g["facing"], g["axis"])
                sd.size, sd.size_y, sd.energy = g["sizeX"], g["sizeY"], g["watts"] * 2.0 ** ev
            strip.keyframe_insert("location", frame=f)
            strip.keyframe_insert("rotation_euler", frame=f)
            for path in ("size", "size_y", "energy"):
                sd.keyframe_insert(data_path=path, frame=f)
        for idb in (strip, sd):
            _constant(idb)
        lit.append(strip)
    for idb in (key, ld, flag):
        _constant(idb)
    for ob in (key, flag, *lit[1:]):
        ob["valora_block"] = block
    link_to(list(ctx.meshes), lit, "valora_location_key_receivers")
    facts = {"shots": [{"shot": r["shot"], "detail": r["detail"], "keyW": round(r["key"]["watts"], 3),
                        "keyCenter": [round(v, 4) for v in r["key"]["center"]],
                        "flag": r["flag"] is not None,
                        **({"sheenW": round(r["sheen"]["watts"] * 2.0 ** ev, 3)} if r.get("sheen") else {})}
                       for r in rigs]}
    return [key, flag, *lit[1:]], facts


WEATHER_BLOCKS = ("effect/droplets",)    # water ON the subject: it must catch the subject's key


def link_weather(scene):
    """finalize: the beads and drips are their own objects, built after the lighting, so the key's receiver
    collection (the subject alone) never reached them and a bead showed no highlight of it, only the sky's
    (round 6: the drops read as dark specks). Every droplet object joins the receivers."""
    coll = bpy.data.collections.get("valora_location_key_receivers")
    if coll is None:
        return []
    added = []
    for ob in scene.objects:
        if str(ob.get("valora_block", "")) in WEATHER_BLOCKS and ob.name not in coll.objects:
            coll.objects.link(ob)
            added.append(ob.name)
    for co in coll.collection_objects:
        co.light_linking.link_state = "INCLUDE"
    return added
