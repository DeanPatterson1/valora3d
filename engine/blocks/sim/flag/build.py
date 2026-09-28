"""flag build (phase 6 Task 109; METHODS SC-01): the stateless travelling-wave flag of engine/physics/cloth_waves
keyed per frame as shape keys (engine/blender/cloth.shape_sequence) over the whole clip, on a real-size pole
behind the subject. The wind is the script's one wind (speed, direction); calm air hangs the flag. Nothing is
simulated (bake.method "none", ctx.bake is None)."""

COLOURS = {"white": (0.6, 0.6, 0.58), "black": (0.015, 0.015, 0.016), "red": (0.45, 0.02, 0.025),
           "navy": (0.012, 0.02, 0.08)}


def build(ctx):
    import bpy
    from engine.blender import cloth as BC
    from engine.physics import cloth_waves as F
    s = ctx.script
    fps, dur = s["format"]["fps"], s["format"]["durationS"]
    wp = ((s.get("wind") or {}).get("params") or {})
    speed, direction = float(wp.get("speedMs", 0.0)), float(wp.get("directionDeg", 0.0))
    cam = ctx.hero_pose.position if ctx.hero_pose is not None else None
    pole = F.flag_pole_xy(ctx.profile, (cam[0], cam[1]) if cam is not None else None, direction)
    n = int(round(dur * fps)) + 1
    ph = F.pole_height(ctx.profile)
    frames = {f: F.flag_positions((f - 1) / fps, speed, direction, pole, ctx.seed, ph) for f in range(1, n + 1)}
    ob = BC.sheet("valora_flag", frames[1], F.flag_faces())
    ob["valora_block"] = "sim/flag"
    BC.shape_sequence(ob, frames)
    ob.data.materials.append(BC.fabric_material("valora_flag_" + ctx.params["colour"],
                                                COLOURS[ctx.params["colour"]], 0.6, 0.3, 0.5))
    for poly in ob.data.polygons:
        poly.use_smooth = True
    bpy.ops.mesh.primitive_cylinder_add(radius=F.POLE_R, depth=ph, location=(pole[0], pole[1], ph / 2))
    pl = bpy.context.object
    pl.name = "valora_flag_pole"
    pl["valora_block"] = "sim/flag:pole"
    m = bpy.data.materials.new("valora_flag_pole")
    m.use_nodes = True
    b = next(x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.55, 0.55, 0.56, 1.0)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.35
    pl.data.materials.append(m)
    return ob
