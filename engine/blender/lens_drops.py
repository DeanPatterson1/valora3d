"""The lens_drops compositor stage (plan Task 68). Runs inside Blender, after the camera and the grade.

Blender 5.0 compositor (probed 2026-09-25): no CompositorNodeTexture, but shader function nodes run in the
compositor, so the bead field is a ShaderNodeTexVoronoi on CompositorNodeImageCoordinates; Displace takes a
pixel-space Displacement vector; a keyed ShaderNodeValue carries the per-shot factor."""
import bpy

from engine.compiler.tiers import SHUTTER

BEAD_SCALE = 9.0     # (eng) beads across the frame's short side at amount 1 (fewer, larger beads as amount drops)
BEAD_RADIUS = 0.28   # (eng) bead radius as a share of its Voronoi cell
DISPLACE_PX = 22.0   # (eng) refraction offset at a bead's rim, pixels at a 1080 short side
BLUR_PX = 3.0        # (eng) the soft blur inside a bead


def _tree(scene):
    """The compositor tree and the socket that carries the render (the grade's, or a minimal new one)."""
    tree = scene.compositing_node_group
    if tree is None:
        tree = bpy.data.node_groups.new("valora_comp", "CompositorNodeTree")
        tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        scene.compositing_node_group = tree
        rl = tree.nodes.new("CompositorNodeRLayers")
        rl.name, rl.scene = "render_layers", scene
        out = tree.nodes.new("NodeGroupOutput")
        tree.links.new(rl.outputs["Image"], out.inputs[0])
    rl = next(n for n in tree.nodes if n.bl_idname == "CompositorNodeRLayers")
    return tree, rl


def _factor_keys(node, rec):
    """0 until the shot's opening cut subframe, amount inside, 0 after its closing cut; constant between."""
    sock = node.outputs[0]
    first, last, amount = rec["first"], rec["last"], rec["amount"]
    for f, v in ((min(0.0, first - 1.0), 0.0), (first - SHUTTER / 2, amount), (last + SHUTTER / 2, 0.0)):
        sock.default_value = v
        sock.keyframe_insert("default_value", frame=f)
    from engine.blender.realism_rig import fcurves
    curves = [c for c in fcurves(node.id_data.animation_data.action)]
    for c in curves:
        for kp in c.keyframe_points:
            kp.interpolation = "CONSTANT"
    return curves[0]


def apply(scene):
    rec = scene["valora_fx_lens_drops"].to_dict()
    tree, rl = _tree(scene)
    N, L = tree.nodes, tree.links
    src = rl.outputs["Image"]
    targets = [ln.to_socket for ln in list(src.links)]
    short = min(scene.render.resolution_x, scene.render.resolution_y) * scene.render.resolution_percentage / 100.0

    def math(op, a, b=None):
        m = N.new("ShaderNodeMath")
        m.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = float(v)
            else:
                L.new(v, m.inputs[i])
        return m.outputs[0]

    coords = N.new("CompositorNodeImageCoordinates")
    L.new(src, coords.inputs["Image"])
    vor = N.new("ShaderNodeTexVoronoi")
    vor.name = "valora_lens_beads"
    vor.voronoi_dimensions = "3D"
    vor.inputs["Scale"].default_value = BEAD_SCALE * (0.5 + rec["amount"])
    vor.inputs["Randomness"].default_value = 1.0
    off = N.new("ShaderNodeVectorMath")                  # the seed shifts the field
    off.operation = "ADD"
    L.new(coords.outputs["Uniform"], off.inputs[0])
    off.inputs[1].default_value = (rec["seed"] * 0.37, rec["seed"] * 0.61, rec["seed"] * 0.11)
    L.new(off.outputs["Vector"], vor.inputs["Vector"])
    mask = N.new("ShaderNodeMapRange")
    mask.interpolation_type, mask.clamp = "SMOOTHSTEP", True
    L.new(vor.outputs["Distance"], mask.inputs["Value"])
    mask.inputs["From Min"].default_value, mask.inputs["From Max"].default_value = BEAD_RADIUS, 0.8 * BEAD_RADIUS
    bead = mask.outputs["Result"]                        # 1 inside a bead, 0 outside
    # refraction: push each pixel toward its bead's centre (a small inverted lens), strongest at the rim
    dx = N.new("ShaderNodeVectorMath")
    dx.operation = "SUBTRACT"
    L.new(vor.outputs["Position"], dx.inputs[0])
    L.new(off.outputs["Vector"], dx.inputs[1])
    scale = math("MULTIPLY", bead, DISPLACE_PX * short / 1080.0 * BEAD_SCALE)
    disp = N.new("ShaderNodeVectorMath")
    disp.operation = "SCALE"
    L.new(dx.outputs["Vector"], disp.inputs[0])
    L.new(scale, disp.inputs["Scale"])
    dn = N.new("CompositorNodeDisplace")
    L.new(src, dn.inputs["Image"])
    L.new(disp.outputs["Vector"], dn.inputs["Displacement"])
    blur = N.new("CompositorNodeBlur")
    L.new(dn.outputs["Image"], blur.inputs["Image"])
    blur.inputs["Size"].default_value = (BLUR_PX * short / 1080.0, BLUR_PX * short / 1080.0)
    factor = N.new("ShaderNodeValue")
    factor.name = "valora_lens_factor"
    curve = _factor_keys(factor, rec)
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.name = "valora_lens_mix"
    L.new(math("MULTIPLY", bead, factor.outputs[0]), mix.inputs["Factor"])
    L.new(src, mix.inputs[6])
    L.new(blur.outputs["Image"], mix.inputs[7])
    for t in targets:
        L.new(mix.outputs[2], t)
    mid_in = (rec["first"] + rec["last"]) / 2.0
    return {**rec, "factorInside": float(curve.evaluate(mid_in)), "factorBefore": float(curve.evaluate(rec["first"] - 1.0)),
            "factorAfter": float(curve.evaluate(rec["last"] + 1.0)), "targets": len(targets)}
