"""Subject preparation (realism pass 2026-09-25). Runs inside Blender, once, right after the upload is imported,
placed and rested, before any block builds: the upload's materials are calibrated so the car reads as a real car
under Cycles. The pure role rules are engine/subject_prep.py; this module gathers the facts they need and applies
each role's calibration, ported from ModVision's render-studio (tools/render-studio, the black rain film):

  paint          render_materials.py:150-165 + surface_detail.lacquer :38 / metallic_flake :52
  carbon         render_materials.py:128-149 (+ a procedural twill where the upload has no weave)
  privacy glass  render_materials.py:166-172
  window glass   thin-sheet optics of surface_detail.thin_lens :98, tinted by the upload's own alpha
  lamp cover     render_materials.py:173-179, _blend_to_glass :97, thin_lens :98
  lamp optic     component_materials.py:165-186 (internal pieces lose the repeated smoke tint)
  DRL / tail     rain_look.lamps :446-464, LOOK drl/tail :73-76
  tyre           surface_detail.rubber :86, tire_sidewalls :338-394, _wet_tire_treatment :191, _used_rubber :154
  rubber         surface_detail.rubber :86
  rotor          component_materials.weathered_rotors :17-58, _swept_face :61-119, rotor_face_normals :122
  caliper        component_materials.py:187-204
  trim           rain_look.car_materials :237-250
  road film      road_weathering.film_mask :261, road_film :355, brake_dust :383

What changes from render-studio: roles come from guarded evidence, not the Manthey asset's names; every pattern
is in PLACED metres (valora_realism_offset's space, so it rides with a moving car) or in a rest-position attribute
written on the mesh (so it turns with a rolling wheel); nothing is done to a material with no role."""
import bpy
import numpy as np

from engine.blender.realism_rig import rig, write_attr
from engine.subject_prep import classify, conditions, interior, tokens, vertex_labels

PREP_KEY = "valora_prep"             # material custom property: the role applied (uploads' valora_* are stripped)
WHEEL_ATTR = "valora_prep_wheel"     # per vertex: (rho / wheel r, axial / half width, rho / the part's own reach)
REST_ATTR = "valora_prep_rest"       # per vertex: placed rest position, metres
FILM_GROUP = "valora_prep_road_film"

# ---- ported values (render-studio file:line) ---------------------------------------------------------------------
LACQUER_PEEL = (650.0, 0.000012, 0.18)            # surface_detail.py:45-46 per metre, bump distance, strength
LACQUER_ROUGH = {False: (0.032, 0.048), True: (0.022, 0.034)}   # surface_detail.py:47-48 dry / wet
FLAKE_SCALE, FLAKE_SPREAD = 3200.0, 0.24          # surface_detail.py:65, 73
CARBON = {"metallic": 0.0, "spec": 0.2, "rough": 0.35, "coat": 1.0, "coatRough": {False: 0.16, True: 0.13}}
#         render_materials.py:142-146; coat rough .12-.22 (critique mat-v2 #4: a .025 coat read as black glass)
CARBON_TINT = (0.065, 0.068, 0.075)               # render_materials.py:136 (for the viewer's bright charcoal weave)
CARBON_TARGET = 0.05                              # luminance a bright weave is brought down to (eng, from that tint)
WEAVE_TOW = 0.003                                 # m, one tow of a 2x2 twill (eng; look r1: 4 mm read as a checkerboard)
WEAVE = {"anisotropic": 0.35, "shade": (0.92, 1.08)}   # subtle: the weave shows in the sheen, not as a pattern (eng)
WINDOW_POLARIZER = 0.42   # rain_look.py:233-236: the film's window reflections through a polariser, as a car
#                           photographer shoots glass; the sheet's Fresnel reflection is scaled by it
PRIVACY = {"IOR": 1.52, "Roughness": 0.018, "Coat Weight": 0.0, "Specular IOR Level": 0.5}   # :167-170
GLASS_IOR, GLASS_ROUGH = 1.52, 0.018              # thin_lens reflection roughness surface_detail.py:139
LENS = {"Coat Weight": 0.0, "Roughness": 0.025}   # render_materials.py:175-176
OPTIC_CLEAR = (0.98, 0.98, 0.98, 1.0)             # component_materials.py:183
LAMP = {"drl": ((0.80, 0.89, 1.0), 240.0), "tail": ((1.0, 0.030, 0.012), 95.0)}   # rain_look.py:73-76
LAMP_DARK_SCALE = 0.12    # round 6: after dark the camera opens ~3 stops, so the daylight-film strength clipped each
#                           headlamp into a white disc (real_r5_street_night); at 1/8 the LED bars still clip, the
#                           lens and housing around them do not
RUBBER_GRAIN = (1600.0, 0.00016, 0.3)             # surface_detail.py:89-91
RUBBER_ROUGH = {False: (0.62, 0.78), True: (0.52, 0.68)}   # critique mat-v2 #4: rubber 0.6-0.8 (render-studio
#                                                           .56-.72 sat on the black painted wheel's roughness)
TYRE_WET_PATCH = (0.25, 0.40, 9.0, 0.55)   # wet tyre patches: roughness range, noise frequency (1/m), coverage
#                                            threshold (critique mat-v2 #3: tyre patches 0.25-0.4, shared wetness)
SIDEWALL = (0.76, 0.94, 1100.0)                   # surface_detail.py:386-390 band and ridge frequency (x r)
SIDEWALL_BUMP = {False: (0.000035, 0.25), True: (0.00016, 0.5)}   # surface_detail.py:394
BLOOM = (0.046, 0.037, 0.028, 1.0)                # surface_detail.py:167 antiozonant bloom (0.078/.060/.043 there;
#                                                   round 6: the tyre read grey and dusty beside the film's)
SCRUB = (0.058, 0.054, 0.048, 1.0)                # surface_detail.py:180 road-scrubbed tread face (0.098/.090/.079)
TREAD_BAND = (0.955, 0.99)                        # surface_detail.py:172-173
GROOVES = ((-0.32, 0.32), 0.06, 0.004)            # circumferential grooves: axial centres (x half width), width, m deep (eng)
TYRE_DUST = (0.050, 0.045, 0.038, 1.0)            # surface_detail.py:203 (0.085/.075/.062; round 6 darker)
TYRE_SHADE = 0.7          # round 6: the rubber's base (authored x weathering) darkened: a tyre is ~0.02-0.04 albedo
TYRE_SPECULAR = 0.35      # round 6: dielectric F0 lowered (0.5 = 4%): the grey sheen over the sidewall read as dust
TYRE_WET_SHEEN = (0.35, 0.7)   # the wet coat near the road (was 0.56-1.0)
ROTOR_RAMP = ((0.24, (0.19, 0.20, 0.20, 1.0)), (0.76, (0.70, 0.71, 0.72, 1.0)))   # component_materials.py:38-41
ROTOR_RAMP_GAIN = 1.0 / 0.45   # that ramp multiplied the Manthey's bright disc; on an authored disc colour it is
#                                re-centred on 1 so the aggregate varies the disc without blacking it out (look r1)
ROTOR_ROUGH, ROTOR_METAL = (0.39, 0.56), 0.4      # component_materials.py:51, 54
CALIPER = {"Metallic": 0.0, "Roughness": 0.35, "Coat Weight": 1.0, "Coat Roughness": 0.33,
           "Specular IOR Level": 0.2}             # critique mat-v2 #4: painted caliper Metallic 0, rough .3-.4
