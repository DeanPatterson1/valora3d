"""night_street: a wet city street at dusk or night (phase 5 Task 70). Procedural, CC0 by construction.

The layout is pure (engine/worlds/street_layout.py); this file only realises it:
- the road (valora_ground at z = 0) in Poly Haven asphalt_02 when pinned (Task 62), else noise asphalt, with
  painted lane markings; kerbs and pavements at real size;
- facade blocks with a window grid (a window is lit when its seeded key is under windowsLit) and a warm
  shopfront glow at street level;
- street lamps: a post, an emissive head and a warm SPOT practical (2700-3500 K);
- 0-4 neon bars: plain coloured emissive strips (no text, no logos), hue from neonHue, strength neonAmount;
- sky: a dark gradient at night, or a physical sky with the sun 2 degrees below the horizon at dusk; the lower
  hemisphere gain is LOWER_GAIN (CATALOG-GAPS rank 7: 0.05-0.2).
`wetness` is the street's own damp sheen; when wet_surface is in the script it takes over (the world's sheen is
0). The upload's materials are never touched (spec §4.5). Numbers marked (eng) are in the register."""
import dataclasses
import math

BLOCK = "world/night_street"
TILE_M = 3.0                  # (eng) asphalt texture tile, metres
DASH = (3.0, 6.0, 0.12)       # (eng) centre-line dash length, gap, width (real size)
EDGE_LINE_W = 0.10            # (eng) edge line width, 0.3 m in from the kerb
LAMP_LM = (800.0, 1500.0)     # plan: lamp output, lumens
LAMP_K = (2700.0, 3500.0)     # plan: warm lamp colour temperature
W_PER_LM = 0.3                # (eng) Blender watts per lumen for a night exposure (not photometric: calibrated
                              # by the Task 70 look-check against the grade's exposure)
LAMP_SPOT_DEG = 120.0         # (eng) lamp cone
NEON_STRENGTH = 40.0          # (eng) neon emission at neonAmount 1
WINDOW_STRENGTH = 2.5         # (eng) lit window emission
SHOP_STRENGTH = 1.2           # (eng) shopfront glow emission
LOWER_GAIN = 0.1              # CATALOG-GAPS rank 7 (0.05-0.2): lower hemisphere x the horizon colour
NIGHT_SKY = ((0.0016, 0.0020, 0.0042), (0.010, 0.012, 0.022))   # (eng) zenith, horizon (linear)
DUSK_SUN_DEG = -2.0           # plan: the sun 2 degrees below the horizon at dusk
DUSK_STRENGTH = 0.35          # (eng) dusk sky strength


