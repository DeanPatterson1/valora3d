"""practicals_only (round 13, owner's r12 review): no lighting rig of any kind.

The r12 night still described the car with designed light: the location crew's key, a warm street-sheen strip
along the flank, a lower scrim under the bumper and a wheel glint gave it a bright wraparound contour on the
roofline, fenders and bumper - "lit for beauty", the owner's #1 giveaway. A car parked on a real street is lit by
the street: its lamps (engine/blocks/world/night_street: mixed generations, the one it is parked under just out of
shot), its lit windows and the sky. So this block builds no key, rim, fill, sheen, scrim, flag or card. The
highlights fall where the lamps put them, uneven and partial, and panels facing away go near-black.

exposure meters the whole frame by 2^exposure as a camera would (hdri_only's meter: scene["valora_meter_ev"],
read by the grade), so the lamps, windows and sky move together and none is singled out.

straySpill: the one concession to the cabin. The night glass otherwise shows only reflections; on a real street
the nearest lamp leaks through the side glass onto part of a seat back and the dash edge. A narrow SPOT at that
lamp's own position (its colour, never brighter than it), aimed past the cabin's centre toward the far side so
the cone's edge crosses the interior, light-linked to the cabin materials alone. Where no lamp exists nothing is
built."""
import math

METER_KEY = "valora_meter_ev"
STRAY_NAME = "valora_stray_spill"
STRAY = {"coneDeg": 16.0, "blend": 0.35, "wattsAt1m": 16.0, "aimPast": 0.35}   # (eng, round 13): at 1.0 it
#   matches a 16 W point source a metre off; the aim point sits aimPast of the cabin's width beyond its centre on
#   the side away from the lamp, so the cone's edge falls across the seats instead of centring on them


def _lamp(scene, center):
    """The lamp nearest the subject's centre that the world built: the parked-under lamp first, else a street lamp."""
    hero = scene.objects.get("valora_street_hero_lamp")
    if hero is not None and hero.type == "LIGHT":
        return hero
    lamps = [o for o in scene.objects if o.type == "LIGHT" and o.name.startswith("valora_street_lamp")]
    return min(lamps, key=lambda o: math.dist(tuple(o.location), center)) if lamps else None


def stray_aim(center, cabin_w, lamp_at, past=STRAY["aimPast"]):
    """Pure: the point the stray cone aims at - the cabin's centre pushed `past` x cabin width away from the lamp
    (horizontally), so the lit patch is partial and on the far seats."""
    dx, dy = center[0] - lamp_at[0], center[1] - lamp_at[1]
    h = math.hypot(dx, dy) or 1.0
    return (center[0] + dx / h * past * cabin_w, center[1] + dy / h * past * cabin_w, center[2])


def build(ctx):
    from engine.blender.lights import facts, link_to
    p, prof = ctx.params, ctx.profile
    ev = float(p["exposure"])
    ctx.scene[METER_KEY] = float(ctx.scene.get(METER_KEY, 0.0)) + ev
    built = []
    spill = float(p["straySpill"])
    lamp = _lamp(ctx.scene, prof.center)
    if spill > 0 and lamp is not None:
        import bpy
        from mathutils import Vector
        from engine.blender.location_key import CABIN, _cabin
        cab = [o for o in ctx.meshes if _cabin(o)]
        if cab:
            lo, hi, c = prof.boundsMin, prof.boundsMax, prof.center
            at = (c[0], c[1], lo[2] + CABIN["zFrac"] * 0.8 * (hi[2] - lo[2]))
            width = min(hi[0] - lo[0], hi[1] - lo[1])
            aim = stray_aim(at, width, tuple(lamp.location))
            d = math.dist(tuple(lamp.location), aim)
            sd = bpy.data.lights.new(STRAY_NAME, "SPOT")
            sd.spot_size, sd.spot_blend = math.radians(STRAY["coneDeg"]), STRAY["blend"]
            sd.shadow_soft_size = 0.1
            sd.energy = spill * STRAY["wattsAt1m"] * d * d
            sd.color = tuple(lamp.data.color)
            so = bpy.data.objects.new(STRAY_NAME, sd)
            ctx.scene.collection.objects.link(so)
            so.location = tuple(lamp.location)
            so.rotation_euler = (Vector(aim) - Vector(tuple(lamp.location))).to_track_quat("-Z", "Y").to_euler()
            so.visible_camera = so.visible_glossy = False
            so["valora_block"] = "lighting/practicals_only"
            link_to(cab, [so], "valora_stray_spill_receivers")
            built.append(so)
    ctx.scene["valora_lighting"] = {"block": "practicals_only", "meterEv": ev, "rig": [],
                                    "strayFrom": lamp.name if (lamp is not None and built) else None,
                                    "lights": facts(built)}
