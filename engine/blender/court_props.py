"""rain_courtyard dressing, Blender side: manufactured-edge bevels, metric procedural PBR for stone, soil, iron and
wood, wet fallen-leaf shading, and a varied tree pool (render-studio ports; source lines cited per function).

Every material is driven by world position at real metre scales, so a curb stone and a tree-bed beam share one
concrete without stretching, and by a per-element attribute (VAR_ATTR, one random value per stone / leaf) so no
two pieces are the same colour. `wet` (0..1) scales the rain coat."""
import math

import bpy
import numpy as np

VAR_ATTR = "valora_prop_var"            # one value in [0, 1) per stone / slat / leaf


# ------------------------------------------------------------------------------ node helpers
def _principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")


def _pos(nt):
    return nt.nodes.new("ShaderNodeNewGeometry").outputs["Position"]


def _noise(nt, vec, scale, detail=3.0, rough=0.55):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    nt.links.new(vec, n.inputs["Vector"])
    return n.outputs["Fac"]


def _ramp(nt, fac, stops):
    """ColorRamp over (position, rgb) stops -> colour socket."""
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for e, (p, c) in zip(els, stops):
        e.position = p
        e.color = (*c, 1.0)
    nt.links.new(fac, r.inputs[0])
    return r.outputs[0]


def _maprange(nt, val, a0, a1, b0, b1):
    m = nt.nodes.new("ShaderNodeMapRange")
    m.clamp = True
    nt.links.new(val, m.inputs["Value"])
    for k, v in (("From Min", a0), ("From Max", a1), ("To Min", b0), ("To Max", b1)):
        m.inputs[k].default_value = v
    return m.outputs["Result"]


def _math(nt, op, a, b):
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = op
    for i, x in enumerate((a, b)):
        if isinstance(x, (int, float)):
            m.inputs[i].default_value = x
        else:
            nt.links.new(x, m.inputs[i])
    return m.outputs[0]


def _mix(nt, fac, a, b, blend="MIX"):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type, m.blend_type = "RGBA", blend
    for sock, x in ((m.inputs["Factor"], fac), (m.inputs[6], a), (m.inputs[7], b)):
        if isinstance(x, (int, float)):
            sock.default_value = x
        elif isinstance(x, tuple):
            sock.default_value = (*x, 1.0) if len(x) == 3 else x
        else:
            nt.links.new(x, sock)
    return m.outputs[2]


def _var(nt):
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = VAR_ATTR
    return a.outputs["Fac"]


def _bump(nt, sh, layers):
    """Chained bump nodes: layers = [(height socket, distance m, strength)]."""
    normal = None
    for h, dist, k in layers:
        b = nt.nodes.new("ShaderNodeBump")
        b.inputs["Distance"].default_value = dist
        b.inputs["Strength"].default_value = k
        nt.links.new(h, b.inputs["Height"])
        if normal is not None:
            nt.links.new(normal, b.inputs["Normal"])
        normal = b.outputs["Normal"]
    nt.links.new(normal, sh.inputs["Normal"])


def _coat(sh, wet, weight, rough):
    sh.inputs["Coat Weight"].default_value = weight * wet
    sh.inputs["Coat Roughness"].default_value = rough
    sh.inputs["Coat IOR"].default_value = 1.333