#                                                   (+-.03 via lacquer's satin branch); render-studio .24 / .04 read glassy
EDGE_BEVEL_M = {"caliper": 0.001, "carbon": 0.0003, "trim-matte": 0.0003}   # rounded edges where the part warrants:
#                                                   cast caliper 0.5-1.5 mm, moulded aero 0.2-0.5 mm (critique mat-v2 #4)
RIM_PAINTED = {"lum": 0.12, "rough": (0.27, 0.33)}   # a dark rim is a painted wheel: Metallic 0, satin 0.25-0.35
RIM_BARE = {"lum": 0.3, "rough": (0.20, 0.35)}      # a bright metallic wheel part (centre lock, fasteners): Metallic 1
CERAMIC_DISC = {"lum": 0.4, "metal": 0.1, "rough": (0.45, 0.62), "polish": (0.36, 0.46), "shade": 0.6}
#                                                   a dark authored disc is carbon-ceramic, not shiny steel (mat-v2 #4)
CARBON_WEAVE_HEIGHT = 0.00001                     # m: the tows' relief under the resin, 5-15 um (critique mat-v2 #4)
TRIM_MATTE, TRIM_GRAIN, TRIM_GLOSS = 0.50, (2200.0, 0.00004, 0.15), 0.28   # rain_look.py:241-248; matte aero
#                                                   .4-.55 (critique mat-v2 #4), was .58
FILM_COLOR, DUST_COLOR = (0.058, 0.053, 0.046, 1.0), (0.070, 0.058, 0.046, 1.0)  # road_weathering.py:14-15
MIRROR = {"Metallic": 1.0, "Base Color": (0.92, 0.92, 0.92, 1.0), "Roughness": 0.02, "Alpha": 1.0,
          "Transmission Weight": 0.0, "Coat Weight": 0.0}   # a silvered mirror (eng)


# ---- node helpers (surface_detail.py:7-35, render_materials.py:72) -----------------------------------------------
def set_input(shader, name, value):
    socket = shader.inputs.get(name)
    if socket is not None:
        for link in list(socket.links):
            shader.id_data.links.remove(link)
        socket.default_value = value


def _src(nt, socket):
    """What feeds a socket: its link, or a constant node holding its value (so a chain can be inserted)."""
    if socket.is_linked:
        return socket.links[0].from_socket
    v = socket.default_value
    if hasattr(v, "__len__"):
        n = nt.nodes.new("ShaderNodeRGB")
        n.outputs[0].default_value = tuple(v)
    else:
        n = nt.nodes.new("ShaderNodeValue")
        n.outputs[0].default_value = v
    return n.outputs[0]


def _placed(nt):
    """Placed metres: valora_realism_offset's local space, which moves with the car (road film, lacquer)."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = rig()[1]
    return tc.outputs["Object"]


def _attr(nt, name):
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_type = "GEOMETRY"
    a.attribute_name = name
    return a.outputs["Vector"]


def noise(nt, coords, frequency, detail=2.0):
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = frequency
    tex.inputs["Detail"].default_value = detail
    nt.links.new(coords, tex.inputs["Vector"])
    return tex.outputs["Fac"]


def variation(nt, source, low, high):
    m = nt.nodes.new("ShaderNodeMapRange")
    m.inputs["To Min"].default_value, m.inputs["To Max"].default_value = low, high
    nt.links.new(source, m.inputs["Value"])
    return m.outputs[0]


def _smooth(nt, value, a, b, at_a, at_b):
    m = nt.nodes.new("ShaderNodeMapRange")
    m.interpolation_type = "SMOOTHSTEP"
    for k, v in (("From Min", a), ("From Max", b), ("To Min", at_a), ("To Max", at_b)):
        m.inputs[k].default_value = v
    nt.links.new(value, m.inputs["Value"])
    return m.outputs[0]


def _math(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation, n.use_clamp = op, clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def bump(shader, source, distance, strength, socket="Normal"):
    nt = shader.id_data
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Distance"].default_value, b.inputs["Strength"].default_value = distance, strength
    target = shader.inputs[socket]
    if target.is_linked:                          # chain the authored normal, never replace it
        nt.links.new(target.links[0].from_socket, b.inputs["Normal"])
    nt.links.new(source, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], target)


def edge_bevel(shader, radius, sockets=("Normal",)):
    """Rounded edges in the shading (Cycles Bevel), chained after whatever already feeds each normal socket."""
    nt = shader.id_data
    for name in sockets:
        target = shader.inputs.get(name)
        if target is None:
            continue
        b = nt.nodes.new("ShaderNodeBevel")
        b.samples = 8
        b.inputs["Radius"].default_value = radius
        if target.is_linked:
            nt.links.new(target.links[0].from_socket, b.inputs["Normal"])
        nt.links.new(b.outputs["Normal"], target)


def _vertex_mean_luminance(sock, users):
    """Mean luminance of the vertex colours a glTF multiply wrapper feeds into `sock`, over the users; None when
    the socket has no such wrapper or no user carries the layer."""
    if not sock.is_linked:
        return None
    node = sock.links[0].from_node
    if node.type != "MIX":
        return None
    src = next((i.links[0].from_node for i in node.inputs if i.type == "RGBA" and i.is_linked
                and _vertex_wrapper(i.links[0].from_node)), None)
    if src is None:
        return None
    name = getattr(src, "layer_name", "") or getattr(src, "attribute_name", "")
    tot, n = 0.0, 0
    for o in users:
        attrs = getattr(o.data, "color_attributes", None)
        if not attrs:
            continue
        a = attrs.get(name) if name else attrs.active_color
        if a is None:
            continue
        px = np.empty(len(a.data) * 4, np.float32)
        a.data.foreach_get("color", px)
        rgb = px.reshape(-1, 4)[:, :3]
        tot += float((rgb @ np.array([0.2126, 0.7152, 0.0722])).sum())
        n += len(rgb)
    return tot / n if n else None


def effective_luminance(sh, users):
    """What the renderer sees as the base colour's luminance: the constant pigment times the glTF vertex colours
    it is multiplied by (a black wheel is often a white pigment on black vertex colours)."""
    pig = constant_pigment(sh.inputs["Base Color"])
    if pig is None:
        return None
    lum = 0.2126 * pig[0] + 0.7152 * pig[1] + 0.0722 * pig[2]
    v = _vertex_mean_luminance(sh.inputs["Base Color"], users)
    return lum * v if v is not None else lum


def _toward_color(nt, socket, color, factor):
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.use_clamp = True
    nt.links.new(_src(nt, socket), mix.inputs[1])
    mix.inputs[2].default_value = color
    nt.links.new(factor, mix.inputs[0])
    nt.links.new(mix.outputs[0], socket)


def _toward_value(nt, socket, target, factor):
    """road_weathering._toward_value :332: factor 0 keeps the authored value or map; 1 reaches target."""
    m = nt.nodes.new("ShaderNodeMapRange")
    nt.links.new(_src(nt, socket), m.inputs["To Min"])
    m.inputs["To Max"].default_value = target
    nt.links.new(factor, m.inputs["Value"])
    nt.links.new(m.outputs[0], socket)


# ---- facts ---------------------------------------------------------------------------------------------------------
def _principled(m):
    return next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m.use_nodes else None


def _output(m):
    outs = [n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL"]
    return next((n for n in outs if n.is_active_output), outs[0] if outs else None)


def _vertex_wrapper(node):
    return node.type == "VERTEX_COLOR" or (node.type == "ATTRIBUTE" and node.attribute_type == "GEOMETRY")


def constant_pigment(socket):
    """rain_look.constant_pigment :148: a constant colour, including glTF's vertex-colour multiply wrapper."""
    if not socket.is_linked:
        return tuple(socket.default_value)[:3]
    node = socket.links[0].from_node
    if node.type == "MIX" and getattr(node, "data_type", "") == "RGBA" and node.blend_type == "MULTIPLY":
        a = next(s for s in node.inputs if s.name == "A" and s.type == "RGBA")
        b = next(s for s in node.inputs if s.name == "B" and s.type == "RGBA")
        f = node.inputs[0]
        if not f.is_linked and abs(f.default_value - 1) < 1e-4:
            if a.is_linked and _vertex_wrapper(a.links[0].from_node) and not b.is_linked:
                return tuple(b.default_value)[:3]
            if b.is_linked and _vertex_wrapper(b.links[0].from_node) and not a.is_linked:
                return tuple(a.default_value)[:3]
    return None


