"""Photographic set helpers shared by the outdoor worlds (art pass 2026-09-25). Runs inside Blender.

What makes the rain courtyard read as real is copied here so golden_field and night_street can use it too:
- an HDRI world, rotated so the photo's sun sits where the set's own key is;
- photo-textured PBR surfaces on world-scale coordinates (Poly Haven diff / rough / GL normal scans);
- glTF scatter: photoscanned tufts (Poly Haven CC0) joined into ONE foliage mesh with numpy (the foliage
  contract needs one island per blade with valora_sway 0 at its root), with a per-tuft tint attribute; and
  static instanced tufts (Geometry Nodes, never realised) for ground cover and the far field;
- aerial perspective: a surface mixed toward haze by its distance from the camera, the haze being the HDRI's
  own sky just above the horizon in the view direction (depth without a second volume).
Every asset arrives as a path from engine.assets.resolve()/resolve_gltf() or None; callers keep their fallback."""
import math

import bpy
import numpy as np

TINT_ATTR = "valora_tint"       # per-tuft random 0..1, constant over a tuft (material variation)


# ---------------------------------------------------------------------------------------------- HDRI
def env_colour(nt, vector, path, rot_deg, tint=None):
    """Colour socket: the HDRI at `path` looked up along `vector`, rotated rot_deg about +Z."""
    tex = nt.nodes.new("ShaderNodeTexEnvironment")
    tex.image = bpy.data.images.load(str(path), check_existing=True)
    rot = nt.nodes.new("ShaderNodeMapping")
    rot.inputs["Rotation"].default_value[2] = math.radians(rot_deg)
    nt.links.new(vector, rot.inputs["Vector"])
    nt.links.new(rot.outputs["Vector"], tex.inputs["Vector"])
    colour = tex.outputs["Color"]
    if tint is not None:
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(colour, mul.inputs[6])
        mul.inputs[7].default_value = (*tint, 1.0)
        colour = mul.outputs[2]
    return colour


