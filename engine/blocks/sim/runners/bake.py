"""runners: seed the drops on the host side (engine/physics/runners.seed_runners, from ctx.rng) on the upload's
side faces below the fill line, then bake the GN zone (engine/blender/runners) to ctx.bake["dir"] on the absolute
frame range (gn_disk)."""


def bake(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import runners as BR
    from engine.physics import runners as R
    from engine.physics import sim_facts
    p, fr, prof = ctx.params, ctx.bake["frames"], ctx.profile
    fill = sim_facts.fill_line(prof, ctx.script.get("markers") or [])
    verts, tris, normals = BR.world_triangles(ctx.meshes)
    z0 = prof.boundsMin[2]
    parts = R.seed_runners(verts, tris, normals, count=p["count"], fill_z=fill["z"], z_min=z0,
                           height=prof.boundsMax[2] - z0, first=fr["bake_first"], last=fr["bake_last"],
                           fps=ctx.scene.render.fps, speed_cms=p["speedCmS"], drop_mm=p["dropMm"], rng=ctx.rng)
    em = G.emitter_object("valora_runners_emitter", parts, extras=R.EXTRAS)
    ob = G.sim_object("valora_runners", BR.ensure(ctx, em), ctx.bake["dir"], fr, "sim/runners")
    G.bake_sim_object(ob)
    return {"runners": len(parts), "fillZ": round(fill["z"], 6), "fillSource": fill["source"],
            "substeps": R.SUBSTEPS}
