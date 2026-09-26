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


def shot_shares(ctx):
    """[(switch frame, streak share)] per shot: engine/physics/rain.streak_share by the shot's framing, switched on
    the camera's cut subframes (timeline: first - SHUTTER / 2)."""
    from engine.compiler.tiers import SHUTTER
    from engine.physics import rain as R
    fps, out = ctx.script["format"]["fps"], []
    keys = getattr(ctx, "camera_keys", None) or []           # a bare context (probes) has no timeline
    for i, sh in enumerate(ctx.script.get("shots") or []):
        detail = any(k.target is not None for k in keys if k.shot == i)
        f = 0.0 if i == 0 else int(round(sh["startS"] * fps)) + 1 - SHUTTER / 2
        out.append((f, R.streak_share(detail)))
    return out or [(0.0, R.STREAK_SHARE)]


def _key_share(socket_owner, path, base, shares):
    """Key base x share at every switch, CONSTANT between (a streak's brightness never fades across a cut)."""
    from engine.blender.realism_rig import fcurves
    owner, attr = socket_owner
    for f, k in shares:
        setattr(owner, attr, base * k)
        owner.keyframe_insert(path, frame=f)
    idb = owner.id_data
    for c in fcurves(idb.animation_data.action):
        for kp in c.keyframe_points:
            kp.interpolation = "CONSTANT"


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
    shares = shot_shares(ctx)
    glow = R.GLOW * p["backlight"] / 0.6
    rain_mat = wn.water("valora_rain_water", glow=glow)
    if glow > 0:     # the streaks' own brightness, cut per shot (critique mat-v2 #3)
        em = next(n for n in rain_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Emission Strength"]
        _key_share((em, "default_value"), "default_value", glow, shares)
    rv = d.node("FunctionNodeRandomValue", data_type="FLOAT")        # round 8: per-drop size (R.STREAK_SIZE)
    next(s for s in rv.inputs if s.name == "Min" and s.type == "VALUE").default_value = R.STREAK_SIZE[0]
    next(s for s in rv.inputs if s.name == "Max" and s.type == "VALUE").default_value = R.STREAK_SIZE[1]
    next(s for s in rv.inputs if s.name == "Seed").default_value = int(ctx.seed) % 100003
    size = next(s for s in rv.outputs if s.type == "VALUE")
    wn.instance(d, wn.ico(d, 1), d.vmath("SCALE", d.vec(r, r, 1.8 * r), scale=size), rotation=wn.align_z(d, fall),
                material=rain_mat)
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
        _key_share((ld, "energy"), "energy", energy, shares)

    scene["valora_fx_rain"] = {"count": n, "side": side, "height": height, "speedMs": speed, "dropSizeMm": size_mm,
                               "rateMmH": rate, "slantDeg": R.slant_deg(math.hypot(wind[0], wind[1]), speed),
                               "impactSlots": slots, "impactLattice": lattice or {}, "nearM": R.NEAR_FRAC * near, "backlightW": energy,
                               "streakShares": [k for _, k in shares],
                               "velocityMs": list(velocity),
                               "streakM": R.streak_len(math.hypot(*velocity), ctx.script["format"]["fps"])}
    return ob