def constant_scalar(socket):
    """A constant value, including glTF's vertex-alpha multiply wrapper; None for anything else linked."""
    if not socket.is_linked:
        return float(socket.default_value)
    node = socket.links[0].from_node
    if node.type == "MATH" and node.operation == "MULTIPLY":
        ins = [i for i in node.inputs if i.enabled][:2]
        linked = [i for i in ins if i.is_linked]
        if len(linked) == 1 and _vertex_wrapper(linked[0].links[0].from_node):
            return float(next(i for i in ins if not i.is_linked).default_value)
    return None


def _facts(m, users, geo, painted):
    sh = _principled(m)
    f = {"name": m.name, "users": [o.name for o in users], "principled": sh is not None, "geo": geo,
         "painted": painted}
    if sh is None:
        return f
    out = _output(m)
    surf = out.inputs["Surface"] if out is not None else None
    ecol = constant_pigment(sh.inputs["Emission Color"])
    f.update({
        "textured": any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes),
        "volume": bool(out is not None and out.inputs["Volume"].is_linked),
        "direct": bool(surf is not None and surf.is_linked and surf.links[0].from_node == sh),
        "alpha": constant_scalar(sh.inputs["Alpha"]), "transmission": constant_scalar(sh.inputs["Transmission Weight"]),
        "metallic": constant_scalar(sh.inputs["Metallic"]), "roughness": constant_scalar(sh.inputs["Roughness"]),
        "coat": constant_scalar(sh.inputs["Coat Weight"]), "pigment": constant_pigment(sh.inputs["Base Color"]),
        "emission": constant_scalar(sh.inputs["Emission Strength"]) or 0.0,
        "emissionColor": ecol if ecol is not None else (1.0, 1.0, 1.0),
        "emissionLinked": sh.inputs["Emission Strength"].is_linked or ecol is None})
    return f


# ---- geometry --------------------------------------------------------------------------------------------------
def _loop_vertex_material(me):
    """(vertex index, material slot) for every loop of a mesh, vectorised."""
    npoly = len(me.polygons)
    mi, ls, lt = (np.empty(npoly, np.int32) for _ in range(3))
    me.polygons.foreach_get("material_index", mi)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    first = np.repeat(ls, lt)
    step = np.arange(lt.sum()) - np.repeat(np.cumsum(lt) - lt, lt)
    return lv[first + step], np.repeat(mi, lt)


def _geometry(meshes, wheels):
    """Per object: placed points and wheel labels; per material: {label: share of its vertices}."""
    from engine.blender.realism_rig import placed_points
    per_obj, counts = {}, {}
    for o in meshes:
        me = o.data
        if not len(me.vertices) or not len(me.polygons):
            continue
        P = placed_points(o)
        lab = vertex_labels(P, wheels)
        per_obj[o] = (P, lab)
        verts, slots = _loop_vertex_material(me)
        for s, slot in enumerate(o.material_slots):
            m = slot.material
            if m is None:
                continue
            vs = np.unique(verts[slots == s])
            c = counts.setdefault(m, {"_": 0})
            c["_"] += len(vs)
            for name in ("tyre", "rim", "disc", "caliper"):
                c[name] = c.get(name, 0) + int((lab[vs] == name).sum())
    shares = {m: {k: v / max(c["_"], 1) for k, v in c.items() if k != "_" and v} for m, c in counts.items()}
    return per_obj, shares


def _write_wheel_attrs(o, P, lab, wheels):
    """WHEEL_ATTR and REST_ATTR on an object carrying wheel parts (they turn with the wheel_roll spin)."""
    from engine.physics.wheel_mask import _frame, half_width, radial
    on = lab != ""
    near = np.argmin([np.linalg.norm(P - np.asarray(w["center"]), axis=1) for w in wheels], axis=0)
    vec = np.zeros((len(P), 3), np.float32)
    for i, w in enumerate(wheels):
        sel = on & (near == i)
        if not sel.any():
            continue
        ai, _ = _frame(w)
        rho = radial(P[sel], w)
        vec[sel, 0] = rho / w["radius"]
        vec[sel, 1] = (P[sel, ai] - w["center"][ai]) / half_width(w)
        vec[sel, 2] = rho / max(float(rho.max()), 1e-9)
    write_attr(o, WHEEL_ATTR, vec, "FLOAT_VECTOR")
    write_attr(o, REST_ATTR, P, "FLOAT_VECTOR")


def _reassign(o, old, new):
    """Point o's slots holding `old` at `new` (a mesh shared with another object is copied first)."""
    if o.data.users > 1:
        o.data = o.data.copy()
    for slot in o.material_slots:
        if slot.material == old:
            slot.material = new


def _on_wheel(P, w):
    """Most of an object's points in this wheel's tyre band (a tyre object belongs to it)."""
    from engine.physics.wheel_mask import tyre_mask
    return len(P) > 0 and float(tyre_mask(P, w).mean()) >= 0.6


def _bbox(P):
    return P.min(axis=0), P.max(axis=0)


def _inside(inner, outer):
    (lo, hi), (olo, ohi) = inner, outer
    pad = 0.02 * (ohi - olo) + 1e-4
    return bool(np.all(lo >= olo - pad) and np.all(hi <= ohi + pad)) and \
        float(np.prod(np.maximum(hi - lo, 1e-6))) < float(np.prod(np.maximum(ohi - olo, 1e-6)))


# ---- calibrations ------------------------------------------------------------------------------------------------
def lacquer(sh, coords, wet):
    """surface_detail.lacquer :38: orange peel on Coat Normal and a slightly varied coat roughness. A glossy coat
    takes the film's .032-.048; a coat the upload made satin keeps its roughness, varied +/-15%."""
    nt = sh.id_data
    freq, dist, strength = LACQUER_PEEL
    tex = noise(nt, coords, freq)
    bump(sh, tex, dist, strength, "Coat Normal")
    cr = sh.inputs["Coat Roughness"]
    if cr.is_linked:
        return
    lo, hi = LACQUER_ROUGH[wet] if cr.default_value <= 0.1 else (cr.default_value * 0.85, cr.default_value * 1.15)
    nt.links.new(variation(nt, tex, lo, hi), cr)


def metallic_flake(sh, coords):
    """surface_detail.metallic_flake :52: aluminium platelets a few degrees off the panel, under the lacquer."""
    nt = sh.id_data
    cells = nt.nodes.new("ShaderNodeTexVoronoi")
    cells.feature = "F1"
    cells.inputs["Scale"].default_value = FLAKE_SCALE
    nt.links.new(coords, cells.inputs["Vector"])
    tilt = nt.nodes.new("ShaderNodeVectorMath")
    tilt.operation = "SUBTRACT"
    tilt.inputs[1].default_value = (0.5, 0.5, 0.5)
    nt.links.new(cells.outputs["Color"], tilt.inputs[0])
    spread = nt.nodes.new("ShaderNodeVectorMath")
    spread.operation = "SCALE"
    spread.inputs["Scale"].default_value = FLAKE_SPREAD
    nt.links.new(tilt.outputs[0], spread.inputs[0])
    lean = nt.nodes.new("ShaderNodeVectorMath")
    lean.operation = "ADD"
    target = sh.inputs["Normal"]
    base = target.links[0].from_socket if target.is_linked else nt.nodes.new("ShaderNodeNewGeometry").outputs["Normal"]
    nt.links.new(base, lean.inputs[0])
    nt.links.new(spread.outputs[0], lean.inputs[1])
    unit = nt.nodes.new("ShaderNodeVectorMath")
    unit.operation = "NORMALIZE"
    nt.links.new(lean.outputs[0], unit.inputs[0])
    nt.links.new(unit.outputs[0], target)


