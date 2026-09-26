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
0). The upload's materials are never touched (spec §4.5). Numbers marked (eng) are in the register.

Art pass (2026-09-25, the rain courtyard's recipe): with the pinned CC0 library the blocks are Poly Haven's
modular apartment facade (brick, cornices, real window and door frames with glass) over emissive room cards
that vary per window (ceiling-lit, a lamp's pool, blinds, curtains, dark), the lamps are real lantern posts,
the pavements concrete_pavement slabs, the road carries standing-water puddles that mirror the lamps and neon,
each neon tube sits on a dark sign box, distant practicals past both ends of the street fall into bokeh, and at
night the sky is a real night-street HDRI. With an empty library every piece falls back to the procedural
street above."""
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
# art pass 2026-09-25 (all eng): with the pinned CC0 library the street is built from real assets
NIGHT_HDRI = "cobblestone_street_night_4k"   # a lamp-lit night street: the sky, the skyline past the blocks
NIGHT_HDRI_K = 0.14           # its strength: a night fill and the skyline, never a key
NIGHT_HDRI_ROT = 0.0          # its rotation about Z, degrees
PAVE_TILE_M = 1.8             # concrete_pavement is a 1.8 m scan
PUDDLE_SCALE = 0.22           # standing-water patch scale (1 / m; round 9, was 0.35: larger patches)
DAMP_ROUGH = 0.15            # (eng, round 9) wet asphalt between the pools: roughness x (1 - 0.15 x wetness)
PUDDLE_DETAIL = 2.0           # round 8 (was 6): the owner read the fine-edged patches as sparkle; fewer octaves give
PUDDLE_GROW = 0.20            # larger, smoother wet patches (the level rises 0.16 x wetness, was 0.12) ...
PUDDLE_SHORE = 0.08           # ... with a softer shore (the mask's band, was 0.04)
LAMP_BULB, LAMP_GLASS = 60.0, 6.0     # lantern bulb / glass glow
LANTERN_Z = 0.87              # the lantern's height as a share of the post
ROOM_STRENGTH = 3.2           # lit room card emission
SIGN_PAD_M = 0.16             # a neon tube's sign box reaches this far round it
NEON_OUT_M = 0.3              # with the kit, the tube stands this far further out (clear of sills and doors)
NEON_KIT_Z, NEON_KIT_DZ = 2.95, 0.08   # ... and hangs over the ground floor: 2.95 m, +8 cm per metre of the
                                       # layout's band above 4 m (the kit's first-floor windows start at 3 m)
BOKEH_N, BOKEH_FAR_M, BOKEH_STRENGTH = 26, 140.0, 25.0   # distant practicals past each end of the street
FAR_BLOCKS_M = 70.0           # the street runs on past both ends of the set: kit blocks, road and pavement
FAR_LAMP_GAP = 16.0           # far lantern posts (glow only: the practicals stay the set's lamps)
LAMP_H_FAR = 5.0              # their height
# round 2 (all eng)
DUSK_HDRI, DUSK_HDRI_K = "neuer_zollhof_4k", 0.55   # a blue-hour city: the dusk sky and skyline
FAR_SHOP_SHARE = 0.85         # far ground floors are mostly lit shops (the street's end reads as a high street)
FAR_SIGN_P = 0.45             # ... and this share of far blocks carries a neon shop sign
FAR_SIGN_STRENGTH = 14.0
PAVE_PUDDLES = 0.55           # pavement standing water, x the street's wetness
TRACK_W, TRACK_DARK, TRACK_POLISH = 0.38, 0.82, 0.8   # wheel tracks: width, albedo x, roughness x
GUTTER_W = 0.45               # the wet gutter along each kerb
# round 3 (eng): a sheet of standing water round the subject (the film's courtyard mirror)
SHEET_K = (2.6, 1.9)          # its half-extent, x the subject's half-length / half-width (along, across)
SHEET_MIN_WET = 0.35          # below this wetness the road only carries puddles
SHEET_ROUGH = 0.015
# realism pass (2026-09-25, all eng): the grey-day and twilight looks the film was shot in (a foggy overcast day
# is why its wet mirror is bright). Both use a Poly Haven overcast London street (urban_street_01, CC0); twilight
# dims and cools it. `glow` scales every emitter the street owns (rooms, shopfronts, neon, lantern glass, far
# signs), `lamps` its spot practicals; `haze` = (half distance m, max share) of the aerial perspective that
# dissolves the far street into the sky (env_assets.aerial), `bokeh` the distant practicals.
OVERCAST_HDRI = "urban_street_01_4k"
TOD_LOOK = {
    "night": {"hdri": NIGHT_HDRI, "k": NIGHT_HDRI_K, "tint": None, "glow": 1.0, "lamps": 1.0, "haze": None,
              "bokeh": True},
    "dusk": {"hdri": DUSK_HDRI, "k": DUSK_HDRI_K, "tint": None, "glow": 1.0, "lamps": 1.0, "haze": None,
             "bokeh": False},
    "twilight": {"hdri": OVERCAST_HDRI, "k": 0.22, "tint": (0.78, 0.86, 1.0), "glow": 0.8, "lamps": 1.0,
                 "haze": (70.0, 0.55), "bokeh": True},
    "overcast_day": {"hdri": OVERCAST_HDRI, "k": 1.0, "tint": (0.97, 0.99, 1.0), "glow": 0.05, "lamps": 0.0,
                     "haze": (45.0, 0.7), "bokeh": False},
}
OVERCAST_FALLBACK = (0.40, 0.42, 0.45)   # procedural grey sky when the photo is not pinned (previews only)
FURNITURE_ASSETS = {          # layout type -> (pinned glTF, the variant's mesh names)
    "bin": ("metal_trash_can_1k", lambda n: n in ("metal_trash_can", "metal_trash_can_handle_left",
                                                  "metal_trash_can_handle_right")),
    "hydrant": ("fire_hydrant_1k", lambda n: "aged" not in n),
    "utility_box": ("utility_box_01_1k", None), "trashbag": ("trashbag_1k", None),
    "chalkboard": ("standing_chalkboard_01_1k", None), "planter": ("planter_box_02_1k", None),
    "parked_car": ("covered_car_1k", None), "manhole": ("water_manhole_cover_1k", None)}


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
    if tod == "overcast_day":
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = (*OVERCAST_FALLBACK, 1.0)
        colour, horizon, strength = rgb.outputs[0], OVERCAST_FALLBACK, 1.0
    elif tod in ("dusk", "twilight"):
        colour = nishita(nt, tc.outputs["Generated"], DUSK_SUN_DEG, dust=2.0, air=1.5).outputs["Color"]
        horizon = (0.05, 0.045, 0.06)
        strength = DUSK_STRENGTH * (0.5 if tod == "twilight" else 1.0)
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


def _library():
    from engine.assets import resolve, resolve_gltf
    return {"hdri": resolve(NIGHT_HDRI), "dusk": resolve(DUSK_HDRI), "overcast": resolve(OVERCAST_HDRI),
            "furniture": {t: resolve_gltf(a) for t, (a, _) in FURNITURE_ASSETS.items()},
            "kit": resolve_gltf("modular_urban_apartments_facade_1k"),
            "lamp": resolve_gltf("street_lamp_01_1k"),
            "paving": {k: resolve(f"concrete_pavement_{k}_2k") for k in ("diff", "rough", "nor_gl")}}


def _facade_frame(lay, fa):
    """Module frame of a facade block: x along the street (whichever way keeps the frame right-handed),
    y into the building, z up; origin on the street face at the block's end where x starts."""
    from mathutils import Matrix, Vector
    ia = 1 - _along(lay)
    U = Vector((1.0, 0.0, 0.0)) if ia == 0 else Vector((0.0, 1.0, 0.0))
    V = Vector((0.0, 1.0, 0.0)) if ia == 0 else Vector((1.0, 0.0, 0.0))
    s = 1.0 if fa["u"] > 0 else -1.0
    Y, Z = s * U, Vector((0.0, 0.0, 1.0))
    X = Y.cross(Z)
    start = fa["v0"] if X.dot(V) > 0 else fa["v1"]
    cx, cy = lay["road"]["centre"]
    o = Vector((cx, cy, 0.0)) + fa["u"] * U + start * V
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = X[i], Y[i], Z[i], o[i]
    return m


def _wet_paving(maps, wet, name, tint):
    """concrete_pavement slabs (1.8 m scan), darkened and smoothed by the street's wetness."""
    from engine.blender.env_assets import pbr
    m = pbr(name, maps, PAVE_TILE_M, tint=tuple(c * (1.0 - 0.35 * wet) for c in tint), rough_k=1.0 - 0.3 * wet,
            bump_k=0.8, rough_min=0.32)
    return m


def _puddles(mat, wet):
    """Standing water on the road: a noise mask where roughness drops to near-mirror and the albedo darkens,
    so lamps and neon streak across the asphalt. Scales with the street's own wetness."""
    nt = mat.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    rl = next((l for l in nt.links if l.to_socket == sh.inputs["Roughness"]), None)
    bl = next((l for l in nt.links if l.to_socket == sh.inputs["Base Color"]), None)
    if rl is None or bl is None:
        return
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = PUDDLE_SCALE
    noise.inputs["Detail"].default_value = PUDDLE_DETAIL
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    mask = nt.nodes.new("ShaderNodeMapRange")
    mask.inputs["From Min"].default_value = 0.62 - PUDDLE_GROW * wet
    mask.inputs["From Max"].default_value = 0.62 - PUDDLE_GROW * wet + PUDDLE_SHORE
    nt.links.new(noise.outputs["Fac"], mask.inputs["Value"])
    k = nt.nodes.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    k.inputs[1].default_value = wet
    nt.links.new(mask.outputs["Result"], k.inputs[0])
    r = nt.nodes.new("ShaderNodeMix")
    r.data_type = "FLOAT"
    nt.links.new(k.outputs[0], r.inputs["Factor"])
    nt.links.new(rl.from_socket, r.inputs[2])
    r.inputs[3].default_value = 0.03
    nt.links.new(r.outputs[0], sh.inputs["Roughness"])
    c = nt.nodes.new("ShaderNodeMix")
    c.data_type, c.blend_type = "RGBA", "MULTIPLY"
    nt.links.new(k.outputs[0], c.inputs["Factor"])
    nt.links.new(bl.from_socket, c.inputs[6])
    c.inputs[7].default_value = (0.45, 0.45, 0.47, 1.0)
    nt.links.new(c.outputs[2], sh.inputs["Base Color"])
    nl = next((l for l in nt.links if l.to_socket == sh.inputs["Normal"]), None)
    if nl is not None:     # round 9: a pool is flat. A mirror over the asphalt's bumpy normal glittered at every
        nm = nt.nodes.new("ShaderNodeMix")                   # lamp (the owner's "crunchy pavement sparkle")
        nm.data_type = "VECTOR"
        nt.links.new(k.outputs[0], nm.inputs["Factor"])
        nt.links.new(nl.from_socket, nm.inputs[4])
        nt.links.new(geo.outputs["Normal"], nm.inputs[5])
        nt.links.new(nm.outputs[1], sh.inputs["Normal"])


def _standing_water(mat, lay, prof, wet):
    """A sheet of standing water round and in front of the subject: an ellipse (SHEET_K x its half-extents,
    its edge broken by noise) where the road is a near-mirror, darker, and its normal map flattens, so a low
    camera sees the subject mirrored under itself. It grows with the street's wetness; wet_surface, when in
    the script, owns the water instead (wetness is 0 then)."""
    nt = mat.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    rl = next((l for l in nt.links if l.to_socket == sh.inputs["Roughness"]), None)
    bl = next((l for l in nt.links if l.to_socket == sh.inputs["Base Color"]), None)
    nl = next((l for l in nt.links if l.to_socket == sh.inputs["Normal"]), None)
    if rl is None or bl is None:
        return
    ia = 1 - _along(lay)
    cx, cy = prof.center[0], prof.center[1]
    hx, hy = max(prof.half[0], 0.05), max(prof.half[1], 0.05)
    along, across = (hy, hx) if ia == 0 else (hx, hy)
    rv, ru = SHEET_K[0] * max(along, across), SHEET_K[1] * max(min(along, across), 0.35 * max(along, across))
    rx, ry = (ru, rv) if ia == 0 else (rv, ru)
    k = 0.6 + 0.4 * wet
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])

    def m(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                nt.links.new(x, n.inputs[i])
        return n.outputs[0]
    dx = m("DIVIDE", m("SUBTRACT", sep.outputs["X"], cx), rx * k)
    dy = m("DIVIDE", m("SUBTRACT", sep.outputs["Y"], cy), ry * k)
    d = m("SQRT", m("ADD", m("MULTIPLY", dx, dx), m("MULTIPLY", dy, dy)))
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.9
    noise.inputs["Detail"].default_value = 4.0
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    d = m("ADD", d, m("MULTIPLY", m("SUBTRACT", noise.outputs["Fac"], 0.5), 0.7))
    mask = nt.nodes.new("ShaderNodeMapRange")
    mask.interpolation_type = "SMOOTHSTEP"
    mask.inputs["From Min"].default_value, mask.inputs["From Max"].default_value = 1.0, 0.8
    nt.links.new(d, mask.inputs["Value"])
    f = mask.outputs["Result"]
    r = nt.nodes.new("ShaderNodeMix")
    r.data_type = "FLOAT"
    nt.links.new(f, r.inputs["Factor"])
    nt.links.new(rl.from_socket, r.inputs[2])
    r.inputs[3].default_value = SHEET_ROUGH
    nt.links.new(r.outputs[0], sh.inputs["Roughness"])
    c = nt.nodes.new("ShaderNodeMix")
    c.data_type, c.blend_type = "RGBA", "MULTIPLY"
    nt.links.new(f, c.inputs["Factor"])
    nt.links.new(bl.from_socket, c.inputs[6])
    c.inputs[7].default_value = (0.3, 0.3, 0.32, 1.0)
    nt.links.new(c.outputs[2], sh.inputs["Base Color"])
    if nl is not None:                                        # still water is flat: the asphalt's grain drowns
        nm = nt.nodes.new("ShaderNodeMix")
        nm.data_type = "VECTOR"
        nt.links.new(f, nm.inputs["Factor"])
        nt.links.new(nl.from_socket, nm.inputs[4])
        nt.links.new(geo.outputs["Normal"], nm.inputs[5])
        nt.links.new(nm.outputs[1], sh.inputs["Normal"])


def _road_wear(mat, lay, wet):
    """What a used road carries: two polished, darker wheel tracks per lane (noise-broken, so they read as
    wear, not paint) and a wet, dark gutter along each kerb."""
    nt = mat.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    rl = next((l for l in nt.links if l.to_socket == sh.inputs["Roughness"]), None)
    bl = next((l for l in nt.links if l.to_socket == sh.inputs["Base Color"]), None)
    if rl is None or bl is None:
        return
    ia = 1 - _along(lay)
    cx, cy = lay["road"]["centre"]
    W = lay["road"]["width"]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])

    def m(op, a, b):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                nt.links.new(x, n.inputs[i])
        return n.outputs[0]
    u = m("ABSOLUTE", m("SUBTRACT", sep.outputs["X" if ia == 0 else "Y"], cx if ia == 0 else cy), 0.0)
    lane = W / 4                                              # each lane's centre, |u|
    track = None
    for off in (-0.8, 0.8):                                   # a 1.6 m track either side of the lane centre
        d = m("ABSOLUTE", m("SUBTRACT", u, lane + off), 0.0)
        t = m("SUBTRACT", 1.0, m("MINIMUM", m("DIVIDE", d, TRACK_W / 2), 1.0))
        track = t if track is None else m("MAXIMUM", track, t)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.6
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    track = m("MULTIPLY", track, m("MULTIPLY", noise.outputs["Fac"], 1.6))
    gutter = m("SUBTRACT", 1.0, m("MINIMUM", m("DIVIDE", m("SUBTRACT", W / 2, u), GUTTER_W), 1.0))
    dark = m("ADD", m("MULTIPLY", track, 1.0 - TRACK_DARK), m("MULTIPLY", gutter, 0.35))
    col = nt.nodes.new("ShaderNodeMix")
    col.data_type, col.blend_type = "RGBA", "MULTIPLY"
    nt.links.new(m("MINIMUM", dark, 1.0), col.inputs["Factor"])
    nt.links.new(bl.from_socket, col.inputs[6])
    col.inputs[7].default_value = (0.0, 0.0, 0.0, 1.0)
    nt.links.new(col.outputs[2], sh.inputs["Base Color"])
    polish = m("SUBTRACT", 1.0, m("ADD", m("MULTIPLY", track, 1.0 - TRACK_POLISH),
                                  m("MULTIPLY", gutter, 0.6 * max(wet, 0.3))))
    nt.links.new(m("MULTIPLY", rl.from_socket, polish), sh.inputs["Roughness"])


