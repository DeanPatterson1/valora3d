"""wet_surface: wet ground, puddles that mirror, ripples only while it rains (port of render-studio
rain_scene.wet_asphalt / car_apron / wet_detail.puddle_normal, generalised; maths in engine/physics/wet.py).

Shader-only on the world's valora_ground materials (M-SHD, FL-06/07). The block WRAPS each ground material's
Principled BSDF in one `valora_wet` group node: whatever fed Base Color and Roughness now feeds the group, and
the group feeds Base Color, Roughness and the water coat (Coat Weight / Roughness / Normal). The world's own
nodes are kept. Standing water: a summed height noise below the level holding `puddles` of the ground, deepened under the subject's posed
footprint (render-studio's car apron, a mask term through valora_realism_offset, so the subject's reflection
lands in water). Rain ripples: rings on the shared impact lattice (the rain crowns' Voronoi, seed and ages; a keyed
clock stands in for Scene Time, so frame N depends on time alone), connected only while rain falls; alone, `drips` connects slow sparse rings to a
separate input and the puddles stay calm mirrors. The upload's materials are never touched (spec §4.5)."""

GROUP = "valora_wet"


def _math(nt, op, a, b=None, c=None):
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = op
    for i, v in enumerate((a, b, c)):
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
                       ("Drip", "NodeSocketFloat"), ("Height", "NodeSocketFloat"), ("Stone Normal", "NodeSocketVector")):
        sock = ng.interface.new_socket(name, in_out="INPUT", socket_type=kind)
        if name == "Height":
            sock.default_value = 0.5          # no scan: the zero-mean scan term adds nothing
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
    # the world's scanned displacement roughens every shore (wet.scan_height_term, zero-mean: same puddle share)
    height = _math(nt, "ADD", height, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", gi.outputs["Height"], 0.5),
                                            W.SCAN_HEIGHT_K))
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
    damp = _smooth(nt, depth, *W.DAMP_BAND)            # saturated bank round each pool
    deep = _smooth(nt, depth, *W.DEEP_BAND)            # the pool's bed
    wet = float(p["wetness"])
    # wet stone: darker, smoother; banks and beds darker again (render-studio wet_asphalt, rain_scene.py:195-201)
    k = _math(nt, "MULTIPLY", W.albedo_factor(wet),
              _math(nt, "MULTIPLY", _math(nt, "MULTIPLY_ADD", damp, W.BANK_ALBEDO - 1.0, 1.0),
                    _math(nt, "MULTIPLY_ADD", deep, W.BED_ALBEDO - 1.0, 1.0)))
    dark = nt.nodes.new("ShaderNodeMix")
    dark.data_type, dark.blend_type = "RGBA", "MULTIPLY"
    dark.inputs["Factor"].default_value = 1.0
    grey = nt.nodes.new("ShaderNodeCombineColor")
    for ch in ("Red", "Green", "Blue"):
        nt.links.new(k, grey.inputs[ch])
    nt.links.new(grey.outputs[0], dark.inputs[7])
    nt.links.new(gi.outputs["Color"], dark.inputs[6])
    nt.links.new(dark.outputs[2], go.inputs["Color"])
    # the stone under the water stays stone (never a bumpy mirror: the first look-check read as a choppy sea);
    # its roughness follows the scan (wet.stone_roughness, 0.34-0.62 at full wetness, no flat clamp)
    r_in = gi.outputs["Roughness"]
    lo, hi = W.STONE_ROUGH_SCAN
    rough = _math(nt, "ADD", _math(nt, "MULTIPLY", r_in, 1.0 - wet),
                  _math(nt, "MULTIPLY", _math(nt, "MULTIPLY_ADD", r_in, hi - lo, lo), wet))
    nt.links.new(rough, go.inputs["Roughness"])
    # the coat is the water: a broken film outside the pools, flat inside them
    film_w = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY_ADD", damp, W.FILM_COAT[1] - W.FILM_COAT[0], W.FILM_COAT[0]), wet)
    nt.links.new(_math(nt, "MAXIMUM", film_w, puddle), go.inputs["Coat"])
    flo, fhi = W.FILM_ROUGH_SCAN
    film_r = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY_ADD", r_in, fhi - flo, flo),
                   _math(nt, "MULTIPLY_ADD", damp, W.FILM_SATURATED - 1.0, 1.0))
    film_r = _math(nt, "MULTIPLY", film_r, _math(nt, "SUBTRACT", 1.0, puddle))
    nt.links.new(_math(nt, "ADD", film_r, W.COAT_ROUGH_FLOOR), go.inputs["Coat Roughness"])
    # the film follows the stone's relief, softened (saturated: less), flat in the pools
    rl0, rl1 = W.FILM_RELIEF
    relief = _math(nt, "ADD", _math(nt, "MULTIPLY", _math(nt, "MULTIPLY_ADD", damp, rl1 - rl0, rl0),
                                    _math(nt, "SUBTRACT", 1.0, puddle)), 0.004)
    fmix = nt.nodes.new("ShaderNodeMix")
    fmix.data_type = "VECTOR"
    nt.links.new(relief, fmix.inputs["Factor"])
    nt.links.new(geo.outputs["Normal"], fmix.inputs[4])
    nt.links.new(gi.outputs["Stone Normal"], fmix.inputs[5])
    fnorm = nt.nodes.new("ShaderNodeVectorMath")
    fnorm.operation = "NORMALIZE"
    nt.links.new(fmix.outputs[1], fnorm.inputs[0])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 0.0015
    nt.links.new(fnorm.outputs[0], bump.inputs["Normal"])
    # no rain lands under the subject (the crowns are sheltered there too): rain ripples stop at its footprint
    ax = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(rel.outputs["Vector"], ax.inputs[0])
    under = _math(nt, "MULTIPLY", _math(nt, "LESS_THAN", _math(nt, "ABSOLUTE", ax.outputs[0]), 1.0 / 1.5),
                  _math(nt, "LESS_THAN", _math(nt, "ABSOLUTE", ax.outputs[1]), 1.0 / 1.5))
    ripple = _math(nt, "MULTIPLY", gi.outputs["Ripple"], _math(nt, "SUBTRACT", 1.0, under))
    rings = _math(nt, "ADD", ripple, gi.outputs["Drip"])
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


