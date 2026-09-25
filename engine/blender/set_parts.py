"""Shared set-building helpers for the outdoor worlds (rain_courtyard, night_street, golden_field). Runs
inside Blender. Every object a helper makes is tagged with the calling block's `valora_block`."""
import math

import bpy


def tag(ob, block, ground=False, foliage=False):
    ob["valora_block"] = block
    if ground:
        ob["valora_ground"] = True
    if foliage:
        ob["valora_foliage"] = True
    return ob


def mat(name, colour, rough, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Base Color"].default_value = (*colour, 1.0)
    sh.inputs["Roughness"].default_value = rough
    sh.inputs["Metallic"].default_value = metallic
    return m


def emissive(name, colour, strength):
    """A pure emitter (neon, a lit window, a lamp head): Emission only, so it glows at any exposure."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out, em = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*colour, 1.0)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def mesh(scene, name, block, verts, faces, mats=(), mat_idx=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(m)
    if mat_idx is not None:
        me.polygons.foreach_set("material_index", mat_idx)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return tag(ob, block)


def aabb(verts, faces, lo, hi):
    """Append an axis-aligned box from its min and max corners."""
    k = len(verts)
    verts += [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    faces += [(k, k + 1, k + 3, k + 2), (k + 4, k + 6, k + 7, k + 5), (k, k + 4, k + 5, k + 1),
              (k + 2, k + 3, k + 7, k + 6), (k, k + 2, k + 6, k + 4), (k + 1, k + 5, k + 7, k + 3)]


def quad(verts, faces, corners):
    k = len(verts)
    verts += list(corners)
    faces.append((k, k + 1, k + 2, k + 3))


def asphalt(ob, maps, wetness, name, prefix, tile_m=3.0, wet_darken=0.35, wet_rough=0.7):
    """Poly Haven asphalt_02 (colour, roughness, GL normal) on world-scale UVs, else noise asphalt; wetness
    darkens and smooths it (a damp sheen; wet_surface adds water later). Moved from rain_courtyard (Task 70)."""
    import numpy as np
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    co = np.array([tuple(ob.data.vertices[li.vertex_index].co)[:2] for li in me.loops]) / tile_m
    uv.data.foreach_set("uv", co.astype(np.float32).ravel())
    m = bpy.data.materials.new(name)
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
        noise.inputs["Scale"].default_value = 40.0 / tile_m
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
    dark.name = f"{prefix}_wetness_albedo"
    dark.inputs["Factor"].default_value = 1.0
    k = 1.0 - wet_darken * wetness
    dark.inputs[7].default_value = (k, k, k, 1.0)
    nt.links.new(base, dark.inputs[6])
    nt.links.new(dark.outputs[2], sh.inputs["Base Color"])
    smooth = nt.nodes.new("ShaderNodeMath")
    smooth.operation = "MULTIPLY"
    smooth.name = f"{prefix}_wetness_rough"
    smooth.inputs[1].default_value = 1.0 - wet_rough * wetness
    nt.links.new(rough, smooth.inputs[0])
    nt.links.new(smooth.outputs[0], sh.inputs["Roughness"])
    me.materials.append(m)
    return m


def hue_rgb(hue_deg, sat=1.0, val=1.0):
    """HSV hue (degrees) -> linear-ish RGB for an emitter colour."""
    import colorsys
    return colorsys.hsv_to_rgb((hue_deg % 360.0) / 360.0, sat, val)


def nishita(nt, vector, sun_elevation_deg, sun_rotation_deg=0.0, dust=1.0, air=1.0):
    """A physical sky node (Nishita, or Blender 5's multiple/single-scattering successor), sun disc off.
    Enum identifiers are read from the node, never hardcoded (they change between Blender versions)."""
    sky = nt.nodes.new("ShaderNodeTexSky")
    kinds = [i.identifier for i in sky.bl_rna.properties["sky_type"].enum_items]
    for want in ("NISHITA", "MULTIPLE_SCATTERING", "SINGLE_SCATTERING"):
        if want in kinds:
            sky.sky_type = want
            break
    for attr, val in (("sun_disc", False), ("sun_elevation", math.radians(sun_elevation_deg)),
                      ("sun_rotation", math.radians(sun_rotation_deg)), ("air_density", air),
                      ("dust_density", dust)):
        if hasattr(sky, attr):
            try:
                setattr(sky, attr, val)
            except (TypeError, ValueError):
                pass
    if vector is not None:
        nt.links.new(vector, sky.inputs["Vector"])
    return sky
