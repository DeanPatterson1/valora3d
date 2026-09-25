"""rain: stateless falling water (port of render-studio rain_atmosphere.build + rain_look, generalised; the
maths and its (eng) numbers live in engine/physics/rain.py).

render-studio cast every column against the car once (a BVH) and grew the cloud tall enough for the whole
clip. Here the drops are analytic (engine/blender/weather_nodes.box_points): a seeded lattice in a square box
that follows the camera, advanced by velocity x Scene Time and wrapped, so any frame evaluates on its own
(METHODS R1). The subject shelters the rain through its posed footprint (valora_realism_offset), so a moving
subject stays dry underneath. Drops are real size (dropSizeMm), slightly elongated like render-studio's, and
carry a `velocity` attribute so Cycles blurs them into streaks of speed x shutter (METHODS R7). Ground crowns
come from the impact lattice (lattice_impacts) that wet_surface's ripples also read. A rain-only area light behind the subject (light linking: receivers = the rain) makes
the streaks read without relighting the subject (LM-05). No car gates, no mesh names."""
import math

BACKLIGHT_W = 3200.0      # render-studio's rain lamp at backlight 1, car scale (4.5 m); scales with size^2
CAR_M = 4.5


def build(ctx):
    import bpy
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.blender.realism_rig import OFFSET
    from engine.physics import rain as R
    from engine.physics import wind as W
    from engine.physics.wind_calibration import perms
    scene, prof, p = ctx.scene, ctx.profile, ctx.params
    rate, size_mm = R.resolve(p)
    speed = R.fall_speed(size_mm)
    w = scene.get("valora_wind") or {"directionDeg": 0.0, "speedMs": 0.0}
    k = perms(ctx.catalog, "effect", "rain")
    wind = W.vector(float(w["directionDeg"]), float(w["speedMs"]) * k)
    fall = R.slant_vector(wind, speed)             # orientation only
    velocity = R.velocity(wind, speed)             # the drift: full wind and full fall speed (review chunk3 #3)
    side, height, far, near = R.clip_box(prof, ctx.camera_positions, ctx.camera_lenses_mm)
    n = R.drop_count(rate, side * side * height)
    r = R.VISIBLE_SIZE_K * size_mm / 2000.0          # render-studio's visibility cheat (see engine/physics/rain.py)
    offset = bpy.data.objects[OFFSET]

    ob = wn.weather_object(scene, "valora_rain", "effect/rain")
    ob.visible_shadow = False
    t = Tree("valora_rain_points")
    centre = wn.box_centre(t, prof.center[:2])
    vel = t.vec(*velocity)
    wn.box_points(t, n, ctx.seed, side, height, centre, t.vmath("SCALE", vel, scale=t.time()))
    # gustiness and turbulence of the one field (review chunk3 #4); velocity = d(position)/dt (review chunk5 #9)
    wn.gusts(t, wind, k, vel)
    wn.shelter(t, offset, prof.boundsMin, prof.boundsMax, near_m=R.NEAR_FRAC * near)
    add_modifier(ob, t.finish(), "valora_rain_points")
    d = Tree("valora_rain_drops")
    wn.instance(d, wn.ico(d, 1), (r, r, 1.8 * r), rotation=wn.align_z(d, fall), material=wn.water("valora_rain_water", glow=R.GLOW * p["backlight"] / 0.6))
    add_modifier(ob, d.finish(), "valora_rain_drops")

    slots = 0
    receivers = bpy.data.collections.new("valora_rain_receivers")
    receivers.objects.link(ob)
    lattice = R.clip_lattice(ctx.script, prof, ctx.camera_positions, ctx.camera_lenses_mm)  # wet_surface's too
    if p["impacts"] and lattice is not None:
        slots = R.impact_slots(rate, size_mm, side * side)
        imp = wn.weather_object(scene, "valora_rain_impacts", "effect/rain")
        imp.visible_shadow = False
        g = Tree("valora_rain_impacts")
        scale = wn.lattice_impacts(g, lattice, wn.box_centre(g, prof.center[:2]), r)
        wn.shelter(g, offset, prof.boundsMin, prof.boundsMax, top=False)
        wn.instance(g, wn.ring(g), scale, material=wn.water("valora_rain_crown"))
        add_modifier(imp, g.finish(), "valora_rain_impacts")
        receivers.objects.link(imp)

    energy = 0.0
    if p["backlight"] > 0 and ctx.hero_pose is not None:
        cx, cy, cz = prof.center
        hx, hy = ctx.hero_pose.position[0] - cx, ctx.hero_pose.position[1] - cy
        hl = math.hypot(hx, hy) or 1.0
        k = prof.longest / CAR_M
        energy = BACKLIGHT_W * p["backlight"] * k * k
        ld = bpy.data.lights.new("valora_rain_backlight", "AREA")
        ld.energy, ld.shape = energy, "RECTANGLE"
        ld.size, ld.size_y = 1.5 * prof.longest, 0.7 * prof.longest
        ld.color, ld.volume_factor = (0.8, 0.9, 1.0), 0.0
        lo = bpy.data.objects.new("valora_rain_backlight", ld)
        lo["valora_block"] = "effect/rain"
        scene.collection.objects.link(lo)
        back = 0.9 * prof.longest                                   # behind the subject, seen from the hero camera
        lo.location = (cx - hx / hl * back, cy - hy / hl * back, cz + 0.9 * prof.longest)
        from mathutils import Vector
        aim = Vector((cx, cy, cz)) - Vector(lo.location)
        lo.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
        lo.light_linking.receiver_collection = receivers         # the streaks only (LM-05): the subject is not relit

    scene["valora_fx_rain"] = {"count": n, "side": side, "height": height, "speedMs": speed, "dropSizeMm": size_mm,
                               "rateMmH": rate, "slantDeg": R.slant_deg(math.hypot(wind[0], wind[1]), speed),
                               "impactSlots": slots, "impactLattice": lattice or {}, "nearM": R.NEAR_FRAC * near, "backlightW": energy,
                               "velocityMs": list(velocity),
                               "streakM": R.streak_len(math.hypot(*velocity), ctx.script["format"]["fps"])}
    return ob
