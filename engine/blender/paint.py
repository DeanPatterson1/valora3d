"""Apply a validated paint override (engine/paint.py) to the upload's paint materials. Runs inside Blender.

Recolour only (realism pass 2026-09-25). The override chooses the pigment and the finish; it no longer builds the
lacquer itself. Finish calibration - the orange-peel lacquer, varied coat roughness and metallic flakes, ported
from render-studio - is the subject preparation stage (engine/blender/subject_prep.py), which runs right after
this on every paint, overridden or not, so a recoloured car and an uploaded one get the same clear coat.

Which materials are paint: subject_prep's classifier (a paint word with the guards), the browser runtime's
`mv-unified-paint*` family and its `mv-body-paint*` export name. Each is copied (valora_paint_<finish>); the copy
takes the flat pigment and the finish's base values. The upload's base normal is kept."""
import bpy

PAINT_PREFIXES = ("mv-unified-paint", "mv-body-paint")
FINISH = {                    # finish -> base metallic, base roughness, spec level, coat, coat roughness
    "gloss": (0.0, 0.30, 0.15, 1.0, 0.032),
    "metallic": (0.6, 0.32, 0.5, 1.0, 0.032),
    "satin": (0.0, 0.45, 0.25, 1.0, 0.26),
    "matte": (0.0, 0.72, 0.2, 0.0, 0.5),
}


def is_paint(name):
    return str(name or "").lower().split(".")[0].startswith(PAINT_PREFIXES)


def _set(sh, sock, value):
    nt = sh.id_data
    for link in list(sh.inputs[sock].links):
        nt.links.remove(link)
    sh.inputs[sock].default_value = value


def _recolour(mat, paint):
    sh = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if sh is None:
        return False
    metal, rough, spec, coat, coat_rough = FINISH[paint["finish"]]
    _set(sh, "Base Color", (*paint["linear"], 1.0))
    _set(sh, "Metallic", metal)
    _set(sh, "Roughness", rough)
    _set(sh, "Specular IOR Level", spec)
    _set(sh, "Coat Weight", coat)
    _set(sh, "Coat Roughness", coat_rough)
    sh.inputs["IOR"].default_value = 1.5
    sh.inputs["Coat IOR"].default_value = 1.5
    return True


def apply_paint(meshes, paint, targets=()):
    """Recolour every paint material on the subject meshes (name rule, plus `targets`: materials the subject
    preparation classifier calls paint). Returns (report {materials, finish, color}, the recoloured copies)."""
    if not paint:
        return None, []
    targets = set(targets)
    done = {}
    for ob in meshes:
        for slot in ob.material_slots:
            m = slot.material
            if m is None or not m.use_nodes or not (is_paint(m.name) or m in targets):
                continue
            if m.name not in done:
                new = m.copy()
                new.name = f"valora_paint_{paint['finish']}"
                done[m.name] = new if _recolour(new, paint) else m
            slot.material = done[m.name]
    copies = [m for m in {m.name: m for m in done.values()}.values() if m.name.startswith("valora_paint_")]
    return {"materials": sorted(done), "finish": paint["finish"], "color": paint["color"]}, copies


def _pigment(socket):
    """The constant pigment under any chain the preparation inserted in front of it (road film mixes)."""
    seen = 0
    while socket.is_linked and seen < 16:
        node = socket.links[0].from_node
        if node.type == "RGB":
            return list(node.outputs[0].default_value)[:3]
        if node.type in ("MIX_RGB", "MIX") and len(node.inputs) > 1:
            socket = next((s for s in node.inputs if s.name in ("Color1", "A") and s.type == "RGBA"), node.inputs[1])
            seen += 1
            continue
        return None
    return list(socket.default_value)[:3] if not socket.is_linked else None


def paint_readback(copies):
    """The finished paint shaders (after preparation), for compile.json and the tests."""
    shaders = {}
    for new in copies:
        sh = next((n for n in new.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if sh is None:
            continue
        pig = _pigment(sh.inputs["Base Color"])
        shaders[new.name] = {
            "baseColor": [round(v, 6) for v in pig] if pig is not None else None,
            "metallic": round(sh.inputs["Metallic"].default_value, 4),
            "specular": round(sh.inputs["Specular IOR Level"].default_value, 4),
            "coat": round(sh.inputs["Coat Weight"].default_value, 4),
            "coatNormal": sh.inputs["Coat Normal"].is_linked,
            "flakes": any(n.type == "TEX_VORONOI" for n in new.node_tree.nodes),
            "baseLinked": pig is None}
    return shaders