def world_hdri(scene, name, path, rot_deg, strength, tint=None):
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(env_colour(nt, tc.outputs["Generated"], path, rot_deg, tint), bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    scene.world = w
    return w


def rotation_for(photo_az_deg, want_dir):
    """The Z rotation (deg) that puts a photo feature at azimuth photo_az_deg onto the world direction want_dir.
    The Mapping node rotates the lookup vector: lookup(R v); R(want) must land on the photo azimuth."""
    return photo_az_deg - math.degrees(math.atan2(want_dir[1], want_dir[0]))


def camera_only(ob):
    """Seen by the camera (and in mirror reflections), never lighting or shadowing the set."""
    ob.visible_shadow = ob.visible_diffuse = ob.visible_transmission = False
    ob.visible_volume_scatter = False
    return ob


# --------------------------------------------------------------------------------------- aerial depth
def aerial(mat, colour, half_m, max_mix=0.85, hdri=None, horizon_lift=0.02):
    """Mix a material's surface toward haze with camera distance: share 1 - 2^(-d/half_m), capped at max_mix.
    The haze is a flat colour, or with hdri = (path, rot_deg, strength, tint) the photo's own sky just above the
    horizon in the direction the camera looks (horizon_lift: its elevation, as a slope), so far ground and trees
    dissolve into exactly the skyline behind them. Emission: it survives any exposure."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    link = next((l for l in nt.links if l.to_node == out and l.to_socket.name == "Surface"), None)
    if link is None:
        return mat
    src = link.from_socket
    nt.links.remove(link)
    cam = nt.nodes.new("ShaderNodeCameraData")
    k = nt.nodes.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    k.inputs[1].default_value = -math.log(2.0) / max(half_m, 1e-3)
    nt.links.new(cam.outputs["View Distance"], k.inputs[0])
    e = nt.nodes.new("ShaderNodeMath")
    e.operation = "EXPONENT"
    nt.links.new(k.outputs[0], e.inputs[0])
    inv = nt.nodes.new("ShaderNodeMapRange")          # 1 - exp(...) mapped onto 0..max_mix
    inv.inputs["From Min"].default_value, inv.inputs["From Max"].default_value = 1.0, 0.0
    inv.inputs["To Min"].default_value, inv.inputs["To Max"].default_value = 0.0, max_mix
    nt.links.new(e.outputs[0], inv.inputs["Value"])
    em = nt.nodes.new("ShaderNodeEmission")
    if hdri is None:
        em.inputs["Color"].default_value = (*colour, 1.0)
    else:
        path, rot, strength, tint = hdri
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Incoming"], sep.inputs[0])       # toward the viewer: the view is its negative
        nx, ny = nt.nodes.new("ShaderNodeMath"), nt.nodes.new("ShaderNodeMath")
        for n_, ax in ((nx, "X"), (ny, "Y")):
            n_.operation = "MULTIPLY"
            n_.inputs[1].default_value = -1.0
            nt.links.new(sep.outputs[ax], n_.inputs[0])
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(nx.outputs[0], comb.inputs["X"])
        nt.links.new(ny.outputs[0], comb.inputs["Y"])
        flat = nt.nodes.new("ShaderNodeVectorMath")
        flat.operation = "NORMALIZE"
        nt.links.new(comb.outputs[0], flat.inputs[0])
        up = nt.nodes.new("ShaderNodeVectorMath")
        up.operation = "ADD"
        up.inputs[1].default_value = (0.0, 0.0, horizon_lift)
        nt.links.new(flat.outputs["Vector"], up.inputs[0])
        nt.links.new(env_colour(nt, up.outputs["Vector"], path, rot, tint), em.inputs["Color"])
        em.inputs["Strength"].default_value = strength
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.name = "valora_aerial"
    fac = inv.outputs["Result"]
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None and bsdf.inputs["Alpha"].is_linked:   # round 11: a cut-out leaf card's clear part stays clear
        am = nt.nodes.new("ShaderNodeMath")
        am.operation = "MULTIPLY"
        nt.links.new(fac, am.inputs[0])
        nt.links.new(bsdf.inputs["Alpha"].links[0].from_socket, am.inputs[1])
        fac = am.outputs[0]
    nt.links.new(fac, mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


# ------------------------------------------------------------------------------------- PBR textures
# Realism audit #14 + texture repetition: engine/texture_projection.py is the maths; these two node groups
# realise it. valora_pbr_frame: per shading point, the face's metric projection (XY for ground, YZ / XZ with
# texture-up = world-up for kerb and wall faces), the second anti-tiling sample's coordinates, the decode frames
# (tangent to the shading normal) and the blend / macro-wear noises. valora_pbr_normal: a GL normal-map colour
# decoded into WORLD space with a frame (no UVs, no tangents), so position-projected scans light correctly.
FRAME_GROUP, NORMAL_GROUP = "valora_pbr_frame", "valora_pbr_normal"


def _vm(nt, op, a, b=None, scale=None, c=None):
    n = nt.nodes.new("ShaderNodeVectorMath")
    n.operation = op
    for i, v in enumerate((a, b, c)):
        if v is None:
            continue
        if isinstance(v, (tuple, list)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    if scale is not None:
        if isinstance(scale, (int, float)):
            n.inputs["Scale"].default_value = float(scale)
        else:
            nt.links.new(scale, n.inputs["Scale"])
    return n.outputs["Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector"]


def _fm(nt, op, a, b=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _xyz(nt, x, y, z=0.0):
    c = nt.nodes.new("ShaderNodeCombineXYZ")
    for i, v in enumerate((x, y, z)):
        if isinstance(v, (int, float)):
            c.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, c.inputs[i])
    return c.outputs[0]


def frame_group():
    """valora_pbr_frame(Tile) -> UV, UV2, T, B, T2, B2, Blend, Macro (engine/texture_projection.py)."""
    from engine import texture_projection as TP
    ng = bpy.data.node_groups.get(FRAME_GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(FRAME_GROUP, "ShaderNodeTree")
    ng.interface.new_socket("Tile", in_out="INPUT", socket_type="NodeSocketFloat").default_value = 1.0
    for name in ("UV", "UV2", "T", "B", "T2", "B2"):
        ng.interface.new_socket(name, in_out="OUTPUT", socket_type="NodeSocketVector")
    for name in ("Blend", "Macro"):
        ng.interface.new_socket(name, in_out="OUTPUT", socket_type="NodeSocketFloat")
    nt = ng
    gi, go = nt.nodes.new("NodeGroupInput"), nt.nodes.new("NodeGroupOutput")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    P, N, Nt = geo.outputs["Position"], geo.outputs["Normal"], geo.outputs["True Normal"]
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(_vm(nt, "ABSOLUTE", Nt), sep.inputs[0])
    ax, ay, az = sep.outputs
    is_z = _fm(nt, "MULTIPLY", _fm(nt, "GREATER_THAN", _fm(nt, "SUBTRACT", az, ax), -1e-6),
               _fm(nt, "GREATER_THAN", _fm(nt, "SUBTRACT", az, ay), -1e-6))
    not_z = _fm(nt, "SUBTRACT", 1.0, is_z)
    x_wins = _fm(nt, "GREATER_THAN", ax, ay)
    is_x = _fm(nt, "MULTIPLY", not_z, x_wins)
    is_y = _fm(nt, "MULTIPLY", not_z, _fm(nt, "SUBTRACT", 1.0, x_wins))
    # projection_frame: z -> T=x, B=y; x -> T=y, B=z; y -> T=x, B=z
    t0 = _xyz(nt, _fm(nt, "ADD", is_z, is_y), is_x, 0.0)
    b0 = _xyz(nt, 0.0, is_z, not_z)
    hand = _vm(nt, "DOT_PRODUCT", _vm(nt, "CROSS_PRODUCT", t0, b0), Nt)
    sign = _fm(nt, "SUBTRACT", _fm(nt, "MULTIPLY", _fm(nt, "GREATER_THAN", hand, -1e-6), 2.0), 1.0)
    t0 = _vm(nt, "SCALE", t0, scale=sign)
    inv = _fm(nt, "DIVIDE", 1.0, gi.outputs["Tile"])
    u = _fm(nt, "MULTIPLY", _vm(nt, "DOT_PRODUCT", P, t0), inv)
    v = _fm(nt, "MULTIPLY", _vm(nt, "DOT_PRODUCT", P, b0), inv)
    th = math.radians(TP.ANTI_TILE_ROT_DEG)
    c, s_ = math.cos(th) * TP.ANTI_TILE_SCALE, math.sin(th) * TP.ANTI_TILE_SCALE
    u2 = _fm(nt, "ADD", _fm(nt, "SUBTRACT", _fm(nt, "MULTIPLY", u, c), _fm(nt, "MULTIPLY", v, s_)), TP.ANTI_TILE_OFFSET[0])
    v2 = _fm(nt, "ADD", _fm(nt, "ADD", _fm(nt, "MULTIPLY", u, s_), _fm(nt, "MULTIPLY", v, c)), TP.ANTI_TILE_OFFSET[1])
    # face_frame: T' = normalize(T - N (N.T)), B' = N x T'
    tp = _vm(nt, "NORMALIZE", _vm(nt, "SUBTRACT", t0, _vm(nt, "SCALE", N, scale=_vm(nt, "DOT_PRODUCT", N, t0))))
    bp = _vm(nt, "CROSS_PRODUCT", N, tp)
    cr, sr = math.cos(th), math.sin(th)
    t2 = _vm(nt, "SUBTRACT", _vm(nt, "SCALE", tp, scale=cr), _vm(nt, "SCALE", bp, scale=sr))
    b2 = _vm(nt, "ADD", _vm(nt, "SCALE", tp, scale=sr), _vm(nt, "SCALE", bp, scale=cr))
    blend_n = nt.nodes.new("ShaderNodeTexNoise")
    blend_n.inputs["Detail"].default_value = 2.0
    nt.links.new(_vm(nt, "SCALE", P, scale=_fm(nt, "DIVIDE", inv, TP.ANTI_TILE_NOISE_TILES)), blend_n.inputs["Vector"])
    band = nt.nodes.new("ShaderNodeMapRange")
    band.interpolation_type, band.clamp = "SMOOTHSTEP", True
    band.inputs["From Min"].default_value, band.inputs["From Max"].default_value = TP.ANTI_TILE_BAND
    nt.links.new(blend_n.outputs["Fac"], band.inputs["Value"])
    macro_n = nt.nodes.new("ShaderNodeTexNoise")
    macro_n.inputs["Detail"].default_value = 3.0
    nt.links.new(_vm(nt, "SCALE", P, scale=_fm(nt, "DIVIDE", inv, 1.1)), macro_n.inputs["Vector"])
    macro = nt.nodes.new("ShaderNodeMapRange")
    macro.inputs["From Min"].default_value, macro.inputs["From Max"].default_value = 0.3, 0.7
    macro.inputs["To Min"].default_value, macro.inputs["To Max"].default_value = TP.MACRO_VALUE
    macro.clamp = True
    nt.links.new(macro_n.outputs["Fac"], macro.inputs["Value"])
    for name, sock in (("UV", _xyz(nt, u, v)), ("UV2", _xyz(nt, u2, v2)), ("T", tp), ("B", bp), ("T2", t2),
                       ("B2", b2), ("Blend", band.outputs["Result"]), ("Macro", macro.outputs["Result"])):
        nt.links.new(sock, go.inputs[name])
    return ng


def normal_group():
    """valora_pbr_normal(Color, T, B, Strength) -> world Normal: n = x T + y B + z N (GL: green = +v)."""
    ng = bpy.data.node_groups.get(NORMAL_GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(NORMAL_GROUP, "ShaderNodeTree")
    ng.interface.new_socket("Color", in_out="INPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket("T", in_out="INPUT", socket_type="NodeSocketVector")
    ng.interface.new_socket("B", in_out="INPUT", socket_type="NodeSocketVector")
    ng.interface.new_socket("Strength", in_out="INPUT", socket_type="NodeSocketFloat").default_value = 1.0
    ng.interface.new_socket("Normal", in_out="OUTPUT", socket_type="NodeSocketVector")
    nt = ng
    gi, go = nt.nodes.new("NodeGroupInput"), nt.nodes.new("NodeGroupOutput")
    N = nt.nodes.new("ShaderNodeNewGeometry").outputs["Normal"]
    d = _vm(nt, "MULTIPLY_ADD", gi.outputs["Color"], (2.0, 2.0, 2.0), c=(-1.0, -1.0, -1.0))
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(d, sep.inputs[0])
    x = _fm(nt, "MULTIPLY", sep.outputs[0], gi.outputs["Strength"])
    y = _fm(nt, "MULTIPLY", sep.outputs[1], gi.outputs["Strength"])
    n = _vm(nt, "ADD", _vm(nt, "ADD", _vm(nt, "SCALE", gi.outputs["T"], scale=x), _vm(nt, "SCALE", gi.outputs["B"], scale=y)),
            _vm(nt, "SCALE", N, scale=sep.outputs[2]))
    nt.links.new(_vm(nt, "NORMALIZE", n), go.inputs["Normal"])
    return ng


def pbr_sampler(nt, maps, tile_m, bump_k=1.0):
    """Nodes in material tree nt sampling the scans in `maps` (diff, rough, nor_gl, optional disp) on the metric
    face projection, twice (anti-tiling), blended. Returns {"color", "rough", "normal", "height"} sockets (None for
    a missing map). Colour carries the macro wear; `height` is the named node valora_scan_height (wet_surface)."""
    fr = nt.nodes.new("ShaderNodeGroup")
    fr.node_tree, fr.name = frame_group(), "valora_pbr_frame"
    fr.inputs["Tile"].default_value = float(tile_m)
    out = {"color": None, "rough": None, "normal": None, "height": None}

    def pair(path, colour):
        img = bpy.data.images.load(str(path), check_existing=True)
        if not colour:
            img.colorspace_settings.is_data = True
        res = []
        for uv in ("UV", "UV2"):
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = img
            nt.links.new(fr.outputs[uv], t.inputs["Vector"])
            res.append(t.outputs["Color"])
        return res

    def blend(a, b):
        m = nt.nodes.new("ShaderNodeMix")
        m.data_type = "RGBA"
        nt.links.new(fr.outputs["Blend"], m.inputs["Factor"])
        nt.links.new(a, m.inputs[6])
        nt.links.new(b, m.inputs[7])
        return m.outputs[2]
    if maps.get("diff"):
        base = blend(*pair(maps["diff"], True))
        wear = nt.nodes.new("ShaderNodeMix")
        wear.data_type, wear.blend_type = "RGBA", "MULTIPLY"
        wear.inputs["Factor"].default_value = 1.0
        nt.links.new(base, wear.inputs[6])
        nt.links.new(_xyz(nt, fr.outputs["Macro"], fr.outputs["Macro"], fr.outputs["Macro"]), wear.inputs[7])
        out["color"] = wear.outputs[2]
    if maps.get("rough"):
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        bw.name = "valora_scan_rough"
        nt.links.new(blend(*pair(maps["rough"], False)), bw.inputs[0])
        out["rough"] = bw.outputs[0]
    if maps.get("nor_gl"):
        ca, cb = pair(maps["nor_gl"], False)
        ns = []
        for col, t, b in ((ca, "T", "B"), (cb, "T2", "B2")):
            g = nt.nodes.new("ShaderNodeGroup")
            g.node_tree = normal_group()
            g.inputs["Strength"].default_value = bump_k
            nt.links.new(col, g.inputs["Color"])
            nt.links.new(fr.outputs[t], g.inputs["T"])
            nt.links.new(fr.outputs[b], g.inputs["B"])
            ns.append(g.outputs["Normal"])
        m = nt.nodes.new("ShaderNodeMix")
        m.data_type = "VECTOR"
        nt.links.new(fr.outputs["Blend"], m.inputs["Factor"])
        nt.links.new(ns[0], m.inputs[4])
        nt.links.new(ns[1], m.inputs[5])
        out["normal"] = _vm(nt, "NORMALIZE", m.outputs[1])
    if maps.get("disp"):
        hb = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(blend(*pair(maps["disp"], False)), hb.inputs[0])
        h = nt.nodes.new("ShaderNodeMath")
        h.operation, h.name = "ADD", "valora_scan_height"
        h.inputs[1].default_value = 0.0
        nt.links.new(hb.outputs[0], h.inputs[0])
        out["height"] = h.outputs[0]
    return out


def pbr(name, maps, tile_m, tint=None, rough_k=1.0, bump_k=1.0, uv_from="position", rough_min=0.0,
        specular=0.5):
    """A Principled material from Poly Haven diff / rough / nor_gl maps on metric world coordinates (pbr_sampler:
    per-face projection, world-space normals, anti-tiling). tint multiplies the colour; roughness is the map x
    rough_k, never under rough_min (a meadow must not turn to a mirror at a grazing angle). uv_from is kept for
    callers; every scan is position-projected now (no mesh relies on UVs for a tiling scan)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    smp = pbr_sampler(nt, maps, tile_m, bump_k)
    base = smp["color"]
    if tint is not None:
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(base, mul.inputs[6])
        mul.inputs[7].default_value = (*tint, 1.0)
        base = mul.outputs[2]
    nt.links.new(base, sh.inputs["Base Color"])
    sh.inputs["Specular IOR Level"].default_value = specular
    if smp["rough"] is not None:
        r = nt.nodes.new("ShaderNodeMath")
        r.operation = "MULTIPLY"
        r.inputs[1].default_value = rough_k
        nt.links.new(smp["rough"], r.inputs[0])
        lo = nt.nodes.new("ShaderNodeMath")
        lo.operation = "MAXIMUM"
        lo.inputs[1].default_value = rough_min
        nt.links.new(r.outputs[0], lo.inputs[0])
        nt.links.new(lo.outputs[0], sh.inputs["Roughness"])
    if smp["normal"] is not None:
        nt.links.new(smp["normal"], sh.inputs["Normal"])
    return m


# ------------------------------------------------------------------------------------ glTF protos
def _import(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return sorted(set(bpy.data.objects) - before, key=lambda o: o.name)


def _islands(n, loop_v, poly_start, poly_size):
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for s, k in zip(poly_start, poly_size):
        r = find(loop_v[s])
        for v in loop_v[s + 1:s + k]:
            q = find(v)
            if q != r:
                parent[q] = r
    return np.array([find(i) for i in range(n)])


def mesh_arrays(me, mw=None):
    """(co (N,3), loop vertex (L,), poly loop_start (P,), poly size (P,), uv (L,2) or None, poly material (P,))."""
    n, L, P = len(me.vertices), len(me.loops), len(me.polygons)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    if mw is not None:
        m = np.array(mw, np.float32)
        co = co @ m[:3, :3].T + m[:3, 3]
    lv = np.empty(L, np.int64)
    me.loops.foreach_get("vertex_index", lv)
    ps, pz, pm = np.empty(P, np.int64), np.empty(P, np.int64), np.empty(P, np.int64)
    me.polygons.foreach_get("loop_start", ps)
    me.polygons.foreach_get("loop_total", pz)
    me.polygons.foreach_get("material_index", pm)
    uv = None
    if me.uv_layers.active:
        uv = np.empty(L * 2, np.float32)
        me.uv_layers.active.data.foreach_get("uv", uv)
        uv = uv.reshape(L, 2)
    return co, lv, ps, pz, uv, pm


def load_protos(path, keep=None, target_verts=None):
    """Mesh prototypes from a glTF (tufts, plants): each root-centred on XY at z = 0 with its sway arrays.
    keep: substrings a mesh name must contain (None: every mesh). A proto over target_verts vertices is
    collapsed to about that many first (the foliage probe walks every edge; millions would stall it)."""
    new = _import(path)
    protos = []
    for o in new:
        if o.type != "MESH" or (keep and not any(k in o.name for k in keep)):
            continue
        if target_verts and len(o.data.vertices) > target_verts:
            mod = o.modifiers.new("dec", "DECIMATE")
            mod.ratio = target_verts / len(o.data.vertices)
            deps = bpy.context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(o.evaluated_get(deps))
        else:
            me = o.data
        co, lv, ps, pz, uv, pm = mesh_arrays(me, o.matrix_world)
        lo, hi = co.min(0), co.max(0)
        co = co - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]], np.float32)
        isl = _islands(len(co), lv, ps, pz)
        zlo, zhi = {}, {}
        for i, z in zip(isl, co[:, 2]):
            zlo[i] = min(zlo.get(i, z), z)
            zhi[i] = max(zhi.get(i, z), z)
        base = np.array([zlo[i] for i in isl], np.float32)
        top = np.array([zhi[i] for i in isl], np.float32)
        ln = np.maximum(top - base, 1e-6)
        protos.append({"name": o.name, "co": co, "lv": lv, "ps": ps, "pz": pz, "uv": uv, "pm": pm,
                       "u": (co[:, 2] - base) / ln, "len": ln, "h": float(max(1e-3, hi[2] - lo[2])),
                       "r": float(max(hi[0] - lo[0], hi[1] - lo[1]) / 2),
                       "mats": list(o.data.materials)})
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    return protos


