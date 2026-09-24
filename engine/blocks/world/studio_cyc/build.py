"""Seamless cyclorama sized to the subject, plus a two-hemisphere world (V-L06).
Ported from tools/product-render/render_product.py build_cyclorama (:181), which worked at a
1 m subject; every length here is multiplied by the subject's longest side."""
import math

TONES = {"white": 0.8, "grey": 0.18, "black": 0.02}  # albedo (eng)
GLOSS_ROUGHNESS = 0.25  # (eng)


def _cyc_mesh(bpy, k):
    import bmesh
    width, y_front, y_bend, radius, wall_h, segs = 60.0 * k, -30.0 * k, 9.0 * k, 5.0 * k, 16.0 * k, 24
    bm = bmesh.new()
    prof = [(y_front, 0.0), (y_bend, 0.0)]
    for i in range(1, segs + 1):
        a = (i / segs) * (math.pi / 2)
        prof.append((y_bend + radius * math.sin(a), radius - radius * math.cos(a)))
    prof.append((y_bend + radius, wall_h))
    rows = [[bm.verts.new((x, y, z)) for x in (-width / 2, width / 2)] for (y, z) in prof]
    for r0, r1 in zip(rows, rows[1:]):
        bm.faces.new((r0[0], r0[1], r1[1], r1[0]))
    me = bpy.data.meshes.new("valora_cyc")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _cyc_material(bpy, albedo, floor_gloss):
    # Fixed-weight diffuse + glossy mix (no Fresnel ramp: the far floor/wall never turn to mirror).
    mat = bpy.data.materials.new("valora_cyc")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diff.inputs["Color"].default_value = (albedo, albedo, albedo, 1.0)
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    gloss.inputs["Roughness"].default_value = GLOSS_ROUGHNESS
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.3 * floor_gloss
    nt.links.new(diff.outputs[0], mix.inputs[1])
    nt.links.new(gloss.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def _world(bpy, scene, upper, lower_gain):
    """Upper hemisphere = upper, lower = upper * lowerHemisphereGain (V-L06)."""
    world = bpy.data.worlds.new("valora_world")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.name = "valora_world_bg"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    lo = upper * lower_gain
    mix.inputs["A"].default_value = (lo, lo, lo, 1.0)
    mix.inputs["B"].default_value = (upper, upper, upper, 1.0)
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], gt.inputs[0])
    nt.links.new(gt.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    scene.world = world
    return world


def build(ctx):
    import bpy
    p, prof = ctx.params, ctx.profile
    k = prof.longest
    albedo = TONES[p["tone"]]
    ob = bpy.data.objects.new("valora_cyc", _cyc_mesh(bpy, k))
    ctx.scene.collection.objects.link(ob)
    cx, cy, _ = prof.center
    hero = ctx.hero_pose.position
    hero_az = math.atan2(hero[1] - cy, hero[0] - cx)
    ob.location = (cx, cy, 0.0)
    ob.rotation_euler = (0.0, 0.0, hero_az + math.pi / 2)  # wall's local +Y points away from the hero camera
    ob.data.materials.append(_cyc_material(bpy, albedo, p["floorGloss"]))
    _world(bpy, ctx.scene, albedo * 0.5, p["lowerHemisphereGain"])
