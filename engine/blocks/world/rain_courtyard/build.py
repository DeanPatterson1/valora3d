"""rain_courtyard: the generalised render-studio courtyard (phase 5 Task 63).

Ported from render-studio rain_scene.build / environment / park_ground and rain_look.environment with every
car gate removed (no MANTHEY_992 materials, no drl-*/tail-light lamp keys, no wheel reflector or cabin
fill, no per-car leaf box: the layout's exclusion is the subject's bounds + margin). The upload's own
materials are never touched (spec §4.5). The layout is pure (engine/worlds/courtyard_layout.py); this file
only realises it.

Assets resolve through engine.assets (pinned CC0 Poly Haven files) and every one has a fallback, so the
world builds with the library empty: HDRI -> an overcast procedural sky; asphalt maps -> noise asphalt;
grass glTF -> procedural blades; tree glTF -> no trees. Foliage follows the realism world contract
(valora_foliage, one island per blade with valora_sway 0 at its root and valora_sway_len); the asphalt is
valora_ground. Trees stay rigid (a 5 m trunk is not a grass blade; canopy sway is later work)."""
import math

HDRI_ROT_DEG = 110.0          # render-studio's HDRI rotation
DOME_M, PARK_M = 90.0, 180.0  # background dome radius and park ground size, x the court scale
TILE_M = 3.0                  # (eng) asphalt texture tile, metres
WET_DARKEN, WET_ROUGH = 0.35, 0.7   # (eng) damp sheen at wetness 1: albedo x 0.65, roughness x 0.3
DUSK = {"strength": 0.18, "tint": (1.0, 0.72, 0.52)}   # (eng) dusk: dimmer, warmer sky
SKY_ELEVATION = {"overcast_day": 35.0, "dusk": 3.0}
GRASS_PROTOS = ("small", "mid", "tall", "tiny")        # the glTF's lighter tufts (the large ones are 5-7k verts)
BLADES_PER_TUFT, BLADE_W = 9, 0.012                     # procedural fallback: real-size blades
LEAF_COLOURS = ((0.42, 0.27, 0.030), (0.34, 0.16, 0.022), (0.20, 0.085, 0.018), (0.30, 0.24, 0.045),
                (0.105, 0.070, 0.022))                  # render-studio's wet autumn litter
# (eng) props: bevel radius per procedural piece (render-studio rain_scene.py:51 box: 0.012 curbs, 0.025 bed
# edging, 0.015 default); tree-bed frame; curb setting jitter; grate bar pitch (render-studio 0.028)
BEVEL_M = {"curb": 0.012, "bed": 0.015, "soil": 0.0, "iron": 0.003, "wood": 0.006, "slot": 0.0}
BED_BEAM_M, BED_RIM_M, BED_SOIL_M, BED_MOUND_M = 0.10, 0.14, 0.095, 0.03
CURB_JITTER_M = 0.003
GRATE_PITCH_M = 0.028
BENCH_PARTS = {"seat", "seat_back", "back_support_l", "back_support_r", "legs_single", "legs_double",
               "arm_rest_01", "crossbar", "suspended_support_01"}   # modular_street_seating_1k's backed bench
TREE_SIBLINGS = 2           # (eng) regrown tree_small_02 siblings (render-studio grew 4; each is 1.8 M verts)
TREE_MAX_SCALE = 2.0        # (eng) render-studio stood tree_small_02 (4.6 m scan) up to ~9 m: 2x
SHRUBS = ("shrub_03_a", "shrub_03_b", "shrub_03_c", "shrub_03_d")
SHRUBS_PER_BED, SHRUB_H_M = 5, (0.35, 0.7)      # (eng) understorey round each trunk
BED_LEAVES = 140            # (eng) fallen leaves on each bed's soil (~40 per m^2: it sits under its tree)


def _tag(ob, ground=False, foliage=False):
    ob["valora_block"] = "world/rain_courtyard"
    if ground:
        ob["valora_ground"] = True
    if foliage:
        ob["valora_foliage"] = True
    return ob