def build_mesh(scene, name, co, lv, ps, uv=None, pm=None, mats=()):
    """A mesh from flat arrays (fast path for millions of vertices)."""
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", np.ascontiguousarray(co, np.float32).ravel())
    me.loops.add(len(lv))
    me.loops.foreach_set("vertex_index", np.ascontiguousarray(lv, np.int32))
    me.polygons.add(len(ps))
    me.polygons.foreach_set("loop_start", np.ascontiguousarray(ps, np.int32))
    if pm is not None:
        me.polygons.foreach_set("material_index", np.ascontiguousarray(pm, np.int32))
    for m in mats:
        me.materials.append(m)
    me.update(calc_edges=True)
    if uv is not None:
        layer = me.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", np.ascontiguousarray(uv, np.float32).ravel())
    me.validate(clean_customdata=False)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def scatter(protos, sites):
    """Joined arrays for protos placed at sites = [(x, y, yaw_deg, scale, proto_index, tint)], with each
    proto's material slots offset so all protos share one material list. Returns a dict of arrays."""
    slot0, off = [], 0
    for p in protos:
        slot0.append(off)
        off += max(1, len(p["mats"]))
    parts = {k: [] for k in ("co", "lv", "ps", "uv", "pm", "u", "len", "tint")}
    nv = nl = 0
    by = {}
    for s in sites:
        by.setdefault(int(s[4]), []).append(s)
    for pi, group in sorted(by.items()):
        p = protos[pi]
        g = np.asarray([s[:4] + (s[5],) for s in group], np.float32)          # x y yaw scale tint
        a = np.radians(g[:, 2])
        ca, sa, sc = np.cos(a)[:, None], np.sin(a)[:, None], g[:, 3][:, None]
        vx, vy, vz = p["co"][None, :, 0], p["co"][None, :, 1], p["co"][None, :, 2]
        px, py, pz = sc * (vx * ca - vy * sa), sc * (vx * sa + vy * ca), sc * vz
        if len(group[0]) > 7:                          # round 12: (tilt_deg, toward_deg) lays the plant over,
            t = np.asarray([s[6] for s in group], np.float32)[:, None]            # rotating it about its root
            w = np.radians(np.asarray([s[7] for s in group], np.float32))[:, None]
            ct, st, dx, dy = np.cos(np.radians(t)), np.sin(np.radians(t)), np.cos(w), np.sin(w)
            # a rotation for the upright parts (a vertical stem keeps its length) as a height-proportional shear
            # with a uniform drop: every vertex keeps its height order, so each island's root stays its lowest point
            px, py, pz = px + pz * st * dx, py + pz * st * dy, pz * ct
        co = np.stack([g[:, 0:1] + px, g[:, 1:2] + py, pz - 0.004], -1).reshape(-1, 3)
        S, N, L, P = len(g), len(p["co"]), len(p["lv"]), len(p["ps"])
        vbase = nv + np.arange(S)[:, None] * N
        lbase = nl + np.arange(S)[:, None] * L
        parts["co"].append(co)
        parts["lv"].append((p["lv"][None] + vbase).ravel())
        parts["ps"].append((p["ps"][None] + lbase).ravel())
        parts["uv"].append(np.tile(p["uv"] if p["uv"] is not None else np.zeros((L, 2), np.float32), (S, 1)))
        parts["pm"].append(np.tile(p["pm"] + slot0[pi], S))
        parts["u"].append(np.tile(p["u"], S))
        parts["len"].append((p["len"][None] * sc).ravel())
        parts["tint"].append(np.repeat(g[:, 4], N))
        nv += S * N
        nl += S * L
    if not nv:
        return None
    out = {k: np.concatenate(v) for k, v in parts.items()}
    out["mats"] = [m for p in protos for m in (p["mats"] or [None])]
    return out