def _furniture(bpy, ctx, lay, lib):
    """The layout's street furniture as real CC0 models (one shared mesh per type); none without the library."""
    from engine.blender import set_parts as P
    from engine.blender.env_assets import shared_mesh
    ia = 1 - _along(lay)
    along = 90.0 if ia == 0 else 0.0                          # model x along the street
    meshes, out = {}, []
    for i, it in enumerate(lay["furniture"]):
        t = it["type"]
        path = lib["furniture"].get(t)
        if path is None:
            continue
        if t not in meshes:
            meshes[t] = shared_mesh(path, FURNITURE_ASSETS[t][1])[0]
        if meshes[t] is None:
            continue
        ob = bpy.data.objects.new(f"valora_street_furniture_{i}", meshes[t])
        ctx.scene.collection.objects.link(ob)
        x, y = (it["min"][0] + it["max"][0]) / 2, (it["min"][1] + it["max"][1]) / 2
        z = -0.03 if t == "manhole" else it["min"][2]
        ob.location = (x, y, z)
        base = (along - 90.0) if t == "parked_car" else along
        ob.rotation_euler[2] = math.radians(base + it["yaw"])
        out.append(P.tag(ob, BLOCK))
    return out


def _lamp_model(bpy, path):
    """street_lamp_01 as one shared mesh; its bulb and glass made to glow warm."""
    from engine.blender.env_assets import shared_mesh
    me, h = shared_mesh(path)
    if me is None:
        return None, 0.0
    for i, m in enumerate(me.materials):
        if m is None or not any(k in m.name for k in ("bulb", "glass")):
            continue
        g = m.copy()
        nt = g.node_tree
        sh = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if sh is not None:
            sh.inputs["Emission Color"].default_value = (1.0, 0.72, 0.42, 1.0)
            sh.inputs["Emission Strength"].default_value = LAMP_BULB if "bulb" in m.name else LAMP_GLASS
        me.materials[i] = g
    return me, h


