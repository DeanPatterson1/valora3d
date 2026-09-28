"""drape_reveal build (phase 6 Task 108): the baked sheet from cloth.pc2 (engine/blender/cloth.cached_sheet: a
MESH_CACHE modifier, sample i at render frame bake_first + offset + i; Cycles deformation blur), smoothed by one
subdivision level at render, in a fabric material. Reads the cache only; never simulates (SimInCompile)."""

COLOURS = {                 # (eng) linear base colours, restrained (the taste rule)
    "black": (0.012, 0.012, 0.013),
    "charcoal": (0.035, 0.036, 0.038),
    "ivory": (0.62, 0.58, 0.50),
    "deep_red": (0.22, 0.012, 0.016),
}
FABRIC = {                  # (eng) roughness, sheen weight, sheen roughness
    "silk": (0.32, 0.6, 0.3),
    "satin": (0.28, 0.8, 0.25),
    "canvas": (0.85, 0.3, 0.6),
}


def _material(colour, fabric):
    import bpy
    m = bpy.data.materials.new(f"valora_drape_{fabric}_{colour}")
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    rough, sheen, sheen_r = FABRIC[fabric]
    vals = {"Base Color": (*COLOURS[colour], 1.0), "Roughness": rough, "Sheen Weight": sheen,
            "Sheen Roughness": sheen_r}
    for name, v in vals.items():
        s = bsdf.inputs.get(name)
        if s is not None:
            s.default_value = v
    return m


def build(ctx):
    from engine.blender import cloth as BC
    p = ctx.params
    ob, _ = BC.cached_sheet(ctx, "valora_drape", "drape_reveal")
    ob.data.materials.append(_material(p["colour"], p["fabric"]))
    for poly in ob.data.polygons:
        poly.use_smooth = True
    sub = ob.modifiers.new("valora_smooth", "SUBSURF")
    sub.levels, sub.render_levels = 0, 1
    return ob