def _mat(bpy, name, colour, rough, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Base Color"].default_value = (*colour, 1.0)
    sh.inputs["Roughness"].default_value = rough
    sh.inputs["Metallic"].default_value = metallic
    return m


def _mesh(bpy, ctx, name, verts, faces, mats=(), mat_idx=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(m)
    if mat_idx is not None:
        me.polygons.foreach_set("material_index", mat_idx)
    ob = bpy.data.objects.new(name, me)
    ctx.scene.collection.objects.link(ob)
    return _tag(ob)


def _box(verts, faces, c, size, yaw_deg):
    """Append an axis box (centre c = (x, y, z-bottom), size (across, along, h)) rotated by yaw 0/90."""
    sx, sy, sz = size
    if yaw_deg % 180:
        sx, sy = sy, sx
    x0, x1, y0, y1, z0, z1 = c[0] - sx / 2, c[0] + sx / 2, c[1] - sy / 2, c[1] + sy / 2, c[2], c[2] + sz
    k = len(verts)
    verts += [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    faces += [(k, k + 1, k + 3, k + 2), (k + 4, k + 6, k + 7, k + 5), (k, k + 4, k + 5, k + 1),
              (k + 2, k + 3, k + 7, k + 6), (k, k + 2, k + 6, k + 4), (k + 1, k + 5, k + 7, k + 3)]


def _local(pr, a, b):
    """A point a across, b along the prop's own frame -> placed xy (the court's along axis)."""
    x, y = pr["xy"]
    return (x + a, y + b) if pr["yaw"] % 180 == 0 else (x + b, y + a)


def _props(bpy, ctx, lay, wet, lib):
    """Curbs, tree beds, benches, grates and a manhole at real size. Library models where they fit (the scanned
    modular bench and manhole cover), else bevelled procedural stand-ins; every procedural piece has soft
    manufactured edges and weighted normals (render-studio rain_scene.py:51 box) and metric PBR materials
    (engine/blender/court_props.py). One object per (material, bevel radius) plus the library instances."""
    import random
    from engine.blender import court_props as K
    from engine.blender.env_assets import shared_mesh
    rng = random.Random(ctx.seed * 7919 + 63)                  # own stream: the layout's draws are untouched
    cx, cy = lay["court"]["centre"]
    geo = {k: ([], [], []) for k in BEVEL_M}                    # verts, faces, per-vertex VAR_ATTR

    def box(key, c, size, yaw, var=None):
        v, f, a = geo[key]
        _box(v, f, c, size, yaw)
        a += [rng.random() if var is None else var] * 8

    lib_meshes, out = {}, []

    def instance(kind, i, pr, z, rot_deg):
        if kind not in lib_meshes:
            keep = BENCH_PARTS.__contains__ if kind == "bench" else None
            lib_meshes[kind] = shared_mesh(lib[kind], keep)[0] if lib.get(kind) is not None else None
        me = lib_meshes[kind]
        if me is None:
            return False
        ob = bpy.data.objects.new(f"valora_court_{kind}_{i}", me)
        ctx.scene.collection.objects.link(ob)
        ob.location = (pr["xy"][0], pr["xy"][1], z)
        ob.rotation_euler[2] = math.radians(rot_deg)
        out.append(_tag(ob))
        return True

    for i, pr in enumerate(lay["props"]):
        kind, yaw = pr["kind"], pr["yaw"]
        if kind == "curb":                                    # each stone its own height, set and shade
            sx, sy, sz = pr["size"]
            dz = rng.uniform(-CURB_JITTER_M, CURB_JITTER_M)
            box("curb", (*_local(pr, rng.uniform(-0.003, 0.003), 0.0), 0.0), (sx, sy, sz + dz), yaw)
        elif kind == "tree_bed":                              # a stone frame round soil set below its rim
            A, B, _ = pr["size"]
            w = BED_BEAM_M
            var = rng.random()
            for s in (-1, 1):
                box("bed", (*_local(pr, s * (A - w) / 2, 0.0), 0.0), (w, B, BED_RIM_M), yaw, var)
                box("bed", (*_local(pr, 0.0, s * (B - w) / 2), 0.0), (A - 2 * w, w, BED_RIM_M), yaw, var)
            _soil_grid(geo["soil"], pr, A - 2 * w, B - 2 * w, rng)
        elif kind == "bench":
            ax = 1 if lay["court"]["alongAxis"] == "y" else 0   # the across axis (x when the court runs along y)
            out_sign = 1.0 if (pr["xy"][0] - cx if ax == 1 else pr["xy"][1] - cy) >= 0 else -1.0
            rot = (-90.0 if out_sign > 0 else 90.0) if ax == 1 else (0.0 if out_sign > 0 else 180.0)
            if not instance("bench", i, pr, 0.0, rot):
                bs = out_sign                                 # procedural: legs, seat slats, a back on the outside
                for s in (-0.9, 0.9):
                    box("iron", (*_local(pr, 0.0, s), 0.0), (0.55, 0.06, 0.43), yaw)
                for k in range(5):
                    box("wood", (*_local(pr, bs * (-0.24 + k * 0.12), 0.0), 0.43), (0.10, 2.3, 0.035), yaw)
                for k in range(3):
                    box("wood", (*_local(pr, bs * 0.3, 0.0), 0.55 + k * 0.11), (0.05, 2.3, 0.08), yaw)
        elif kind == "grate":                                 # frame, bars, and dark water under them
            gx, gy, _ = pr["size"]
            for s in (-1, 1):
                box("iron", (*_local(pr, s * (gx - 0.025) / 2, 0.0), 0.0), (0.025, gy, 0.010), yaw, 0.5)
                box("iron", (*_local(pr, 0.0, s * (gy - 0.025) / 2), 0.0), (gx - 0.05, 0.025, 0.010), yaw, 0.5)
            n = int((gy - 0.05) / GRATE_PITCH_M)
            for k in range(n):
                b = -(gy - 0.05) / 2 + (k + 0.5) * GRATE_PITCH_M
                box("iron", (*_local(pr, 0.0, b), 0.0), (gx - 0.05, 0.012, 0.009), yaw, 0.5)
            box("slot", (*pr["xy"], -0.004), (gx - 0.05, gy - 0.05, 0.0045), yaw, 0.0)
        elif kind == "manhole":
            if not instance("manhole", i, pr, -0.03, rng.uniform(0.0, 360.0)):
                box("iron", (*pr["xy"], 0.0), (0.62, 0.62, 0.012), yaw)
    mats = {"curb": K.stone("valora_court_stone", wet), "soil": K.soil("valora_court_soil", lay["court"]["scale"]),
            "iron": K.iron("valora_court_metal", wet), "slot": K.wet_slot("valora_court_drain")}
    mats["bed"] = mats["curb"]
    along = "y" if lay["court"]["alongAxis"] == "y" else "x"
    for key, (v, f, a) in geo.items():
        if not v:
            continue
        if key == "wood":
            mats["wood"] = K.wood("valora_court_wood", wet, along)
        ob = _mesh(bpy, ctx, f"valora_court_{key}", v, f, [mats[key]])
        K.write_var(ob, a)
        if key != "soil":
            K.finish_edges(ob, BEVEL_M[key])
        else:
            ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
        out.append(ob)
    return out


def _soil_z(pr, u, w):
    """Soil height at (u across, w along) of a tree bed: set BED_SOIL_M up, mounded toward the trunk."""
    A, B = pr["size"][0] - 2 * BED_BEAM_M, pr["size"][1] - 2 * BED_BEAM_M
    r = math.hypot(u / (A / 2), w / (B / 2))
    return BED_SOIL_M + BED_MOUND_M * max(0.0, 1.0 - r * r)


def _soil_grid(g, pr, A, B, rng):
    """The bed's soil: a grid inside the rim at _soil_z with a few millimetres of crumb relief."""
    v, f, a = g
    nx, ny = 10, 14
    k0 = len(v)
    for i in range(nx + 1):
        for j in range(ny + 1):
            u, w = (i / nx - 0.5) * A, (j / ny - 0.5) * B
            v.append((*_local(pr, u, w), _soil_z(pr, u, w) + rng.uniform(-0.004, 0.004)))
            a.append(0.5)
    for i in range(nx):
        for j in range(ny):
            q = k0 + i * (ny + 1) + j
            f.append((q, q + ny + 1, q + ny + 2, q + 1))


def _litter(bpy, ctx, lay, wet):
    """render-studio's fallen leaves (rain_scene.py:337 LEAF_PROFILE, :340 leaf_mesh, ported pure as
    engine/worlds/leaf_geometry): folded, curled, twisted ovate leaves resting on the court (or on a curb
    stone's top), wet-shaded with per-leaf colour (court_props.leaf_mats)."""
    import random
    from engine.blender import court_props as K
    from engine.worlds.courtyard_layout import footprint
    from engine.worlds.leaf_geometry import leaf, shape
    rng = random.Random(ctx.seed * 104729 + 18)
    curbs = [(footprint(p), p["size"][2]) for p in lay["props"] if p["kind"] == "curb"]
    verts, faces, idx, var = [], [], [], []
    for lf in lay["litter"]:
        fold, curl, twist = shape(rng)
        x, y = lf["xy"]
        z0 = next((h for r, h in curbs if r[0] < x < r[2] and r[1] < y < r[3]), 0.0)
        v, q = leaf(lf["xy"], lf["yaw"], lf["width"], lf["length"], fold, curl, twist, z0)
        k = len(verts)
        verts += v
        faces += [tuple(k + i for i in f) for f in q]
        idx += [lf["tint"]] * len(q)
        var += [rng.random()] * len(v)
    for bed in (p for p in lay["props"] if p["kind"] == "tree_bed"):     # the trees' own leaf fall on the soil
        A, B = bed["size"][0] - 2 * BED_BEAM_M, bed["size"][1] - 2 * BED_BEAM_M
        for _ in range(BED_LEAVES):
            u, w = rng.uniform(-0.48, 0.48) * A, rng.uniform(-0.48, 0.48) * B
            fold, curl, twist = shape(rng)
            v, q = leaf(_local(bed, u, w), rng.uniform(0, 360.0), rng.uniform(0.016, 0.034),
                        rng.uniform(0.055, 0.105), fold, curl, twist, _soil_z(bed, u, w) + 0.004)
            k = len(verts)
            verts += v
            faces += [tuple(k + i for i in f) for f in q]
            idx += [rng.randrange(len(LEAF_COLOURS))] * len(q)
            var += [rng.random()] * len(v)
    if not verts:
        return None
    ob = _mesh(bpy, ctx, "valora_court_leaves", verts, faces, K.leaf_mats(LEAF_COLOURS, wet), idx)
    ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
    K.write_var(ob, var)
    return ob


def _islands(n_verts, faces):
    """Island id per vertex (union-find over face corners)."""
    parent = list(range(n_verts))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for f in faces:
        r = find(f[0])
        for v in f[1:]:
            q = find(v)
            if q != r:
                parent[q] = r
    return [find(i) for i in range(n_verts)]


def _sway(verts, faces):
    """valora_sway (0 at each island's lowest point .. 1 at its tip) and valora_sway_len (metres)."""
    isl = _islands(len(verts), faces)
    lo, hi = {}, {}
    for i, v in zip(isl, verts):
        lo[i] = min(lo.get(i, v[2]), v[2])
        hi[i] = max(hi.get(i, v[2]), v[2])
    u = [(v[2] - lo[i]) / max(1e-6, hi[i] - lo[i]) for i, v in zip(isl, verts)]
    ln = [hi[i] - lo[i] for i in isl]
    return isl, u, ln


def _grass_protos(bpy, path):
    """Mesh data (verts, faces, uvs, material) of the glTF's lighter tufts, root at the origin."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in set(bpy.data.objects) - before]
    protos = []
    for o in sorted(new, key=lambda o: o.name):
        if o.type != "MESH" or not any(k in o.name for k in GRASS_PROTOS):
            continue
        mw = o.matrix_world
        vs = [tuple(mw @ v.co) for v in o.data.vertices]
        lx, ly, lz = (min(v[i] for v in vs) for i in range(3))
        hx, hy, hz = (max(v[i] for v in vs) for i in range(3))
        cx, cy = (lx + hx) / 2, (ly + hy) / 2
        vs = [(v[0] - cx, v[1] - cy, v[2] - lz) for v in vs]
        faces = [tuple(p.vertices) for p in o.data.polygons]
        uv = o.data.uv_layers.active
        uvs = [tuple(d.uv) for d in uv.data] if uv else None
        protos.append({"verts": vs, "faces": faces, "uvs": uvs, "h": max(1e-3, hz - lz),
                       "mat": o.data.materials[0] if o.data.materials else None})
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    return protos


def _grass(bpy, ctx, lay, path):
    """One joined foliage mesh: glTF tufts when the asset resolves, else procedural blades."""
    import numpy as np
    from engine.blender.realism_rig import SWAY, SWAY_LEN, write_attr
    protos = _grass_protos(bpy, path) if path is not None else []
    verts, faces, uvs, mat = [], [], [], None
    for t in lay["grass"]:
        a = math.radians(t["yaw"])
        ca, sa = math.cos(a), math.sin(a)
        x, y = t["xy"]
        k = len(verts)
        if protos:
            pr = protos[int(t["pick"] * len(protos)) % len(protos)]
            s = t["height"] / pr["h"]
            verts += [(x + s * (vx * ca - vy * sa), y + s * (vx * sa + vy * ca), s * vz - 0.004)
                      for vx, vy, vz in pr["verts"]]
            faces += [tuple(k + i for i in f) for f in pr["faces"]]
            uvs += pr["uvs"] or [(0.0, 0.0)] * sum(len(f) for f in pr["faces"])
            mat = mat or pr["mat"]
        else:
            for b in range(BLADES_PER_TUFT):
                ang = a + b * 2.39996                        # golden-angle spread round the tuft
                r = 0.03 * math.sqrt((b + 0.5) / BLADES_PER_TUFT)
                bx, by = x + r * math.cos(ang), y + r * math.sin(ang)
                h = t["height"] * (0.7 + 0.3 * ((b * 7919) % 11) / 10.0)
                ox, oy = -math.sin(ang) * BLADE_W / 2, math.cos(ang) * BLADE_W / 2
                q = len(verts)
                verts += [(bx - ox, by - oy, 0.0), (bx + ox, by + oy, 0.0),
                          (bx + 0.25 * h * math.cos(ang), by + 0.25 * h * math.sin(ang), h)]
                faces.append((q, q + 1, q + 2))
    if not verts:
        return None, 0.0
    if mat is None:
        mat = _mat(bpy, "valora_court_grass", (0.05, 0.09, 0.025), 0.6)
    ob = _mesh(bpy, ctx, "valora_court_grass", verts, faces, [mat])
    if protos and len(uvs) == len(ob.data.loops):
        layer = ob.data.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", np.asarray(uvs, np.float32).ravel())
    _tag(ob, foliage=True)
    isl, u, ln = _sway(verts, faces)
    write_attr(ob, SWAY, np.asarray(u), "FLOAT")
    write_attr(ob, SWAY_LEN, np.asarray(ln), "FLOAT")
    lowest = {}
    for i, (v, w) in enumerate(zip(verts, u)):     # contract check: sway at each island's lowest point
        if isl[i] not in lowest or v[2] < lowest[isl[i]][0]:
            lowest[isl[i]] = (v[2], w)
    return ob, max(w for _, w in lowest.values())


def _tree_pool(ctx, lib):
    """Distinct silhouettes: tree_small_02 plus render-studio's regrown siblings of it (scene_plants.py:42
    shape_variants, ported as court_props.tree_siblings), island_tree_01 and island_tree_02: [(mesh, height)]."""
    from engine.blender import court_props as K
    from engine.blender.env_assets import shared_mesh
    pool = []
    for key in ("tree", "island_01", "island_02"):
        if lib.get(key) is None:
            continue
        me, h = shared_mesh(lib[key])
        if me is None:
            continue
        K.tune_foliage(me)
        pool += K.tree_siblings(me, h, TREE_SIBLINGS, ctx.seed + 20260919) if key == "tree" else [(me, h)]
    return pool


def _trees(bpy, ctx, lay, lib):
    """Rigid trees in the beds from a pool of silhouettes dealt so neighbours differ (render-studio
    scene_plants.py:118 plant_tree), each at the layout's height capped at TREE_MAX_SCALE x its scan (no leaf
    blown up to a dinner plate) with its own yaw; shrub_03 plants round every trunk on the bed's soil. None
    without the library."""
    import random
    from engine.blender import court_props as K
    from engine.blender.env_assets import shared_mesh
    trees = [p for p in lay["props"] if p["kind"] == "tree"]
    beds = {tuple(p["xy"]): p for p in lay["props"] if p["kind"] == "tree_bed"}
    pool = _tree_pool(ctx, lib) if trees else []
    out = []
    if not pool:
        return out
    for i, (t, pick) in enumerate(zip(trees, K.deal(len(trees), len(pool)))):
        me, h0 = pool[pick]
        ob = bpy.data.objects.new(f"valora_court_tree_{i}", me)
        ctx.scene.collection.objects.link(ob)
        s = min(TREE_MAX_SCALE, t["height"] / h0)
        ob.scale = (s, s, s)
        bed = beds.get(tuple(t["xy"]))
        ob.location = (t["xy"][0], t["xy"][1], (_soil_z(bed, 0.0, 0.0) if bed else 0.1) - 0.02)
        ob.rotation_euler[2] = ctx.rng.uniform(0, math.tau)
        out.append(_tag(ob))
    shrubs = []
    if lib.get("shrub") is not None:
        for name in SHRUBS:
            me, h = shared_mesh(lib["shrub"], lambda n, name=name: n == name)
            if me is not None:
                shrubs.append((me, h))
    rng = random.Random(ctx.seed * 131 + 5)
    for j, bed in enumerate(beds.values()):
        if not shrubs:
            break
        A, B = bed["size"][0] - 2 * BED_BEAM_M, bed["size"][1] - 2 * BED_BEAM_M
        for k in range(SHRUBS_PER_BED):
            ang = (k + rng.uniform(-0.3, 0.3)) * math.tau / SHRUBS_PER_BED
            r = rng.uniform(0.45, 0.8)
            u, w = 0.5 * A * r * math.cos(ang), 0.5 * B * r * math.sin(ang)
            me, h = shrubs[rng.randrange(len(shrubs))]
            ob = bpy.data.objects.new(f"valora_court_shrub_{j}_{k}", me)
            ctx.scene.collection.objects.link(ob)
            s = rng.uniform(*SHRUB_H_M) / h
            ob.scale = (s, s, s)
            ob.location = (*_local(bed, u, w), _soil_z(bed, u, w) - 0.01)
            ob.rotation_euler[2] = rng.uniform(0, math.tau)
            out.append(_tag(ob))
    return out


def _sky(nt, vector, hdri, tod):
    """Background colour for a direction: the pinned HDRI (rotated as render-studio did), else an overcast
    procedural sky mixed toward grey. Dusk dims and warms either one."""
    if hdri is not None:
        import bpy
        tex = nt.nodes.new("ShaderNodeTexEnvironment")
        tex.image = bpy.data.images.load(str(hdri), check_existing=True)
        rot = nt.nodes.new("ShaderNodeMapping")
        rot.inputs["Rotation"].default_value[2] = math.radians(HDRI_ROT_DEG)
        nt.links.new(vector, rot.inputs["Vector"])
        nt.links.new(rot.outputs["Vector"], tex.inputs["Vector"])
        colour = tex.outputs["Color"]
    else:
        sky = nt.nodes.new("ShaderNodeTexSky")
        kinds = [i.identifier for i in sky.bl_rna.properties["sky_type"].enum_items]
        for want in ("NISHITA", "MULTIPLE_SCATTERING", "SINGLE_SCATTERING"):
            if want in kinds:
                sky.sky_type = want
                break
        for attr, val in (("sun_disc", False), ("sun_elevation", math.radians(SKY_ELEVATION[tod])),
                          ("air_density", 2.0), ("dust_density", 6.0), ("aerosol_density", 6.0)):
            if hasattr(sky, attr):
                try:
                    setattr(sky, attr, val)
                except (TypeError, ValueError):
                    pass
        nt.links.new(vector, sky.inputs["Vector"])
        grey = nt.nodes.new("ShaderNodeMix")
        grey.data_type = "RGBA"
        grey.inputs["Factor"].default_value = 0.55            # overcast: most of the sky is cloud grey
        nt.links.new(sky.outputs["Color"], grey.inputs[6])
        grey.inputs[7].default_value = (0.42, 0.44, 0.46, 1.0)
        colour = grey.outputs[2]
    if tod == "dusk":
        tint = nt.nodes.new("ShaderNodeMix")
        tint.data_type, tint.blend_type = "RGBA", "MULTIPLY"
        tint.inputs["Factor"].default_value = 1.0
        nt.links.new(colour, tint.inputs[6])
        tint.inputs[7].default_value = (*DUSK["tint"], 1.0)
        colour = tint.outputs[2]
    return colour


def _world(bpy, ctx, hdri, tod):
    w = bpy.data.worlds.new("valora_courtyard_sky")
    w.use_nodes = True
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(_sky(nt, tc.outputs["Generated"], hdri, tod), bg.inputs["Color"])
    bg.inputs["Strength"].default_value = DUSK["strength"] if tod == "dusk" else 1.0
    ctx.scene.world = w


def _emissive(bpy, name, centre, hdri, tod, lift=0.0):
    """Camera-only background material: the sky seen from `centre` (+ lift) through each surface point."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out, em = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeEmission")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = (centre[0], centre[1], lift)
    nt.links.new(geo.outputs["Position"], sub.inputs[0])
    nt.links.new(_sky(nt, sub.outputs["Vector"], hdri, tod), em.inputs["Color"])
    em.inputs["Strength"].default_value = DUSK["strength"] if tod == "dusk" else 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def _asphalt(bpy, ob, maps, wetness):
    """Poly Haven asphalt_02 or noise asphalt with a damp sheen (engine/blender/set_parts.asphalt)."""
    from engine.blender.set_parts import asphalt
    return asphalt(ob, maps, wetness, "valora_court_asphalt", "valora_court", TILE_M, WET_DARKEN, WET_ROUGH)