# ------------------------------------------------------------------------------ materials
def stone(name, wet):
    """Rain-darkened precast concrete (render-studio rain_scene.py:34 textured_stone, rebuilt at metric scale):
    cloudy cement tone, per-stone shade, grime creeping up from the wet base, pitted aggregate relief, coat."""
    m, nt, sh = _principled(name)
    p = _pos(nt)
    tone = _ramp(nt, _noise(nt, p, 2.2, 4.0), [(0.3, (0.085, 0.092, 0.088)), (0.7, (0.155, 0.160, 0.150))])
    speck = _noise(nt, p, 260.0, 2.0)
    tone = _mix(nt, _maprange(nt, speck, 0.45, 0.75, 0.0, 0.35), tone, (0.045, 0.047, 0.046))
    shade = _maprange(nt, _var(nt), 0.0, 1.0, 0.78, 1.18)
    tone = _mix(nt, 1.0, tone, _combine(nt, shade), "MULTIPLY")
    z = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(p, z.inputs[0])
    grime = _math(nt, "MULTIPLY", _maprange(nt, z.outputs["Z"], 0.0, 0.07, 1.0, 0.0),
                  _maprange(nt, _noise(nt, p, 9.0, 5.0), 0.35, 0.7, 0.35, 0.9))
    col = _mix(nt, grime, tone, (0.030, 0.034, 0.022))
    nt.links.new(col, sh.inputs["Base Color"])
    nt.links.new(_maprange(nt, _noise(nt, p, 14.0, 4.0), 0.3, 0.7, 0.52, 0.82), sh.inputs["Roughness"])
    _bump(nt, sh, [(_noise(nt, p, 5.0, 3.0), 0.004, 0.25), (_noise(nt, p, 140.0, 6.0, 0.7), 0.0012, 0.45)])
    _coat(sh, wet, 0.22, 0.18)
    return m


def _combine(nt, v):
    c = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(v, c.inputs[i])
    return c.outputs[0]


def soil(name, scale=1.0):
    """render-studio's dark earth (rain_scene.py:381-402: broken microgeometry, low specular, so a grazing view
    is not a grey mirror), plus a mulch / crumb layer at centimetre scale."""
    m, nt, sh = _principled(name)
    sh.inputs["Specular IOR Level"].default_value = 0.07
    p = _pos(nt)
    earth = _noise(nt, p, 1.5 / scale, 4.0)
    # render-studio's ramp ran olive (0.045, 0.050, 0.013): seen close in a bed it read as a green film. Wet
    # garden soil is a dark umber, lighter where the mulch crumbs dry out.
    col = _ramp(nt, earth, [(0.0, (0.012, 0.009, 0.006)), (1.0, (0.050, 0.036, 0.022))])
    crumbs = _noise(nt, p, 45.0, 6.0, 0.65)
    col = _mix(nt, _maprange(nt, crumbs, 0.52, 0.72, 0.0, 0.7), col, (0.070, 0.050, 0.030))
    nt.links.new(col, sh.inputs["Base Color"])
    nt.links.new(_maprange(nt, crumbs, 0.3, 0.7, 0.98, 0.82), sh.inputs["Roughness"])
    clods = _noise(nt, p, 14.0, 4.0, 0.6)
    _bump(nt, sh, [(earth, 0.06 * scale, 0.65), (clods, 0.012, 0.9), (crumbs, 0.006, 1.0)])
    return m


def iron(name, wet):
    """Cast iron street metal: graphite with worn bright edges replaced by rust bloom in patches and a wet coat
    (render-studio's flat 'graphite furniture' 0.025/0.30/0.75 as the base)."""
    m, nt, sh = _principled(name)
    p = _pos(nt)
    rust = _maprange(nt, _noise(nt, p, 7.0, 6.0, 0.6), 0.52, 0.68, 0.0, 1.0)
    col = _mix(nt, rust, (0.025, 0.030, 0.028), (0.085, 0.040, 0.018))
    nt.links.new(col, sh.inputs["Base Color"])
    nt.links.new(_maprange(nt, rust, 0.0, 1.0, 0.75, 0.0), sh.inputs["Metallic"])
    nt.links.new(_maprange(nt, _math(nt, "ADD", rust, _math(nt, "MULTIPLY", _noise(nt, p, 60.0, 4.0), 0.4)),
                           0.0, 1.4, 0.32, 0.85), sh.inputs["Roughness"])
    _bump(nt, sh, [(_noise(nt, p, 90.0, 5.0), 0.0008, 0.35)])
    _coat(sh, wet, 0.35, 0.12)
    return m