def _sky(bpy, ctx, tod):
    from engine.blender.set_parts import nishita
    w = bpy.data.worlds.new("valora_street_sky")
    w.use_nodes = True
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    norm = nt.nodes.new("ShaderNodeVectorMath")
    norm.operation = "NORMALIZE"
    nt.links.new(tc.outputs["Generated"], norm.inputs[0])
    nt.links.new(norm.outputs["Vector"], sep.inputs[0])
    if tod == "dusk":
        colour = nishita(nt, tc.outputs["Generated"], DUSK_SUN_DEG, dust=2.0, air=1.5).outputs["Color"]
        horizon = (0.05, 0.045, 0.06)
        strength = DUSK_STRENGTH
    else:
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.0, 1.0
        ramp.color_ramp.elements[0].color = (*NIGHT_SKY[1], 1.0)     # horizon
        ramp.color_ramp.elements[1].color = (*NIGHT_SKY[0], 1.0)     # zenith
        up = nt.nodes.new("ShaderNodeMath")
        up.operation = "MAXIMUM"
        up.inputs[1].default_value = 0.0
        nt.links.new(sep.outputs["Z"], up.inputs[0])
        nt.links.new(up.outputs[0], ramp.inputs["Fac"])
        colour, horizon, strength = ramp.outputs["Color"], NIGHT_SKY[1], 1.0
    below = nt.nodes.new("ShaderNodeMix")                      # the lower hemisphere: a dim ground bounce
    below.data_type = "RGBA"
    step = nt.nodes.new("ShaderNodeMath")
    step.operation = "LESS_THAN"
    step.inputs[1].default_value = 0.0
    nt.links.new(sep.outputs["Z"], step.inputs[0])
    nt.links.new(step.outputs[0], below.inputs["Factor"])
    nt.links.new(colour, below.inputs[6])
    below.inputs[7].default_value = (*(LOWER_GAIN * c for c in horizon), 1.0)
    nt.links.new(below.outputs[2], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    ctx.scene.world = w


def _along(lay):
    return 1 if lay["road"]["alongAxis"] == "y" else 0


def _markings(lay, prof):
    """Dashed centre line and two edge lines, 2 mm above the road; no paint inside the subject's exclusion."""
    ia = 1 - _along(lay)
    cx, cy = lay["road"]["centre"]
    L, W = lay["road"]["length"], lay["road"]["width"]
    e = lay["exclusion"]
    rects = []
    v = -L / 2
    while v < L / 2:
        rects.append((-DASH[2] / 2, v, DASH[2] / 2, min(v + DASH[0], L / 2)))
        v += DASH[0] + DASH[1]
    for s in (-1, 1):
        u = s * (W / 2 - 0.3)
        rects.append((u - EDGE_LINE_W / 2, -L / 2, u + EDGE_LINE_W / 2, L / 2))
    out = []
    for u0, v0, u1, v1 in rects:
        if ia == 0:
            r = (cx + u0, cy + v0, cx + u1, cy + v1)
        else:
            r = (cx + v0, cy + u0, cx + v1, cy + u1)
        if r[0] < e[2] and e[0] < r[2] and r[1] < e[3] and e[1] < r[3]:
            continue
        out.append(r)
    return out


def _window_quads(fa, lay, lit_share, verts_on, faces_on, verts_off, faces_off):
    """Window quads 2 cm proud of the street face of a facade; lit when the window's key < lit_share."""
    from engine.blender.set_parts import quad
    ia = 1 - _along(lay)
    cx, cy = lay["road"]["centre"]
    u = fa["u"] - math.copysign(0.02, fa["u"])
    ww, wh = 1.2, 1.5
    for w in fa["windows"]:
        v0, v1, z0, z1 = w["v"] - ww / 2, w["v"] + ww / 2, w["z"], w["z"] + wh
        pts = [(u, v0, z0), (u, v1, z0), (u, v1, z1), (u, v0, z1)]
        corners = [((cx + a, cy + b, z) if ia == 0 else (cx + b, cy + a, z)) for a, b, z in pts]
        if w["key"] < lit_share:
            quad(verts_on, faces_on, corners)
        else:
            quad(verts_off, faces_off, corners)


def build(ctx):
    import bpy
    from engine.assets import resolve
    from engine.blender import set_parts as P
    from engine.color import kelvin_to_rgb
    from engine.worlds.street_layout import layout
    p, prof = ctx.params, ctx.profile
    m = ctx.catalog.get("world", "night_street")
    hero = ctx.hero_pose
    if hero is not None and ctx.camera_lenses_mm:
        hero = dataclasses.replace(hero, lens_mm=min(ctx.camera_lenses_mm))       # the widest lens the clip uses
    lay = layout(prof, ctx.seed, m["driveLaneM"], hero=hero, aspect=ctx.script["format"]["aspect"],
                 cameras=[tuple(c) for c in ctx.camera_positions])
    ids = [e["id"] for e in ctx.script.get("effects", [])]
    wet = 0.0 if "wet_surface" in ids else float(p["wetness"])           # wet_surface takes over
    tod = p["timeOfDay"]
    _sky(bpy, ctx, tod)

    cx, cy = lay["road"]["centre"]
    L, W = lay["road"]["length"], lay["road"]["width"]
    ax, ay = (W / 2, L / 2) if lay["road"]["alongAxis"] == "y" else (L / 2, W / 2)
    road = P.mesh(ctx.scene, "valora_street_road", BLOCK,
                  [(cx - ax, cy - ay, 0.0), (cx + ax, cy - ay, 0.0), (cx + ax, cy + ay, 0.0), (cx - ax, cy + ay, 0.0)],
                  [(0, 1, 2, 3)])
    P.tag(road, BLOCK, ground=True)
    maps = {k: resolve(f"asphalt_02_{k}") for k in ("diff", "rough", "nor_gl")}
    P.asphalt(road, maps, wet, "valora_street_asphalt", "valora_street", TILE_M)

    far = max(L, 60.0)                                                    # a dark apron to the horizon
    apron = P.mesh(ctx.scene, "valora_street_apron", BLOCK,
                   [(cx - far, cy - far, -0.01), (cx + far, cy - far, -0.01), (cx + far, cy + far, -0.01),
                    (cx - far, cy + far, -0.01)], [(0, 1, 2, 3)], [P.mat("valora_street_apron", (0.02, 0.02, 0.022), 0.8)])

    paint = P.mat("valora_street_paint", (0.55, 0.55, 0.52), 0.55)
    v, f = [], []
    for r in _markings(lay, prof):
        P.quad(v, f, [(r[0], r[1], 0.002), (r[2], r[1], 0.002), (r[2], r[3], 0.002), (r[0], r[3], 0.002)])
    marks = P.mesh(ctx.scene, "valora_street_markings", BLOCK, v, f, [paint]) if v else None

    stone = P.mat("valora_street_stone", (0.10, 0.10, 0.10), 0.7)
    paving = P.mat("valora_street_paving", (0.07, 0.07, 0.072), 0.75)
    v, f = [], []
    for it in lay["kerbs"]:
        P.aabb(v, f, it["min"], it["max"])
    kerbs = P.mesh(ctx.scene, "valora_street_kerbs", BLOCK, v, f, [stone])
    v, f = [], []
    for it in lay["pavements"]:
        P.aabb(v, f, it["min"], it["max"])
    pavements = P.mesh(ctx.scene, "valora_street_pavements", BLOCK, v, f, [paving])

    wall = P.mat("valora_street_facade", (0.045, 0.043, 0.041), 0.85)
    glass_off = P.mat("valora_street_window_dark", (0.01, 0.012, 0.015), 0.08)
    lit = P.emissive("valora_street_window_lit", kelvin_to_rgb(3000.0), WINDOW_STRENGTH)
    shop = P.emissive("valora_street_shopfront", kelvin_to_rgb(3400.0), SHOP_STRENGTH)
    v, f, von, fon, voff, foff, vs, fs = [], [], [], [], [], [], [], []
    ia = 1 - _along(lay)
    for fa in lay["facades"]:
        P.aabb(v, f, fa["min"], fa["max"])
        _window_quads(fa, lay, float(p["windowsLit"]), von, fon, voff, foff)
        if ctx.rng.random() < 0.5:                                        # a lit shopfront at street level
            u = fa["u"] - math.copysign(0.03, fa["u"])
            v0, v1 = fa["v0"] + 0.3, fa["v1"] - 0.3
            pts = [(u, v0, 0.4), (u, v1, 0.4), (u, v1, 2.6), (u, v0, 2.6)]
            P.quad(vs, fs, [((cx + a, cy + b, z) if ia == 0 else (cx + b, cy + a, z)) for a, b, z in pts])
    facades = [P.mesh(ctx.scene, "valora_street_facades", BLOCK, v, f, [wall])] if v else []
    windows = []
    if von:
        windows.append(P.mesh(ctx.scene, "valora_street_windows_lit", BLOCK, von, fon, [lit]))
    if voff:
        windows.append(P.mesh(ctx.scene, "valora_street_windows_dark", BLOCK, voff, foff, [glass_off]))
    if vs:
        windows.append(P.mesh(ctx.scene, "valora_street_shopfronts", BLOCK, vs, fs, [shop]))

    metal = P.mat("valora_street_lamp_post", (0.03, 0.032, 0.035), 0.35, 0.8)
    head_mats, lights = [], []
    v, f = [], []
    for i, it in enumerate(lay["lamps"]):
        x0, y0, _ = it["min"]
        x1, y1, _ = it["max"]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        P.aabb(v, f, (mx - 0.06, my - 0.06, 0.0), (mx + 0.06, my + 0.06, it["max"][2]))
        hx, hy, hz = it["head"]
        P.aabb(v, f, (min(mx, hx) - 0.04, min(my, hy) - 0.04, hz - 0.08), (max(mx, hx) + 0.04, max(my, hy) + 0.04, hz))
        kelvin = ctx.rng.uniform(*LAMP_K)
        lm = ctx.rng.uniform(*LAMP_LM)
        ld = bpy.data.lights.new(f"valora_street_lamp_{i}", "SPOT")
        ld.energy, ld.color = lm * W_PER_LM, kelvin_to_rgb(kelvin)
        ld.spot_size, ld.spot_blend = math.radians(LAMP_SPOT_DEG), 0.6
        ld.shadow_soft_size = 0.12
        lo = bpy.data.objects.new(f"valora_street_lamp_{i}", ld)
        ctx.scene.collection.objects.link(lo)
        lo.location = (hx, hy, hz - 0.12)                                  # just under the head, pointing down
        P.tag(lo, BLOCK)
        lights.append(lo)
        hv, hf = [], []
        P.quad(hv, hf, [(hx - 0.25, hy - 0.25, hz - 0.085), (hx + 0.25, hy - 0.25, hz - 0.085),
                        (hx + 0.25, hy + 0.25, hz - 0.085), (hx - 0.25, hy + 0.25, hz - 0.085)])
        head = P.mesh(ctx.scene, f"valora_street_lamp_head_{i}", BLOCK, hv, hf,
                      [P.emissive(f"valora_street_lamp_head_{i}", kelvin_to_rgb(kelvin), 6.0)])
        head.visible_shadow = False
        head_mats.append(head)
    posts = P.mesh(ctx.scene, "valora_street_lamp_posts", BLOCK, v, f, [metal]) if v else None

    neon = []
    for i, it in enumerate(lay["neon"]):
        colour = P.hue_rgb(float(p["neonHue"]) + it["hue"])
        nv, nf = [], []
        P.aabb(nv, nf, it["min"], it["max"])
        ob = P.mesh(ctx.scene, f"valora_street_neon_{i}", BLOCK, nv, nf,
                    [P.emissive(f"valora_street_neon_{i}", colour, NEON_STRENGTH * float(p["neonAmount"]))])
        ob.visible_shadow = False
        ob["valora_neon"] = True
        neon.append(ob)

    e = lay["exclusion"]
    props = [o for o in [kerbs, pavements, posts, *facades] if o is not None]
    inside = 0
    for ob in props + neon:
        inside += sum(1 for vv in ob.data.vertices if e[0] < vv.co.x < e[2] and e[1] < vv.co.y < e[3]
                      and vv.co.z > 0.0)
    items = lay["lamps"] + lay["neon"] + lay["facades"]              # every set piece a camera could stand in
    cams_in = sum(1 for c in ctx.camera_positions for it in items
                  if all(it["min"][i] <= c[i] <= it["max"][i] for i in range(3)))
    lit_n = sum(1 for fa in lay["facades"] for w in fa["windows"] if w["key"] < float(p["windowsLit"]))
    ctx.scene["valora_street"] = {
        "timeOfDay": tod, "asphaltMaps": all(maps.values()), "lamps": len(lights), "neon": len(neon),
        "neonHue": float(p["neonHue"]), "facades": len(lay["facades"]), "windowsLit": lit_n,
        "road": {k: v for k, v in lay["road"].items() if k != "alongAxis"}, "exclusion": list(e),
        "propVertsInExclusion": inside, "camerasInsideProps": int(cams_in), "wetness": wet,
        "markings": marks is not None, "apron": apron.name,
        "neonAllEmissive": all(any(n.type == "EMISSION" for n in mm.node_tree.nodes)
                               and not any(n.type == "BSDF_PRINCIPLED" for n in mm.node_tree.nodes)
                               for ob in neon for mm in ob.data.materials)}
    return road
