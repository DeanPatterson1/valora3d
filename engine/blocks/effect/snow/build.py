"""snow: stateless flakes, a snow layer on up-facing surfaces and a white ground coat (maths in
engine/physics/snow.py; the particle box is the rain's, engine/blender/weather_nodes).

Flakes: box_points with a per-flake seeded fall speed and wobble plus the wind drift (perMs 0.9), sheltered by
the posed footprint, instanced with a `velocity` attribute (the analytic derivative), so motion blur is right
and nothing depends on the frame before. Every flake is a textured card of its own size (snow.flake_size_mm,
most small, a few big), turned at random and tumbling (snow.tumble); CLUMP_SHARE of them are aggregated clumps
(three crossed crystals, bigger). The card shader cuts a soft irregular disc or a six-armed dendrite out of the
card by alpha, per flake. Accumulation: a SEPARATE object reading each upload mesh through Object Info keeps
only faces with n.up > 0.7 and lifts them into a smoothed shell: the depth (accumulationMm, growing slowly with
time) varies with a drift noise and rolls off to the paint where the smooth surface normal turns past UP_DOT,
so the edge is rounded and meets the car instead of floating (snow.cover_depth_mm); its shader has ~1 mm ice
grain, glints and explicit subsurface scattering. The upload gets no modifier. The ground coat wraps each
valora_ground material's Principled BSDF in one valora_snow group, as wet_surface wraps it. groundType stays
the world's: ground_conform does not switch to snow sink in phase 5 (deferred coupling, in the register)."""
import math

GROUP = "valora_snow"
COAT_FULL_MM = 10.0   # (eng) the ground reads fully white at 10 mm of snow


def _shader_math(nt):
    def math_(op, a, b=0.0):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for s, v in zip(n.inputs, (a, b)):
            if hasattr(v, "is_output"):
                nt.links.new(v, s)
            else:
                s.default_value = v
        return n.outputs[0]
    return math_


def _snow_material(bpy):
    """The flake card: a soft irregular disc, or (DENDRITE_SHARE of flakes) a six-armed dendrite with side
    branches, cut out of the card by alpha (per flake: valora_flake_rnd), white diffuse with translucency (a
    thin crystal glows back-lit). Card UVs: valora_uv."""
    from engine.physics import snow as S
    m = bpy.data.materials.new("valora_snow")
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    mth = _shader_math(nt)
    sh = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Base Color"].default_value = (0.93, 0.95, 0.98, 1.0)
    sh.inputs["Roughness"].default_value = 0.6
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    uv, rnd = N.new("ShaderNodeAttribute"), N.new("ShaderNodeAttribute")
    uv.attribute_name, rnd.attribute_name = "valora_uv", "valora_flake_rnd"
    fr = rnd.outputs["Fac"]
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(uv.outputs["Vector"], sep.inputs[0])
    cx, cy = mth("SUBTRACT", sep.outputs["X"], 0.5), mth("SUBTRACT", sep.outputs["Y"], 0.5)
    r = mth("MULTIPLY", mth("SQRT", mth("ADD", mth("MULTIPLY", cx, cx), mth("MULTIPLY", cy, cy))), 2.0)   # 0 centre, 1 edge
    ang = mth("ADD", mth("ARCTAN2", cy, cx), mth("MULTIPLY", fr, 6.283))
    comb = N.new("ShaderNodeCombineXYZ")                    # the irregular edge: noise over the card, per flake
    L.new(cx, comb.inputs[0])
    L.new(cy, comb.inputs[1])
    L.new(mth("MULTIPLY", fr, 37.0), comb.inputs[2])
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 3.0, 3.0
    L.new(comb.outputs[0], nz.inputs["Vector"])
    edge = mth("ADD", r, mth("MULTIPLY", mth("SUBTRACT", nz.outputs["Factor"], 0.5), 0.9))
    disc = mth("SUBTRACT", 1.0, mth("POWER", mth("MINIMUM", mth("MAXIMUM", mth("DIVIDE", mth("SUBTRACT", edge, 0.42), 0.5), 0.0), 1.0), 0.7))
    six = mth("ABSOLUTE", mth("COSINE", mth("MULTIPLY", ang, 3.0)))
    arms = mth("POWER", six, 14.0)                                         # six thin arms
    branches = mth("MULTIPLY", mth("POWER", mth("ABSOLUTE", mth("COSINE", mth("MULTIPLY", r, 21.0))), 3.0), mth("POWER", six, 4.0))
    star = mth("MULTIPLY", mth("MAXIMUM", arms, mth("MULTIPLY", branches, 0.8)), mth("SUBTRACT", 1.0, mth("MINIMUM", mth("DIVIDE", r, 0.95), 1.0)))
    star = mth("MULTIPLY", star, mth("MINIMUM", mth("MULTIPLY", nz.outputs["Factor"], 1.8), 1.0))   # broken, uneven arms
    star = mth("MAXIMUM", star, mth("SUBTRACT", 1.0, mth("MINIMUM", mth("DIVIDE", r, 0.2), 1.0)))      # the centre plate
    dend = mth("GREATER_THAN", mth("FRACT", mth("MULTIPLY", fr, 7.13)), 1.0 - S.DENDRITE_SHARE)
    alpha = mth("ADD", mth("MULTIPLY", disc, mth("SUBTRACT", 1.0, dend)), mth("MULTIPLY", mth("MINIMUM", mth("MULTIPLY", star, 1.6), 1.0), dend))
    alpha = mth("MULTIPLY", alpha, S.FLAKE_OPACITY)
    tl = N.new("ShaderNodeBsdfTranslucent")
    tl.inputs["Color"].default_value = (0.85, 0.9, 0.97, 1.0)
    body = N.new("ShaderNodeMixShader")
    body.inputs[0].default_value = S.FLAKE_TRANSLUCENCY
    L.new(sh.outputs[0], body.inputs[1])
    L.new(tl.outputs[0], body.inputs[2])
    tr = N.new("ShaderNodeBsdfTransparent")
    cut = N.new("ShaderNodeMixShader")
    L.new(alpha, cut.inputs[0])
    L.new(tr.outputs[0], cut.inputs[1])
    L.new(body.outputs[0], cut.inputs[2])
    L.new(cut.outputs[0], out.inputs["Surface"])
    return m


