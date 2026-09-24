def build(ctx):
    from engine.blender.grade import realise
    from engine.grade_plan import plan_for
    return realise(ctx.scene, plan_for({"id": ctx.script["grade"]["id"], "params": ctx.params}), ctx.meshes)