GREEN_LIFE = (0.8, 1.2, 0.62)    # (eng, round 11) a live tuft's colour x this: olive scan -> living green


def tinted_foliage(src, name, dry_path=None, dry_rgb=(0.62, 0.48, 0.24), tip_rgb=None, value_jitter=0.35,
                   per_object=None, translucency=0.0, split=None):
    """A copy of a glTF plant material whose base colour varies per tuft (TINT_ATTR): mixed toward the dry
    texture (or a straw colour), lightened toward the tip (valora_sway) and jittered in value."""
    m = src.copy() if src is not None else bpy.data.materials.new(name)
    m.name = name
    m.use_nodes = True
    nt = m.node_tree
    sh = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if sh is None:
        return m
    link = next((l for l in nt.links if l.to_socket == sh.inputs["Base Color"]), None)
    if link is not None:
        base, tex_node = link.from_socket, link.from_node
    else:
        base, tex_node = None, None
    if per_object is None:
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = TINT_ATTR
        tint_out = attr.outputs["Fac"]
    else:                                                     # instances: a random per instance round the mean
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = max(0.0, per_object - 0.35)
        mr.inputs["To Max"].default_value = min(1.0, per_object + 0.35)
        nt.links.new(oi.outputs["Random"], mr.inputs["Value"])
        tint_out = mr.outputs["Result"]
    if split is not None:                                     # round 11: mostly green or mostly straw per tuft
        sp = nt.nodes.new("ShaderNodeMapRange")
        sp.interpolation_type = "SMOOTHSTEP"
        sp.inputs["From Min"].default_value, sp.inputs["From Max"].default_value = split
        nt.links.new(tint_out, sp.inputs["Value"])
        tint_mix = sp.outputs["Result"]
    else:
        tint_mix = tint_out
    sway = nt.nodes.new("ShaderNodeAttribute")
    sway.attribute_name = "valora_sway"
    if dry_path is not None and tex_node is not None and tex_node.type == "TEX_IMAGE":
        dry = nt.nodes.new("ShaderNodeTexImage")
        dry.image = bpy.data.images.load(str(dry_path), check_existing=True)
        vin = tex_node.inputs["Vector"].links[0].from_socket if tex_node.inputs["Vector"].links else None
        if vin is not None:
            nt.links.new(vin, dry.inputs["Vector"])
        dry_col = dry.outputs["Color"]
    else:
        straw = nt.nodes.new("ShaderNodeMix")
        straw.data_type, straw.blend_type = "RGBA", "MULTIPLY"
        straw.inputs["Factor"].default_value = 1.0
        if base is not None:
            nt.links.new(base, straw.inputs[6])
        else:
            straw.inputs[6].default_value = (0.3, 0.3, 0.3, 1.0)
        straw.inputs[7].default_value = (dry_rgb[0] * 2.4, dry_rgb[1] * 2.4, dry_rgb[2] * 2.4, 1.0)
        dry_col = straw.outputs[2]
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(tint_mix, mix.inputs["Factor"])
    if base is not None:
        nt.links.new(base, mix.inputs[6])
    nt.links.new(dry_col, mix.inputs[7])
    col = mix.outputs[2]
    if split is not None:                                     # round 11: a green tuft is green, not olive
        live = nt.nodes.new("ShaderNodeMix")
        live.data_type, live.blend_type = "RGBA", "MULTIPLY"
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        nt.links.new(tint_mix, inv.inputs[1])
        nt.links.new(inv.outputs[0], live.inputs["Factor"])
        nt.links.new(col, live.inputs[6])
        live.inputs[7].default_value = (*GREEN_LIFE, 1.0)
        col = live.outputs[2]
    if tip_rgb is not None:                                   # dry, sun-bleached tips
        tip = nt.nodes.new("ShaderNodeMix")
        tip.data_type, tip.blend_type = "RGBA", "MIX"
        pw = nt.nodes.new("ShaderNodeMath")
        pw.operation = "POWER"
        pw.inputs[1].default_value = 2.0
        nt.links.new(sway.outputs["Fac"], pw.inputs[0])
        k = nt.nodes.new("ShaderNodeMath")
        k.operation = "MULTIPLY"
        k.inputs[1].default_value = 0.55
        nt.links.new(pw.outputs[0], k.inputs[0])
        tip_k = k.outputs[0]
        if split is not None:                                 # only a dry tuft bleaches at its tips
            kd = nt.nodes.new("ShaderNodeMath")
            kd.operation = "MULTIPLY"
            nt.links.new(tip_k, kd.inputs[0])
            nt.links.new(tint_mix, kd.inputs[1])
            tip_k = kd.outputs[0]
        nt.links.new(tip_k, tip.inputs["Factor"])
        nt.links.new(col, tip.inputs[6])
        tip.inputs[7].default_value = (*tip_rgb, 1.0)
        col = tip.outputs[2]
    fr = nt.nodes.new("ShaderNodeMath")                     # value jitter from the tint's fractional hash
    fr.operation = "MULTIPLY"
    fr.inputs[1].default_value = 37.17
    nt.links.new(tint_out, fr.inputs[0])
    fr2 = nt.nodes.new("ShaderNodeMath")
    fr2.operation = "FRACT"
    nt.links.new(fr.outputs[0], fr2.inputs[0])
    val = nt.nodes.new("ShaderNodeMapRange")
    val.inputs["To Min"].default_value = 1.0 - value_jitter
    val.inputs["To Max"].default_value = 1.0 + value_jitter * 0.4
    nt.links.new(fr2.outputs[0], val.inputs["Value"])
    bright = nt.nodes.new("ShaderNodeMix")
    bright.data_type, bright.blend_type = "RGBA", "MULTIPLY"
    bright.inputs["Factor"].default_value = 1.0
    nt.links.new(col, bright.inputs[6])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    for ax in ("X", "Y", "Z"):
        nt.links.new(val.outputs["Result"], comb.inputs[ax])
    nt.links.new(comb.outputs[0], bright.inputs[7])
    nt.links.new(bright.outputs[2], sh.inputs["Base Color"])
    if translucency > 0:                                      # thin blades glow when the sun is behind them
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        link = next(l for l in nt.links if l.to_node == out and l.to_socket.name == "Surface")
        tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
        nt.links.new(bright.outputs[2], tr.inputs["Color"])
        mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = translucency
        nt.links.new(link.from_socket, mx.inputs[1])
        nt.links.new(tr.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m


def shared_mesh(path, keep=None):
    """One glTF's meshes joined into a single mesh datablock (world transforms applied), z from 0, centred on
    XY; for rigid instances (trees, lamps) that all share it. keep(name) -> bool picks one variant of a file
    that lays several side by side (a clean and a rusted bin). Returns (mesh, height) or (None, 0)."""
    new = _import(path)
    names = [o.name for o in new]                           # a joined object is freed: remember names
    meshes = [o for o in new if o.type == "MESH" and (keep is None or keep(o.name))]
    if not meshes:
        for o in new:
            bpy.data.objects.remove(o, do_unlink=True)
        return None, 0.0
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=meshes[0], selected_editable_objects=meshes,
                                       selected_objects=meshes):
            bpy.ops.object.join()
    src = meshes[0]
    me = src.data.copy()
    me.transform(src.matrix_world)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(0), co.max(0)
    from mathutils import Matrix
    me.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    for n in names:
        if n in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
    return me, float(hi[2] - lo[2])


