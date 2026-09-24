"""Realise a pure grade plan as a Blender 5 compositor tree (port of render-studio
rain_look.compositor, generalised and no longer rain-gated). Node names are stable ids the
tests and passes code look up.

Blender 5.0 API (probed 2026-09-24): node properties are inputs (Glare/ColorBalance `Type` are
MENU sockets); there is no CompositorNodeMixRGB/Math, so ShaderNodeMix (RGBA) and ShaderNodeMath
are used; IDMask takes `ID value` + INT `Index` and outputs `Alpha`; Blur `Size` is a pixel VECTOR;
AgX looks are named "AgX - ..." (the plan's first candidates)."""
import bpy

SUBJECT_PASS_INDEX = 1
VIGNETTE_SIZE = (1.25, 1.25)   # ellipse relative to the frame (eng)
VIGNETTE_SOFTNESS = 0.18       # blur radius as a fraction of the short side (eng)


def _set_view(scene, plan):
    vs = scene.view_settings
    vs.view_transform = "AgX"
    for look in plan["agxLookCandidates"]:
        try:
            vs.look = look
            break
        except TypeError:
            continue
    # Exposure lives in the "exposure" compositor node (scene-linear, before the view transform);
    # setting it here as well would apply it twice.
    vs.exposure, vs.gamma = 0.0, 1.0


def realise(scene, plan, subject_meshes):
    _set_view(scene, plan)
    scene.view_layers[0].use_pass_object_index = True
    for o in subject_meshes:
        o.pass_index = SUBJECT_PASS_INDEX
    tree = bpy.data.node_groups.new("valora_grade", "CompositorNodeTree")
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = tree
    N, L = tree.nodes, tree.links

    def node(kind, name):
        n = N.new(kind)
        n.name = name
        return n

    def mix_rgba(name, blend="MIX"):
        m = node("ShaderNodeMix", name)
        m.data_type, m.blend_type = "RGBA", blend
        return m, m.inputs["Factor"], m.inputs[6], m.inputs[7], m.outputs[2]  # Factor, A, B, Result (RGBA)

    src = node("CompositorNodeRLayers", "render_layers")
    src.scene = scene
    exposure = node("CompositorNodeExposure", "exposure")
    exposure.inputs["Exposure"].default_value = plan["exposureEv"]
    lgg = node("CompositorNodeColorBalance", "lgg")
    lgg.inputs["Type"].default_value = "Lift/Gamma/Gain"
    for sock, rgb in (("Lift", plan["lift"]), ("Gamma", plan["gamma"]), ("Gain", plan["gain"])):
        next(s for s in lgg.inputs if s.name == sock and s.type == "RGBA").default_value = (*rgb, 1.0)
    idm = node("CompositorNodeIDMask", "subject_mask")
    idm.inputs["Index"].default_value = SUBJECT_PASS_INDEX
    idm.inputs["Anti-Alias"].default_value = True
    sat_s = node("CompositorNodeHueSat", "subject_sat")
    sat_b = node("CompositorNodeHueSat", "background_sat")
    sat_s.inputs["Saturation"].default_value = plan["saturation"] * plan["subjectSat"]
    sat_b.inputs["Saturation"].default_value = plan["saturation"] * plan["backgroundSat"]
    _, sep_fac, sep_a, sep_b, sep_out = mix_rgba("separation_mix")
    bc = node("CompositorNodeBrightContrast", "contrast")
    bc.inputs["Contrast"].default_value = plan["contrast"]
    bloom = node("CompositorNodeGlare", "bloom")
    bloom.inputs["Type"].default_value = "Fog Glow"
    bloom.inputs["Threshold"].default_value = plan["bloom"]["threshold"]
    bloom.inputs["Strength"].default_value = plan["bloom"]["strength"]
    bloom.inputs["Size"].default_value = plan["bloom"]["size"]
    out = node("NodeGroupOutput", "output")

    L.new(src.outputs["Image"], exposure.inputs["Image"])
    L.new(exposure.outputs["Image"], lgg.inputs["Image"])
    L.new(lgg.outputs["Image"], sat_s.inputs["Image"])
    L.new(lgg.outputs["Image"], sat_b.inputs["Image"])
    L.new(src.outputs["Object Index"], idm.inputs["ID value"])
    L.new(idm.outputs["Alpha"], sep_fac)
    L.new(sat_b.outputs["Image"], sep_a)
    L.new(sat_s.outputs["Image"], sep_b)
    L.new(sep_out, bc.inputs["Image"])
    L.new(bc.outputs["Image"], bloom.inputs["Image"])
    tail = bloom.outputs["Image"]

    if plan["halation"]:
        h = plan["halation"]
        hal = node("CompositorNodeGlare", "halation")
        hal.inputs["Type"].default_value = "Fog Glow"
        hal.inputs["Threshold"].default_value = h["threshold"]
        hal.inputs["Strength"].default_value = h["strength"]
        hal.inputs["Size"].default_value = h["size"]
        hal.inputs["Tint"].default_value = (*h["tint"], 1.0)
        L.new(tail, hal.inputs["Image"])
        tail = hal.outputs["Image"]

    # Vignette: 1 inside a soft ellipse, falling off outside; mix toward black by plan["vignette"].
    ell = node("CompositorNodeEllipseMask", "vignette_shape")
    ell.inputs["Mask"].default_value = 0.0
    ell.inputs["Value"].default_value = 1.0
    ell.inputs["Size"].default_value = VIGNETTE_SIZE
    blur = node("CompositorNodeBlur", "vignette_soften")
    px = VIGNETTE_SOFTNESS * min(scene.render.resolution_x, scene.render.resolution_y)
    blur.inputs["Size"].default_value = (px, px)
    amount = node("ShaderNodeMath", "vignette_amount")  # (1 - shape) * vignette = shape * -v + v
    amount.operation = "MULTIPLY_ADD"
    amount.inputs[1].default_value = -plan["vignette"]
    amount.inputs[2].default_value = plan["vignette"]
    _, v_fac, v_a, v_b, v_out = mix_rgba("vignette")
    v_b.default_value = (0.0, 0.0, 0.0, 1.0)
    L.new(ell.outputs["Mask"], blur.inputs["Image"])
    L.new(blur.outputs["Image"], amount.inputs[0])
    L.new(amount.outputs["Value"], v_fac)
    L.new(tail, v_a)
    L.new(v_out, out.inputs["Image"])
    return tree


def describe(scene, tree):
    return {"viewTransform": scene.view_settings.view_transform, "look": scene.view_settings.look,
            "nodes": [n.name for n in tree.nodes],
            "objectIndexPass": bool(scene.view_layers[0].use_pass_object_index),
            "subjectPassIndex": SUBJECT_PASS_INDEX,
            "invalidLinks": [f"{k.from_node.name}.{k.from_socket.name}->{k.to_node.name}.{k.to_socket.name}"
                             for k in tree.links if not k.is_valid or not k.from_socket.enabled]}