def _paint(sh, cond):
    """render_materials.py:150-165. The pigment, its maps and the base normal stay the upload's. glTF drops the
    clear coat unless KHR_materials_clearcoat was exported, so a glossy uncoated paint gets its lacquer back."""
    nt = sh.id_data
    set_input(sh, "IOR", 1.5)
    coat, rough = sh.inputs["Coat Weight"], constant_scalar(sh.inputs["Roughness"])
    if not coat.is_linked and coat.default_value < 0.5 and (rough is None or rough < 0.6):
        coat.default_value = 1.0
        sh.inputs["Coat Roughness"].default_value = LACQUER_ROUGH[cond["wet"]][0]
    sh.inputs["Coat IOR"].default_value = 1.5
    if coat.is_linked or coat.default_value <= 0.5:
        return "uncoated"
    metal = constant_scalar(sh.inputs["Metallic"])
    if metal is not None and metal < 0.4:
        set_input(sh, "Specular IOR Level", 0.15)
    lacquer(sh, _placed(nt), cond["wet"])
    if metal is not None and metal >= 0.4 and not sh.inputs["Metallic"].is_linked:
        metallic_flake(sh, _placed(nt))
        return "lacquer+flake"
    return "lacquer"


def _mean_image_luminance(m):
    """Mean luminance of the brightest image the material uses, read from a 32 px copy."""
    lums = []
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image is not None and n.image.has_data and n.image.size[0]:
            small = n.image.copy()
            try:
                small.scale(32, 32)
                px = np.empty(32 * 32 * 4, np.float32)
                small.pixels.foreach_get(px)
                lums.append(float((px.reshape(-1, 4)[:, :3] @ np.array([0.2126, 0.7152, 0.0722])).mean()))
            finally:
                bpy.data.images.remove(small)
    return max(lums) if lums else None


def _carbon(m, sh, cond):
    """render_materials.py:128-149: keep the weave and UVs, bring a viewer-bright weave down to carbon's
    reflectance, dielectric base under a smooth resin coat (the weave's normals are UNDER the resin)."""
    nt = sh.id_data
    base = sh.inputs["Base Color"]
    pig = constant_pigment(base)
    lum = (0.2126 * pig[0] + 0.7152 * pig[1] + 0.0722 * pig[2]) if pig is not None else _mean_image_luminance(m)
    if lum is not None and lum > 0.12:
        k = CARBON_TARGET / lum
        mul = nt.nodes.new("ShaderNodeMixRGB")
        mul.blend_type, mul.inputs[0].default_value = "MULTIPLY", 1.0
        nt.links.new(_src(nt, base), mul.inputs[1])
        t = sum(CARBON_TINT) / 3.0
        mul.inputs[2].default_value = (*(k * c / t for c in CARBON_TINT), 1.0)
        nt.links.new(mul.outputs[0], base)
    set_input(sh, "Metallic", CARBON["metallic"])
    set_input(sh, "Specular IOR Level", CARBON["spec"])
    set_input(sh, "Roughness", CARBON["rough"])
    set_input(sh, "Coat Weight", CARBON["coat"])
    set_input(sh, "Coat Roughness", CARBON["coatRough"][cond["wet"]])
    set_input(sh, "Coat Normal", (0.0, 0.0, 0.0))
    if any(n.type == "TEX_IMAGE" for n in nt.nodes) or sh.inputs["Normal"].is_linked:
        return "resin"
    # No weave in the upload: a 2x2 twill of tows whose sheen alternates direction cell by cell, on the rest
    # position (an aero disc on a wheel turns with it). (eng)
    chk = nt.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 1.0 / WEAVE_TOW       # Cycles checker: a cell per 1 / scale
    rot = nt.nodes.new("ShaderNodeVectorRotate")
    rot.rotation_type = "Z_AXIS"
    rot.inputs["Angle"].default_value = 0.7853982
    nt.links.new(_attr(nt, REST_ATTR), rot.inputs["Vector"])
    nt.links.new(rot.outputs[0], chk.inputs["Vector"])
    fac = chk.outputs["Fac"]
    sh.inputs["Anisotropic"].default_value = WEAVE["anisotropic"]
    nt.links.new(_math(nt, "MULTIPLY", fac, 0.25), sh.inputs["Anisotropic Rotation"])
    shade = nt.nodes.new("ShaderNodeMixRGB")
    shade.blend_type, shade.inputs[0].default_value = "MULTIPLY", 1.0
    nt.links.new(_src(nt, base), shade.inputs[1])
    nt.links.new(variation(nt, fac, *WEAVE["shade"]), shade.inputs[2])
    nt.links.new(shade.outputs[0], base)
    bump(sh, fac, CARBON_WEAVE_HEIGHT, 1.0)              # the tows' relief, under the resin (Normal, not Coat)
    edge_bevel(sh, EDGE_BEVEL_M["carbon"], ("Normal", "Coat Normal"))
    return "resin+twill"


