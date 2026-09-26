def build(ctx):
    from engine.blender.grade import realise
    from engine.grade_plan import plan_for, with_capture
    return realise(ctx.scene, with_capture(plan_for({"id": ctx.script["grade"]["id"], "params": ctx.params},
                                                    seed=ctx.script["seed"]), ctx.script), ctx.meshes,
                   seed=ctx.script["seed"])
