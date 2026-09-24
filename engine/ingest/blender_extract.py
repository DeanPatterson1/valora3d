import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import bpy
import numpy as np  # bundled with Blender; this file never runs outside Blender

from engine.blender.scene_io import animation_frames, import_subject, world_bounds

MAX_MEAN_PIXELS = 4096 * 4096  # larger textures read as "unknown" rather than risk a huge buffer
MAX_SAMPLES = 20000


def _mesh_bounds(mesh):
    """Per-axis (min, max) of a mesh's vertex coordinates, via one foreach_get."""
    co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co.min(axis=0), co.max(axis=0)


_CHANNEL = {"Red": 0, "Green": 1, "Blue": 2, "R": 0, "G": 1, "B": 2}
_mean_cache = {}


def _image_mean(image, channel):
    """Mean of one channel (0-2) or of RGB luminance (channel=None), on a strided sample.
    None for images over MAX_MEAN_PIXELS."""
    w, h = image.size[0], image.size[1]
    if w * h > MAX_MEAN_PIXELS:
        return None  # unknown: averaging it would need a w*h*4 float buffer
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
        "textured": bool(node.inputs.get("Normal") is not None and node.inputs["Normal"].is_linked),
    }


def _poly_rows(mesh, slot_to_global):
    """Rows [x,y,z,nx,ny,nz,area,mat,curv] for every polygon of a world-space mesh copy."""
    n = len(mesh.polygons)
    f64 = lambda k, size: np.empty(size, dtype=np.float64)
    cen, nor, area = f64("c", n * 3), f64("n", n * 3), f64("a", n)
    mesh.polygons.foreach_get("center", cen)
    mesh.polygons.foreach_get("normal", nor)
    mesh.polygons.foreach_get("area", area)
    mi = np.empty(n, dtype=np.int32); mesh.polygons.foreach_get("material_index", mi)
    ltot = np.empty(n, dtype=np.int32); mesh.polygons.foreach_get("loop_total", ltot)
    lv = np.empty(len(mesh.loops), dtype=np.int32); mesh.loops.foreach_get("vertex_index", lv)
    vn = np.empty(len(mesh.vertices) * 3); mesh.vertex_normals.foreach_get("vector", vn)
    nor3, vn3 = nor.reshape(-1, 3), vn.reshape(-1, 3)
    poly_of_loop = np.repeat(np.arange(n), ltot)
    dots = (vn3[lv] * nor3[poly_of_loop]).sum(axis=1)
    curv = 1.0 - np.bincount(poly_of_loop, weights=dots, minlength=n) / np.maximum(ltot, 1)
    gmat = np.array([slot_to_global.get(int(i), -1) for i in range(max(int(mi.max(initial=0)) + 1, 1))])[mi]
    return np.column_stack([cen.reshape(-1, 3), nor3, area, gmat, curv])


class _Reservoir:
    """Streaming area-weighted sampling without replacement (Efraimidis-Spirakis:
    key = log(u)/area, keep the k largest keys), in bounded memory whatever the poly count."""

    def __init__(self, k, seed=0):
        self.k, self.rng = k, np.random.default_rng(seed)
        self.rows, self.keys, self.total_area, self.count = np.empty((0, 9)), np.empty(0), 0.0, 0

    def add(self, rows):
        a = np.maximum(rows[:, 6], 1e-30)
        self.total_area += float(a.sum()); self.count += len(rows)
        keys = np.log(self.rng.random(len(rows))) / a
        rows, keys = np.vstack([self.rows, rows]), np.concatenate([self.keys, keys])
        if len(keys) > self.k:
            keep = np.argpartition(keys, -self.k)[-self.k:]
            rows, keys = rows[keep], keys[keep]
        self.rows, self.keys = rows, keys

    def result(self):
        out = self.rows.copy()
        if self.count > self.k:  # sampled by area: every row now stands for an equal share
            out[:, 6] = self.total_area / len(out)
        return out


def main():
    glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
    objs, meshes = import_subject(glb)

    # Posed bounds: a union over the subject's animation frames (rigs swing out of rest bounds).
    scene = bpy.context.scene
    frames = animation_frames(scene)
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for f in (frames or [scene.frame_current]):
        scene.frame_set(f)
        flo, fhi = world_bounds(meshes, bpy.context.evaluated_depsgraph_get())
        lo, hi = np.minimum(lo, flo), np.maximum(hi, fhi)
    scene.frame_set(frames[0] if frames else scene.frame_current)

    # Samples, materials and parts are taken at the first frame.
    deps = bpy.context.evaluated_depsgraph_get()
    polys = 0
    mat_index = {}  # material name (None = no material) -> stable global index, first sight
    areas = []
    res = _Reservoir(MAX_SAMPLES)
    parts = []

    def gidx(name):
        if name not in mat_index:
            mat_index[name] = len(mat_index)
            areas.append(0.0)
        return mat_index[name]

    for obj in meshes:
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        mesh.transform(obj.matrix_world)
        if len(mesh.polygons):
            slot_to_global = {i: gidx(slot.material.name if slot.material else None)
                              for i, slot in enumerate(obj.material_slots)}
            rows = _poly_rows(mesh, slot_to_global)
            if (rows[:, 7] < 0).any():  # a polygon past the object's slots has no material
                rows[rows[:, 7] < 0, 7] = gidx(None)
            for gi, a in enumerate(np.bincount(rows[:, 7].astype(np.int64), weights=rows[:, 6],
                                               minlength=len(areas))):
                areas[gi] += float(a)
            res.add(rows)
            mlo, mhi = _mesh_bounds(mesh)
            parts.append({"boundsMin": [float(v) for v in mlo], "boundsMax": [float(v) for v in mhi],
                          "polys": len(mesh.polygons)})
        polys += len(mesh.polygons)
        ev.to_mesh_clear()

    if polys == 0:
        sys.exit(f"no mesh geometry found in {glb}")

    materials = []
    for name, gi in mat_index.items():
        m = bpy.data.materials.get(name) if name else None
        materials.append({"area": areas[gi], **_props(m)})

    raw = {
        "boundsMin": [float(v) for v in lo], "boundsMax": [float(v) for v in hi], "polyCount": polys,
        "boundsPosed": frames is not None,
        "rigged": any(o.type == "ARMATURE" for o in scene.objects),
        "animated": any(o.animation_data and o.animation_data.action for o in scene.objects),
        "materials": materials,
        "samples": [[round(float(v), 6) for v in r] for r in res.result()],
        "parts": parts,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(raw, f)


if __name__ == "__main__":
    main()