def _thin_sheet(sh, out, tint, rough=GLASS_ROUGH, ior=GLASS_IOR, weight=1.0):
    """surface_detail.thin_lens :98: a thin cover crosses two interfaces, so transmission is (almost) undeviated:
    transparent(tint) mixed with a sharp reflection by 2F/(1+F). `tint` is a colour or a socket."""
    nt = sh.id_data
    fres = nt.nodes.new("ShaderNodeFresnel")
    fres.inputs["IOR"].default_value = ior
    factor = _math(nt, "DIVIDE", _math(nt, "MULTIPLY", fres.outputs[0], 2.0 * weight), _math(nt, "ADD", fres.outputs[0], 1.0))
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    if isinstance(tint, bpy.types.NodeSocket):
        nt.links.new(tint, clear.inputs["Color"])
    else:
        clear.inputs["Color"].default_value = (*tint[:3], 1.0)
    try:
        refl = nt.nodes.new("ShaderNodeBsdfAnisotropic")
    except RuntimeError:
        refl = nt.nodes.new("ShaderNodeBsdfGlossy")
    refl.inputs["Roughness"].default_value = rough
    normal = sh.inputs["Normal"]
    if normal.is_linked:
        nt.links.new(normal.links[0].from_socket, fres.inputs["Normal"])
        nt.links.new(normal.links[0].from_socket, refl.inputs["Normal"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(factor, mix.inputs[0])
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(refl.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return True


def _blend_to_glass(sh):
    """render_materials._blend_to_glass :97: an alpha-faded lens becomes a transmissive cover (tint kept)."""
    a = constant_scalar(sh.inputs["Alpha"])
    t = constant_scalar(sh.inputs["Transmission Weight"])
    if a is None or t is None:
        return False
    if a < 0.999:
        set_input(sh, "Alpha", 1.0)
        set_input(sh, "Transmission Weight", 1.0)
    return constant_scalar(sh.inputs["Transmission Weight"]) >= 0.99


def _lens(m, sh, optic):
    if optic and constant_pigment(sh.inputs["Base Color"]) is not None:
        set_input(sh, "Base Color", OPTIC_CLEAR)       # no smoke tint multiplied through every internal piece
    for k, v in LENS.items():
        set_input(sh, k, v)
    if not _blend_to_glass(sh):
        return "kept"
    pig = constant_pigment(sh.inputs["Base Color"])
    _thin_sheet(sh, _output(m), pig if pig is not None else _src(sh.id_data, sh.inputs["Base Color"]))
    return "thin-cover"


def _window(m, sh):
    """Alpha-blended glazing fades its reflections with its opacity: real glass reflects by Fresnel whatever its
    tint. Keep the see-through amount the upload authored (T = 1 - alpha (1 - tint)) as a thin sheet."""
    a, pig = constant_scalar(sh.inputs["Alpha"]), constant_pigment(sh.inputs["Base Color"])
    t = constant_scalar(sh.inputs["Transmission Weight"])
    if pig is None or a is None:
        return "kept"
    if t is not None and t >= 0.5 and a >= 0.999:
        tint = pig
    else:
        tint = tuple(1.0 - a * (1.0 - c) for c in pig)
    _thin_sheet(sh, _output(m), tint, weight=WINDOW_POLARIZER)
    return "thin-sheet"


def _lamp(sh, kind, cond):
    if not cond["lampsOn"] and (constant_scalar(sh.inputs["Emission Strength"]) or 0.0) <= 0:
        return "off"
    color, strength = LAMP[kind]
    if cond.get("dark"):
        strength *= LAMP_DARK_SCALE
    set_input(sh, "Emission Color", (*color, 1.0))
    set_input(sh, "Emission Strength", strength)
    return "led"


def rubber(sh, coords, wet):
    """surface_detail.rubber :86: micrograin; authored maps take priority."""
    nt = sh.id_data
    set_input(sh, "Metallic", 0.0)                   # rubber is a dielectric (critique mat-v2 #4)
    freq, dist, strength = RUBBER_GRAIN
    tex = noise(nt, coords, freq)
    if not sh.inputs["Normal"].is_linked:
        bump(sh, tex, dist, strength)
    if not sh.inputs["Roughness"].is_linked:
        nt.links.new(variation(nt, tex, *RUBBER_ROUGH[wet]), sh.inputs["Roughness"])
    return tex


def _tyre(sh, cond):
    """rubber + tire_sidewalls :338 (concentric moulding ridges on the sidewall band) + tread differentiation
    (_used_rubber :154: brown antiozonant bloom on the sidewall, a paler scrubbed tread face; plus circumferential
    grooves, eng) + _wet_tire_treatment :191 when wet (road residue, wear, a sheen that fades above the ground).
    Radial and axial position come from WHEEL_ATTR, so all of it turns with a rolling wheel."""
    nt, wet = sh.id_data, cond["wet"]
    rest = _attr(nt, REST_ATTR)
    grain = rubber(sh, rest, wet)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(_attr(nt, WHEEL_ATTR), sep.inputs[0])
    rho, axial = sep.outputs["X"], sep.outputs["Y"]
    lo, hi, freq = SIDEWALL
    band = _math(nt, "MULTIPLY", _math(nt, "GREATER_THAN", rho, lo), _math(nt, "LESS_THAN", rho, hi))
    ridge = _math(nt, "MULTIPLY", _math(nt, "SINE", _math(nt, "MULTIPLY", rho, freq)), band)
    bump(sh, ridge, *SIDEWALL_BUMP[wet])
    color, roughness = sh.inputs["Base Color"], sh.inputs["Roughness"]
    if wet:
        scuff = variation(nt, noise(nt, rest, 38.0, 3.0), 0.04, 0.34)
        _toward_color(nt, color, TYRE_DUST, scuff)
        wear = nt.nodes.new("ShaderNodeMixRGB")
        nt.links.new(scuff, wear.inputs[0])
        nt.links.new(_src(nt, roughness), wear.inputs[1])
        wear.inputs[2].default_value = (0.73, 0.73, 0.73, 1.0)
        nt.links.new(wear.outputs[0], roughness)
        z = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(_placed(nt), z.inputs[0])
        ground = _smooth(nt, z.outputs["Z"], 0.015, 0.23, 0.62, 0.035)
        sheen = _math(nt, "MULTIPLY", ground, variation(nt, grain, *TYRE_WET_SHEEN))
        nt.links.new(sheen, sh.inputs["Coat Weight"])
        # wet patches on the rubber itself, 0.25-0.4, densest near the road (the ground's wetness reaches the tyre)
        r0, r1, freq, cov = TYRE_WET_PATCH
        wetp = _smooth(nt, noise(nt, rest, freq, 3.0), cov, cov + 0.12, 0.0, 1.0)
        wetp = _math(nt, "MULTIPLY", wetp, _math(nt, "MINIMUM", _math(nt, "MULTIPLY", ground, 1.6), 1.0))
        film = nt.nodes.new("ShaderNodeMixRGB")
        nt.links.new(wetp, film.inputs[0])
        nt.links.new(_src(nt, roughness), film.inputs[1])
        nt.links.new(variation(nt, grain, r0, r1), film.inputs[2])
        nt.links.new(film.outputs[0], roughness)
        sh.inputs["Coat IOR"].default_value = 1.333
        sh.inputs["Coat Roughness"].default_value = 0.19
    if cond["outdoor"]:
        patches = variation(nt, noise(nt, rest, 7.0, 2.0), -0.35, 0.75)
        _toward_color(nt, color, BLOOM, patches)
    tread = _smooth(nt, rho, TREAD_BAND[0], TREAD_BAND[1], 0.0, 0.6)
    if cond["outdoor"]:
        _toward_color(nt, color, SCRUB, tread)
        dry = nt.nodes.new("ShaderNodeMapRange")
        nt.links.new(tread, dry.inputs["Value"])
        dry.inputs["From Max"].default_value = 0.6
        nt.links.new(_src(nt, roughness), dry.inputs["To Min"])
        dry.inputs["To Max"].default_value = 0.84
        nt.links.new(dry.outputs[0], roughness)
    centres, width, depth = GROOVES
    groove = None
    for c in centres:
        g = _smooth(nt, _math(nt, "ABSOLUTE", _math(nt, "SUBTRACT", axial, c)), width * 0.5, width * 0.8, 1.0, 0.0)
        groove = g if groove is None else _math(nt, "MAXIMUM", groove, g)
    on_tread = _math(nt, "GREATER_THAN", rho, TREAD_BAND[0])
    bump(sh, _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", groove, on_tread), -1.0), depth, 1.0)
    shade = nt.nodes.new("ShaderNodeMixRGB")
    shade.blend_type, shade.inputs[0].default_value = "MULTIPLY", 1.0
    nt.links.new(_src(nt, color), shade.inputs[1])
    shade.inputs[2].default_value = (TYRE_SHADE, TYRE_SHADE, TYRE_SHADE, 1.0)
    nt.links.new(shade.outputs[0], color)
    set_input(sh, "Specular IOR Level", TYRE_SPECULAR)
    return "tyre+wet" if wet else "tyre"


def _rotor(sh, cond):
    """component_materials.weathered_rotors :17 + _swept_face :61: aggregate grain, dusty unswept lip,
    burnished concentric pad tracks (1D noise along the disc radius, so wear is circular, never blotchy)."""
    nt = sh.id_data
    pig = constant_pigment(sh.inputs["Base Color"])       # the authored disc, before any weathering is chained
    rest = _attr(nt, REST_ATTR)
    tex = noise(nt, rest, 1100.0, 2.0)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    for el, (pos, col) in zip(ramp.color_ramp.elements, ROTOR_RAMP):
        el.position, el.color = pos, (*(min(1.0, c * ROTOR_RAMP_GAIN) for c in col[:3]), 1.0)
    nt.links.new(tex, ramp.inputs[0])
    color = sh.inputs["Base Color"]
    tint = nt.nodes.new("ShaderNodeMixRGB")
    tint.blend_type, tint.inputs[0].default_value = "MULTIPLY", 1.0
    nt.links.new(_src(nt, color), tint.inputs[1])
    nt.links.new(ramp.outputs[0], tint.inputs[2])
    nt.links.new(tint.outputs[0], color)
    ceramic = pig is not None and (0.2126 * pig[0] + 0.7152 * pig[1] + 0.0722 * pig[2]) <= CERAMIC_DISC["lum"]
    nt.links.new(variation(nt, tex, *(CERAMIC_DISC["rough"] if ceramic else ROTOR_ROUGH)), sh.inputs["Roughness"])
    bump(sh, tex, 0.000025, 0.18)
    metal = constant_scalar(sh.inputs["Metallic"])
    if ceramic:              # a dark authored disc is carbon-ceramic: nearly dielectric, darker grey (mat-v2 #4)
        set_input(sh, "Metallic", CERAMIC_DISC["metal"])
        dim = nt.nodes.new("ShaderNodeMixRGB")
        dim.blend_type, dim.inputs[0].default_value = "MULTIPLY", 1.0
        nt.links.new(_src(nt, color), dim.inputs[1])
        k = CERAMIC_DISC["shade"]
        dim.inputs[2].default_value = (k, k, k, 1.0)
        nt.links.new(dim.outputs[0], color)
    elif metal is None or metal < ROTOR_METAL:            # an iron disc keeps its sheen
        set_input(sh, "Metallic", ROTOR_METAL)
    set_input(sh, "Coat Weight", 0.0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(_attr(nt, WHEEL_ATTR), sep.inputs[0])
    r = sep.outputs["Z"]                                  # 0 at the hub .. 1 at the disc's own rim

    def track(freq, detail):
        t = nt.nodes.new("ShaderNodeTexNoise")
        t.noise_dimensions = "1D"
        t.inputs["Scale"].default_value, t.inputs["Detail"].default_value = freq, detail
        nt.links.new(r, t.inputs["W"])
        return t.outputs["Fac"]

    bands, scoring = track(34.0, 3.0), track(420.0, 2.0)
    swept = _smooth(nt, r, 0.955, 0.985, 1.0, 0.0)
    wear = nt.nodes.new("ShaderNodeMapRange")
    for k, v in (("From Min", 0.3), ("From Max", 0.7), ("To Min", 0.62), ("To Max", 1.08)):
        wear.inputs[k].default_value = v
    nt.links.new(bands, wear.inputs["Value"])
    shade = nt.nodes.new("ShaderNodeMixRGB")
    shade.blend_type, shade.inputs[0].default_value = "MULTIPLY", 1.0
    nt.links.new(_src(nt, color), shade.inputs[1])
    nt.links.new(wear.outputs[0], shade.inputs[2])
    nt.links.new(shade.outputs[0], color)
    polish = variation(nt, scoring, *(CERAMIC_DISC["polish"] if ceramic else (0.20, 0.34)))
    mix = nt.nodes.new("ShaderNodeMixRGB")
    nt.links.new(swept, mix.inputs[0])
    nt.links.new(_src(nt, sh.inputs["Roughness"]), mix.inputs[1])
    nt.links.new(polish, mix.inputs[2])
    nt.links.new(mix.outputs[0], sh.inputs["Roughness"])
    bump(sh, scoring, 0.00006, 0.35)
    return "ceramic-rotor" if ceramic else "weathered-rotor"


def rotor_face_normals(o):
    """component_materials.rotor_face_normals :122: hole-wall normals pull flat friction faces into triangular
    dents; give the corners of faces square to the axle their face normal. Vertices and topology untouched."""
    from mathutils import Vector
    offset = rig()[1]
    m = (offset.matrix_world.inverted() @ o.matrix_world).to_3x3()
    corners = [m @ Vector(v) for v in o.bound_box]
    dims = [max(v[i] for v in corners) - min(v[i] for v in corners) for i in range(3)]
    axle = min(range(3), key=lambda i: dims[i])
    if dims[axle] > max(dims) * 0.15:
        return 0
    me = o.data
    normals = [tuple(n.vector) for n in me.corner_normals]
    tr = m.inverted().transposed()
    count = 0
    for face in me.polygons:
        if abs((tr @ face.normal).normalized()[axle]) < 0.999:
            continue
        for li in face.loop_indices:
            normals[li] = tuple(face.normal)
        count += 1
    if count:
        me.normals_split_custom_set(normals)
    return count


def _caliper(sh, cond):
    """component_materials.py:187-204: a caliper is pigment under a clear lacquer, satin here (mat-v2 #4), with
    the cast part's rounded edges."""
    for k, v in CALIPER.items():
        set_input(sh, k, v)
    lacquer(sh, _placed(sh.id_data), cond["wet"])
    edge_bevel(sh, EDGE_BEVEL_M["caliper"], ("Normal", "Coat Normal"))
    return "lacquered-caliper"


def _rim(sh, users):
    """The wheel's own parts apart (critique mat-v2 #4: dark materials collapsed into one charcoal): a dark rim is
    a painted wheel (Metallic 0, satin 0.25-0.35, no coat); a bright metallic part is bare machined metal (centre
    lock, fasteners: Metallic 1, 0.2-0.35); anything between keeps the upload's satin."""
    lum = effective_luminance(sh, users)
    metal = constant_scalar(sh.inputs["Metallic"])
    if lum is None or sh.inputs["Roughness"].is_linked:
        return "satin"
    nt = sh.id_data
    tex = noise(nt, _placed(nt), 900.0, 2.0)
    if lum <= RIM_PAINTED["lum"]:
        set_input(sh, "Metallic", 0.0)
        set_input(sh, "Coat Weight", 0.0)
        nt.links.new(variation(nt, tex, *RIM_PAINTED["rough"]), sh.inputs["Roughness"])
        return "painted-wheel"
    if lum >= RIM_BARE["lum"] and metal is not None and metal >= 0.5:
        set_input(sh, "Metallic", 1.0)
        nt.links.new(variation(nt, tex, *RIM_BARE["rough"]), sh.inputs["Roughness"])
        return "bare-metal"
    return "satin"


def _trim(sh, role):
    """rain_look.car_materials :237-250: satin trim with injection-moulded micrograin, semi-gloss trim."""
    set_input(sh, "Metallic", 0.0)
    if role == "trim-gloss":
        set_input(sh, "Roughness", TRIM_GLOSS)
        return "semi-gloss"
    set_input(sh, "Roughness", TRIM_MATTE)
    set_input(sh, "Coat Weight", 0.0)
    freq, dist, strength = TRIM_GRAIN
    bump(sh, noise(sh.id_data, _placed(sh.id_data), freq), dist, strength)
    edge_bevel(sh, EDGE_BEVEL_M["trim-matte"])
    return "satin-grain"


def _privacy(sh):
    for k, v in PRIVACY.items():
        set_input(sh, k, v)
    return "privacy"


def _mirror(sh):
    for k, v in MIRROR.items():
        set_input(sh, k, v)
    return "silvered"


LETTER_WORDS = (("PERFORMANCE", 0.0, 1, 0.81), ("ROAD TIRE", 3.14159265, -1, 0.89))   # surface_detail.py:265-266
LETTER = {"size": 0.018, "step": 0.042, "extrude": 0.00022, "bevel": 0.00008, "lift": 0.00010}  # :267, :287-291, :308


def molded_lettering(tyre, wheel, wet):
    """surface_detail._molded_tire_letters :239: generic, shallow moulded words (no brand or size claim) on the
    OUTER sidewall of a static car's tyre, each glyph conformed to the sidewall by ray casts. Separate render
    geometry parented to the tyre; the tyre mesh is untouched. Returns the glyph count."""
    import math
    from mathutils import Matrix, Vector
    offset = rig()[1]
    mw = tyre.matrix_world
    inv = mw.inverted()
    nmat = mw.to_3x3().inverted().transposed()
    to_world = offset.matrix_world
    centre_w = to_world @ Vector(wheel["center"])
    axis_w = (to_world.to_3x3() @ Vector(wheel["axis"])).normalized()
    car_w = to_world @ Vector((0.0, 0.0, wheel["center"][2]))
    if (centre_w - car_w).dot(axis_w) < 0:
        axis_w = -axis_w                                   # outward: away from the car's centre line
    centre, outward = inv @ centre_w, (inv.to_3x3() @ axis_w).normalized()
    up = inv.to_3x3() @ Vector((0.0, 0.0, 1.0))
    up -= outward * up.dot(outward)
    if up.length < 0.01:
        return 0
    up.normalize()
    right = up.cross(outward).normalized()
    scale = (inv.to_3x3() @ axis_w).length                 # object units per metre
    radius, reach = wheel["radius"] * scale, 1.3 * wheel.get("width", 0.6 * wheel["radius"]) * scale
    start = 0.65 * wheel.get("width", 0.6 * wheel["radius"]) * scale
    verts, faces = [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for word, a0, direction, frac in LETTER_WORDS:
        for i, ch in enumerate(word):
            if ch == " ":
                continue
            ang = a0 + direction * (i - (len(word) - 1) / 2) * LETTER["step"]
            radial = up * math.cos(ang) + right * math.sin(ang)
            tangent = (right * math.cos(ang) - up * math.sin(ang)) * direction
            origin = centre + radial * radius * frac + outward * start
            hit, loc, nrm, _ = tyre.ray_cast(origin, -outward, distance=reach)
            if not hit or abs(nrm.dot(outward)) < 0.65:      # a sidewall face, whichever way it was wound
                continue
            n_w = (nmat @ (nrm if nrm.dot(outward) > 0 else -nrm)).normalized()
            t_w = (mw.to_3x3() @ tangent).normalized()
            t_w = (t_w - n_w * t_w.dot(n_w)).normalized()
            rot = Matrix((t_w, n_w.cross(t_w).normalized(), n_w)).transposed().to_4x4()
            rot.translation = mw @ loc
            curve = bpy.data.curves.new("valora_prep_glyph", "FONT")
            curve.body, curve.align_x = ch, "CENTER"
            curve.size, curve.extrude = LETTER["size"], LETTER["extrude"]
            curve.bevel_depth, curve.bevel_resolution, curve.resolution_u = LETTER["bevel"], 1, 3
            glyph = bpy.data.objects.new("valora_prep_glyph", curve)
            bpy.context.scene.collection.objects.link(glyph)
            glyph.matrix_world = rot
            ev = glyph.evaluated_get(dg)
            me = ev.to_mesh()
            base = len(verts)
            for v in me.vertices:
                w = rot @ v.co
                local = inv @ w
                o2 = local + outward * (start - (local - centre).dot(outward))
                h2, l2, _n, _ = tyre.ray_cast(o2, -outward, distance=reach)
                if h2:
                    w = mw @ l2 + n_w * (v.co.z + LETTER["lift"])
                verts.append(tuple(w))
            faces.extend(tuple(base + k for k in f.vertices) for f in me.polygons)
            ev.to_mesh_clear()
            bpy.data.objects.remove(glyph, do_unlink=True)
            bpy.data.curves.remove(curve)
    if not verts:
        return 0
    me = bpy.data.meshes.new("valora_prep_lettering")
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new("valora_prep_lettering", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent, ob.matrix_parent_inverse = tyre, mw.inverted()
    mat = bpy.data.materials.get("valora_prep_lettering_rubber")
    if mat is None:                                         # surface_detail.py:324-333
        mat = bpy.data.materials.new("valora_prep_lettering_rubber")
        mat.use_nodes = True
        sh = _principled(mat)
        sh.inputs["Base Color"].default_value = (0.012, 0.012, 0.011, 1.0)
        sh.inputs["Roughness"].default_value = 0.52
        sh.inputs["Coat Weight"].default_value = 0.16 if wet else 0.0
        sh.inputs["Coat Roughness"].default_value = 0.24
        sh.inputs["Coat IOR"].default_value = 1.333
    me.materials.append(mat)
    ob["valora_block"] = "prep/lettering"
    return len(faces)


# ---- road weathering (road_weathering.py) ----------------------------------------------------------------------
def film_mask(wheels, low, rear_end, axis, sign, strength):
    """road_weathering.film_mask :261 in placed metres: sills, a plume trailing each wheel, the tail in the wake.
    axis: the horizontal index along the car; sign: +1/-1 the nose's direction on it (None: plumes both ways)."""
    tree = bpy.data.node_groups.new(FILM_GROUP, "ShaderNodeTree")
    tree.interface.new_socket(name="Film", in_out="OUTPUT", socket_type="NodeSocketFloat")
    xyz = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(_placed(tree), xyz.inputs[0])
    across_i = 1 - axis if axis in (0, 1) else 0
    along_s, across_s, z = xyz.outputs[axis], xyz.outputs[across_i], xyz.outputs[2]
    height = _math(tree, "SUBTRACT", z, low)
    sill = _math(tree, "MULTIPLY", _smooth(tree, height, 0.06, 0.58, 1.0, 0.0), 0.8)
    plume_h = _smooth(tree, height, 0.20, 0.95, 1.0, 0.0)
    plume = None
    for w in wheels:
        for s in ((sign,) if sign else (1, -1)):
            behind = w["center"][axis] - s * 0.62
            along = _math(tree, "MULTIPLY", _math(tree, "SUBTRACT", along_s, behind), 1 / 0.60)
            across = _math(tree, "MULTIPLY", _math(tree, "SUBTRACT", across_s, w["center"][across_i]), 1 / 0.30)
            d = _math(tree, "ADD", _math(tree, "MULTIPLY", along, along), _math(tree, "MULTIPLY", across, across))
            lobe = _math(tree, "EXPONENT", _math(tree, "MULTIPLY", d, -1.0 if sign else -1.6))
            plume = lobe if plume is None else _math(tree, "MAXIMUM", plume, lobe)
    film = sill
    if sign:
        t = _math(tree, "MULTIPLY", along_s, -sign)       # grows toward the rear
        tail = _math(tree, "MULTIPLY", _smooth(tree, t, rear_end - 0.50, rear_end - 0.05, 0.0, 0.75),
                     _smooth(tree, height, 0.15, 0.90, 1.0, 0.0))
        film = _math(tree, "MAXIMUM", film, tail)
    if plume is not None:
        film = _math(tree, "MAXIMUM", film, _math(tree, "MULTIPLY", plume, plume_h))
    stretch = tree.nodes.new("ShaderNodeVectorMath")
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = tuple(1.0 if i == axis else 3.2 for i in range(3))
    tree.links.new(_placed(tree), stretch.inputs[0])
    streaks = tree.nodes.new("ShaderNodeTexNoise")
    streaks.inputs["Scale"].default_value, streaks.inputs["Detail"].default_value = 1.6, 4.0
    streaks.inputs["Roughness"].default_value = 0.6
    tree.links.new(stretch.outputs[0], streaks.inputs["Vector"])
    film = _math(tree, "MULTIPLY", film, _smooth(tree, streaks.outputs["Fac"], 0.34, 0.68, 0.25, 1.0))
    speck = noise(tree, _placed(tree), 60.0, 1.0)
    film = _math(tree, "MULTIPLY", film, _smooth(tree, speck, 0.40, 0.66, 0.65, 1.0))
    film = _math(tree, "MULTIPLY", film, strength, clamp=True)
    out = tree.nodes.new("NodeGroupOutput")
    tree.links.new(film, out.inputs["Film"])
    return tree


def road_film(materials, mask):
    """road_weathering.road_film :355: a grey-brown film that covers, never replaces, the pigment."""
    done = []
    for m in sorted(materials, key=lambda m: m.name):
        sh = _principled(m)
        nt = m.node_tree
        g = nt.nodes.new("ShaderNodeGroup")
        g.node_tree = mask
        film = g.outputs["Film"]
        _toward_color(nt, sh.inputs["Base Color"], FILM_COLOR, _math(nt, "MULTIPLY", film, 0.6))
        _toward_value(nt, sh.inputs["Roughness"], 0.62, film)
        coat = sh.inputs["Coat Weight"]
        if coat.is_linked or coat.default_value > 0.01:
            _toward_value(nt, sh.inputs["Coat Roughness"], 0.32, film)
        done.append(m.name)
    return done


def brake_dust(materials, strength):
    """road_weathering.brake_dust :383: warm-grey dust settling in the barrel and spoke roots (AO cavities)."""
    done = []
    for m in sorted(materials, key=lambda m: m.name):
        nt, sh = m.node_tree, _principled(m)
        settle = _smooth(nt, noise(nt, _attr(nt, REST_ATTR), 28.0, 3.0), 0.35, 0.72, 0.15, 1.0)
        ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
        ao.samples = 8
        ao.inputs["Distance"].default_value = 0.05
        cavity = _smooth(nt, ao.outputs["AO"], 0.35, 0.95, 1.0, 0.30)
        dust = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", settle, cavity), strength, clamp=True)
        _toward_color(nt, sh.inputs["Base Color"], DUST_COLOR, dust)
        _toward_value(nt, sh.inputs["Roughness"], 0.72, dust)
        _toward_value(nt, sh.inputs["Metallic"], 0.15, dust)
        done.append(m.name)
    return done


def _nose(per_obj, roles_of, axis):
    """+1/-1: which way the nose points along `axis`, from where the lamps sit (DRL / covers vs tail);
    None when the upload says nothing trustworthy (GLBs carry no front: ingest measure.py H5)."""
    front, back = [], []
    for o, (P, _lab) in per_obj.items():
        rs = roles_of.get(o, set())
        if rs & {"lamp-drl"}:
            front.append(float(P[:, axis].mean()))
        if rs & {"lamp-tail"}:
            back.append(float(P[:, axis].mean()))
    if not front or not back:
        return None
    d = np.mean(front) - np.mean(back)
    return None if abs(d) < 0.2 else (1 if d > 0 else -1)


# ---- the stage -----------------------------------------------------------------------------------------------------
def _roles(meshes, wheels, painted):
    """(per-object geometry, material -> user objects, material -> role) for the not-yet-prepared materials."""
    per_obj, shares = _geometry(meshes, wheels)
    users = {}
    for o in meshes:
        for slot in o.material_slots:
            if slot.material is not None:
                users.setdefault(slot.material, [])
                if o not in users[slot.material]:
                    users[slot.material].append(o)
    roles = {}
    for m, us in sorted(users.items(), key=lambda kv: kv[0].name):
        if m.get(PREP_KEY) or not m.use_nodes:
            continue
        role = classify(_facts(m, us, shares.get(m, {}), m in painted))
        if role:
            roles[m] = role
    return per_obj, users, roles


def paint_targets(meshes, profile):
    """The materials the classifier calls paint: what a paint override recolours besides the name rule."""
    return [m for m, r in _roles(meshes, list(getattr(profile, "wheels", None) or []), set())[2].items()
            if r == "paint"]


def prepare_subject(meshes, script, profile, painted=(), outdoor=True, moving=False):
    """Calibrate every recognised material of the upload (see the module docstring). Idempotent per material.
    Returns the report compile.json carries as `subjectPrep`."""
    cond = conditions(script, outdoor)
    wheels = list(getattr(profile, "wheels", None) or [])
    per_obj, users, roles = _roles(meshes, wheels, set(painted))
    # object-level refinements: lamp covers vs internal optics, mirrors among the window glass
    boxes = {o: _bbox(per_obj[o][0]) for m, r in roles.items() if r == "lamp-lens" for o in users[m] if o in per_obj}
    final, copies = {}, []
    for m, role in list(roles.items()):
        if role == "lamp-lens":
            optic = [o for o in users[m] if o in boxes and any(q is not o and _inside(boxes[o], boxes[q]) for q in boxes)]
            cover = [o for o in users[m] if o not in optic]
            if optic and cover:
                new = m.copy()
                new.name = "valora_prep_optic"
                for o in optic:
                    _reassign(o, m, new)
                final[new] = ("lamp-optic", optic)
                copies.append(new)
                final[m] = ("lamp-cover", cover)
            else:
                final[m] = ("lamp-optic" if optic else "lamp-cover", users[m])
        elif role == "window-glass":
            mirrors = [o for o in users[m] if "mirror" in tokens(o.name)]
            rest = [o for o in users[m] if o not in mirrors]
            if mirrors and rest:
                new = m.copy()
                new.name = "valora_prep_mirror"
                for o in mirrors:
                    _reassign(o, m, new)
                final[new] = ("mirror", mirrors)
                final[m] = (role, rest)
            else:
                final[m] = ("mirror" if mirrors else role, users[m])
        else:
            final[m] = (role, users[m])
    # attributes the wheel and weave patterns read (rest position turns with the wheel_roll spin)
    need_rest = {o for m, (r, us) in final.items() if r in ("carbon",) for o in us}
    for o, (P, lab) in per_obj.items():
        if (lab != "").any() and wheels:
            _write_wheel_attrs(o, P, lab, wheels)
        elif o in need_rest:
            write_attr(o, REST_ATTR, P, "FLOAT_VECTOR")
    report = []
    film_targets, dust_targets, rotor_faces = [], [], 0
    for m, (role, us) in sorted(final.items(), key=lambda kv: kv[0].name):
        sh = _principled(m)
        if role == "paint":
            how = _paint(sh, cond)
        elif role == "carbon":
            how = _carbon(m, sh, cond)
        elif role == "privacy-glass":
            how = _privacy(sh)
        elif role == "window-glass":
            how = _window(m, sh)
        elif role == "mirror":
            how = _mirror(sh)
        elif role in ("lamp-cover", "lamp-optic"):
            how = _lens(m, sh, role == "lamp-optic")
        elif role in ("lamp-drl", "lamp-tail"):
            how = _lamp(sh, role[5:], cond)
        elif role == "tyre":
            how = _tyre(sh, cond)
        elif role == "rubber":
            rubber(sh, _placed(m.node_tree), cond["wet"])
            how = "grain"
        elif role == "rotor":
            how = _rotor(sh, cond)
            for o in us:
                if o in per_obj and (per_obj[o][1] == "disc").all():
                    rotor_faces += rotor_face_normals(o)
        elif role == "caliper":
            how = _caliper(sh, cond)
        elif role == "rim":
            how = _rim(sh, us)
            if cond["brakeDust"] > 0:
                dust_targets.append(m)
        elif role in ("trim-matte", "trim-gloss"):
            how = _trim(sh, role)
        else:
            continue
        m[PREP_KEY] = role
        if role in ("paint", "carbon", "trim-matte", "trim-gloss") and not interior(m.name, [o.name for o in us]):
            film_targets.append(m)
        report.append({"material": m.name, "role": role, "treatment": how, "users": len(us)})
    film = []
    if cond["roadFilm"] > 0 and film_targets:
        axis = 1
        fwd = (getattr(profile, "vehicle", None) or {}).get("forwardAxis")
        if fwd:
            axis = max((0, 1), key=lambda k: abs(fwd[k]))
        roles_of = {}
        for m, (r, us) in final.items():
            for o in us:
                roles_of.setdefault(o, set()).add(r)
        sign = _nose(per_obj, roles_of, axis)
        lo, hi = list(profile.boundsMin), list(profile.boundsMax)
        rear_end = (-sign * (lo[axis] if sign > 0 else hi[axis])) if sign else 0.0
        mask = film_mask(wheels, lo[2], rear_end, axis, sign, cond["roadFilm"])
        film = road_film(film_targets, mask)
    dust = brake_dust(dust_targets, cond["brakeDust"]) if dust_targets else []
    letters = 0
    if not moving and wheels:            # lettering would not turn with wheel_roll's spin: static cars only
        tyres = {o for m, (r, us) in final.items() if r == "tyre" for o in us}
        for w in wheels:
            best = max((o for o in tyres if o in per_obj and _on_wheel(per_obj[o][0], w)),
                       key=lambda o: len(per_obj[o][0]), default=None)
            if best is not None:
                letters += molded_lettering(best, w, cond["wet"])
    return {"conditions": cond, "materials": report, "roadFilm": film, "brakeDust": dust, "letterFaces": letters,
            "rotorFaces": rotor_faces, "copies": [c.name for c in copies]}
