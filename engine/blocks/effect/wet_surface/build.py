"""wet_surface: wet ground, puddles that mirror, ripples only while it rains (port of render-studio
rain_scene.wet_asphalt / car_apron / wet_detail.puddle_normal, generalised; maths in engine/physics/wet.py).

Shader-only on the world's valora_ground materials (M-SHD, FL-06/07). The block WRAPS each ground material's
Principled BSDF in one `valora_wet` group node: whatever fed Base Color and Roughness now feeds the group, and
the group feeds Base Color, Roughness and the water coat (Coat Weight / Roughness / Normal). The world's own
nodes are kept. Standing water: a summed height noise below the level holding `puddles` of the ground, deepened under the subject's posed
footprint (render-studio's car apron, a mask term through valora_realism_offset, so the subject's reflection
lands in water). Ripples: a ring field whose phase is keyed linearly over the clip (a shader has no clock, so
frame N depends on time alone), connected only while rain falls; alone, `drips` connects slow sparse rings to a
separate input and the puddles stay calm mirrors. The upload's materials are never touched (spec §4.5)."""

GROUP = "valora_wet"


def _math(nt, op, a, b=None):
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = op
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, m.inputs[i])
    return m.outputs[0]


def _smooth(nt, value, a, b):
    m = nt.nodes.new("ShaderNodeMapRange")
    m.interpolation_type, m.clamp = "SMOOTHSTEP", True
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = a, b
    nt.links.new(value, m.inputs["Value"])
    return m.outputs["Result"]


