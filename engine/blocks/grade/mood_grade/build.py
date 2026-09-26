def build(ctx):
    from engine.blender.grade import realise
    from engine.grade_plan import keep_sun_colour, plan_for, with_capture
    plan = plan_for({"id": ctx.script["grade"]["id"], "params": ctx.params}, seed=ctx.script["seed"])
    plan = with_capture(keep_sun_colour(plan, ctx.script, ctx.params), ctx.script)
    return realise(ctx.scene, plan, ctx.meshes, seed=ctx.script["seed"])
