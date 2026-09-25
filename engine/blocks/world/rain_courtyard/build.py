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


def _props(bpy, ctx, lay, mats):
    """Curbs, tree beds, benches and grates at real size: one mesh per material."""
    geo = {k: ([], []) for k in ("stone", "soil", "metal", "wood")}
    for pr in lay["props"]:
        kind, yaw = pr["kind"], pr["yaw"]
        if kind == "curb":
            _box(*geo["stone"], (*pr["xy"], 0.0), pr["size"], yaw)
        elif kind == "tree_bed":
            _box(*geo["stone"], (*pr["xy"], 0.0), pr["size"], yaw)
            _box(*geo["soil"], (*pr["xy"], 0.08), (1.62, 2.32, 0.07), yaw)
        elif kind == "bench":
            for s in (-0.65, 0.65):
                _box(*geo["metal"], (*_local(pr, 0.0, s), 0.0), (0.5, 0.05, 0.46), yaw)
            for i in range(5):
                _box(*geo["wood"], (*_local(pr, -0.24 + i * 0.12, 0.0), 0.46), (0.10, 1.8, 0.035), yaw)
            for i in range(3):
                _box(*geo["wood"], (*_local(pr, 0.24, 0.0), 0.64 + i * 0.12), (0.05, 1.8, 0.09), yaw)
        elif kind == "grate":
            for i in range(30):
                _box(*geo["metal"], (*_local(pr, 0.0, -0.41 + i * 0.028), 0.0), (0.26, 0.014, 0.009), yaw)
    return [_mesh(bpy, ctx, f"valora_court_{k}", v, f, [mats[k]]) for k, (v, f) in geo.items() if v]


def _litter(bpy, ctx, lay):
    """render-studio's fallen leaves (static litter in phase 5): one pointed quad per leaf, 1 mm up."""
    mats = [_mat(bpy, f"valora_court_leaf_{i}", c, 0.46) for i, c in enumerate(LEAF_COLOURS)]
    verts, faces, idx = [], [], []
    for lf in lay["litter"]:
        a = math.radians(lf["yaw"])
        ux, uy, wx, wy = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
        (x, y), L, W = lf["xy"], lf["length"], lf["width"]
        k = len(verts)
        verts += [(x - ux * L / 2, y - uy * L / 2, 0.001), (x + wx * W / 2, y + wy * W / 2, 0.0015),
                  (x + ux * L / 2, y + uy * L / 2, 0.001), (x - wx * W / 2, y - wy * W / 2, 0.0015)]
        faces.append((k, k + 1, k + 2, k + 3))
        idx.append(lf["tint"])
    return _mesh(bpy, ctx, "valora_court_leaves", verts, faces, mats, idx) if verts else None


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


