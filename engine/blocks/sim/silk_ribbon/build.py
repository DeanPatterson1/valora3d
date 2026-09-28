"""silk_ribbon build (phase 6 Task 109; METHODS SC-05): the stateless ribbon of engine/physics/cloth_waves keyed
per frame as shape keys (engine/blender/cloth.shape_sequence) over the whole clip; outside the subject's bounds
by construction. Nothing is simulated (bake.method "none")."""

COLOURS = {"ivory": (0.70, 0.66, 0.57), "champagne": (0.62, 0.50, 0.34), "deep_red": (0.25, 0.012, 0.02),
           "black": (0.012, 0.012, 0.013)}


def build(ctx):
    from engine.blender import cloth as BC
    from engine.physics import cloth_waves as R
    s, p = ctx.script, ctx.params
    fps, dur = s["format"]["fps"], s["format"]["durationS"]
    cam = ctx.hero_pose.position if ctx.hero_pose is not None else None
    cxy = (cam[0], cam[1]) if cam is not None else None
    n = int(round(dur * fps)) + 1
    frames, faces = {}, None
    for f in range(1, n + 1):
        frames[f], faces = R.ribbon_positions((f - 1) / fps, ctx.profile, p["widthFrac"], p["flow"], ctx.seed, cxy)
    ob = BC.sheet("valora_silk_ribbon", frames[1], faces)
    ob["valora_block"] = "sim/silk_ribbon"
    BC.shape_sequence(ob, frames)
    ob.data.materials.append(BC.fabric_material("valora_ribbon_" + p["colour"], COLOURS[p["colour"]], 0.3, 0.8, 0.25))
    for poly in ob.data.polygons:
        poly.use_smooth = True
    sub = ob.modifiers.new("valora_smooth", "SUBSURF")
    sub.levels, sub.render_levels = 0, 1
    return ob
