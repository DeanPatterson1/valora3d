import json
import sys

import bpy
import numpy as np  # bundled with Blender; this file never runs outside Blender

glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)

deps = bpy.context.evaluated_depsgraph_get()
lo = [float("inf")] * 3
hi = [float("-inf")] * 3
polys = 0
areas = {}
for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    mesh.transform(obj.matrix_world)
    for v in mesh.vertices:
        for i in range(3):
            lo[i] = min(lo[i], v.co[i])
            hi[i] = max(hi[i], v.co[i])
    polys += len(mesh.polygons)
    for p in mesh.polygons:
        slot = obj.material_slots[p.material_index] if p.material_index < len(obj.material_slots) else None
        mat = slot.material if slot else None
        key = mat.name if mat else None
        areas[key] = areas.get(key, 0.0) + p.area
    ev.to_mesh_clear()

if polys == 0:
    sys.exit(f"no mesh geometry found in {glb}")

_CHANNEL = {"Red": 0, "Green": 1, "Blue": 2, "R": 0, "G": 1, "B": 2}
_mean_cache = {}


def _image_mean(image, channel):
    """Mean of one channel (0-2) or of RGB luminance (channel=None), on a strided sample."""
    key = (image.name, channel)
    if key not in _mean_cache:
        px = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(px)
        px = px.reshape(-1, 4)[::97]  # ~1% sample is plenty for a mean
        v = px[:, :3].mean(axis=1) if channel is None else px[:, channel]
        _mean_cache[key] = float(v.mean()) if len(v) else 0.0
    return _mean_cache[key]


def _resolve(socket, channel=None, depth=0):
    """Scalar value reaching `socket`: its default, or the mean of the texture behind it.
    glTF imports wire metallicRoughness as Image -> Separate Color (G=roughness, B=metallic),
    sometimes through a Math MULTIPLY holding the factor. Returns None if it can't tell."""
    if depth > 6:
        return None
    if not socket.is_linked:
        v = socket.default_value
        if isinstance(v, (int, float)):
            return float(v)
        return float(sum(v[:3]) / 3)  # colour socket -> brightness
    link = socket.links[0]
    node, out = link.from_node, link.from_socket
    if node.type == "TEX_IMAGE" and node.image is not None and node.image.size[0] > 0:
        return _image_mean(node.image, channel)
    if node.type == "SEPARATE_COLOR":
        return _resolve(node.inputs[0], _CHANNEL.get(out.name), depth + 1)
    if node.type == "MATH" and node.operation == "MULTIPLY":
        vals = [_resolve(i, channel, depth + 1) for i in node.inputs[:2]]
        return None if None in vals else vals[0] * vals[1]
    return None


def _input(node, name, default):
    s = node.inputs.get(name)
    if s is None:
        return default
    v = _resolve(s)
    return default if v is None else v


def _props(mat):
    if mat is None or mat.node_tree is None:
        return {}
    node = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if node is None:
        return {}
    col = node.inputs.get("Emission Color")
    brightness = _resolve(col) if col is not None else 0.0
    emission = _input(node, "Emission Strength", 0.0) * (brightness or 0.0)
    return {
        "metallic": _input(node, "Metallic", 0.0),
        "roughness": _input(node, "Roughness", 0.5),
        "transmission": _input(node, "Transmission Weight", 0.0),
        "emission": emission,
        "subsurface": _input(node, "Subsurface Weight", 0.0),
    }


materials = []
for name, area in areas.items():
    m = bpy.data.materials.get(name) if name else None
    materials.append({"area": area, **_props(m)})

raw = {
    "boundsMin": lo, "boundsMax": hi, "polyCount": polys,
    "rigged": any(o.type == "ARMATURE" for o in bpy.context.scene.objects),
    "animated": any(o.animation_data and o.animation_data.action for o in bpy.context.scene.objects),
    "materials": materials,
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(raw, f)
