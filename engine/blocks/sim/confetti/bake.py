"""confetti bake (phase 6 Task 105): one seeded burst at the window start over a disc of spread x longest,
height x the subject height above the ground, fluttering down on the shared GN point sim against the closed
shell and the ground, baked to disk (gn_disk, absolute frames)."""


def bake(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import particle_pack as B
    from engine.physics import particle_pack as P
    fr, fps, p, prm = ctx.bake["frames"], ctx.scene.render.fps, ctx.profile, ctx.params
    h = p.boundsMax[2] - p.boundsMin[2]
    parts = P.confetti({"count": prm["count"], "spreadM": prm["spread"] * p.longest, "palette": prm["palette"]},
                       (p.center[0], p.center[1]), p.boundsMin[2] + prm["height"] * h, fr["clip_first"], fps, ctx.rng,
                       grade_colours=None)
    for q in parts:
        q["ang"], q["tilt"] = 0.0, 1.0
    src = G.emitter_object("valora_sim_confetti_emitter", parts,
                           extras=("colour", "metal", "phase", "spin", "ang", "tilt"))
    ob = G.sim_object("valora_sim_confetti", B.confetti_group(src, ctx.bake["proxy"]["shell"], prm["timeScale"]),
                      ctx.bake["dir"], fr, "sim/confetti")
    G.bake_sim_object(ob)
    return {"particles": len(parts), "frames": fr["bake_last"] - fr["bake_first"] + 1}