def _group(bpy, ctx):
    """The shared wet-ground group: (Color, Roughness, Ripple, Drip) -> (Color, Roughness, Coat, Coat Roughness,
    Coat Normal)."""
    from engine.blender.realism_rig import OFFSET
    from engine.physics import wet as W
    p, prof = ctx.params, ctx.profile
    ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    for name, kind in (("Color", "NodeSocketColor"), ("Roughness", "NodeSocketFloat"), ("Ripple", "NodeSocketFloat"),
                       ("Drip", "NodeSocketFloat")):
        ng.interface.new_socket(name, in_out="INPUT", socket_type=kind)
    for name, kind in (("Color", "NodeSocketColor"), ("Roughness", "NodeSocketFloat"), ("Coat", "NodeSocketFloat"),
                       ("Coat Roughness", "NodeSocketFloat"), ("Coat Normal", "NodeSocketVector")):
        ng.interface.new_socket(name, in_out="OUTPUT", socket_type=kind)
    nt = ng
    gi, go = nt.nodes.new("NodeGroupInput"), nt.nodes.new("NodeGroupOutput")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    macro = nt.nodes.new("ShaderNodeTexNoise")
    macro.inputs["Scale"].default_value = 1.0 / W.PUDDLE_SCALE_M
    macro.inputs["Detail"].default_value = 1.0
    nt.links.new(geo.outputs["Position"], macro.inputs["Vector"])
    patch = nt.nodes.new("ShaderNodeTexNoise")
    patch.inputs["Scale"].default_value = W.PATCH_SCALE
    patch.inputs["Detail"].default_value = W.PATCH_DETAIL
    nt.links.new(geo.outputs["Position"], patch.inputs["Vector"])
    height = _math(nt, "ADD", macro.outputs["Fac"], _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", patch.outputs["Fac"], 0.5), W.PATCH_AMP))
    depth = _math(nt, "SUBTRACT", W.puddle_threshold(p["puddles"]), height)
    # the apron: deeper water under the posed footprint (placed space), gone by 1.5 x its half size
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = bpy.data.objects[OFFSET]
    lo, hi = prof.boundsMin, prof.boundsMax
    half = [max(1e-4, 0.75 * (hi[i] - lo[i])) for i in range(2)]
    rel = nt.nodes.new("ShaderNodeMapping")
    rel.inputs["Location"].default_value = (-(lo[0] + hi[0]) / 2 / half[0], -(lo[1] + hi[1]) / 2 / half[1], 0.0)
    rel.inputs["Scale"].default_value = (1.0 / half[0], 1.0 / half[1], 0.0)
    nt.links.new(tc.outputs["Object"], rel.inputs["Vector"])
    reach = nt.nodes.new("ShaderNodeVectorMath")
    reach.operation = "LENGTH"
    nt.links.new(rel.outputs["Vector"], reach.inputs[0])
    basin = _math(nt, "SUBTRACT", 1.0, _smooth(nt, reach.outputs["Value"], 0.6, 1.0))
    depth = _math(nt, "ADD", depth, _math(nt, "MULTIPLY", basin, W.APRON_DEPTH * p["puddles"] / 0.4))
    puddle = _smooth(nt, depth, 0.0, W.PUDDLE_EDGE)
    # wet stone: darker, smoother; the coat is the water (a film outside the pools, flat inside them)
    dark = nt.nodes.new("ShaderNodeMix")
    dark.data_type, dark.blend_type = "RGBA", "MULTIPLY"
    dark.inputs["Factor"].default_value = 1.0
    k = W.albedo_factor(p["wetness"])
    dark.inputs[7].default_value = (k, k, k, 1.0)
    nt.links.new(gi.outputs["Color"], dark.inputs[6])
    nt.links.new(dark.outputs[2], go.inputs["Color"])
    # the stone under the water stays stone (never a bumpy mirror: the first look-check read as a choppy sea);
    # the mirror is the coat, optically flat inside the pools
    rough = _math(nt, "MAXIMUM", _math(nt, "MULTIPLY", gi.outputs["Roughness"], W.roughness_factor(p["wetness"])),
                  W.STONE_ROUGH_MIN)
    nt.links.new(rough, go.inputs["Roughness"])
    nt.links.new(_math(nt, "MAXIMUM", W.coat_weight(p["wetness"]), puddle), go.inputs["Coat"])
    film = _math(nt, "MULTIPLY", 0.12, _math(nt, "SUBTRACT", 1.0, puddle))
    nt.links.new(_math(nt, "ADD", film, W.PUDDLE_ROUGH * 0.2), go.inputs["Coat Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 0.0015
    rings = _math(nt, "ADD", gi.outputs["Ripple"], gi.outputs["Drip"])
    nt.links.new(_math(nt, "MULTIPLY", rings, puddle), bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], go.inputs["Coat Normal"])
    return ng


def _rings(ctx, nt, hz, scale_m, density):
    """A ring field in the material: a 4D Voronoi whose W is keyed linearly over the clip; rings of
    sin(distance) that expand as W runs, sparse by `density`."""
    import math
    from engine.blender.realism_rig import fcurves
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.voronoi_dimensions = "4D"
    vor.inputs["Scale"].default_value = 1.0 / scale_m
    nt.links.new(geo.outputs["Position"], vor.inputs["Vector"])
    fps, n = ctx.script["format"]["fps"], ctx.scene.frame_end
    for f in (1, n):
        vor.inputs["W"].default_value = hz * (f - 1) / fps
        vor.inputs["W"].keyframe_insert("default_value", frame=f)
    for c in fcurves(nt.animation_data.action):
        for kp in c.keyframe_points:
            kp.interpolation = "LINEAR"
        c.extrapolation = "LINEAR"
    d = vor.outputs["Distance"]
    wave = _math(nt, "SINE", _math(nt, "MULTIPLY", d, 2.0 * math.pi * 6.0))
    fade = _math(nt, "SUBTRACT", 1.0, _smooth(nt, d, 0.0, density))
    return _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", wave, fade), 0.5)


def _wrap(ctx, mat, group, mode):
    """Insert the group between whatever fed the BSDF and the BSDF; the world's own nodes stay."""
    from engine.physics import wet as W
    nt = mat.node_tree
    sh = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if sh is None:
        return None
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree, g.name = group, GROUP
    for src, dst in (("Base Color", "Color"), ("Roughness", "Roughness")):
        sock = sh.inputs[src]
        if sock.is_linked:
            nt.links.new(sock.links[0].from_socket, g.inputs[dst])
        else:
            g.inputs[dst].default_value = sock.default_value
    nt.links.new(g.outputs["Color"], sh.inputs["Base Color"])
    nt.links.new(g.outputs["Roughness"], sh.inputs["Roughness"])
    nt.links.new(g.outputs["Coat"], sh.inputs["Coat Weight"])
    nt.links.new(g.outputs["Coat Roughness"], sh.inputs["Coat Roughness"])
    nt.links.new(g.outputs["Coat Normal"], sh.inputs["Coat Normal"])
    sh.inputs["Coat IOR"].default_value = 1.333
    if mode == "rain":
        nt.links.new(_rings(ctx, nt, W.RIPPLE_HZ, 0.35, 0.9), g.inputs["Ripple"])
    elif mode == "drips":   # rare, faint rings: after the rain the puddles are mirrors (Task 65 look-check)
        nt.links.new(_math(nt, "MULTIPLY", _rings(ctx, nt, W.DRIP_HZ, 1.2, W.DRIP_SPREAD), W.DRIP_AMP), g.inputs["Drip"])
    return g


def build(ctx):
    import bpy
    from engine.blender.realism_rig import ground_objects
    from engine.physics import wet as W
    ids = [e["id"] for e in ctx.script.get("effects", [])]
    mode = W.ripple_mode(ctx.params, ids)
    group = _group(bpy, ctx)
    wrapped, placed = [], {}
    for ob in ground_objects():
        for mat in {m for m in ob.data.materials if m is not None and m.use_nodes}:
            if _wrap(ctx, mat, group, mode) is not None:
                wrapped.append(mat.name)
            placed[mat.name] = sum(1 for n in mat.node_tree.nodes
                                   if n.type == "GROUP" and n.node_tree is not None and n.node_tree.name == GROUP)
    g_nodes = [n for m in bpy.data.materials if m.name in placed for n in m.node_tree.nodes
               if n.type == "GROUP" and n.node_tree is group]
    ctx.scene["valora_fx_wet_surface"] = {
        "materials": sorted(wrapped), "groupsPerMaterial": placed, "rippleMode": mode or "none",
        "rippleLinked": any(n.inputs["Ripple"].is_linked for n in g_nodes),
        "dripLinked": any(n.inputs["Drip"].is_linked for n in g_nodes),
        "puddleThreshold": W.puddle_threshold(ctx.params["puddles"]),
        "albedoFactor": W.albedo_factor(ctx.params["wetness"]), "roughFactor": W.roughness_factor(ctx.params["wetness"])}
    return group
