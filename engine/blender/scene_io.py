"""The ONE GLB import (runs inside Blender). Ingest and the compiler both use it, with the same
importer settings, so the compiler's placed bounds can equal the SubjectProfile's."""
import bpy


def import_subject(glb):
    """Factory-reset the file, import the GLB, drop any cameras/lights it carried.
    Returns (new_objects, mesh_objects)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.type in ("CAMERA", "LIGHT")]:
        new.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    return new, [o for o in new if o.type == "MESH"]


def world_bounds(meshes, depsgraph):
    """Per-axis (min, max) numpy arrays over evaluated world-space vertices. Ingest and the
    compiler's placement guard (Task 19) share it, so they measure the same thing."""
    import numpy as np
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for obj in meshes:
        ev = obj.evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        n = len(mesh.vertices)
        if n:
            co = np.empty(n * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", co)
            m = np.array(ev.matrix_world, dtype=np.float64)
            w = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
            lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
        ev.to_mesh_clear()
    return lo, hi


def animation_frames(scene, max_n=16):
    """Up to max_n frames spanning every action in the scene, or None if nothing is animated."""
    ranges = [o.animation_data.action.frame_range for o in scene.objects
              if o.animation_data and o.animation_data.action]
    if not ranges:
        return None
    a = int(min(r[0] for r in ranges))
    b = int(max(r[1] for r in ranges) + 0.999)
    n = max(2, min(max_n, b - a + 1))
    return sorted({round(a + (b - a) * k / (n - 1)) for k in range(n)})
