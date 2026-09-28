"""sparks bake (phase 6 Task 105): a seeded stream from the first emitter (a marker, else an emissive / exhaust
detail point; engine/physics/sim_facts.emitters) over the whole bake range, simulated on the shared GN point sim
against the subject's closed shell and the ground, baked to disk (gn_disk, absolute frames)."""


def bake(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import particle_pack as B
    from engine.physics import particle_pack as P
    from engine.physics.sim_facts import emitters
    fr, fps = ctx.bake["frames"], ctx.scene.render.fps
    em = emitters(ctx.profile, ctx.script.get("markers") or [])[0]
    parts = P.sparks(ctx.params, em, fr["bake_first"], fr["bake_last"], fps, ctx.rng)
    src = G.emitter_object("valora_sim_sparks_emitter", parts, extras=("temp",))
    ob = G.sim_object("valora_sim_sparks", B.sparks_group(src, ctx.bake["proxy"]["shell"], ctx.params["timeScale"], fps),
                      ctx.bake["dir"], fr, "sim/sparks")
    G.bake_sim_object(ob)
    return {"particles": len(parts), "emitter": em["source"], "frames": fr["bake_last"] - fr["bake_first"] + 1}
