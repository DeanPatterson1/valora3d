"""hard_sun (phase 5 Task 72): the sun is the key.

A world that owns a sun (golden_field tags it valora_world_sun) keeps its direction and colour (timeOfDay,
sunAzimuthDeg); hard_sun takes it over: a crisp angular size and the key's strength. Never a second SUN.
A world sun tagged valora_world_sun_soft (golden_field overcast) keeps its own strength and angular size: an
overcast sky is soft by definition and a crisp 4 W/m^2 key would defeat it (review chunk 4 #6); the takeover
then only adds the cards. valora_* props are the engine's alone (scene_io strips them from uploads).
Elsewhere it adds its own SUN at elevationDeg, side-back from the hero view (engine/lighting/rigs.py). A bounce
card (fillRatio) and an optional rim (rim) light the subject only (light linking), never the set."""
import math

HARD_ANGLE_DEG = 0.53       # the real sun's angular diameter
SUN_W = 4.0                 # (eng) sun strength, W/m^2, as the key
OWN_K_LOW, OWN_K_HIGH = 3400.0, 5600.0   # (eng) own sun colour below / above 15 degrees


def build(ctx):
    import bpy
    from mathutils import Vector
    from engine.blender.lights import area_light, facts, link_to
    from engine.color import kelvin_to_rgb
    from engine.lighting import rigs as R
    p, prof = ctx.params, ctx.profile
    hero = ctx.hero_pose.position
    sun = next((o for o in ctx.scene.objects if o.type == "LIGHT" and o.get("valora_world_sun")), None)
    took_over = sun is not None
    keep_soft = bool(took_over and sun.get("valora_world_sun_soft"))
    if took_over:
        kelvin = None
    else:
        el = float(p["elevationDeg"])
        kelvin = OWN_K_LOW if el < 15.0 else OWN_K_HIGH
        ld = bpy.data.lights.new("valora_hard_sun", "SUN")
        ld.color = kelvin_to_rgb(kelvin)
        sun = bpy.data.objects.new("valora_hard_sun", ld)
        ctx.scene.collection.objects.link(sun)
        d = R.sun_vector(prof, hero, R.OWN_SUN_AZ, el)
        sun.rotation_euler = Vector([-c for c in d]).to_track_quat("-Z", "Y").to_euler()
        sun["valora_block"] = "lighting/hard_sun"
    if not keep_soft:
        sun.data.energy = SUN_W
        sun.data.angle = math.radians(HARD_ANGLE_DEG)
    card_k = kelvin or 4500.0
    cards = [area_light(ctx.scene, spec, card_k) for spec in R.hard_sun_cards(prof, hero, p)]
    for c in cards:
        c["valora_block"] = "lighting/hard_sun"
    link_to(ctx.meshes, cards, "valora_hard_sun_receivers")
    ctx.scene["valora_lighting"] = {"block": "hard_sun", "sunTakenOver": took_over, "sunKeptSoft": keep_soft,
                                    "sun": sun.name,
                                    "lights": facts([sun, *cards])}
