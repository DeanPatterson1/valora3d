def build(ctx):
    from engine.blender.lights import realise
    from engine.softbox import softbox_layout
    realise(ctx.scene, softbox_layout(ctx.profile, ctx.hero_pose.position, ctx.params), ctx.params["colorTempK"])
