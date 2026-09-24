"""Seamless cyclorama sized to the subject and the camera path, plus a two-hemisphere world (V-L06).
Ported from tools/product-render/render_product.py build_cyclorama (:181), which worked at a
1 m subject and one hero camera.

The cove is a full 360 degree revolve (floor, curved cove, wall), not a single back wall: orbit
and reverse-angle shots (script_t3 arc_orbit at -100 deg from the hero) looked past the ends of the
old 60k-wide sweep into the world. Its floor reaches past every camera key and its wall is tall
enough that no keyed frustum sees over it (engine/tests/test_studio_look_blender.py).

The floor is a dielectric (Principled, F0 0.04), not a fixed 30%-weight white glossy mix: that mix
made a 'black' floor 12% mirror against 2% diffuse, so it rendered as the lights it reflected."""
import math

TONES = {"white": 0.8, "grey": 0.18, "black": 0.02}  # albedo (eng)
ROUGH_MATTE, ROUGH_GLOSS = 0.6, 0.15  # floor roughness at floorGloss 0 and 1 (eng)
BEND_K = 9.0      # flat floor radius, x the subject's longest side (the old sweep's bend)
COVE = 5.0 / 9.0  # cove radius, x the flat floor radius (the old sweep's proportion)
CAM_REACH = 1.5   # the floor runs flat to at least 1.5 x the farthest camera's horizontal distance (eng)
WALL_OVER = 2.0   # wall height, x the wall's radius: every sightline below ~63 deg from the centre
SEGS_AROUND, SEGS_COVE = 128, 24


def cyc_dims(k, centre, cameras):
    """(flat floor radius, cove radius, wall height) in metres for a subject of longest side k."""
    reach = max((math.hypot(c[0] - centre[0], c[1] - centre[1]) for c in cameras), default=0.0)
    bend = max(BEND_K * k, CAM_REACH * reach)
    radius = COVE * bend
    return bend, radius, WALL_OVER * (bend + radius)


def _cyc_mesh(bpy, bend, radius, wall_h):
    import bmesh
    prof = [(0.0, 0.0), (0.5 * bend, 0.0), (bend, 0.0)]
    for i in range(1, SEGS_COVE + 1):
        a = (i / SEGS_COVE) * (math.pi / 2)
        prof.append((bend + radius * math.sin(a), radius - radius * math.cos(a)))
    prof.append((bend + radius, wall_h))
    bm = bmesh.new()
    centre = bm.verts.new((0.0, 0.0, 0.0))
    rings = []
    for (rr, z) in prof[1:]:
        rings.append([bm.verts.new((rr * math.cos(2 * math.pi * j / SEGS_AROUND),
                                    rr * math.sin(2 * math.pi * j / SEGS_AROUND), z))
                      for j in range(SEGS_AROUND)])
    n = SEGS_AROUND
    for j in range(n):
        bm.faces.new((centre, rings[0][j], rings[0][(j + 1) % n]))
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(n):
            bm.faces.new((r0[j], r1[j], r1[(j + 1) % n], r0[(j + 1) % n]))
    bm.normal_update()
    me = bpy.data.meshes.new("valora_cyc")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:  # the set faces inward and up, toward the subject
        p.use_smooth = True
    return me


def _cyc_material(bpy, albedo, floor_gloss):
    mat = bpy.data.materials.new("valora_cyc")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (albedo, albedo, albedo, 1.0)
    bsdf.inputs["Roughness"].default_value = ROUGH_MATTE + (ROUGH_GLOSS - ROUGH_MATTE) * floor_gloss
    return mat


def _world(bpy, scene, upper, lower_gain):
    """Upper hemisphere = upper, lower = upper * lowerHemisphereGain (V-L06)."""
    world = bpy.data.worlds.new("valora_world")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.name = "valora_world_bg"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    lo = upper * lower_gain
    mix.inputs["A"].default_value = (lo, lo, lo, 1.0)
    mix.inputs["B"].default_value = (upper, upper, upper, 1.0)
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], gt.inputs[0])
    nt.links.new(gt.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    scene.world = world
    return world


def build(ctx):
    import bpy
    p, prof = ctx.params, ctx.profile
    albedo = TONES[p["tone"]]
    cx, cy, _ = prof.center
    bend, radius, wall_h = cyc_dims(prof.longest, prof.center, ctx.camera_positions)
    ob = bpy.data.objects.new("valora_cyc", _cyc_mesh(bpy, bend, radius, wall_h))
    ctx.scene.collection.objects.link(ob)
    ob.location = (cx, cy, 0.0)
    ob.data.materials.append(_cyc_material(bpy, albedo, p["floorGloss"]))
    _world(bpy, ctx.scene, albedo * 0.5, p["lowerHemisphereGain"])