def wood(name, wet, along="y"):
    """Weathered hardwood slats (fallback bench): grain streaks along the slat (world `along` axis), per-slat
    shade."""
    m, nt, sh = _principled(name)
    p = _pos(nt)
    grain_vec = nt.nodes.new("ShaderNodeMapping")
    grain_vec.inputs["Scale"].default_value = (3.0, 60.0, 60.0) if along == "x" else (60.0, 3.0, 60.0)
    nt.links.new(p, grain_vec.inputs["Vector"])
    streak = _noise(nt, grain_vec.outputs[0], 1.0, 8.0, 0.7)
    col = _ramp(nt, streak, [(0.3, (0.040, 0.026, 0.013)), (0.7, (0.085, 0.058, 0.030))])
    col = _mix(nt, 1.0, col, _combine(nt, _maprange(nt, _var(nt), 0.0, 1.0, 0.75, 1.2)), "MULTIPLY")
    nt.links.new(col, sh.inputs["Base Color"])
    nt.links.new(_maprange(nt, streak, 0.3, 0.7, 0.45, 0.75), sh.inputs["Roughness"])
    _bump(nt, sh, [(streak, 0.0008, 0.4)])
    _coat(sh, wet, 0.4, 0.15)
    return m


def wet_slot(name):
    """The dark water-filled channel under a drain grate."""
    m, nt, sh = _principled(name)
    sh.inputs["Base Color"].default_value = (0.004, 0.005, 0.004, 1.0)
    sh.inputs["Roughness"].default_value = 0.08
    return m


def leaf_mats(palette, wet):
    """render-studio's wet autumn litter (rain_scene.py:315 foliage_materials: subsurface 0.10, coat 0.65 /
    0.12 / IOR 1.333, roughness 0.46), plus per-leaf hue/saturation/value from VAR_ATTR, leaf-scale mottling
    (decay spots, darker vein side) and thin-sheet translucency."""
    mats = []
    for i, c in enumerate(palette):
        m, nt, sh = _principled(f"valora_court_leaf_{i}")
        v = _var(nt)
        hsv = nt.nodes.new("ShaderNodeHueSaturation")
        hsv.inputs["Color"].default_value = (*c, 1.0)
        nt.links.new(_maprange(nt, v, 0.0, 1.0, 0.47, 0.53), hsv.inputs["Hue"])
        nt.links.new(_maprange(nt, _math(nt, "FRACT", _math(nt, "MULTIPLY", v, 7.0), 0.0), 0.0, 1.0, 0.8, 1.2),
                     hsv.inputs["Saturation"])
        nt.links.new(_maprange(nt, _math(nt, "FRACT", _math(nt, "MULTIPLY", v, 13.0), 0.0), 0.0, 1.0, 0.7, 1.3),
                     hsv.inputs["Value"])
        p = _pos(nt)
        spots = _maprange(nt, _noise(nt, p, 90.0, 4.0, 0.6), 0.55, 0.72, 0.0, 0.7)
        col = _mix(nt, spots, hsv.outputs[0], (0.035, 0.020, 0.008))
        nt.links.new(col, sh.inputs["Base Color"])
        sh.inputs["Roughness"].default_value = 0.46
        sh.inputs["Subsurface Weight"].default_value = 0.10
        sh.inputs["Subsurface Scale"].default_value = 0.002
        if "Transmission Weight" in sh.inputs:
            sh.inputs["Transmission Weight"].default_value = 0.0
        _bump(nt, sh, [(_noise(nt, p, 300.0, 3.0), 0.0003, 0.3)])
        _coat(sh, wet, 0.65, 0.12)
        mats.append(m)
    return mats


# ------------------------------------------------------------------------------ geometry finishing
def finish_edges(ob, width, segments=2):
    """render-studio rain_scene.py:51 box(): 'Soft manufactured edges' bevel + 'Weighted face normals'."""
    if width > 0:
        bev = ob.modifiers.new("Soft manufactured edges", "BEVEL")
        bev.width = width
        bev.segments = segments
        bev.limit_method = "ANGLE"
        bev.harden_normals = True
    ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
    wn = ob.modifiers.new("Weighted face normals", "WEIGHTED_NORMAL")
    wn.keep_sharp = True
    return ob