def _bokeh(lay, rng):
    """Distant practicals past both ends of the street (windows, lamps, a car's tail light): small emitters the
    lens throws into bokeh, giving the street depth beyond the built blocks."""
    ia = 1 - _along(lay)
    cx, cy = lay["road"]["centre"]
    L, W = lay["road"]["length"], lay["road"]["width"]
    out = []
    for end in (-1, 1):
        for _ in range(BOKEH_N):
            v = end * (L / 2 + rng.uniform(8.0, BOKEH_FAR_M))
            u = rng.uniform(-(W / 2 + 10.0), W / 2 + 10.0)
            z = rng.choice((rng.uniform(0.4, 1.2), rng.uniform(3.0, 16.0), rng.uniform(4.5, 6.0)))
            kind = rng.random()
            colour = (1.0, 0.62, 0.3) if kind < 0.55 else (0.85, 0.9, 1.0) if kind < 0.85 else (1.0, 0.08, 0.05)
            xy = (cx + u, cy + v) if ia == 0 else (cx + v, cy + u)
            out.append((xy[0], xy[1], z, rng.uniform(0.05, 0.14), colour, rng.uniform(0.5, 1.0)))
    return out


def _far_street(ctx, lay, asm, road_mat, paving, lamp_me, lamp_h, lit_share):
    """The street past both ends of the set, out to FAR_BLOCKS_M: road and pavement strips, kit blocks on both
    sides and glowing lantern posts, so a camera looking down the street sees a city, not a void. Nothing here
    is ground, a light or a layout item: it stands beyond every camera (the set's road is 30 m+, the cameras
    frame a subject at its centre) and along the kerb line, never across a view of the subject."""
    import bpy
    from engine.blender import set_parts as P
    ia = 1 - _along(lay)
    cx, cy = lay["road"]["centre"]
    L, W, face = lay["road"]["length"], lay["road"]["width"], lay["road"]["faceU"]

    def at(u, v, z=0.0):
        return (cx + u, cy + v, z) if ia == 0 else (cx + v, cy + u, z)
    rv, rf, pv, pf = [], [], [], []
    blocks, posts, signs, sbv, sbf = 0, [], [], [], []
    for end in (-1, 1):
        v0, v1 = sorted((end * L / 2, end * (L / 2 + FAR_BLOCKS_M)))
        P.quad(rv, rf, [at(-W / 2, v0), at(W / 2, v0), at(W / 2, v1), at(-W / 2, v1)])
        for s_ in (-1, 1):
            a, b = sorted((s_ * W / 2, s_ * face))
            lo, hi = at(a, v0), at(b, v1, 0.15)
            P.aabb(pv, pf, tuple(min(x, y) for x, y in zip(lo, hi)), tuple(max(x, y) for x, y in zip(lo, hi)))
            if asm is None:
                continue
            v = v0
            while v < v1 - 1.0:
                w = min(ctx.rng.uniform(6.0, 12.0), v1 - v)
                h = ctx.rng.uniform(7.0, 16.0)
                fa = {"u": s_ * face, "v0": v, "v1": v + w, "height": h}
                frame = _facade_frame(lay, fa)
                top = asm.facade(fa, frame, w, h, ctx.rng, lit_share, shop_share=FAR_SHOP_SHARE)
                if ctx.rng.random() < FAR_SIGN_P:                          # a shop's neon sign
                    vc, sl = v + w * ctx.rng.uniform(0.3, 0.7), min(2.4, 0.6 * w)
                    uo = s_ * (face - 0.34)
                    lo_, hi_ = at(uo - 0.06, vc - sl / 2, 2.89), at(uo + 0.06, vc + sl / 2, 3.01)
                    signs.append((tuple(min(a, b) for a, b in zip(lo_, hi_)), tuple(max(a, b) for a, b in zip(lo_, hi_))))
                    lo_, hi_ = at(uo, vc - sl / 2 - 0.16, 2.73), at(s_ * face, vc + sl / 2 + 0.16, 3.17)
                    P.aabb(sbv, sbf, tuple(min(a, b) for a, b in zip(lo_, hi_)), tuple(max(a, b) for a, b in zip(lo_, hi_)))
                ua, ub = sorted((s_ * (face + 1.2), s_ * (face + 7.2)))       # the block's mass behind the rooms
                lo2, hi2 = at(ua, v), at(ub, v + w, top - 0.05)
                P.aabb(pv, pf, tuple(min(x, y) for x, y in zip(lo2, hi2)), tuple(max(x, y) for x, y in zip(lo2, hi2)))
                blocks += 1
                v += w
            if lamp_me is not None:
                v = v0 + ctx.rng.uniform(2.0, FAR_LAMP_GAP)
                while v < v1:
                    ob = bpy.data.objects.new(f"valora_street_far_lamp_{len(posts)}", lamp_me)
                    ctx.scene.collection.objects.link(ob)
                    sc = LAMP_H_FAR / lamp_h
                    ob.scale = (sc, sc, sc)
                    ob.location = at(s_ * (W / 2 + 0.55), v)
                    posts.append(P.tag(ob, BLOCK))
                    v += FAR_LAMP_GAP
    far_road = P.mesh(ctx.scene, "valora_street_far_road", BLOCK, rv, rf, [road_mat])
    for ob in (far_road,):
        me = ob.data                                                     # world-scale UVs like the set's road
        uv = me.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", [c / TILE_M for li in me.loops for c in me.vertices[li.vertex_index].co[:2]])
    far_blocks = P.mesh(ctx.scene, "valora_street_far_blocks", BLOCK, pv, pf, [paving])
    if signs:                                               # glow only: never valora_neon, never a light
        tv, tf, tm = [], [], []
        hue = float(ctx.params["neonHue"])
        mats = [P.emissive(f"valora_street_far_sign_{i}", P.hue_rgb(hue + d), FAR_SIGN_STRENGTH)
                for i, d in enumerate((-40.0, 0.0, 35.0, 180.0))]
        for lo_, hi_ in signs:
            P.aabb(tv, tf, lo_, hi_)
            tm += [ctx.rng.randrange(len(mats))] * 6
        tubes = P.mesh(ctx.scene, "valora_street_far_signs", BLOCK, tv, tf, mats, tm)
        tubes.visible_shadow = False
        P.mesh(ctx.scene, "valora_street_far_sign_backs", BLOCK, sbv, sbf,
               [P.mat("valora_street_far_sign_back", (0.012, 0.012, 0.014), 0.4, 0.6)])
    return blocks, len(posts)


