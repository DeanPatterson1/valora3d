import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import bpy
import numpy as np  # bundled with Blender; this file never runs outside Blender

from engine.blender.scene_io import import_subject, posed_bounds

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


def _poly_curvature(mesh, pi):
    """Curvature proxy for polygon pi: 1 - mean(vertex normal . face normal) over its corners.
    Vertex normals are the mesh's smooth ones, so this reads ~0 on flat faces and grows where the
    surface bends between neighbouring faces. It also reads ~0 on split hard edges (a seam, or
    an importer's split normals, gives each side its own vertices with face-aligned normals),
    so a crisp crease can score as flat. Accepted: it only ranks detail candidates."""
    poly = mesh.polygons[pi]
    nrm = poly.normal
    vns = mesh.vertex_normals
    dots = [vns[mesh.loops[li].vertex_index].vector.dot(nrm) for li in poly.loop_indices]
    return 1.0 - sum(dots) / max(len(dots), 1)


def _eval_mesh(obj, deps):
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    mesh.transform(obj.matrix_world)
    mesh.calc_loop_triangles()
    return ev, mesh


def surface_samples(meshes, deps, gidx_of, k=MAX_SAMPLES, seed=0):
    """True area sampling WITH replacement: k points, each on a triangle picked with probability
    area/total, at a uniform random point inside it. Every row then stands for the same area,
    total/k, so a material's sample share estimates its area share (sampling without
    replacement over polygons had made it a polygon-count share).

    Rows are [x, y, z, nx, ny, nz, w, mat, curv] in world space; mat = gidx_of(obj, slot).
    Also returns per-object info {polys, lo, hi, matArea: {gidx: area}} in `meshes` order.
    Memory: pass 1 keeps one float64 area array per object; pass 2 re-evaluates each object and
    reads only the triangles it drew. Deterministic: seed, and objects drawn in name order."""
    info, tri_areas = [], {}
    for obj in meshes:
        ev, mesh = _eval_mesh(obj, deps)
        nt = len(mesh.loop_triangles)
        rec = {"polys": len(mesh.polygons), "matArea": {}}
        if len(mesh.polygons):
            rec["lo"], rec["hi"] = _mesh_bounds(mesh)
        if nt:
            ar = np.empty(nt, dtype=np.float64); mesh.loop_triangles.foreach_get("area", ar)
            mi = np.empty(nt, dtype=np.int32); mesh.loop_triangles.foreach_get("material_index", mi)
            table = np.array([gidx_of(obj, i) for i in range(int(mi.max()) + 1)], dtype=np.int64)
            per = np.bincount(table[mi], weights=ar)
            rec["matArea"] = {int(g): float(v) for g, v in enumerate(per) if v > 0 or g in table}
            tri_areas[obj.name] = ar
        info.append(rec)
        ev.to_mesh_clear()

    names = sorted(tri_areas)
    totals = np.array([tri_areas[n].sum() for n in names])
    total = float(totals.sum())
    if total <= 0 or k <= 0:
        return np.empty((0, 9)), info
    rng = np.random.default_rng(seed)
    per_obj = rng.multinomial(k, totals / total)
    by_name = {o.name: o for o in meshes}
    rows = []
    for name, kn in zip(names, per_obj):
        if kn == 0:
            continue
        ar = tri_areas[name]
        counts = rng.multinomial(int(kn), ar / ar.sum())
        tris = np.nonzero(counts)[0]
        obj = by_name[name]
        ev, mesh = _eval_mesh(obj, deps)
        # A mirroring (negative-determinant) matrix_world reverses winding: normals come out inward.
        flip = -1.0 if np.linalg.det(np.array(obj.matrix_world, dtype=np.float64)[:3, :3]) < 0 else 1.0
        slots = {}
        for ti in tris:
            lt = mesh.loop_triangles[int(ti)]
            va, vb, vc = (np.array(mesh.vertices[v].co, dtype=np.float64) for v in lt.vertices)
            n = np.array(lt.normal, dtype=np.float64) * flip
            if lt.material_index not in slots:
                slots[lt.material_index] = gidx_of(obj, lt.material_index)
            curv = _poly_curvature(mesh, lt.polygon_index)
            c = int(counts[ti])
            uv = rng.random((c, 2))
            fold = uv.sum(axis=1) > 1
            uv[fold] = 1 - uv[fold]
            pts = va + uv[:, :1] * (vb - va) + uv[:, 1:] * (vc - va)
            for p in pts:
                rows.append([p[0], p[1], p[2], n[0], n[1], n[2], 0.0, slots[lt.material_index], curv])
        ev.to_mesh_clear()
    out = np.array(rows, dtype=np.float64)
    out[:, 6] = total / k
    return out, info


