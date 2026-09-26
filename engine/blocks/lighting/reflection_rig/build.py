"""Reflection rig. Light linking (Blender 5 Cycles, probed 2026-09-24): every rig light gets a
receiver collection holding the set (cyc, any world mesh) as EXCLUDE, so it lights the subject,
the haze and nothing else; the set neither receives it nor sees it in a glossy reflection. The
one floor pool gets the set as INCLUDE, lights nothing but the floor and is kept out of glossy
rays (a diffuse pool, never a mirrored rectangle). Without this the overhead and rim, placed
within a radius or two of the floor, lit a black cyc to ~109/255 and cut hard-edged light
blocks into it where their one-sided planes met the floor.

Outdoors (round 6) the studio overhead, strips and accents are not built: every shot gets the location crew's
per-set-up key and windshield flag (engine/lighting/location_key, as under hdri_only), the rim drops to a low,
dim edge light, and after dark the key is NIGHT_KEY_EV brighter."""


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
REFLECTION_ONLY_ROLES = ("overhead", "strip", "accent")   # studio cards a location shoot replaces (round 6)
OUTDOOR_KEY_ENV = "VALORA_LOCATION_KEY_W"                  # look-check brackets only, as under hdri_only
NIGHT_KEY_EV = 1.6          # after dark the key is this much brighter than hdri_only's overcast 35 W: bracketed on the
#                             night street's near-front hero (preview, 1x / 3x / 8x): 1x left a silhouette, 8x a white
#                             patch on the hood, 3x (+1.6 stops) one soft band across the bonnet and wing
OUTDOOR_RIM = {"elevationDeg": 12.0, "power": 0.25}       # round 6: the studio rim at 30-60 deg sat exactly where a
# low front camera's windshield and roof mirror (a white cap over the glass in a variant render); at 12 deg and a
# quarter power it draws the roofline and the hood's silhouette as a thin line, as a distant street light would


def _outdoor(layout, profile):
    """The layout a location keeps (round 6, 2026-09-25). A studio's overhead, strips and accents are placed
    once, for the hero pose, and mirror wherever the other set-ups look: under a dark street sky the overhead
    filled the low hero's windshield and hood with a white rectangle and the strips turned the bumper and intake
    white (real_r5_street_night; a variant render without them was black paint again). Outdoors they are dropped
    and every shot gets the crew's per-set-up key and windshield flag instead (engine/lighting/location_key),
    the same shaping hdri_only carries. The rim, the negative fill and the floor pool stay."""
    import dataclasses
    import math
    from engine.geometry import _norm, _sub
    from engine.reflect import RigLayout
    kept = []
    for s in layout.lights:
        if s.role in REFLECTION_ONLY_ROLES:
            continue
        if s.role == "rim":
            cx, cy, cz = profile.center
            dx, dy = s.center[0] - cx, s.center[1] - cy
            h = math.hypot(dx, dy) or 1.0
            dist = math.dist(s.center, profile.center)
            el = math.radians(OUTDOOR_RIM["elevationDeg"])
            c = (cx + dx / h * dist * math.cos(el), cy + dy / h * dist * math.cos(el), cz + dist * math.sin(el))
            s = dataclasses.replace(s, center=c, facing=_norm(_sub(profile.center, c)),
                                    power=s.power * OUTDOOR_RIM["power"])
        kept.append(s)
    return RigLayout(tuple(kept), layout.ambient, layout.notes)


def build(ctx):
    import os
    import bpy
    from engine.blender.lights import facts, is_outdoor, realise
    from engine.reflect import rig_layout
    layout = rig_layout(ctx.profile, ctx.hero_pose.position, ctx.params)
    outdoor = is_outdoor(ctx)            # the studio is untouched
    if outdoor:
        layout = _outdoor(layout, ctx.profile)
    realise(ctx.scene, layout, ctx.params["colorTempK"], ctx.params["exposureEv"])
    if outdoor:
        for spec in layout.lights:
            ob = ctx.scene.objects.get(spec.name)
            if ob is not None and spec.role == "negfill":   # no black rectangles mirrored in outdoor water
                ob.visible_glossy = False
            if ob is not None and ob.type == "LIGHT" and ob.data.type == "AREA" and spec.name != "valora_floor_pool":
                ob.data.size *= OUTDOOR_SOFT_K
                ob.data.size_y *= OUTDOOR_SOFT_K
    link_to_subject(bpy, ctx.scene, layout, ctx.meshes)
    if outdoor and ctx.camera_keys:
        from engine.blender.location_key import build as location_key
        w = os.environ.get(OUTDOOR_KEY_ENV)
        from engine.subject_prep import conditions
        dark = conditions(ctx.script, True)["dark"]
        objs, shaping = location_key(ctx, "lighting/reflection_rig", watts=float(w) if w else None,
                                     ev=float(ctx.params["exposureEv"]) + (NIGHT_KEY_EV if dark else 0.0),
                                     sheen=dark)       # round 7: after dark the car reads by street-light sheen
        ctx.scene["valora_lighting"] = {"block": "reflection_rig", "shaping": shaping, "lights": facts(objs)}


def finalize(ctx):
    """Water built on the subject after the lighting (droplets) catches the per-shot key too (round 6)."""
    from engine.blender.lights import is_outdoor
    if is_outdoor(ctx) and ctx.camera_keys:
        from engine.blender.location_key import link_weather
        link_weather(ctx.scene)
