def build(ctx):
    """A studio three-point rig. Outdoors (art pass round 2) its lights reach the subject and the ground only:
    a softbox must not light a street's facades or a field's trees. The studio is untouched."""
    from engine.blender.lights import is_outdoor, link_to, outdoor_receivers, realise
    from engine.softbox import softbox_layout
    before = set(ctx.scene.objects)
    realise(ctx.scene, softbox_layout(ctx.profile, ctx.hero_pose.position, ctx.params), ctx.params["colorTempK"])
    if is_outdoor(ctx):
        lights = [o for o in set(ctx.scene.objects) - before if o.type == "LIGHT"]
        if lights:
            link_to(outdoor_receivers(ctx.scene, ctx.meshes), lights, "valora_softbox_receivers")