def _time_of_day(ctx, look, sky_hdri, lights):
    """Scale the street's own emitters (glow) and practicals (lamps) for the time of day, and dissolve the far
    street into the sky with aerial perspective (haze). Rooms are scaled at build (their strength is a node)."""
    from engine.blender import env_assets as E
    for lo in lights:
        lo.data.energy *= look["lamps"]
    seen = set()
    for ob in ctx.scene.objects:
        if ob.get("valora_block") != BLOCK or ob.type != "MESH":
            continue
        for m in ob.data.materials:
            if m is None or m.name in seen or not m.use_nodes:
                continue
            seen.add(m.name)
            if look["glow"] != 1.0:
                for n in m.node_tree.nodes:
                    if n.type == "EMISSION" and not n.inputs["Strength"].is_linked:
                        n.inputs["Strength"].default_value *= look["glow"]
                    elif n.type == "BSDF_PRINCIPLED" and not n.inputs["Emission Strength"].is_linked:
                        n.inputs["Emission Strength"].default_value *= look["glow"]
            if look["haze"] and not ob.get("valora_ground") and "rooms" not in m.name:
                half, share = look["haze"]
                hdri = (sky_hdri, NIGHT_HDRI_ROT, look["k"], look["tint"]) if sky_hdri is not None else None
                E.aerial(m, OVERCAST_FALLBACK, half, max_mix=share, hdri=hdri)


