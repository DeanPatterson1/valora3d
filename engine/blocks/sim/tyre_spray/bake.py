"""tyre_spray bake (phase 6 Task 106): seeded particles from the rolling tyre contacts of the driving subject
(engine/physics/road_spray.particles through the drive's pose function), on the shared GN point sim with the
tyre_spray step (engine/blender/road_spray), baked to disk (gn_disk, absolute frames: the pose is on render time)."""


def bake(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import road_spray as B
    from engine.physics import road_spray as R
    fr, fps = ctx.bake["frames"], ctx.scene.render.fps
    parts = R.particles("spray", ctx.params, ctx.script, ctx.profile, ctx.catalog, fr["bake_first"], fr["bake_last"],
                        fps, ctx.rng)
    src = G.emitter_object("valora_sim_tyre_spray_emitter", parts, extras=("puff",))
    ob = G.sim_object("valora_sim_tyre_spray", B.group("spray", src, ctx.params["timeScale"]), ctx.bake["dir"], fr,
                      "sim/tyre_spray")
    G.bake_sim_object(ob)
    return {"particles": len(parts), "puffs": int(sum(p["puff"] for p in parts)),
            "frames": fr["bake_last"] - fr["bake_first"] + 1}
