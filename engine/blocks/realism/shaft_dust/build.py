"""Dust in light shafts (TAXONOMY PT-01, LM-03; METHODS §2.6 PT-01). Up to N_MAX tiny points in the haze
shell around the subject (between the clear pocket's outer radius and the haze's full-density radius),
drifting with the mean wind plus a slow wander, wrapped inside the shell's box. Not emissive and not
shadow-casting: a mote reads only where a light beam crosses it, i.e. in the shafts the haze shows.
Motes are rendered at ~MOTE_PX pixels (real dust is 20-100 um; METHODS PT-01's deliberate cheat), sized from
the median metres-per-pixel over the camera keys (each key's distance and its own lens, review item 10). A
mote whose wrapped position falls inside the clear pocket (haze_volume's POCKET, imported) gets radius 0
(never seen, never inside the subject), and motes shrink to nothing within FADE_FRAC of a wrap face, so none
pops in or out where the box wraps. Stateless: position = base + drift(t), no frame depends on the one before."""
import math

N_MAX = 4000        # motes at density 1 (eng)
MOTE_PX = 1.5       # rendered diameter in pixels at the median camera distance, 1080 short side (eng)
WANDER_FRAC = 0.05  # wander amplitude, x subject radius (eng; METHODS 1-3 cm/s brownian at car scale)
FADE_FRAC = 0.1     # motes fade out over the outer 10% of the wrap box's smallest side (eng)
SENSOR_MM = 36.0    # engine/geometry.SENSOR_MM (the camera's long side)


def build(ctx):
    import bpy
    from engine.blender import gn
    from engine.blender.realism_rig import record
    from engine.physics import wind as W
    scene, prof = ctx.scene, ctx.profile
    fade = scene.get("valora_haze_fade")
    n = int(N_MAX * ctx.params["density"])
    if fade is None or n == 0:          # haze skipped (skip_kinds) or density 0
        record("dust_points", 0)
        record("dust_emissive", False)
        return
    cx, cy, cz, r_full, _ = [float(v) for v in fade]
    r = prof.radius
    pocket_out = ctx.catalog.load_builder("effect", "haze_volume").__globals__["POCKET"][1]   # one source
    inner, outer = pocket_out * r, max(pocket_out * r * 1.5, min(r_full, 4.0 * r))
    lo = (cx - outer, cy - outer, max(0.0, cz - outer))
    span = (2 * outer, 2 * outer, cz + outer - lo[2])
    base = []
    while len(base) < n:
        p = (lo[0] + ctx.rng.random() * span[0], lo[1] + ctx.rng.random() * span[1],
             lo[2] + ctx.rng.random() * span[2])
        if inner <= math.dist(p, (cx, cy, cz)) <= outer:
            base.append(p)
    me = bpy.data.meshes.new("valora_rz_dust")
    me.from_pydata(base, [], [])
    ob = bpy.data.objects.new("valora_rz_dust", me)
    scene.collection.objects.link(ob)
    ob.visible_shadow = False
    w = scene.get("valora_wind") or {"directionDeg": 0.0, "speedMs": 0.0}
    vx, vy, _ = W.vector(float(w["directionDeg"]), float(w["speedMs"]))
    lens = ctx.camera_lenses_mm or [50.0] * len(ctx.camera_positions)
    mpp = sorted(math.dist(c, prof.center) * SENSOR_MM / lm / 1080.0          # metres per pixel at each key
                 for c, lm in zip(ctx.camera_positions, lens)) or [4.0 * r * SENSOR_MM / 50.0 / 1080.0]
    m_per_px = mpp[len(mpp) // 2]
    radius = 0.5 * MOTE_PX * m_per_px
    fade_w = FADE_FRAC * min(span)
    t = gn.Tree("valora_rz_dust")
    sec = t.time()
    pos = t.position()
    _, col = t.noise(t.vmath("ADD", t.vmath("SCALE", pos, scale=1.0 / r), t.vec(0.0, 0.0, t.math("MULTIPLY", sec, 0.3))))
    wander = t.vmath("SCALE", t.vmath("SUBTRACT", col, t.vec(0.5, 0.5, 0.5)), scale=2.0 * WANDER_FRAC * r)
    moved = t.vmath("ADD", t.vmath("ADD", pos, t.vmath("SCALE", t.vec(vx, vy, 0.0), scale=sec)), wander)
    mx, my, mz = t.xyz(moved)
    wrap = [t.math("WRAP", c, lo[k] + span[k], lo[k]) for k, c in enumerate((mx, my, mz))]   # sockets: Value, Max, Min
    p2 = t.vec(*wrap)
    d = t.vmath("DISTANCE", p2, t.vec(cx, cy, cz))
    face = None
    for k, c in enumerate(wrap):
        dk = t.math("MINIMUM", t.math("SUBTRACT", c, lo[k]), t.math("SUBTRACT", lo[k] + span[k], c))
        face = dk if face is None else t.math("MINIMUM", face, dk)
    rad = t.math("MULTIPLY", t.math("MULTIPLY", radius, t.math("GREATER_THAN", d, inner)),
                 t.smoothstep(0.0, fade_w, face))
    t.set_position(p2)
    t.store("valora_dust_r", rad, "FLOAT")
    gn.add_modifier(ob, t.finish(), "valora_rz_dust_move")
    t2 = gn.Tree("valora_rz_dust_points")
    pts = t2.node("GeometryNodeMeshToPoints")
    t2.feed(pts.inputs["Mesh"], t2.geometry)
    t2.feed(pts.inputs["Radius"], t2.attr("valora_dust_r"))
    mat = bpy.data.materials.new("valora_rz_dust")
    mat.use_nodes = True
    bsdf = next(nd for nd in mat.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.78, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Emission Strength"].default_value = 0.0
    sm = t2.node("GeometryNodeSetMaterial")
    t2.feed(sm.inputs["Geometry"], pts.outputs["Points"])
    sm.inputs["Material"].default_value = mat
    t2.geometry = sm.outputs["Geometry"]
    gn.add_modifier(ob, t2.finish(), "valora_rz_dust_points")
    record("dust_points", n)
    record("dust_emissive", False)
    record("dust_radius_m", radius)
    record("dust_m_per_px", m_per_px)
    record("dust_fade_m", fade_w)
    record("dust_box", [*lo, *(lo[k] + span[k] for k in range(3))])