def build(ctx):
    import bpy
    from engine.assets import resolve
    from engine.blender import env_assets as E
    from engine.blender import facade_kit as K
    from engine.blender import set_parts as P
    from engine.color import kelvin_to_rgb
    from engine.worlds.street_layout import NEON, layout
    p, prof = ctx.params, ctx.profile
    m = ctx.catalog.get("world", "night_street")
    hero = ctx.hero_pose
    if hero is not None and ctx.camera_lenses_mm:
        hero = dataclasses.replace(hero, lens_mm=min(ctx.camera_lenses_mm))       # the widest lens the clip uses
    lay = layout(prof, ctx.seed, m["driveLaneM"], hero=hero, aspect=ctx.script["format"]["aspect"],
                 cameras=[tuple(c) for c in ctx.camera_positions])
    ids = [e["id"] for e in ctx.script.get("effects", [])]
    from engine.physics.wet import world_wetness
    wet = world_wetness(p["wetness"], ids)                                # wet_surface takes over (one owner)
    tod = p["timeOfDay"]
    look = TOD_LOOK[tod]
    lib = _library()
    sky_hdri = {"night": lib["hdri"], "dusk": lib["dusk"]}.get(tod, lib["overcast"])
    photo_sky = sky_hdri is not None
    if photo_sky:
        E.world_hdri(ctx.scene, "valora_street_sky", sky_hdri, NIGHT_HDRI_ROT, look["k"], look["tint"])
    else:
        _sky(bpy, ctx, tod)

    cx, cy = lay["road"]["centre"]
    L, W = lay["road"]["length"], lay["road"]["width"]
    ax, ay = (W / 2, L / 2) if lay["road"]["alongAxis"] == "y" else (L / 2, W / 2)
    road = P.mesh(ctx.scene, "valora_street_road", BLOCK,
                  [(cx - ax, cy - ay, 0.0), (cx + ax, cy - ay, 0.0), (cx + ax, cy + ay, 0.0), (cx - ax, cy + ay, 0.0)],
                  [(0, 1, 2, 3)])
    P.tag(road, BLOCK, ground=True)
    maps = {k: resolve(f"asphalt_02_{k}") for k in ("diff", "rough", "nor_gl", "disp")}
    # round 9 (owner's r8 grade: "crunchy pavement sparkle"): the damp asphalt between the pools keeps 85% of its
    # roughness (was 0.3 x), so its aggregate reads as matte damp stone and only the pools mirror the lamps
    road_mat = P.asphalt(road, maps, wet, "valora_street_asphalt", "valora_street", TILE_M, wet_rough=DAMP_ROUGH)
    _road_wear(road_mat, lay, wet)
    if wet > 0:
        _puddles(road_mat, wet)
    sheet = wet >= SHEET_MIN_WET
    if sheet:
        _standing_water(road_mat, lay, prof, wet)

    far = max(L, 60.0)                                                    # a dark apron to the horizon
    apron = P.mesh(ctx.scene, "valora_street_apron", BLOCK,
                   [(cx - far, cy - far, -0.01), (cx + far, cy - far, -0.01), (cx + far, cy + far, -0.01),
                    (cx - far, cy + far, -0.01)], [(0, 1, 2, 3)],
                   [P.mat("valora_street_apron", (0.02, 0.02, 0.022), 0.35 if wet > 0 else 0.8)])

    paint = P.mat("valora_street_paint", (0.55, 0.55, 0.52), 0.55)
    v, f = [], []
    for r in _markings(lay, prof):
        P.quad(v, f, [(r[0], r[1], 0.002), (r[2], r[1], 0.002), (r[2], r[3], 0.002), (r[0], r[3], 0.002)])
    marks = P.mesh(ctx.scene, "valora_street_markings", BLOCK, v, f, [paint]) if v else None

    paved = all(lib["paving"].values())
    stone = (_wet_paving(lib["paving"], wet, "valora_street_stone", (0.55, 0.55, 0.55)) if paved
             else P.mat("valora_street_stone", (0.10, 0.10, 0.10), 0.7))
    paving = (_wet_paving(lib["paving"], wet, "valora_street_paving", (0.8, 0.78, 0.75)) if paved
              else P.mat("valora_street_paving", (0.07, 0.07, 0.072), 0.75))
    if paved and wet > 0:
        _puddles(paving, PAVE_PUDDLES * wet)                  # standing water and drying patches, not a mirror
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
    kit = K.load(lib["kit"]) if lib["kit"] is not None else None
    asm = K.Assembler(ctx.scene, kit, BLOCK, lambda o: P.tag(o, BLOCK)) if kit else None
    v, f, von, fon, voff, foff, vs, fs, ve, fe = [], [], [], [], [], [], [], [], [], []
    ia = 1 - _along(lay)
    lit_share = float(p["windowsLit"])
    for fa in lay["facades"]:
        if asm is None:
            P.aabb(v, f, fa["min"], fa["max"])
            _window_quads(fa, lay, lit_share, von, fon, voff, foff)
            if ctx.rng.random() < 0.5:                                    # a lit shopfront at street level
                u = fa["u"] - math.copysign(0.03, fa["u"])
                v0, v1 = fa["v0"] + 0.3, fa["v1"] - 0.3
                pts = [(u, v0, 0.4), (u, v1, 0.4), (u, v1, 2.6), (u, v0, 2.6)]
                P.quad(vs, fs, [((cx + a, cy + b, z) if ia == 0 else (cx + b, cy + a, z)) for a, b, z in pts])
            continue
        frame = _facade_frame(lay, fa)
        top = asm.facade(fa, frame, fa["v1"] - fa["v0"], fa["height"], ctx.rng, lit_share)
        s = 1.0 if fa["u"] > 0 else -1.0
        back = fa["u"] + s * K.MASS_BACK_M
        lo, hi = list(fa["min"]), list(fa["max"])
        k = 0 if ia == 0 else 1                                           # the placed axis u runs along
        lo[k], hi[k] = (back, fa["max"][k]) if s > 0 else (fa["min"][k], back)
        hi[2] = top - 0.05
        P.aabb(v, f, lo, hi)                                              # the building's mass, behind the rooms
        for vv in (fa["v0"], fa["v1"]):                                   # close the ends of the room gap
            pts = [(fa["u"], vv, 0.0), (back, vv, 0.0), (back, vv, top), (fa["u"], vv, top)]
            P.quad(ve, fe, [((cx + a, cy + b, z) if ia == 0 else (cx + b, cy + a, z)) for a, b, z in pts])
    facades = [P.mesh(ctx.scene, "valora_street_facades", BLOCK, v, f, [wall])] if v else []
    if ve:
        facades.append(P.mesh(ctx.scene, "valora_street_facade_ends", BLOCK, ve, fe, [wall]))
    windows = []
    if von:
        windows.append(P.mesh(ctx.scene, "valora_street_windows_lit", BLOCK, von, fon, [lit]))
    if voff:
        windows.append(P.mesh(ctx.scene, "valora_street_windows_dark", BLOCK, voff, foff, [glass_off]))
    if vs:
        windows.append(P.mesh(ctx.scene, "valora_street_shopfronts", BLOCK, vs, fs, [shop]))
    lamp_me, lamp_h = _lamp_model(bpy, lib["lamp"]) if lib["lamp"] is not None else (None, 0.0)
    far_blocks, far_lamps = _far_street(ctx, lay, asm, road_mat, paving, lamp_me, lamp_h, lit_share)
    rooms = asm.finish(ROOM_STRENGTH * look["glow"], kelvin_to_rgb(2900.0)) if asm is not None else None

    metal = P.mat("valora_street_lamp_post", (0.03, 0.032, 0.035), 0.35, 0.8)
    lights, models = [], []
    v, f = [], []
    for i, it in enumerate(lay["lamps"]):
        x0, y0, _ = it["min"]
        x1, y1, _ = it["max"]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        kelvin = ctx.rng.uniform(*LAMP_K)
        lm = ctx.rng.uniform(*LAMP_LM)
        if lamp_me is not None:                                           # a real lantern post
            ob = bpy.data.objects.new(f"valora_street_lamp_model_{i}", lamp_me)
            ctx.scene.collection.objects.link(ob)
            sc = it["max"][2] / lamp_h
            ob.scale = (sc, sc, sc)
            ob.location = (mx, my, 0.0)
            models.append(P.tag(ob, BLOCK))
            hx, hy, hz = mx, my, LANTERN_Z * it["max"][2]
        else:
            P.aabb(v, f, (mx - 0.06, my - 0.06, 0.0), (mx + 0.06, my + 0.06, it["max"][2]))
            hx, hy, hz = it["head"]
            P.aabb(v, f, (min(mx, hx) - 0.04, min(my, hy) - 0.04, hz - 0.08),
                   (max(mx, hx) + 0.04, max(my, hy) + 0.04, hz))
        ld = bpy.data.lights.new(f"valora_street_lamp_{i}", "SPOT")
        ld.energy, ld.color = lm * W_PER_LM, kelvin_to_rgb(kelvin)
        ld.spot_size, ld.spot_blend = math.radians(LAMP_SPOT_DEG), 0.6
        ld.shadow_soft_size = 0.12
        lo = bpy.data.objects.new(f"valora_street_lamp_{i}", ld)
        ctx.scene.collection.objects.link(lo)
        lo.location = (hx, hy, hz - 0.12)                                  # just under the head, pointing down
        P.tag(lo, BLOCK)
        lights.append(lo)
        if lamp_me is None:
            hv, hf = [], []
            P.quad(hv, hf, [(hx - 0.25, hy - 0.25, hz - 0.085), (hx + 0.25, hy - 0.25, hz - 0.085),
                            (hx + 0.25, hy + 0.25, hz - 0.085), (hx - 0.25, hy + 0.25, hz - 0.085)])
            head = P.mesh(ctx.scene, f"valora_street_lamp_head_{i}", BLOCK, hv, hf,
                          [P.emissive(f"valora_street_lamp_head_{i}", kelvin_to_rgb(kelvin), 6.0)])
            head.visible_shadow = False
    posts = P.mesh(ctx.scene, "valora_street_lamp_posts", BLOCK, v, f, [metal]) if v else None
    for i, it in enumerate(lay.get("lampLights", [])):             # a post dropped for a camera: its light stays
        mx, my = (it["min"][0] + it["max"][0]) / 2, (it["min"][1] + it["max"][1]) / 2
        hz = LANTERN_Z * it["max"][2] if lamp_me is not None else it["head"][2]
        hx, hy = (mx, my) if lamp_me is not None else it["head"][:2]
        ld = bpy.data.lights.new(f"valora_street_lamp_light_{i}", "SPOT")
        ld.energy, ld.color = ctx.rng.uniform(*LAMP_LM) * W_PER_LM, kelvin_to_rgb(ctx.rng.uniform(*LAMP_K))
        ld.spot_size, ld.spot_blend = math.radians(LAMP_SPOT_DEG), 0.6
        ld.shadow_soft_size = 0.12
        lo = bpy.data.objects.new(f"valora_street_lamp_light_{i}", ld)
        ctx.scene.collection.objects.link(lo)
        lo.location = (hx, hy, hz - 0.12)
        lights.append(P.tag(lo, BLOCK))
    furniture = _furniture(bpy, ctx, lay, lib)

    neon, signs = [], []
    sign_mat = P.mat("valora_street_sign_back", (0.012, 0.012, 0.014), 0.4, 0.6)
    sv, sf = [], []
    for i, it in enumerate(lay["neon"]):
        colour = P.hue_rgb(float(p["neonHue"]) + it["hue"])
        lo, hi = list(it["min"]), list(it["max"])
        if asm is not None:                                               # a shop sign over the ground floor:
            k = 0 if ia == 0 else 1                                       # the tube stands off the kit's sills
            s = 1.0 if (lo[k] + hi[k]) > 2 * (cx if k == 0 else cy) else -1.0     # and doors on a sign box
            lo[k], hi[k] = lo[k] - s * NEON_OUT_M, hi[k] - s * NEON_OUT_M
            zc = NEON_KIT_Z + NEON_KIT_DZ * (lo[2] - 4.0)
            lo[2], hi[2] = zc - NEON[1] / 2, zc + NEON[1] / 2
            blo, bhi = list(lo), list(hi)
            blo[2], bhi[2] = lo[2] - SIGN_PAD_M, hi[2] + SIGN_PAD_M
            j = 1 - k                                                     # along the street
            blo[j], bhi[j] = lo[j] - SIGN_PAD_M, hi[j] + SIGN_PAD_M
            wall_u = it["max"][k] if s > 0 else it["min"][k]
            blo[k], bhi[k] = (hi[k], wall_u) if s > 0 else (wall_u, lo[k])
            P.aabb(sv, sf, blo, bhi)
        nv, nf = [], []
        P.aabb(nv, nf, lo, hi)
        ob = P.mesh(ctx.scene, f"valora_street_neon_{i}", BLOCK, nv, nf,
                    [P.emissive(f"valora_street_neon_{i}", colour, NEON_STRENGTH * float(p["neonAmount"]))])
        ob.visible_shadow = False
        ob["valora_neon"] = True
        neon.append(ob)
    if sv:
        signs.append(P.mesh(ctx.scene, "valora_street_sign_backs", BLOCK, sv, sf, [sign_mat]))

    bokeh = []
    if look["bokeh"]:
        bv, bf, bm = [], [], []
        mats = []
        for x, y, z, r, colour, k in _bokeh(lay, ctx.rng):
            P.aabb(bv, bf, (x - r, y - r, z - r), (x + r, y + r, z + r))
            mats.append(P.emissive(f"valora_street_bokeh_{len(mats)}", colour, BOKEH_STRENGTH * k))
            bm += [len(mats) - 1] * 6
        if bv:
            ob = P.mesh(ctx.scene, "valora_street_bokeh", BLOCK, bv, bf, mats, bm)
            E.camera_only(ob)
            bokeh.append(ob)

    _time_of_day(ctx, look, sky_hdri, lights)
    e = lay["exclusion"]
    props = [o for o in [kerbs, pavements, posts, *facades] if o is not None]
    inside = 0
    for ob in props + neon:
        inside += sum(1 for vv in ob.data.vertices if e[0] < vv.co.x < e[2] and e[1] < vv.co.y < e[3]
                      and vv.co.z > 0.0)
    items = (lay["lamps"] + lay["neon"] + lay["facades"] + lay["kerbs"] + lay["pavements"]    # every solid piece a
             + lay["furniture"])
    # camera could stand in: kerbs and pavements are 15 cm slabs a low camera can sink into (review chunk 4 #5)
    cams_in = sum(1 for c in ctx.camera_positions for it in items
                  if all(it["min"][i] <= c[i] <= it["max"][i] for i in range(3)))
    lit_n = (asm.lit if asm is not None else
             sum(1 for fa in lay["facades"] for w in fa["windows"] if w["key"] < lit_share))
    ctx.scene["valora_street"] = {
        "timeOfDay": tod, "asphaltMaps": all(maps.values()), "lamps": len(lights), "neon": len(neon),
        "neonHue": float(p["neonHue"]), "facades": len(lay["facades"]), "windowsLit": lit_n,
        "road": {k: v for k, v in lay["road"].items() if k != "alongAxis"}, "exclusion": list(e),
        "propVertsInExclusion": inside, "camerasInsideProps": int(cams_in), "wetness": wet,
        "slabCuts": len(lay["kerbs"]) + len(lay["pavements"]) - 4,     # extra slab pieces = dropped-kerb gaps
        "markings": marks is not None, "apron": apron.name, "photoSky": photo_sky,
        "facadeKit": asm is not None, "kitPieces": len(asm.objects) if asm else 0,
        "rooms": asm.windows if asm else 0, "lampModels": len(models), "pavingMaps": paved,
        "bokeh": sum(len(o.data.polygons) // 6 for o in bokeh), "farBlocks": far_blocks, "farLamps": far_lamps, "furniture": len(furniture), "lampPosts": len(lay["lamps"]),
        "lampLightsOnly": len(lay.get("lampLights", [])), "standingWater": sheet,
        "neonAllEmissive": all(any(n.type == "EMISSION" for n in mm.node_tree.nodes)
                               and not any(n.type == "BSDF_PRINCIPLED" for n in mm.node_tree.nodes)
                               for ob in neon for mm in ob.data.materials)}
    return road