def _cover_material(bpy):
    """The accumulated snow: near-white with explicit subsurface scattering (Burley, the shell is an open sheet;
    SSS_SCALE_M ~ 1 cm, blue furthest), ~1 mm ice grain in the bump and the roughness, a few glinting grains."""
    from engine.physics import snow as S
    m = bpy.data.materials.new("valora_snow_cover")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    sh = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    sh.subsurface_method = "BURLEY"
    sh.inputs["Base Color"].default_value = (0.86, 0.88, 0.92, 1.0)
    sh.inputs["Subsurface Weight"].default_value = S.SSS_WEIGHT
    sh.inputs["Subsurface Radius"].default_value = S.SSS_RADIUS
    sh.inputs["Subsurface Scale"].default_value = S.SSS_SCALE_M
    geo = N.new("ShaderNodeNewGeometry")
    grain = N.new("ShaderNodeTexVoronoi")
    grain.inputs["Scale"].default_value = 1.0 / S.GRAIN_M
    L.new(geo.outputs["Position"], grain.inputs["Vector"])
    lump = N.new("ShaderNodeTexNoise")
    lump.inputs["Scale"].default_value, lump.inputs["Detail"].default_value = S.LUMP_NOISE_M, 6.0
    L.new(geo.outputs["Position"], lump.inputs["Vector"])
    h = N.new("ShaderNodeMath")
    h.operation = "MULTIPLY_ADD"
    L.new(grain.outputs["Distance"], h.inputs[0])
    h.inputs[1].default_value = 0.35
    L.new(lump.outputs["Factor"], h.inputs[2])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value, bump.inputs["Distance"].default_value = 0.6, S.LUMP_BUMP_M
    L.new(h.outputs[0], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], sh.inputs["Normal"])
    sep = N.new("ShaderNodeSeparateColor")
    L.new(grain.outputs["Color"], sep.inputs[0])
    glint = N.new("ShaderNodeMath")
    glint.operation = "GREATER_THAN"
    L.new(sep.outputs[0], glint.inputs[0])
    glint.inputs[1].default_value = 1.0 - S.GLINT_SHARE
    rough = N.new("ShaderNodeMapRange")                     # grains 0.55-0.85 rough, glints 0.12
    L.new(sep.outputs[1], rough.inputs["Value"])
    rough.inputs["To Min"].default_value, rough.inputs["To Max"].default_value = 0.55, 0.85
    mixr = N.new("ShaderNodeMix")
    mixr.data_type = "FLOAT"
    L.new(glint.outputs[0], mixr.inputs[0])
    L.new(rough.outputs["Result"], mixr.inputs[2])
    mixr.inputs[3].default_value = 0.12
    L.new(mixr.outputs[0], sh.inputs["Roughness"])
    spec = N.new("ShaderNodeMapRange")
    L.new(glint.outputs[0], spec.inputs["Value"])
    spec.inputs["To Min"].default_value, spec.inputs["To Max"].default_value = 0.35, 1.0
    L.new(spec.outputs["Result"], sh.inputs["Specular IOR Level"])
    # coverage: full where the shell is deep, a patchy dusting as it rolls off, bare paint at the edge
    roll = N.new("ShaderNodeAttribute")
    roll.attribute_name = "valora_snow_roll"
    patch = N.new("ShaderNodeTexNoise")
    patch.inputs["Scale"].default_value, patch.inputs["Detail"].default_value = S.DUST_NOISE_M, 3.0
    patch.inputs["Roughness"].default_value = 0.5
    L.new(geo.outputs["Position"], patch.inputs["Vector"])
    mth = _shader_math(m.node_tree)
    lvl = mth("ADD", mth("MULTIPLY", roll.outputs["Fac"], S.DUST_ROLL_GAIN), mth("MULTIPLY", mth("SUBTRACT", patch.outputs["Factor"], 0.5), S.DUST_NOISE_GAIN))
    # the dusting breaks up grain by grain (the ice-grain cells), not along one torn line
    lvl = mth("ADD", lvl, mth("MULTIPLY", mth("SUBTRACT", sep.outputs[2], 0.5), S.DUST_GRAIN_GAIN))
    cov = N.new("ShaderNodeMapRange")
    cov.interpolation_type = "SMOOTHSTEP"
    L.new(lvl, cov.inputs["Value"])
    cov.inputs["From Min"].default_value, cov.inputs["From Max"].default_value = S.DUST_EDGE
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    tr = N.new("ShaderNodeBsdfTransparent")
    mix = N.new("ShaderNodeMixShader")
    L.new(cov.outputs["Result"], mix.inputs[0])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(sh.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    return m


def _flake_protos(d, flake_mm):
    """[a single card, a clump of three crossed cards] at unit flake size, with card UVs in valora_uv."""
    from engine.blender import weather_nodes as wn

    def card(rot=(0.0, 0.0, 0.0), offset=(0.0, 0.0, 0.0), size=1.0):
        g = d.node("GeometryNodeMeshGrid")
        g.inputs["Size X"].default_value = g.inputs["Size Y"].default_value = size
        g.inputs["Vertices X"].default_value = g.inputs["Vertices Y"].default_value = 2
        st = d.node("GeometryNodeStoreNamedAttribute", data_type="FLOAT_VECTOR", domain="CORNER")
        d.feed(st.inputs["Geometry"], g.outputs["Mesh"])
        st.inputs["Name"].default_value = "valora_uv"
        d.feed(st.inputs["Value"], g.outputs["UV Map"])
        tr = d.node("GeometryNodeTransform")
        d.feed(tr.inputs["Geometry"], st.outputs["Geometry"])
        tr.inputs["Rotation"].default_value = rot
        tr.inputs["Translation"].default_value = offset
        return tr.outputs["Geometry"]

    s = flake_mm / 1000.0
    single = card(size=s)
    clump = d.node("GeometryNodeJoinGeometry")
    for rot, off, k in (((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.7), ((1.1, 0.4, 0.0), (0.25, 0.1, 0.05), 0.55),
                        ((-0.5, 1.2, 0.7), (-0.2, 0.2, -0.05), 0.5)):
        d.feed(clump.inputs["Geometry"], card(rot, tuple(o * s for o in off), k * s))
    return wn.prototypes(d, [single, clump.outputs["Geometry"]])


def _flakes(bpy, ctx, mat, speed_ms_wind, per_ms=1.0):
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.blender.realism_rig import OFFSET
    from engine.physics import rain as R
    from engine.physics import snow as S
    prof, p = ctx.profile, ctx.params
    far = max((math.dist(q, prof.center) for q in ctx.camera_positions), default=4.0 * prof.radius)
    near = min((math.dist(q, prof.center) for q in ctx.camera_positions), default=far)
    side, height = R.box_size(prof.longest, prof.sizeM[2], far, min(ctx.camera_lenses_mm or [50.0]))
    n = S.flake_count(p["rate"], side * side * height)
    ob = wn.weather_object(ctx.scene, "valora_snow", "effect/snow")
    ob.visible_shadow = False
    t = Tree("valora_snow_points")
    rnd = lambda lo, hi, k: wn.random(t, "FLOAT", lo, hi, ctx.seed + k)  # noqa: E731
    speed = rnd(*S.SPEED_MS, 11)
    amp, f1, f2 = rnd(*S.WOBBLE_A_M, 12), rnd(*S.WOBBLE_HZ, 13), rnd(*S.WOBBLE_HZ, 14)
    p1, p2 = rnd(0.0, 2 * math.pi, 15), rnd(0.0, 2 * math.pi, 16)
    sec = t.time()
    arg1 = t.math("ADD", t.math("MULTIPLY", t.math("MULTIPLY", f1, 2 * math.pi), sec), p1)
    arg2 = t.math("ADD", t.math("MULTIPLY", t.math("MULTIPLY", f2, 2 * math.pi), sec), p2)
    wx, wy = speed_ms_wind
    drift = t.vec(t.math("ADD", t.math("MULTIPLY", sec, wx), t.math("MULTIPLY", amp, t.math("SINE", arg1))),
                  t.math("ADD", t.math("MULTIPLY", sec, wy), t.math("MULTIPLY", amp, t.math("COSINE", arg2))),
                  t.math("MULTIPLY", t.math("MULTIPLY", speed, sec), -1.0))
    wn.box_points(t, n, ctx.seed, side, height, wn.box_centre(t, prof.center[:2]), drift)
    # d(drift)/dt: the mean wind + the wobble's derivative + the fall
    carrier = t.vec(t.math("ADD", wx, t.math("MULTIPLY", t.math("MULTIPLY", amp, t.math("MULTIPLY", f1, 2 * math.pi)), t.math("COSINE", arg1))),
                    t.math("SUBTRACT", wy, t.math("MULTIPLY", t.math("MULTIPLY", amp, t.math("MULTIPLY", f2, 2 * math.pi)), t.math("SINE", arg2))),
                    t.math("MULTIPLY", speed, -1.0))
    # the one field's gusts and turbulence on top of the mean drift (review chunk3 #4); stores velocity =
    # carrier + the gust displacement's derivative (review chunk5 #9)
    wn.gusts(t, (wx, wy, 0.0), per_ms, carrier)
    # the flake's own look, stored before the shelter compacts the indices: its turn and tumble (snow.tumble),
    # a clump or a single crystal (snow.is_clump), its size (snow.flake_size_mm, as a share of flakeMm)
    t.store("valora_spin", wn.random(t, "FLOAT_VECTOR", (0.0, 0.0, 0.0), (6.3, 6.3, 6.3), ctx.seed + 17), "FLOAT_VECTOR")
    t.store("valora_tumble", wn.random(t, "FLOAT_VECTOR", (-S.TUMBLE_RAD_S,) * 3, (S.TUMBLE_RAD_S,) * 3, ctx.seed + 18),
            "FLOAT_VECTOR")
    clump = t.math("LESS_THAN", rnd(0.0, 1.0, 19), S.CLUMP_SHARE)
    lo, hi = S.SIZE_SPREAD
    size = t.math("MULTIPLY_ADD", t.math("POWER", rnd(0.0, 1.0, 20), S.SIZE_SKEW), hi - lo, lo)
    csize = t.math("MULTIPLY_ADD", rnd(0.0, 1.0, 21), S.CLUMP_SIZE[1] - S.CLUMP_SIZE[0], S.CLUMP_SIZE[0])
    t.store("valora_clump", clump)
    t.store("valora_flake_size", t.math("MULTIPLY", size, t.math("ADD", 1.0, t.math("MULTIPLY", clump, t.math("SUBTRACT", csize, 1.0)))))
    t.store("valora_flake_rnd", rnd(0.0, 1.0, 22))
    wn.shelter(t, bpy.data.objects[OFFSET], prof.boundsMin, prof.boundsMax, near_m=R.NEAR_FRAC * near)
    add_modifier(ob, t.finish(), "valora_snow_points")
    d = Tree("valora_snow_flakes")
    k = d.attr("valora_flake_size")
    turn = d.vmath("ADD", d.attr("valora_spin", "FLOAT_VECTOR"), d.vmath("SCALE", d.attr("valora_tumble", "FLOAT_VECTOR"), scale=d.time()))
    wn.instance_pick(d, _flake_protos(d, p["flakeMm"]), d.attr("valora_clump"), d.vec(k, k, k), rotation=turn,
                     material=mat, realize=True)
    add_modifier(ob, d.finish(), "valora_snow_flakes")
    return ob, n, side, height


def _cover(bpy, ctx, mat):
    """The snow layer on the subject: up-facing faces of the evaluated upload lifted into a smoothed shell. Its
    depth varies with a drift noise and rolls off to MIN_LIFT_MM where the smooth surface normal (the upload's
    split normals, captured per vertex before they are dropped) turns past UP_DOT: snow.cover_depth_mm."""
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.physics import snow as S
    p = ctx.params
    ob = wn.weather_object(ctx.scene, "valora_snow_cover", "effect/snow")
    t = Tree("valora_snow_cover")
    join = t.node("GeometryNodeJoinGeometry")
    for m in ctx.meshes:
        info = t.node("GeometryNodeObjectInfo", transform_space="RELATIVE")
        info.inputs["Object"].default_value = m
        t.feed(join.inputs["Geometry"], info.outputs["Geometry"])
    cap = t.node("GeometryNodeCaptureAttribute", domain="POINT")   # the smooth (shading) normal, per vertex
    cap.capture_items.new("VECTOR", "Normal")
    t.feed(cap.inputs["Geometry"], join.outputs["Geometry"])
    t.feed(cap.inputs[1], t.node("GeometryNodeInputNormal").outputs["Normal"])
    smooth_nz = t.xyz(cap.outputs[1])[2]
    # the upload's custom (split) normals would make the Normal field a smoothed normal: drop them on this copy so
    # "faces up" is the true face normal (glTF imports carry custom_normal; the upload itself is untouched)
    tri = t.node("GeometryNodeTriangulate")               # planar faces: a non-planar quad has no one normal
    t.feed(tri.inputs["Mesh"], cap.outputs["Geometry"])
    rm = t.node("GeometryNodeRemoveAttribute")
    t.feed(rm.inputs["Geometry"], tri.outputs["Mesh"])
    rm.inputs["Name"].default_value = "custom_normal"
    t.geometry = rm.outputs["Geometry"]
    t.store("valora_snz", smooth_nz)
    nz = t.xyz(t.node("GeometryNodeInputNormal").outputs["Normal"])[2]
    d = t.node("GeometryNodeDeleteGeometry", domain="FACE")
    t.feed(d.inputs["Geometry"], t.geometry)
    t.feed(d.inputs["Selection"], t.math("LESS_THAN", nz, S.UP_DOT + 1e-4))
    t.geometry = d.outputs["Geometry"]
    weld = t.node("GeometryNodeMergeByDistance")          # one shell across the import's split seams
    t.feed(weld.inputs["Geometry"], t.geometry)
    weld.inputs["Distance"].default_value = 1e-4
    t.geometry = weld.outputs["Geometry"]
    # snow depth is measured vertically: lift straight up (a lift along vertex normals folds thin parts)
    acc = t.math("ADD", p["accumulationMm"], t.math("MULTIPLY", t.time(), p["rate"] * S.GROW_MM_S))
    n1, _ = t.noise(t.position(), scale=S.DEPTH_NOISE_M[0])
    n2, _ = t.noise(t.vmath("ADD", t.position(), (5.0, 11.0, 3.0)), scale=S.DEPTH_NOISE_M[1])
    drift = t.math("MULTIPLY_ADD", n1, 0.7, t.math("MULTIPLY", n2, 0.3))
    var = t.math("ADD", 1.0, t.math("MULTIPLY", t.math("SUBTRACT", t.math("MULTIPLY", drift, 2.0), 1.0), S.DEPTH_VAR))
    roll = t.smoothstep(S.ROLL_NZ[0], S.ROLL_NZ[1], t.attr("valora_snz"))
    depth_mm = t.math("MAXIMUM", t.math("MULTIPLY", t.math("MULTIPLY", acc, var), roll), S.MIN_LIFT_MM)
    t.store("valora_snow_roll", roll)                    # the shader thins the edge into a patchy dusting
    # relax the depth over the mesh: a crease's two split normals, or a dense patch of tiny faces, must not turn
    # a depth step into a cliff (the shell stays a smooth cushion)
    blur = t.node("GeometryNodeBlurAttribute", data_type="FLOAT")
    t.feed(blur.inputs["Value"], depth_mm)
    blur.inputs["Iterations"].default_value = S.DEPTH_BLUR_ITER
    t.set_position(t.vmath("ADD", t.position(), t.vec(0.0, 0.0, t.math("MULTIPLY", blur.outputs["Value"], 0.001))))
    sm = t.node("GeometryNodeSetMaterial")
    t.feed(sm.inputs["Geometry"], t.geometry)
    sm.inputs["Material"].default_value = mat
    ss = t.node("GeometryNodeSetShadeSmooth")
    t.feed(ss.inputs["Geometry"], sm.outputs["Geometry"])
    t.geometry = ss.outputs[0]
    add_modifier(ob, t.finish(), "valora_snow_cover")
    return ob


def _ground_group(bpy, coverage):
    ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    for name, kind in (("Color", "NodeSocketColor"), ("Roughness", "NodeSocketFloat")):
        ng.interface.new_socket(name, in_out="INPUT", socket_type=kind)
        ng.interface.new_socket(name, in_out="OUTPUT", socket_type=kind)
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    geo = ng.nodes.new("ShaderNodeNewGeometry")
    noise = ng.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.6
    ng.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    ramp = ng.nodes.new("ShaderNodeMapRange")                  # patchy where thin, solid where deep
    ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.65 - 0.6 * coverage, 0.75 - 0.6 * coverage
    ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = 0.0, 1.0
    ng.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    mix = ng.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    ng.links.new(ramp.outputs["Result"], mix.inputs["Factor"])
    ng.links.new(gi.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (0.9, 0.92, 0.95, 1.0)
    ng.links.new(mix.outputs[2], go.inputs["Color"])
    rough = ng.nodes.new("ShaderNodeMix")
    rough.data_type = "FLOAT"
    ng.links.new(ramp.outputs["Result"], rough.inputs["Factor"])
    ng.links.new(gi.outputs["Roughness"], rough.inputs[2])
    rough.inputs[3].default_value = 0.8
    ng.links.new(rough.outputs[0], go.inputs["Roughness"])
    return ng


def _coat_ground(bpy, coverage):
    from engine.blender.realism_rig import ground_objects
    group, wrapped = _ground_group(bpy, coverage), []
    # one wrap per material across the whole ground (review chunk3 #9)
    mats = {m.name: m for ob in ground_objects() for m in ob.data.materials if m is not None and m.use_nodes}
    for mat in mats.values():
        sh = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if sh is None:
            continue
        nt = mat.node_tree
        g = nt.nodes.new("ShaderNodeGroup")
        g.node_tree, g.name = group, GROUP
        for src, dst in (("Base Color", "Color"), ("Roughness", "Roughness")):
            sock = sh.inputs[src]
            if sock.is_linked:
                nt.links.new(sock.links[0].from_socket, g.inputs[dst])
            else:
                g.inputs[dst].default_value = sock.default_value
            nt.links.new(g.outputs[dst], sh.inputs[src])
        wrapped.append(mat.name)
    return sorted(wrapped)


def build(ctx):
    import bpy
    from engine.physics import snow as S
    from engine.physics import wind as W
    from engine.physics.wind_calibration import perms
    p = ctx.params
    w = ctx.scene.get("valora_wind") or {"directionDeg": 0.0, "speedMs": 0.0}
    k = perms(ctx.catalog, "effect", "snow")
    wind = W.vector(float(w["directionDeg"]), float(w["speedMs"]) * k)
    mat = _snow_material(bpy)
    ob, n, side, height = _flakes(bpy, ctx, mat, wind[:2], k)
    cover = _cover(bpy, ctx, _cover_material(bpy)) if p["onSubject"] and p["accumulationMm"] > 0 else None
    ground = _coat_ground(bpy, min(1.0, p["accumulationMm"] / COAT_FULL_MM))
    ctx.scene["valora_fx_snow"] = {"count": n, "side": side, "height": height, "cover": cover is not None,
                                   "groundMaterials": ground, "driftMs": [wind[0], wind[1]],
                                   "accumulationMm": p["accumulationMm"]}
    return ob
