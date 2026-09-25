"""Realise LightSpecs in Blender. K_RADIANCE is (eng): calibrate on golden renders (T3-07, T3-08)."""
import math
import bpy
from mathutils import Vector

from engine.color import kelvin_to_rgb  # scene-linear already: Blender light colours are linear

K_RADIANCE = 200.0   # watts per m^2 of emitter at power 1.0 (eng); constant radiance at any size
WORLD_FILL = 0.5     # world strength at ambient 1.0 (eng)


def _visibility(ob, spec):
    # V-L01 (LightSpec.cameraVisible, default False): invisible to camera rays, still seen in
    # glossy reflections. Never leave Blender's default (camera-visible).
    ob.visible_camera = bool(spec.cameraVisible)
    ob.visible_glossy = True


def area_light(scene, spec, kelvin, ev=0.0):
    ld = bpy.data.lights.new(spec.name, "AREA")
    ld.shape, ld.size, ld.size_y = "RECTANGLE", spec.sizeX, spec.sizeY
    ld.energy = K_RADIANCE * spec.power * spec.sizeX * spec.sizeY * 2.0 ** ev
    ld.color = kelvin_to_rgb(kelvin)
    ob = bpy.data.objects.new(spec.name, ld)
    scene.collection.objects.link(ob)
    ob.location = spec.center
    ob.rotation_euler = Vector(spec.facing).to_track_quat("-Z", "Y").to_euler()  # area lights emit along -Z
    _visibility(ob, spec)
    return ob


def black_card(scene, spec):
    """Negative fill (V-L10): a matte black plane seen only in reflections; casts no shadow."""
    hx, hy = spec.sizeX / 2, spec.sizeY / 2
    me = bpy.data.meshes.new(spec.name)
    me.from_pydata([(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0)], [], [(0, 1, 2, 3)])
    mat = bpy.data.materials.new(spec.name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bsdf.inputs["Roughness"].default_value = 1.0
    me.materials.append(mat)
    ob = bpy.data.objects.new(spec.name, me)
    scene.collection.objects.link(ob)
    ob.location = spec.center
    ob.rotation_euler = Vector(spec.facing).to_track_quat("Z", "Y").to_euler()
    _visibility(ob, spec)
    ob.visible_shadow = False
    return ob


def realise(scene, layout, kelvin, ev=0.0):
    for spec in layout.lights:
        if spec.role == "negfill":
            black_card(scene, spec)
        else:
            area_light(scene, spec, kelvin, ev)
    bg = scene.world.node_tree.nodes.get("valora_world_bg") if scene.world and scene.world.node_tree else None
    if bg is not None:
        bg.inputs["Strength"].default_value = WORLD_FILL * layout.ambient


def link_to(objs, lights, name):
    """Light linking: these lights light only `objs` (the subject), never the set (Blender 5 Cycles)."""
    coll = bpy.data.collections.new(name)
    for o in objs:
        coll.objects.link(o)
    for co in coll.collection_objects:
        co.light_linking.link_state = "INCLUDE"
    for lo in lights:
        lo.light_linking.receiver_collection = coll
    return coll


def facts(objs):
    """Plain facts about the lights a lighting block built (compile.json 'lighting')."""
    out = []
    for o in objs:
        if o.type == "LIGHT":
            f = {"name": o.name, "type": o.data.type, "energy": float(o.data.energy),
                 "color": [round(float(c), 4) for c in o.data.color], "location": list(o.location)}
            if o.data.type == "SUN":
                f["angleDeg"] = round(math.degrees(float(o.data.angle)), 6)
            out.append(f)
        else:
            out.append({"name": o.name, "type": "CARD", "location": list(o.location)})
    return out
