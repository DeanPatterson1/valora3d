"""Reflection rig. Light linking (Blender 5 Cycles, probed 2026-09-24): every rig light gets a
receiver collection holding the set (cyc, any world mesh) as EXCLUDE, so it lights the subject,
the haze and nothing else; the set neither receives it nor sees it in a glossy reflection. The
one floor pool gets the set as INCLUDE, lights nothing but the floor and is kept out of glossy
rays (a diffuse pool, never a mirrored rectangle). Without this the overhead and rim, placed
within a radius or two of the floor, lit a black cyc to ~109/255 and cut hard-edged light
blocks into it where their one-sided planes met the floor."""


def _receivers(bpy, name, objs, state):
    coll = bpy.data.collections.new(name)
    for o in objs:
        coll.objects.link(o)
    for co in coll.collection_objects:
        co.light_linking.link_state = state
    return coll


def link_to_subject(bpy, scene, layout, subject_meshes):
    rig = {spec.name for spec in layout.lights}
    subject = {o.name for o in subject_meshes}
    world = [o for o in scene.objects if o.type == "MESH" and o.name not in subject and o.name not in rig]
    lights = [scene.objects[s.name] for s in layout.lights if s.role != "negfill"]
    pool = [o for o in lights if o.name == "valora_floor_pool"]
    if not world:  # no set to light: a pool with an empty receiver set would light everything
        for o in pool:
            bpy.data.objects.remove(o)
        return
    skip = _receivers(bpy, "valora_rig_receivers", world, "EXCLUDE")
    only = _receivers(bpy, "valora_pool_receivers", world, "INCLUDE")
    for o in lights:
        if o in pool:
            o.light_linking.receiver_collection = only
            o.visible_glossy = False
        else:
            o.light_linking.receiver_collection = skip


OUTDOOR_SOFT_K = 2.2        # (eng) art pass round 4: outdoors each card is this much larger each way, same
                            # power (radiance / K^2): long, dim, soft sheens instead of small hard studio cards


def build(ctx):
    import bpy
    from engine.blender.lights import is_outdoor, realise
    from engine.reflect import rig_layout
    layout = rig_layout(ctx.profile, ctx.hero_pose.position, ctx.params)
    realise(ctx.scene, layout, ctx.params["colorTempK"], ctx.params["exposureEv"])
    if is_outdoor(ctx):                  # the studio is untouched
        for spec in layout.lights:
            ob = ctx.scene.objects.get(spec.name)
            if ob is not None and ob.type == "LIGHT" and ob.data.type == "AREA" and spec.name != "valora_floor_pool":
                ob.data.size *= OUTDOOR_SOFT_K
                ob.data.size_y *= OUTDOOR_SOFT_K
    link_to_subject(bpy, ctx.scene, layout, ctx.meshes)