def build(ctx):
    import dataclasses

    import bpy
    from engine.assets import resolve, resolve_gltf
    from engine.worlds.courtyard_layout import layout
    p, prof = ctx.params, ctx.profile
    m = ctx.catalog.get("world", "rain_courtyard")
    hero = ctx.hero_pose
    if hero is not None and ctx.camera_lenses_mm:
        hero = dataclasses.replace(hero, lens_mm=min(ctx.camera_lenses_mm))       # the widest lens the clip uses
    lay = layout(prof, ctx.seed, p["dressing"], m["driveLaneM"], hero=hero, aspect=ctx.script["format"]["aspect"])
    court = lay["court"]
    cx, cy = court["centre"]
    s, tod = court["scale"], p["timeOfDay"]
    from engine.physics.wet import world_wetness
    from engine.world_assets import courtyard_hdri
    tier = str(ctx.scene.get("valora_tier", "preview"))
    hdri = resolve(courtyard_hdri(tier)) or resolve(courtyard_hdri("preview"))   # 8k at final (required there)
    maps = {k: resolve(f"asphalt_02_{k}") for k in ("diff", "rough", "nor_gl", "disp")}
    ground_wet = world_wetness(p["wetness"], [e["id"] for e in ctx.script.get("effects", [])])   # one owner (#15)

    _world(bpy, ctx, hdri, tod)
    hw, hl = court["width"] / 2, court["length"] / 2
    ax, ay = (hw, hl) if court["alongAxis"] == "y" else (hl, hw)
    ground = _mesh(bpy, ctx, "valora_court_ground",
                   [(cx - ax, cy - ay, 0.0), (cx + ax, cy - ay, 0.0), (cx + ax, cy + ay, 0.0), (cx - ax, cy + ay, 0.0)],
                   [(0, 1, 2, 3)])
    _tag(ground, ground=True)
    _asphalt(bpy, ground, maps, ground_wet)
    half = PARK_M * s / 2
    park = _mesh(bpy, ctx, "valora_court_park",
                 [(cx - half, cy - half, -0.02), (cx + half, cy - half, -0.02), (cx + half, cy + half, -0.02),
                  (cx - half, cy + half, -0.02)], [(0, 1, 2, 3)],
                 [_emissive(bpy, "valora_court_park", (cx, cy), hdri, tod, lift=1.6 * s) if hdri is not None
                  else _mat(bpy, "valora_court_park", (0.045, 0.055, 0.035), 0.9)])
    park.visible_diffuse = False
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=DOME_M * s, location=(cx, cy, 0.0))
    dome = _tag(bpy.context.object)
    dome.name = "valora_court_dome"
    dome.visible_shadow = dome.visible_diffuse = dome.visible_glossy = dome.visible_transmission = False
    dome.data.materials.append(_emissive(bpy, "valora_court_dome", (cx, cy), hdri, tod))

    wet = float(p["wetness"])
    props = _props(bpy, ctx, lay, wet, {"bench": resolve_gltf("modular_street_seating_1k"),
                                        "manhole": resolve_gltf("water_manhole_cover_1k")})
    leaves = _litter(bpy, ctx, lay, wet)
    grass_path = resolve_gltf("grass_medium_01_1k")        # the glTF AND its .bin/textures, all pinned
    grass, root_sway = _grass(bpy, ctx, lay, grass_path)
    trees = _trees(bpy, ctx, lay, {"tree": resolve_gltf("tree_small_02_1k"),
                                   "island_01": resolve_gltf("island_tree_01_1k"),
                                   "island_02": resolve_gltf("island_tree_02_1k"),
                                   "shrub": resolve_gltf("shrub_03_1k")})

    e = lay["exclusion"]
    inside = 0
    for ob in props:                                      # the prop meshes as built: none in the exclusion
        mw = ob.matrix_world
        inside += sum(1 for v in ob.data.vertices
                      if e[0] < (mw @ v.co).x < e[2] and e[1] < (mw @ v.co).y < e[3])
    ctx.scene["valora_courtyard"] = {
        "hdri": hdri is not None, "asphaltMaps": all(maps.values()), "grass": "asset" if (
            grass is not None and grass_path is not None) else "procedural",
        "grassIslandRootSwayMax": float(root_sway), "trees": sum(1 for t in trees if "_tree_" in t.name), "props": len(lay["props"]),
        "litter": len(lay["litter"]), "court": {k: v for k, v in court.items() if k != "alongAxis"},
        "exclusion": list(e), "propVertsInExclusion": inside, "timeOfDay": tod, "wetness": float(p["wetness"]),
        "leaves": leaves is not None}
    return ground
