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
LOW_SUN_EL = 15.0           # a world's sun below this (golden_field dawn / golden / dusk) is a golden-hour sun ...
LOW_SUN_W = 18.0            # (eng) ... and keys at 18 W/m^2 (round 7: 10; round 9: 18, the side-lit flank and the
#                             grass still sat under the sky, owner's r8 grade "the car is very dark against a bright
#                             sky"): a low sun's orange light carries half the luminance of white, and at 4 W/m^2
#                             the golden field's sunlit grass and the car's sun side measured no brighter than the HDRI sky's shade (real_r6_field_golden: a flat
#                             warm tint, no sun). A real low sun still lights what faces it 3-5x the open shade.
OWN_K_LOW, OWN_K_HIGH = 3400.0, 5600.0   # (eng) own sun colour below / above 15 degrees
FILL_K = 6500.0             # the bounce card: open shade under a clear sky reads cool (round 8), never the sun
CABIN_SUN_K = 2.0           # (eng, round 11) the cabin spill under an 18 W/m^2 low sun: twice the overcast's
NOSE_K = 9000.0             # (eng, round 10) the sky behind the photographer, away from a low sun: a clear blue
NOSE_WATTS_K = 6.0          # (eng, round 10) x location_key.NOSE's radiance (the courtyard scrim's): under an 18 W/m^2 sun
#                             the r9 field's nose read near-black against the sunlit flank and grass (owner's r9 review)


def _nose_scrim(ctx, hero):
    """Round 10 (owner's r9 review of the field: "the car's nose reads near-black"): photographed black paint at golden
    hour mirrors the open sky behind the camera across the nose, a cool band against the warm flank. The courtyard's
    nose scrim placement (engine/lighting/location_key.nose_scrim) at the hero camera, in the sky's blue, lighting
    the paint only (never the glass or the cabin, which would show it as a panel); None where it would sit below
    the ground."""
    import bpy
    from engine.blender.lights import link_to
    from engine.blender.location_key import _cabin, _glassy, _orient
    from engine.color import kelvin_to_rgb
    from engine.lighting.location_key import nose_scrim
    keys = [k for k in (ctx.camera_keys or []) if k.shot == 0]      # the hook's camera (the frame a feed shows)
    pos = keys[len(keys) // 2].pose.position if keys else hero
    g = nose_scrim(ctx.profile, tuple(pos))
    if g is None:
        return None
    ld = bpy.data.lights.new("valora_sun_nose", "AREA")
    ld.shape, ld.size, ld.size_y = "RECTANGLE", g["sizeX"], g["sizeY"]
    ld.energy = g["watts"] * NOSE_WATTS_K
    ld.color = kelvin_to_rgb(NOSE_K)
    ob = bpy.data.objects.new("valora_sun_nose", ld)
    ctx.scene.collection.objects.link(ob)
    ob.location = g["center"]
    _orient(ob, g["facing"], g["axis"])
    ob.visible_camera = False
    ob["valora_block"] = "lighting/hard_sun"
    link_to([o for o in ctx.meshes if not _glassy(o) and not _cabin(o)], [ob], "valora_sun_nose_receivers")
    return ob


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
        kelvin = sun.get("valora_world_sun_k")      # the world's sun colour (golden_field tags it)
        d = sun.matrix_world.to_quaternion() @ Vector((0.0, 0.0, 1.0))
        el = math.degrees(math.asin(max(-1.0, min(1.0, d.z))))
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
        sun.data.energy = LOW_SUN_W if took_over and el < LOW_SUN_EL else SUN_W   # a world's golden sun
        sun.data.angle = math.radians(HARD_ANGLE_DEG)
    # the rim is the sun's own edge light (its colour); the bounce fill is open shade (neutral)
    low_world_sun = took_over and not keep_soft and el < LOW_SUN_EL
    # round 9 (owner's r8 grade: "the car is very dark, with contrasty studio-ish reflections, the grass says warm
    # sunset"): under a world's low sun the bounce is the sunlit meadow, not open shade, so the card takes the sun's
    # colour and the black flank mirrors one warm band of it (r9e without it: the flank went back to near-black)
    cards = [area_light(ctx.scene, spec, (kelvin or FILL_K) if spec.role == "rim" or low_world_sun else (
        FILL_K if took_over else kelvin)) for spec in R.hard_sun_cards(prof, hero, p)]
    for c in cards:
        c["valora_block"] = "lighting/hard_sun"
    link_to(ctx.meshes, cards, "valora_hard_sun_receivers")
    nose = _nose_scrim(ctx, hero) if low_world_sun else None
    if nose is not None:
        cards.append(nose)
    from engine.blender.lights import is_outdoor
    if is_outdoor(ctx):          # round 11: the cabin reads faintly through the windshield (location_key.CABIN_DAY)
        from engine.blender.location_key import CABIN_DAY, cabin_spill
        cab = cabin_spill(ctx, "lighting/hard_sun", CABIN_DAY["watts"] * CABIN_SUN_K, CABIN_DAY["kelvin"])
        if cab is not None:
            cards.append(cab)
    ctx.scene["valora_lighting"] = {"block": "hard_sun", "sunTakenOver": took_over, "sunKeptSoft": keep_soft,
                                    "sun": sun.name,
                                    "lights": facts([sun, *cards])}