# ------------------------------------------------------------------------------ instanced far foliage
def proto_objects(scene, name, protos, mats):
    """One mesh object per proto (with its valora_sway attribute, so tip colouring still works), in a
    collection excluded from the view layer: the source for Collection Info instancing."""
    from engine.blender.realism_rig import SWAY, write_attr
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    for i, p in enumerate(protos):
        ob = build_mesh(scene, f"{name}_{i}", p["co"], p["lv"], p["ps"], p["uv"], None, [mats[i]])
        scene.collection.objects.unlink(ob)
        col.objects.link(ob)
        write_attr(ob, SWAY, p["u"], "FLOAT")
    for lc in bpy.context.view_layer.layer_collection.children:
        if lc.collection == col:
            lc.exclude = True
    return col


def point_instances(scene, name, col, sites, proto_h, seed):
    """Instances of the protos in `col` at sites = [(x, y, yaw_deg, height, width)], each scaled so its proto
    stands `height` tall and spreads as if `width` tall (proto_h: the protos' mean height), via Geometry Nodes
    on a vertex-only mesh. Never
    realised: tens of thousands of instances cost Cycles almost nothing. Static (no sway)."""
    co = np.asarray([(s[0], s[1], 0.0) for s in sites], np.float32).reshape(-1, 3)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", co.ravel())
    tilt = bool(sites) and len(sites[0]) > 6                 # round 12: (tilt_deg, toward_deg) lays a tuft over
    attrs = [("valora_yaw", [math.radians(s[2]) for s in sites]), ("valora_scale", [s[3] / proto_h for s in sites]),
             ("valora_width", [s[4] / proto_h for s in sites])]
    if tilt:                                                 # as X / Y rotations (small angles: order is moot)
        attrs += [("valora_tilt_x", [-math.radians(s[5]) * math.sin(math.radians(s[6])) for s in sites]),
                  ("valora_tilt_y", [math.radians(s[5]) * math.cos(math.radians(s[6])) for s in sites])]
    for attr, vals in attrs:
        a_ = me.attributes.new(attr, "FLOAT", "POINT")
        a_.data.foreach_set("value", np.asarray(vals, np.float32))
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    pts = N.new("GeometryNodeMeshToPoints")
    L.new(gi.outputs["Geometry"], pts.inputs["Mesh"])
    info = N.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = col
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    inst = N.new("GeometryNodeInstanceOnPoints")
    L.new(pts.outputs["Points"], inst.inputs["Points"])
    L.new(info.outputs[0], inst.inputs["Instance"])
    inst.inputs["Pick Instance"].default_value = True
    pick = N.new("FunctionNodeRandomValue")
    pick.data_type = "INT"
    pick.inputs["Min"].default_value = 0
    pick.inputs["Max"].default_value = max(0, len(col.objects) - 1)
    pick.inputs["Seed"].default_value = seed
    L.new(pick.outputs[2], inst.inputs["Instance Index"])
    yaw = N.new("GeometryNodeInputNamedAttribute")
    yaw.data_type = "FLOAT"
    yaw.inputs["Name"].default_value = "valora_yaw"
    rot = N.new("ShaderNodeCombineXYZ")
    L.new(yaw.outputs["Attribute"], rot.inputs["Z"])
    for ax in ("x", "y") if tilt else ():
        t = N.new("GeometryNodeInputNamedAttribute")
        t.data_type = "FLOAT"
        t.inputs["Name"].default_value = f"valora_tilt_{ax}"
        L.new(t.outputs["Attribute"], rot.inputs[ax.upper()])
    L.new(rot.outputs[0], inst.inputs["Rotation"])
    sc = N.new("GeometryNodeInputNamedAttribute")
    sc.data_type = "FLOAT"
    sc.inputs["Name"].default_value = "valora_scale"
    wd = N.new("GeometryNodeInputNamedAttribute")
    wd.data_type = "FLOAT"
    wd.inputs["Name"].default_value = "valora_width"
    s3 = N.new("ShaderNodeCombineXYZ")
    L.new(wd.outputs["Attribute"], s3.inputs["X"])
    L.new(wd.outputs["Attribute"], s3.inputs["Y"])
    L.new(sc.outputs["Attribute"], s3.inputs["Z"])
    L.new(s3.outputs[0], inst.inputs["Scale"])
    L.new(inst.outputs["Instances"], go.inputs["Geometry"])
    mod = ob.modifiers.new(name, "NODES")
    mod.node_group = ng
    return ob
