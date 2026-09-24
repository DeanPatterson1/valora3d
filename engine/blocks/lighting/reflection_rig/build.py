def build(ctx):
    from engine.blender.lights import realise
    from engine.reflect import rig_layout
    layout = rig_layout(ctx.profile, ctx.hero_pose.position, ctx.params)
    realise(ctx.scene, layout, ctx.params["colorTempK"], ctx.params["exposureEv"])