def write_var(ob, values):
    from engine.blender.realism_rig import write_attr
    write_attr(ob, VAR_ATTR, np.asarray(values, np.float32), "FLOAT")


# ------------------------------------------------------------------------------ trees
def tree_siblings(mesh, height, count, seed):
    """render-studio scene_plants.py:42 shape_variants, verbatim maths: siblings of one scanned tree with their
    own bole height, S-curved leaning trunk, twisted lopsided oval crown and a slow limb warp; zero at the root
    flare so every sibling still stands on its base. Returns [(mesh, height)] (the original first)."""
    import random
    rng = random.Random(seed)
    result = [(mesh, height)]
    for number in range(count):
        copy = mesh.copy()
        copy.name = mesh.name + f"_sibling_{number + 1}"
        co = np.empty(len(copy.vertices) * 3, dtype=np.float32)
        copy.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3).astype(np.float64)
        h = np.clip(co[:, 2] / height, 0, 1)
        crown = np.clip((h - .22) / .33, 0, 1)
        crown = crown * crown * (3 - 2 * crown)
        warp = np.zeros_like(co)
        for _ in range(4):
            k = np.array([rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, .7)])
            k *= rng.uniform(1.6, 3.2) * 2 * np.pi / height / np.linalg.norm(k)
            push = np.array([rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, .45)])
            push *= rng.uniform(.035, .075) * height / np.linalg.norm(push)
            warp += np.sin(co @ k + rng.uniform(0, 6.283))[:, None] * push
        co += warp * crown[:, None]
        twist = rng.choice((-1, 1)) * rng.uniform(.5, 1.7) * crown
        cos, sin = np.cos(twist), np.sin(twist)
        x, y = co[:, 0] * cos - co[:, 1] * sin, co[:, 0] * sin + co[:, 1] * cos
        direction = rng.uniform(0, 6.283)
        wide, narrow = rng.uniform(1.10, 1.55), rng.uniform(.62, .95)
        ax, ay = np.cos(direction), np.sin(direction)
        along, across = x * ax + y * ay, -x * ay + y * ax
        along = along * (1 + (wide - 1) * crown) + rng.uniform(.0, .10) * height * crown
        across *= 1 + (narrow - 1) * crown
        x, y = along * ax - across * ay, along * ay + across * ax
        lean_direction, counter = rng.uniform(0, 6.283), rng.uniform(0, 6.283)
        lean = rng.uniform(.05, .16) * height * h * h
        bow = rng.uniform(.02, .06) * height * np.sin(np.pi * np.clip(h / .55, 0, 1))
        co[:, 0] = x + np.cos(lean_direction) * lean + np.cos(counter) * bow
        co[:, 1] = y + np.sin(lean_direction) * lean + np.sin(counter) * bow
        bole, depth = rng.uniform(.80, 1.30), rng.uniform(.78, 1.30)
        z = co[:, 2]
        split = .30 * height
        co[:, 2] = np.where(z < split, z * bole, split * bole + (z - split) * depth)
        copy.vertices.foreach_set("co", co.astype(np.float32).ravel())
        copy.update()
        result.append((copy, float(co[:, 2].max())))
    return result


def tune_foliage(me):
    """render-studio scene_plants.py:31-36: scanned foliage at specular 0.25 / roughness 0.6 (the glTF's
    defaults read as plastic under an overcast sky)."""
    for m in me.materials:
        if m is None or not m.use_nodes:
            continue
        sh = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if sh is not None:
            sh.inputs["Specular IOR Level"].default_value = 0.25
            if not sh.inputs["Roughness"].is_linked:
                sh.inputs["Roughness"].default_value = 0.6


def deal(n, pool):
    """Species index per tree: dealt in turn with a stride, so neighbours never share a shape
    (render-studio scene_plants.py:118 plant_tree: (planted * 2 + 1) % len)."""
    if pool <= 0:
        return []
    stride = 2 if pool % 2 else 1
    return [(i * stride + 1) % pool for i in range(n)]