def _trees(bpy, ctx, lay, path):
    """Rigid tree instances in the beds (render-studio heights), sharing one glTF mesh; none without it."""
    trees = [p for p in lay["props"] if p["kind"] == "tree"]
    if path is None or not trees:
        return []
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in set(bpy.data.objects) - before]
    src = next((o for o in sorted(new, key=lambda o: o.name) if o.type == "MESH"), None)
    if src is None:
        return []
    me = src.data.copy()
    me.transform(src.matrix_world)
    zs = [v.co.z for v in me.vertices]
    h0, z0 = max(1e-3, max(zs) - min(zs)), min(zs)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    out = []
    for i, t in enumerate(trees):
        ob = bpy.data.objects.new(f"valora_court_tree_{i}", me)
        ctx.scene.collection.objects.link(ob)
        s = t["height"] / h0
        ob.scale = (s, s, s)
        ob.location = (t["xy"][0], t["xy"][1], -z0 * s + 0.1)
        ob.rotation_euler[2] = ctx.rng.uniform(0, math.tau)
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
    """Poly Haven asphalt_02 (colour, roughness, GL normal) on world-scale UVs, else noise asphalt; wetness
    darkens and smooths it (a damp sheen; wet_surface adds water later)."""
    import numpy as np
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    co = np.array([tuple(ob.data.vertices[li.vertex_index].co)[:2] for li in me.loops]) / TILE_M
    uv.data.foreach_set("uv", co.astype(np.float32).ravel())
    m = bpy.data.materials.new("valora_court_asphalt")
    m.use_nodes = True
    nt = m.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Specular IOR Level"].default_value = 0.5
    if all(maps.values()):
        tc = nt.nodes.new("ShaderNodeTexCoord")

        def img(path, colour):
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = bpy.data.images.load(str(path), check_existing=True)
            if not colour:
                t.image.colorspace_settings.is_data = True
            nt.links.new(tc.outputs["UV"], t.inputs["Vector"])
            return t.outputs["Color"]
        base, rough = img(maps["diff"], True), img(maps["rough"], False)
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(img(maps["nor_gl"], False), nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], sh.inputs["Normal"])
        rough_v = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(rough, rough_v.inputs[0])
        rough = rough_v.outputs[0]
    else:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 40.0 / TILE_M
        noise.inputs["Detail"].default_value = 8.0
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["UV"], noise.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.035, 0.037, 0.04, 1.0)
        ramp.color_ramp.elements[1].color = (0.11, 0.11, 0.105, 1.0)
        nt.links.new(noise.outputs["Fac"], ramp.inputs[0])
        base = ramp.outputs[0]
        rmap = nt.nodes.new("ShaderNodeMapRange")
        rmap.inputs["To Min"].default_value, rmap.inputs["To Max"].default_value = 0.55, 0.9
        nt.links.new(noise.outputs["Fac"], rmap.inputs["Value"])
        rough = rmap.outputs["Result"]
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Distance"].default_value = 0.004
        bump.inputs["Strength"].default_value = 0.4
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], sh.inputs["Normal"])
    dark = nt.nodes.new("ShaderNodeMix")
    dark.data_type, dark.blend_type = "RGBA", "MULTIPLY"
    dark.name = "valora_court_wetness_albedo"
    dark.inputs["Factor"].default_value = 1.0
    k = 1.0 - WET_DARKEN * wetness
    dark.inputs[7].default_value = (k, k, k, 1.0)
    nt.links.new(base, dark.inputs[6])
    nt.links.new(dark.outputs[2], sh.inputs["Base Color"])
    smooth = nt.nodes.new("ShaderNodeMath")
    smooth.operation = "MULTIPLY"
    smooth.name = "valora_court_wetness_rough"
    smooth.inputs[1].default_value = 1.0 - WET_ROUGH * wetness
    nt.links.new(rough, smooth.inputs[0])
    nt.links.new(smooth.outputs[0], sh.inputs["Roughness"])
    me.materials.append(m)


def build(ctx):
    import dataclasses

    import bpy
    from engine.assets import resolve
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
    hdri = resolve("cloudy_vondelpark_4k")
    maps = {k: resolve(f"asphalt_02_{k}") for k in ("diff", "rough", "nor_gl")}

    _world(bpy, ctx, hdri, tod)
    hw, hl = court["width"] / 2, court["length"] / 2
    ax, ay = (hw, hl) if court["alongAxis"] == "y" else (hl, hw)
    ground = _mesh(bpy, ctx, "valora_court_ground",
                   [(cx - ax, cy - ay, 0.0), (cx + ax, cy - ay, 0.0), (cx + ax, cy + ay, 0.0), (cx - ax, cy + ay, 0.0)],
                   [(0, 1, 2, 3)])
    _tag(ground, ground=True)
    _asphalt(bpy, ground, maps, p["wetness"])
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

    mats = {"stone": _mat(bpy, "valora_court_stone", (0.12, 0.135, 0.13), 0.48),
            "soil": _mat(bpy, "valora_court_soil", (0.018, 0.023, 0.011), 0.94),
            "metal": _mat(bpy, "valora_court_metal", (0.025, 0.033, 0.029), 0.30, 0.75),
            "wood": _mat(bpy, "valora_court_wood", (0.060, 0.039, 0.018), 0.42)}
    props = _props(bpy, ctx, lay, mats)
    leaves = _litter(bpy, ctx, lay)
    grass, root_sway = _grass(bpy, ctx, lay, resolve("grass_medium_01_1k"))
    trees = _trees(bpy, ctx, lay, resolve("tree_small_02_1k"))

    e = lay["exclusion"]
    inside = 0
    for ob in props:                                      # the prop meshes as built: none in the exclusion
        mw = ob.matrix_world
        inside += sum(1 for v in ob.data.vertices
                      if e[0] < (mw @ v.co).x < e[2] and e[1] < (mw @ v.co).y < e[3])
    ctx.scene["valora_courtyard"] = {
        "hdri": hdri is not None, "asphaltMaps": all(maps.values()), "grass": "asset" if (
            grass is not None and resolve("grass_medium_01_1k") is not None) else "procedural",
        "grassIslandRootSwayMax": float(root_sway), "trees": len(trees), "props": len(lay["props"]),
        "litter": len(lay["litter"]), "court": {k: v for k, v in court.items() if k != "alongAxis"},
        "exclusion": list(e), "propVertsInExclusion": inside, "timeOfDay": tod, "wetness": float(p["wetness"]),
        "leaves": leaves is not None}
    return ground
