"""bubbles bake (phase 6 Task 105): a seeded stream nucleating on the container floor (just above the subject's
lowest point) inside the opening's radius, rising to the fill line (engine/physics/sim_facts container +
fill_line), on the shared GN point sim, baked to disk (gn_disk, absolute frames). No collision: the bubbles
stay inside BUBBLE_WALL_FRAC of the radius and die at the fill line."""


def bake(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import particle_pack as B
    from engine.physics import particle_pack as P
    fr, fps = ctx.bake["frames"], ctx.scene.render.fps
    c, z0, z1 = _region(ctx)
    parts = P.bubbles(ctx.params, c, z0, z1, fr["bake_first"], fr["bake_last"], fps, ctx.rng)
    src = G.emitter_object("valora_sim_bubbles_emitter", parts, extras=("phase", "zig"))
    ob = G.sim_object("valora_sim_bubbles", B.bubbles_group(src, ctx.params["timeScale"]), ctx.bake["dir"], fr,
                      "sim/bubbles")
    G.bake_sim_object(ob)
    return {"particles": len(parts), "floorZ": z0, "fillZ": z1}


def _region(ctx):
    """The drink's axis and radius (sim_facts.container: a rim marker's ring measured about its axis), the inner
    floor and the fill line (never above the opening)."""
    from engine.physics.sim_facts import container, fill_line
    markers = ctx.script.get("markers") or []
    c = container(ctx.profile, markers)
    c = dict(c, radiusM=c["innerRadiusM"])      # the drink and its bubbles fill the inner wall, not the rim's outside
    z1 = min(fill_line(ctx.profile, markers)["z"], c["opening"][2])
    h = ctx.profile.boundsMax[2] - ctx.profile.boundsMin[2]
    return c, ctx.profile.boundsMin[2] + FLOOR_FRAC * h, z1


FLOOR_FRAC = 0.1     # (eng) the inner floor sits above the outer base (a tumbler 8-10 mm bottom)
