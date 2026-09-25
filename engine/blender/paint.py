"""Apply a validated paint override (engine/paint.py) to the upload's paint materials. Runs inside Blender.

Which materials are paint: the name rule ModVision's render-studio uses (material_classes.classify), the
browser runtime's `mv-unified-paint*` family, plus its `mv-body-paint*` export name. Nothing else is touched.
Each paint material is copied (the copy is named valora_paint_<finish>) and rebuilt the way render-studio
shaded the black rain-film car:
- the pigment is a flat colour under a clear lacquer (Coat Weight 1, IOR 1.5); for a solid finish the base
  keeps Specular IOR Level 0.15, so no broad white base highlight washes a dark pigment into grey primer;
- the lacquer has a faint orange peel (noise on Coat Normal) and a slightly varied coat roughness
  (0.032-0.048), which is what draws long, soft, slightly broken reflections along a panel;
- metallic adds aluminium flake platelets under the lacquer (tilted base normals), satin and matte roughen
  and drop the lacquer."""
import bpy

PAINT_PREFIXES = ("mv-unified-paint", "mv-body-paint")
PEEL_SCALE = 650.0            # orange-peel noise, per metre (render-studio surface_detail.lacquer)
PEEL_BUMP = (0.000012, 0.18)  # bump distance (m) and strength on Coat Normal
FLAKE_SCALE = 3200.0          # flake platelets per metre (render-studio metallic_flake)
FINISH = {                    # finish -> base metallic, base roughness, spec level, coat, coat roughness lo, hi
    "gloss": (0.0, 0.30, 0.15, 1.0, 0.032, 0.048),
    "metallic": (0.6, 0.32, 0.5, 1.0, 0.032, 0.048),
    "satin": (0.0, 0.45, 0.25, 1.0, 0.22, 0.30),
    "matte": (0.0, 0.72, 0.2, 0.0, 0.5, 0.5),
}


def is_paint(name):
    return str(name or "").lower().split(".")[0].startswith(PAINT_PREFIXES)


def _rebuild(mat, paint):
    nt = mat.node_tree
    sh = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if sh is None:
        return False
    metal, rough, spec, coat, clo, chi = FINISH[paint["finish"]]
    for sock in ("Base Color", "Metallic", "Roughness", "Coat Weight", "Coat Roughness", "Coat Normal", "Normal"):
        for link in list(sh.inputs[sock].links):
            nt.links.remove(link)
    sh.inputs["Base Color"].default_value = (*paint["linear"], 1.0)
    sh.inputs["Metallic"].default_value = metal
    sh.inputs["Roughness"].default_value = rough
    sh.inputs["Specular IOR Level"].default_value = spec
    sh.inputs["IOR"].default_value = 1.5
    sh.inputs["Coat Weight"].default_value = coat
    sh.inputs["Coat IOR"].default_value = 1.5
    sh.inputs["Coat Roughness"].default_value = clo
    if coat > 0:
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        peel = nt.nodes.new("ShaderNodeTexNoise")
        peel.name = "valora_paint_orange_peel"
        peel.inputs["Scale"].default_value = PEEL_SCALE
        peel.inputs["Detail"].default_value = 2.0
        nt.links.new(geo.outputs["Position"], peel.inputs["Vector"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Distance"].default_value, bump.inputs["Strength"].default_value = PEEL_BUMP
        nt.links.new(peel.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], sh.inputs["Coat Normal"])
        var = nt.nodes.new("ShaderNodeMapRange")
        var.name = "valora_paint_coat_roughness"
        var.inputs["To Min"].default_value, var.inputs["To Max"].default_value = clo, chi
        nt.links.new(peel.outputs["Fac"], var.inputs["Value"])
        nt.links.new(var.outputs["Result"], sh.inputs["Coat Roughness"])
    if paint["finish"] == "metallic":
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        cells = nt.nodes.new("ShaderNodeTexVoronoi")
        cells.name = "valora_paint_flake"
        cells.inputs["Scale"].default_value = FLAKE_SCALE
        nt.links.new(geo.outputs["Position"], cells.inputs["Vector"])
        tilt = nt.nodes.new("ShaderNodeVectorMath")
        tilt.operation = "SUBTRACT"
        tilt.inputs[1].default_value = (0.5, 0.5, 0.5)
        nt.links.new(cells.outputs["Color"], tilt.inputs[0])
        spread = nt.nodes.new("ShaderNodeVectorMath")
        spread.operation = "SCALE"
        spread.inputs["Scale"].default_value = 0.24
        nt.links.new(tilt.outputs[0], spread.inputs[0])
        lean = nt.nodes.new("ShaderNodeVectorMath")
        lean.operation = "ADD"
        nt.links.new(geo.outputs["Normal"], lean.inputs[0])
        nt.links.new(spread.outputs[0], lean.inputs[1])
        unit = nt.nodes.new("ShaderNodeVectorMath")
        unit.operation = "NORMALIZE"
        nt.links.new(lean.outputs[0], unit.inputs[0])
        nt.links.new(unit.outputs[0], sh.inputs["Normal"])
    return True


def apply_paint(meshes, paint):
    """Rebuild every paint material on the subject meshes; returns a report {materials, finish, color}."""
    if not paint:
        return None
    done = {}
    for ob in meshes:
        for slot in ob.material_slots:
            m = slot.material
            if m is None or not m.use_nodes or not is_paint(m.name):
                continue
            if m.name not in done:
                new = m.copy()
                new.name = f"valora_paint_{paint['finish']}"
                done[m.name] = new if _rebuild(new, paint) else m
            slot.material = done[m.name]
    shaders = {}                              # read back from the built materials, for the tests and the log
    for new in {m.name: m for m in done.values()}.values():
        sh = next((n for n in new.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if sh is not None:
            shaders[new.name] = {
                "baseColor": [round(v, 6) for v in list(sh.inputs["Base Color"].default_value)[:3]],
                "metallic": round(sh.inputs["Metallic"].default_value, 4),
                "specular": round(sh.inputs["Specular IOR Level"].default_value, 4),
                "coat": round(sh.inputs["Coat Weight"].default_value, 4),
                "coatNormal": sh.inputs["Coat Normal"].is_linked,
                "baseLinked": sh.inputs["Base Color"].is_linked}
    return {"materials": sorted(done), "finish": paint["finish"], "color": paint["color"], "shaders": shaders}
