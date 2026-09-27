"""Poly Haven's modular_urban_apartments_facade (CC0) assembled onto night_street's facade blocks (art pass
2026-09-25). Runs inside Blender.

The kit is a set of 3 m wide, 3 m tall wall modules (a plain wall, door walls, window walls) with separate
door / window pieces (frames and glass) that sit in their holes, plus trims (a plinth, a string course, a
crown). In the file every piece is laid out on a display grid; a module's own frame is taken from its wall's
bounding box (x from its left edge, y = 0 on the wall's face, z from its foot) and its door / window keeps
the offset it has from that wall, so the pair assembles exactly as authored.

A facade block (street_layout) becomes: a ground floor of door and plain modules, upper floors of one window
style per building, a string course on every floor line, a crown on top; the modules are stretched along the
street to fill the block's width exactly. Behind every window and door, INTERIOR_M in, an interior card: an
emissive room (warm ceiling-lit, a lamp's pool, blinds or curtains, or dark) chosen per window from the
seeded key the layout gives it, so a lit window is a room, not a flat pale square. The building mass box is
pushed back behind the cards and its exposed ends are closed."""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

FLOOR_M, MODULE_M = 3.0, 3.0
INTERIOR_M = 0.55             # (eng) the room card's depth behind the wall face
MASS_BACK_M = 1.2             # (eng) the block's mass box starts this far behind the wall face
CROWN_M = 0.75
UPPER = ("centered_large", "centered_small", "centered_double", "offset_small")
DOORS = ("door_centered_large_01", "door_centered_small_01", "door_centered_small_02", "door_offset_small_01")
TINTS = ((1.0, 1.0, 1.0), (0.82, 0.78, 0.74), (1.05, 0.92, 0.8), (0.7, 0.72, 0.76), (0.92, 0.85, 0.9))   # (eng)
ROOM_ATTR, LIT_ATTR = "valora_room", "valora_lit"
ROOM_T_ATTR, ROOM_N_ATTR, ROOM_WH_ATTR = "valora_room_t", "valora_room_n", "valora_room_wh"   # card frame, size
ROOM_GAIN = 1.8               # (eng) the room box's light x this matches the old card's mean brightness
NIGHT_K = 0.5                 # (eng) the kit's daylight albedo x this: soot and night, so neon and lamps pool


