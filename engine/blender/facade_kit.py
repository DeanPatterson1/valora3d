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
    # ceiling gradient: 0.35 at the sill rising to 1 under the ceiling
    grad = math_("ADD", math_("MULTIPLY", math_("POWER", sep.outputs["Y"], 1.6), 0.65), 0.35)
    # a lamp's pool: a soft blob at a per-room x
    lx = math_("FRACT", math_("MULTIPLY", r, 7.31))
    dx = math_("SUBTRACT", sep.outputs["X"], lx)
    dy = math_("SUBTRACT", sep.outputs["Y"], 0.55)
    d2 = math_("ADD", math_("MULTIPLY", dx, dx), math_("MULTIPLY", dy, dy))
    pool = math_("MULTIPLY", math_("EXPONENT", math_("MULTIPLY", d2, -9.0)), 1.4)
    base = math_("ADD", grad, pool)
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
    k = math_("ADD", math_("MULTIPLY", math_("FRACT", math_("MULTIPLY", r, 11.7)), 0.9), 0.35)
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
    nt.links.new(col.outputs[2], dark.inputs[7])
    nt.links.new(dark.outputs[2], em.inputs["Color"])
    strength_ = math_("MULTIPLY", math_("ADD", on, math_("SUBTRACT", 1.0, lit.outputs["Fac"])), strength)
    nt.links.new(strength_, em.inputs["Strength"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


class Assembler:
    """Places kit pieces as objects sharing the kit's meshes; collects the interior cards and mass boxes."""

    def __init__(self, scene, kit, block, tag):
        self.scene, self.kit, self.block, self.tag = scene, kit, block, tag
        self.rects = {k: _window_rect(me) for k, me in kit.items() if k.startswith(("window_", "door_"))}
        self.cards = ([], [], [], [], [])      # verts, loops per face, uvs, room, lit
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
                    t.node_tree.links.new(mul.outputs[2], sh.inputs["Base Color"])
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
        uv += [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        on = 1.0 if key < lit_share else 0.0
        room.append(math.fmod(key * 97.13, 1.0))
        lit.append(on)
        self.windows += 1
        self.lit += int(on)

    def facade(self, fa, frame, width, height, rng, lit_share):
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
                self.card(frame, door, x, 0.0, sx, rng.random() * (0.6 if c == door_col else 1.0), lit_share + 0.25)
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
        me.materials.append(room_material("valora_street_rooms", kelvin_rgb, strength))
        ob = bpy.data.objects.new("valora_street_rooms", me)
        self.scene.collection.objects.link(ob)
        ob.visible_shadow = False
        return self.tag(ob)