def _clock(ctx, nt):
    """A Value node keyed to Scene Time (frame / fps, linear, extrapolated): the shader's copy of the clock the
    crown tree reads (GeometryNodeInputSceneTime), since a material has no clock of its own."""
    from engine.blender.realism_rig import fcurves
    v = nt.nodes.new("ShaderNodeValue")
    v.name = "valora_wet_clock"
    fps, n = ctx.script["format"]["fps"], ctx.scene.frame_end
    for f in (1, max(n, 2)):
        v.outputs[0].default_value = f / fps
        v.outputs[0].keyframe_insert("default_value", frame=f)
    for c in fcurves(nt.animation_data.action):
        if "valora_wet_clock" in c.data_path:
            for kp in c.keyframe_points:
                kp.interpolation = "LINEAR"
            c.extrapolation = "LINEAR"
    return v.outputs[0]


def _impact_rings(ctx, nt, lat):
    """Rain ripples from the shared impact lattice (engine/physics/rain.impact_lattice; review chunk3 #6): the
    same 2D Voronoi (cell, jitter, seed offset) as the crowns, so each ripple is centred on a crown's feature point
    and its age frac(t / period + the cell's red) is the crown's age: a ring grows to RIPPLE_REACH cells and
    fades over the period."""
    import math
    from engine.physics import wet as W
    S, P, ox, oy = lat["cellM"], lat["periodS"], lat["offset"][0], lat["offset"][1]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    cell = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "ADD", _math(nt, "DIVIDE", sep.outputs[0], S), ox), cell.inputs[0])
    nt.links.new(_math(nt, "ADD", _math(nt, "DIVIDE", sep.outputs[1], S), oy), cell.inputs[1])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.name = "valora_wet_impacts"
    vor.voronoi_dimensions, vor.feature, vor.distance = "2D", "F1", "EUCLIDEAN"
    vor.inputs["Scale"].default_value, vor.inputs["Randomness"].default_value = 1.0, lat["jitter"]
    nt.links.new(cell.outputs[0], vor.inputs["Vector"])
    red = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(vor.outputs["Color"], red.inputs[0])
    age = _math(nt, "FRACT", _math(nt, "ADD", _math(nt, "DIVIDE", _clock(ctx, nt), P), red.outputs[0]))
    x = _math(nt, "DIVIDE", _math(nt, "SUBTRACT", _math(nt, "MULTIPLY", vor.outputs["Distance"], S),
                                  _math(nt, "MULTIPLY", age, W.RIPPLE_REACH * S)), W.RIPPLE_WAVE_M)
    wave = _math(nt, "SINE", _math(nt, "MULTIPLY", x, 2.0 * math.pi))
    env = _math(nt, "MAXIMUM", _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", _math(nt, "ABSOLUTE", x), 0.5)), 0.0)
    return _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", wave, env), _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, age), 0.5))


def _wrap(ctx, mat, group, mode, lattice=None):
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
    height = nt.nodes.get("valora_scan_height")      # the world's scanned displacement, when it has one
    if height is not None:
        nt.links.new(height.outputs[0], g.inputs["Height"])
    nrm = sh.inputs["Normal"]
    if nrm.is_linked:
        nt.links.new(nrm.links[0].from_socket, g.inputs["Stone Normal"])
    else:
        nt.links.new(nt.nodes.new("ShaderNodeNewGeometry").outputs["Normal"], g.inputs["Stone Normal"])
    nt.links.new(g.outputs["Color"], sh.inputs["Base Color"])
    nt.links.new(g.outputs["Roughness"], sh.inputs["Roughness"])
    nt.links.new(g.outputs["Coat"], sh.inputs["Coat Weight"])
    nt.links.new(g.outputs["Coat Roughness"], sh.inputs["Coat Roughness"])
    nt.links.new(g.outputs["Coat Normal"], sh.inputs["Coat Normal"])
    sh.inputs["Coat IOR"].default_value = 1.333
    if mode == "rain" and lattice:
        nt.links.new(_impact_rings(ctx, nt, lattice), g.inputs["Ripple"])
    elif mode == "drips":   # rare, faint rings: after the rain the puddles are mirrors (Task 65 look-check)
        nt.links.new(_math(nt, "MULTIPLY", _rings(ctx, nt, W.DRIP_HZ, 1.2, W.DRIP_SPREAD), W.DRIP_AMP), g.inputs["Drip"])
    return g


def build(ctx):
    import bpy
    from engine.blender.realism_rig import ground_objects
    from engine.physics import wet as W
    ids = [e["id"] for e in ctx.script.get("effects", [])]
    from engine.physics import rain as R
    mode = W.ripple_mode(ctx.params, ids)
    lattice = R.clip_lattice(ctx.script, ctx.profile, ctx.camera_positions, ctx.camera_lenses_mm) if mode == "rain" else None
    group = _group(bpy, ctx)
    wrapped, placed = [], {}
    # one wrap per material across the whole ground (review chunk3 #9: ground pieces sharing a material got one
    # wrapper each, compounding the wetness)
    mats = {m.name: m for ob in ground_objects() for m in ob.data.materials if m is not None and m.use_nodes}
    for mat in mats.values():
        if _wrap(ctx, mat, group, mode, lattice) is not None:
            wrapped.append(mat.name)
        placed[mat.name] = sum(1 for n in mat.node_tree.nodes
                               if n.type == "GROUP" and n.node_tree is not None and n.node_tree.name == GROUP)
    g_nodes = [n for m in bpy.data.materials if m.name in placed for n in m.node_tree.nodes
               if n.type == "GROUP" and n.node_tree is group]
    ctx.scene["valora_fx_wet_surface"] = {
        "materials": sorted(wrapped), "groupsPerMaterial": placed, "rippleMode": mode or "none",
        "rippleLinked": any(n.inputs["Ripple"].is_linked for n in g_nodes), "impactLattice": lattice or {},
        "dripLinked": any(n.inputs["Drip"].is_linked for n in g_nodes),
        "puddleThreshold": W.puddle_threshold(ctx.params["puddles"]),
        "albedoFactor": W.albedo_factor(ctx.params["wetness"]), "roughFactor": W.roughness_factor(ctx.params["wetness"]),
        "scanHeight": sorted(m for m in wrapped if bpy.data.materials[m].node_tree.nodes.get("valora_scan_height"))}
    return group