def load(path):
    """{name: (mesh, origin Vector)} for every kit piece; the scene is left as it was."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in set(bpy.data.objects) - before]
    by = {o.name: o for o in new if o.type == "MESH"}

    def bbox(o):
        vs = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return Vector([min(v[i] for v in vs) for i in range(3)]), Vector([max(v[i] for v in vs) for i in range(3)])
    kit = {}
    for name, o in by.items():
        wall = None
        if name.startswith(("window_", "door_")):
            wall = by.get("wall_" + name)
        lo, _ = bbox(wall or o)
        origin = Vector((lo.x, lo.y if wall is not None or name.startswith("wall_") else 0.0, lo.z))
        me = o.data.copy()
        me.transform(o.matrix_world)
        me.transform(Matrix.Translation(-origin))
        kit[name] = me
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    glass = None
    for me in kit.values():
        for i, mat in enumerate(me.materials):
            if mat is not None and "glass" in mat.name:
                glass = glass or night_glass("valora_street_glass")
                me.materials[i] = glass
    return kit


def night_glass(name):
    """Window glass that shows the room behind it: clear with a Fresnel reflection (the street's lamps and
    neon slide across it) and a faint grime tint. The kit's own glass is a near-opaque daylight texture."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.78, 0.8, 0.8, 1.0)
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.04
    gl.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    fr = nt.nodes.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.52
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fr.outputs[0], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(gl.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m


def _window_rect(me):
    """(x0, x1, z0, z1) of a window / door piece in module coordinates."""
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return float(co[:, 0].min()), float(co[:, 0].max()), float(co[:, 2].min()), float(co[:, 2].max())


def _room_light(nt, math_, uv_sep, room):
    """Interior mapping (engine/interior_mapping.py): the lamp-lit room box seen through the card point along
    the view ray. Returns the brightness socket (SURF_BASE / (1 + LAMP_FALLOFF d^2) + AMBIENT)."""
    from engine import interior_mapping as I

    def attr(name):
        a = nt.nodes.new("ShaderNodeAttribute")
        a.attribute_name = name
        return a.outputs["Vector"]

    def vdot(a, b):
        n = nt.nodes.new("ShaderNodeVectorMath")
        n.operation = "DOT_PRODUCT"
        nt.links.new(a, n.inputs[0])
        nt.links.new(b, n.inputs[1])
        return n.outputs["Value"]

    def sep(v):
        s = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(v, s.inputs[0])
        return s.outputs

    def pick(cond, a, b):                     # cond ? a : b   (cond is 0/1)
        return math_("ADD", math_("MULTIPLY", cond, math_("SUBTRACT", a, b)), b)

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    t_vec, n_vec = attr(ROOM_T_ATTR), attr(ROOM_N_ATTR)
    w, h, _ = sep(attr(ROOM_WH_ATTR))
    inc = sep(geo.outputs["Incoming"])        # toward the viewer: the view ray is its negative
    view = nt.nodes.new("ShaderNodeVectorMath")
    view.operation = "SCALE"
    view.inputs["Scale"].default_value = -1.0
    nt.links.new(geo.outputs["Incoming"], view.inputs[0])
    dx = vdot(view.outputs[0], t_vec)
    dy = math_("MULTIPLY", inc[2], -1.0)
    dz = math_("MAXIMUM", math_("MULTIPLY", vdot(view.outputs[0], n_vec), -1.0), 1e-4)
    px, py = math_("MULTIPLY", uv_sep["X"], w), math_("MULTIPLY", uv_sep["Y"], h)
    x0, x1 = -I.ROOM_SIDE_M, math_("ADD", w, I.ROOM_SIDE_M)
    y0, y1 = -I.ROOM_SILL_M, math_("ADD", h, I.ROOM_HEAD_M)
    z1 = I.ROOM_DEPTH_M
    right, up = math_("GREATER_THAN", dx, 0.0), math_("GREATER_THAN", dy, 0.0)
    tx = math_("DIVIDE", math_("ABSOLUTE", math_("SUBTRACT", pick(right, x1, x0), px)),
               math_("MAXIMUM", math_("ABSOLUTE", dx), 1e-4))
    ty = math_("DIVIDE", math_("ABSOLUTE", math_("SUBTRACT", pick(up, y1, y0), py)),
               math_("MAXIMUM", math_("ABSOLUTE", dy), 1e-4))
    tz = math_("DIVIDE", z1, dz)
    t = math_("MINIMUM", math_("MINIMUM", tx, ty), tz)
    hx, hy, hz = (math_("ADD", px, math_("MULTIPLY", t, dx)), math_("ADD", py, math_("MULTIPLY", t, dy)),
                  math_("MULTIPLY", t, dz))
    is_back = math_("LESS_THAN", tz, math_("ADD", math_("MINIMUM", tx, ty), 1e-5))
    is_side = math_("MULTIPLY", math_("SUBTRACT", 1.0, is_back), math_("LESS_THAN", tx, math_("ADD", ty, 1e-5)))
    is_cf = math_("MULTIPLY", math_("SUBTRACT", 1.0, is_back), math_("SUBTRACT", 1.0, is_side))
    cf = pick(up, I.SURF_BASE["ceiling"], I.SURF_BASE["floor"])
    base = math_("ADD", math_("ADD", math_("MULTIPLY", is_back, I.SURF_BASE["back"]),
                              math_("MULTIPLY", is_side, I.SURF_BASE["side"])), math_("MULTIPLY", is_cf, cf))
    # a per-room lamp position across the room, as the old card's pool (lx = fract(room x 7.31))
    lx = math_("FRACT", math_("MULTIPLY", room, 7.31))
    lamp_x = math_("ADD", x0, math_("MULTIPLY", lx, math_("SUBTRACT", x1, x0)))
    lamp_y = math_("SUBTRACT", y1, 0.15)
    lamp_z = 0.55 * z1
    ddx, ddy, ddz = math_("SUBTRACT", hx, lamp_x), math_("SUBTRACT", hy, lamp_y), math_("SUBTRACT", hz, lamp_z)
    d2 = math_("ADD", math_("ADD", math_("MULTIPLY", ddx, ddx), math_("MULTIPLY", ddy, ddy)), math_("MULTIPLY", ddz, ddz))
    lit = math_("DIVIDE", base, math_("ADD", 1.0, math_("MULTIPLY", d2, I.LAMP_FALLOFF)))
    # furniture: a dark low band (sofa, cabinet) along the back wall in about half the rooms
    furn = math_("MULTIPLY", math_("MULTIPLY", is_back, math_("LESS_THAN", math_("SUBTRACT", hy, y0), 0.85)),
                 math_("LESS_THAN", math_("FRACT", math_("MULTIPLY", room, 4.77)), 0.5))
    lit = math_("MULTIPLY", lit, math_("SUBTRACT", 1.0, math_("MULTIPLY", furn, 0.7)))
    return math_("ADD", lit, I.AMBIENT)


def room_material(name, kelvin_rgb, strength):
    """Interior card: the room's light by (ROOM_ATTR, LIT_ATTR) per face. A lit room is warm, brightest near
    its ceiling with a lamp's pool somewhere along it; one room in three has blinds (bright slats), one in four
    curtains (dim, glowing edges); an unlit room shows a faint cool spill. UV is 0..1 across the window."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out, em = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeEmission")
    uv = nt.nodes.new("ShaderNodeTexCoord").outputs["UV"]
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv, sep.inputs[0])
    room = nt.nodes.new("ShaderNodeAttribute")
    room.attribute_name = ROOM_ATTR
    lit = nt.nodes.new("ShaderNodeAttribute")
    lit.attribute_name = LIT_ATTR

    def math_(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]
    r = room.outputs["Fac"]
    # the room box behind the glass (interior mapping): walls, ceiling and floor lit by one ceiling lamp, so an
    # oblique view along the facade sees depth instead of a flat card (realism audit, facade interior cards)
    base = math_("MULTIPLY", _room_light(nt, math_, sep.outputs, r), ROOM_GAIN)
    # blinds: horizontal slats for one room in three
    slats = math_("ADD", math_("MULTIPLY", math_("SINE", math_("MULTIPLY", sep.outputs["Y"], 95.0)), 0.35), 0.65)
    is_bl = math_("LESS_THAN", math_("FRACT", math_("MULTIPLY", r, 3.17)), 0.33)
    base = math_("MULTIPLY", base, math_("ADD", math_("MULTIPLY", is_bl, math_("SUBTRACT", slats, 1.0)), 1.0))
    # curtains: one room in four, drawn: dim centre, glowing edges
    edge = math_("POWER", math_("ABSOLUTE", math_("SUBTRACT", math_("MULTIPLY", sep.outputs["X"], 2.0), 1.0)), 3.0)
    curt = math_("ADD", math_("MULTIPLY", edge, 0.7), 0.18)
    is_cu = math_("GREATER_THAN", math_("FRACT", math_("MULTIPLY", r, 5.93)), 0.75)
    base = math_("MULTIPLY", base, math_("ADD", math_("MULTIPLY", is_cu, math_("SUBTRACT", curt, 1.0)), 1.0))
    # brightness per room, lit or dark
    # round 15 (owner's r14 night review: "irregular lit windows"): a much wider spread per room - a bare bulb
    # blazing next to a room lit by a single lamp in its far corner (was 0.35-1.25)
    kf = math_("FRACT", math_("MULTIPLY", r, 11.7))
    k = math_("ADD", math_("MULTIPLY", math_("POWER", kf, 1.5), ROOM_SPREAD[1] - ROOM_SPREAD[0]), ROOM_SPREAD[0])
    on = math_("MULTIPLY", math_("MULTIPLY", base, k), lit.outputs["Fac"])
    col = nt.nodes.new("ShaderNodeMix")                       # warm tungsten .. cooler LED per room
    col.data_type = "RGBA"
    nt.links.new(math_("FRACT", math_("MULTIPLY", r, 2.21)), col.inputs["Factor"])
    col.inputs[6].default_value = (*kelvin_rgb, 1.0)
    col.inputs[7].default_value = (1.0, 0.86, 0.66, 1.0)
    dark = nt.nodes.new("ShaderNodeMix")                      # an unlit room: a faint cool spill from outside
    dark.data_type = "RGBA"
    nt.links.new(lit.outputs["Fac"], dark.inputs["Factor"])
    dark.inputs[6].default_value = (0.012, 0.016, 0.026, 1.0)
    tv = nt.nodes.new("ShaderNodeMix")                        # round 15: one room in TV_SHARE lit by a screen
    tv.data_type = "RGBA"
    nt.links.new(math_("LESS_THAN", math_("FRACT", math_("MULTIPLY", r, 7.77)), TV_SHARE), tv.inputs["Factor"])
    nt.links.new(col.outputs[2], tv.inputs[6])
    tv.inputs[7].default_value = (*TV_RGB, 1.0)
    nt.links.new(tv.outputs[2], dark.inputs[7])
    nt.links.new(dark.outputs[2], em.inputs["Color"])
    strength_ = math_("MULTIPLY", math_("ADD", on, math_("SUBTRACT", 1.0, lit.outputs["Fac"])), strength)
    nt.links.new(strength_, em.inputs["Strength"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


# Round 15 (owner's r14 night review: "background walls less controlled - grime, varied materials"): an old street's
# render is never one clean plaster. Rain streaks run down from every sill and cornice (noise stretched vertically),
# soot and damp blotches sit at metre scale, and the ground floor is splashed darker; the roughness wanders with
# them (damp grime is a little glossier). Each building takes its own share. (eng)
GRIME = {"streakHz": (9.0, 0.06), "streak": (0.50, 0.70), "streakDark": 0.8, "blotchHz": 0.7, "blotch": (0.40, 0.70),
         "blotchDark": 0.6, "splashM": 1.1, "splashDark": 0.5, "share": (0.7, 1.0, 0.85, 0.6, 0.95),
         "rough": (0.55, 0.95)}


def _grime(nt, sh, colour, tint_i):
    """colour x the building's grime (GRIME): vertical rain streaks, soot / damp blotches and a darker splashed
    ground floor, by world position; the roughness follows. Returns the new colour socket."""
    g = GRIME
    share = g["share"][tint_i % len(g["share"])]
    geo = nt.nodes.new("ShaderNodeNewGeometry")

    def node_math(op, a, b):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    def noise(vec, hz, detail=4.0):
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value, n.inputs["Detail"].default_value = hz, detail
        nt.links.new(vec, n.inputs["Vector"])
        return n.outputs["Fac"]

    def ramp(v, lo, hi):
        r = nt.nodes.new("ShaderNodeMapRange")
        r.interpolation_type = "SMOOTHSTEP"
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = lo, hi
        nt.links.new(v, r.inputs["Value"])
        return r.outputs["Result"]
    sq = nt.nodes.new("ShaderNodeVectorMath")
    sq.operation = "MULTIPLY"
    sq.inputs[1].default_value = (1.0, 1.0, g["streakHz"][1])
    nt.links.new(geo.outputs["Position"], sq.inputs[0])
    streak = ramp(noise(sq.outputs[0], g["streakHz"][0], 3.0), *g["streak"])
    blotch = ramp(noise(geo.outputs["Position"], g["blotchHz"], 5.0), *g["blotch"])
    z = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], z.inputs[0])
    splash = ramp(z.outputs["Z"], g["splashM"], 0.0)
    dark = node_math("ADD", node_math("ADD", node_math("MULTIPLY", streak, g["streakDark"]),
                                      node_math("MULTIPLY", blotch, g["blotchDark"])),
                     node_math("MULTIPLY", splash, g["splashDark"]))
    dark = node_math("MINIMUM", node_math("MULTIPLY", dark, share), 0.8)
    keep = node_math("SUBTRACT", 1.0, dark)
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(colour, mul.inputs[6])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    for ax in ("X", "Y", "Z"):
        nt.links.new(keep, comb.inputs[ax])
    nt.links.new(comb.outputs[0], mul.inputs[7])
    rough = sh.inputs["Roughness"]
    if not rough.is_linked:
        rr = nt.nodes.new("ShaderNodeMapRange")
        nt.links.new(dark, rr.inputs["Value"])
        rr.inputs["From Max"].default_value = 0.8
        rr.inputs["To Min"].default_value, rr.inputs["To Max"].default_value = g["rough"][1], g["rough"][0]
        nt.links.new(rr.outputs[0], rough)
    return mul.outputs[2]


ROOM_SPREAD = (0.25, 4.0)     # (eng, round 15) a lit room's brightness factor, kf^1.5 between these
TV_SHARE, TV_RGB = 0.14, (0.45, 0.62, 1.0)   # (eng, round 15) rooms lit only by a screen: a cool blue-white


class Assembler:
    """Places kit pieces as objects sharing the kit's meshes; collects the interior cards and mass boxes."""

    def __init__(self, scene, kit, block, tag):
        self.scene, self.kit, self.block, self.tag = scene, kit, block, tag
        self.rects = {k: _window_rect(me) for k, me in kit.items() if k.startswith(("window_", "door_"))}
        self.cards = ([], [], [], [], [])      # verts, loops per face, uvs, room, lit
        self.frames = []                       # per card: (T, N_out, (w, h, 0)) for the room box
        self.objects = []
        self.lit = 0
        self.windows = 0
        self.mats = {}

    def _tinted(self, me, tint_i):
        """A copy of the mesh whose plaster / trim materials are tinted for this building (few variants)."""
        key = (me.name, tint_i)
        if key in self.mats:
            return self.mats[key]
        m2 = me.copy()
        for i, mat in enumerate(m2.materials):
            if mat is None or not any(s in mat.name for s in ("plaster", "trim")):
                continue
            tk = (mat.name, tint_i)
            if tk not in self.mats:
                t = mat.copy()
                sh = next((n for n in t.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                link = next((l for l in t.node_tree.links if sh and l.to_socket == sh.inputs["Base Color"]), None)
                if link is not None:
                    mul = t.node_tree.nodes.new("ShaderNodeMix")
                    mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
                    mul.inputs["Factor"].default_value = 1.0
                    t.node_tree.links.new(link.from_socket, mul.inputs[6])
                    mul.inputs[7].default_value = (*(NIGHT_K * c for c in TINTS[tint_i]), 1.0)
                    t.node_tree.links.new(_grime(t.node_tree, sh, mul.outputs[2], tint_i), sh.inputs["Base Color"])
                self.mats[tk] = t
            m2.materials[i] = self.mats[tk]
        self.mats[key] = m2
        return m2

    def place(self, name, frame, x, z, sx, tint_i=0):
        """One kit piece at module position (x along the facade, z up) in the facade frame, stretched sx."""
        me = self.kit.get(name)
        if me is None:
            return None
        ob = bpy.data.objects.new(f"valora_street_kit_{len(self.objects)}", self._tinted(me, tint_i))
        self.scene.collection.objects.link(ob)
        ob.matrix_world = frame @ Matrix.Translation((x, 0.0, z)) @ Matrix.Diagonal((sx, 1.0, 1.0, 1.0))
        self.objects.append(self.tag(ob))
        return ob

    def card(self, frame, name, x, z, sx, key, lit_share):
        """The room behind a window / door piece at module (x, z), INTERIOR_M behind the wall face."""
        x0, x1, z0, z1 = self.rects[name]
        pts = [(x + x0 * sx, INTERIOR_M, z + z0), (x + x1 * sx, INTERIOR_M, z + z0), (x + x1 * sx, INTERIOR_M, z + z1),
               (x + x0 * sx, INTERIOR_M, z + z1)]
        v, _, uv, room, lit = self.cards
        v += [tuple(frame @ Vector(p)) for p in pts]
        f3 = frame.to_3x3()
        self.frames.append((tuple((f3 @ Vector((1.0, 0.0, 0.0))).normalized()),
                            tuple(-(f3 @ Vector((0.0, 1.0, 0.0))).normalized()), ((x1 - x0) * sx, z1 - z0, 0.0)))
        uv += [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        on = 1.0 if key < lit_share else 0.0
        room.append(math.fmod(key * 97.13, 1.0))
        lit.append(on)
        self.windows += 1
        self.lit += int(on)

    def facade(self, fa, frame, width, height, rng, lit_share, shop_share=None):
        """Fill one facade block: ground floor, window floors, trims. Returns the kit top height."""
        cols = max(1, int(round(width / MODULE_M)))
        sx = width / (cols * MODULE_M)
        floors = max(1, int(round((height - CROWN_M) / FLOOR_M)))
        style = rng.choice(UPPER)
        tint_i = rng.randrange(len(TINTS))
        door_col = rng.randrange(cols)
        for c in range(cols):
            x = c * MODULE_M * sx
            if c == door_col or rng.random() < 0.35:
                door = rng.choice(DOORS)
                self.place("wall_" + door, frame, x, 0.0, sx, tint_i)
                self.place(door, frame, x, 0.0, sx)
                self.card(frame, door, x, 0.0, sx, rng.random() * (0.6 if c == door_col else 1.0),
                          lit_share + 0.25 if shop_share is None else shop_share)
            else:
                self.place("wall_standard_standard_01", frame, x, 0.0, sx, tint_i)
            self.place("base_standard_01", frame, x, 0.0, sx, tint_i)
            for f in range(1, floors):
                n = "01" if f % 2 else "02"
                if f == floors - 1 and floors > 2:
                    n = "03"
                wall, win = f"wall_window_{style}_{n}", f"window_{style}_{n}"
                if wall not in self.kit or win not in self.kit:
                    wall, win = f"wall_window_{style}_01", f"window_{style}_01"
                self.place(wall, frame, x, f * FLOOR_M, sx, tint_i)
                self.place(win, frame, x, f * FLOOR_M, sx)
                self.card(frame, win, x, f * FLOOR_M, sx, rng.random(), lit_share)
                self.place("cornice_standard_standard_01", frame, x, f * FLOOR_M - 0.1, sx, tint_i)
            self.place("crown_standard_standard_01", frame, x, floors * FLOOR_M, sx, tint_i)
        return floors * FLOOR_M + CROWN_M

    def finish(self, strength, kelvin_rgb):
        v, _, uv, room, lit = self.cards
        if not v:
            return None
        n = len(v) // 4
        me = bpy.data.meshes.new("valora_street_rooms")
        me.from_pydata(v, [], [(4 * i, 4 * i + 1, 4 * i + 2, 4 * i + 3) for i in range(n)])
        layer = me.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", np.asarray(uv, np.float32).ravel())
        for nm, vals in ((ROOM_ATTR, room), (LIT_ATTR, lit)):
            a = me.attributes.new(nm, "FLOAT", "FACE")
            a.data.foreach_set("value", np.asarray(vals, np.float32))
        for i, nm in enumerate((ROOM_T_ATTR, ROOM_N_ATTR, ROOM_WH_ATTR)):
            a = me.attributes.new(nm, "FLOAT_VECTOR", "FACE")
            a.data.foreach_set("vector", np.asarray([fr[i] for fr in self.frames], np.float32).ravel())
        me.materials.append(room_material("valora_street_rooms", kelvin_rgb, strength))
        ob = bpy.data.objects.new("valora_street_rooms", me)
        self.scene.collection.objects.link(ob)
        ob.visible_shadow = False
        return self.tag(ob)
