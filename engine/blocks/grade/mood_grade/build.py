def build(ctx):
    from engine.blender.grade import realise
    from engine.grade_plan import keep_sun_colour, plan_for
    plan = plan_for({"id": ctx.script["grade"]["id"], "params": ctx.params}, seed=ctx.script["seed"])
    return realise(ctx.scene, keep_sun_colour(plan, ctx.script, ctx.params), ctx.meshes, seed=ctx.script["seed"])
