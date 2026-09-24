HAZE_K = 0.4        # optical depth ~0.5 across 5 radii at density 0.25 (eng: calibrate via T2-07 [M])
TINTS = {"neutral": (1.0, 1.0, 1.0, 1.0), "warm": (1.0, 0.93, 0.85, 1.0), "cool": (0.86, 0.93, 1.0, 1.0)}


def build(ctx):
    import bpy
    p, prof = ctx.params, ctx.profile
    r = prof.radius
    pts = list(ctx.camera_positions) + [tuple(prof.boundsMin), tuple(prof.boundsMax)]
    lo = [min(q[i] for q in pts) for i in range(3)]
    hi = [max(q[i] for q in pts) for i in range(3)]
    pad = 0.2 * max(h - l for l, h in zip(lo, hi)) + 0.5 * r
    lo = [lo[0] - pad, lo[1] - pad, -0.01 * r]
    hi = [hi[0] + pad, hi[1] + pad, hi[2] + pad]
    me = bpy.data.meshes.new("valora_haze")
    v = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new("valora_haze", me)
    ctx.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new("valora_haze")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = TINTS[p["tint"]]
    vol.inputs["Anisotropy"].default_value = p["anisotropy"]
    density = p["density"] * HAZE_K / r
    if p["clearPocket"]:
        centre = bpy.data.objects.new("valora_subject_centre", None)
        ctx.scene.collection.objects.link(centre)
        centre.location = prof.center
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.object = centre
        length = nt.nodes.new("ShaderNodeVectorMath")
        length.operation = "LENGTH"
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 1.0 * r, 2.0 * r
        ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = 0.0, density
        nt.links.new(tc.outputs["Object"], length.inputs[0])
        nt.links.new(length.outputs["Value"], ramp.inputs["Value"])
        nt.links.new(ramp.outputs["Result"], vol.inputs["Density"])
    else:
        vol.inputs["Density"].default_value = density
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    me.materials.append(mat)
    ob.visible_shadow = False
    ctx.scene["valora_haze_domain"] = [lo, hi]