# The macro camera's reach around a detail normal: azimuth/elevation offsets (defaults 20/10 deg,
# t3_attempt uses -25) plus a lateral slide of up to 0.3 x distance. 40 deg covers the defaults.
OPEN_CONE_DEG = (0.0, 20.0, 40.0)
OPEN_RING = 6  # directions per non-zero cone angle


def _cone(n):
    """Unit directions: n itself, then OPEN_RING evenly spaced at each non-zero OPEN_CONE_DEG."""
    n = n / np.linalg.norm(n)
    a = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(n, a); u /= np.linalg.norm(u)
    v = np.cross(n, u)
    out = []
    for deg in OPEN_CONE_DEG:
        t = np.radians(deg)
        for k in range(OPEN_RING if deg else 1):
            phi = 2 * np.pi * k / OPEN_RING
            out.append(np.cos(t) * n + np.sin(t) * (np.cos(phi) * u + np.sin(phi) * v))
    return out


def openness(samples, meshes, deps, lo, hi):
    """Per sample, the share of its camera cone (OPEN_CONE_DEG around its normal) from which a
    camera outside the subject sees it: a ray from the sample must leave the subject's bounds
    without hitting the subject, and must not reach the floor (the bounds' bottom, where placement
    puts z = 0) within the subject's radius, where no camera stands. Samples on a surface inside a
    cavity, a wheel arch or a closed part read 0."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for obj in meshes:
        ev, mesh = _eval_mesh(obj, deps)  # already world space
        base = len(verts)
        verts += [v.co.copy() for v in mesh.vertices]
        polys += [[base + i for i in p.vertices] for p in mesh.polygons]
        ev.to_mesh_clear()
    out = np.zeros(len(samples))
    if not polys:
        return out
    bvh = BVHTree.FromPolygons(verts, polys)
    lo, hi = np.asarray(lo, dtype=np.float64), np.asarray(hi, dtype=np.float64)
    diag = float(np.linalg.norm(hi - lo))
    reach, eps = 0.5 * diag, 1e-5 * diag + 1e-9
    for i, r in enumerate(samples):
        p, n = np.asarray(r[:3], dtype=np.float64), np.asarray(r[3:6], dtype=np.float64)
        if not np.linalg.norm(n) > 0:
            continue
        o = p + n / np.linalg.norm(n) * eps
        dirs = _cone(n)
        clear = 0
        for d in dirs:
            if d[2] < 0 and max(0.0, o[2] - lo[2]) / -d[2] < reach:
                continue  # the camera would stand at or under the floor
            if bvh.ray_cast(Vector(o), Vector(d), 2.0 * diag)[0] is None:
                clear += 1
        out[i] = clear / len(dirs)
    return out


def main():
    glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
    objs, meshes = import_subject(glb)

    # Posed bounds: a union over every animation clip's key poses (rigs swing out of rest bounds).
    scene = bpy.context.scene
    lo, hi, posed, animated = posed_bounds(scene, meshes)

    # Samples, materials and parts are taken at the scene's current frame.
    deps = bpy.context.evaluated_depsgraph_get()
    mat_index = {}  # material name (None = no material) -> stable global index, first sight

    def gidx_of(obj, slot):
        slots = obj.material_slots
        name = slots[slot].material.name if slot < len(slots) and slots[slot].material else None
        if name not in mat_index:
            mat_index[name] = len(mat_index)
        return mat_index[name]

    samples, info = surface_samples(meshes, deps, gidx_of)
    if len(samples):  # column 9: which samples a camera can see (detail points need it)
        samples = np.column_stack([samples, openness(samples, meshes, deps, lo, hi)])
    polys = sum(r["polys"] for r in info)
    if polys == 0:
        sys.exit(f"no mesh geometry found in {glb}")

    areas = [0.0] * len(mat_index)
    for r in info:
        for gi, a in r["matArea"].items():
            areas[gi] += a
    materials = []
    for name, gi in mat_index.items():
        m = bpy.data.materials.get(name) if name else None
        materials.append({"area": areas[gi], **_props(m)})
    parts = [{"boundsMin": [float(v) for v in r["lo"]], "boundsMax": [float(v) for v in r["hi"]],
              "polys": r["polys"]} for r in info if r["polys"]]

    raw = {
        "boundsMin": [float(v) for v in lo], "boundsMax": [float(v) for v in hi], "polyCount": polys,
        "boundsPosed": posed,
        "rigged": any(o.type == "ARMATURE" for o in scene.objects),
        "animated": animated,
        "materials": materials,
        # Area (col 6) keeps 6 significant digits: 6 decimals would zero every sample of a
        # small model (a pocket watch's polygons are well under 1e-6 m^2).
        "samples": [[float(f"{v:.6g}") if i == 6 else round(float(v), 6) for i, v in enumerate(r)]
                    for r in samples],
        "parts": parts,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(raw, f)


if __name__ == "__main__":
    main()
