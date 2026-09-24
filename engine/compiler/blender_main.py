"""Runs INSIDE Blender. Builds the scene for an already-checked script and renders the requested
frames. Launch only through engine/compiler/run.py, which runs the checker first."""
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))  # phase-1 carry-forward: the engine package is importable here

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from engine.blender.scene_io import import_subject, world_bounds  # noqa: E402
from engine.catalog import Catalog  # noqa: E402
from engine.compiler.context import BuildContext, block_seed, hero_pose  # noqa: E402
from engine.compiler.tiers import SHUTTER, TIERS, resolution  # noqa: E402
from engine.compiler.timeline import camera_keys, frame_count  # noqa: E402
from engine.geometry import camera_matrix  # noqa: E402
from engine.profile import SubjectProfile  # noqa: E402

PLACEMENT_TOL = 1e-4  # of the subject's longest side


def place_subject(objs, profile):
    """placed = (v - (sourceCenter.xy, sourceMinZ)) * scaleFactor, as a root empty's transform."""
    root = bpy.data.objects.new("valora_subject", None)
    bpy.context.scene.collection.objects.link(root)
    for o in objs:
        if o.parent is None:
            o.parent = root  # parent inverse stays identity, so the root transform applies as-is
    f, c = profile.scaleFactor, profile.sourceCenter
    root.scale = (f, f, f)
    root.location = (-c[0] * f, -c[1] * f, -profile.sourceMinZ * f)
    bpy.context.view_layer.update()
    return root


def assert_placement(meshes, profile):
    lo, hi = world_bounds(meshes, bpy.context.evaluated_depsgraph_get())
    got = [float(v) for v in list(lo) + list(hi)]
    want = list(profile.boundsMin) + list(profile.boundsMax)
    tol = PLACEMENT_TOL * max(profile.sizeM) + 1e-6
    if profile.boundsPosed:  # this pose must fit inside the union over all poses
        ok = all(g >= w - tol for g, w in zip(got[:3], want[:3])) and all(g <= w + tol for g, w in zip(got[3:], want[3:]))
    else:
        ok = all(abs(g - w) <= tol for g, w in zip(got, want))
    if not ok:
        raise SystemExit(f"placement mismatch: got {got}, profile says {want}")
    return got


def _fcurves(action):
    """F-curves of an action, for both Blender 5 layered actions and legacy ones
    (ported from render-studio film_camera.animate)."""
    if hasattr(action, "layers"):
        return [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves]
    return list(action.fcurves)


def build_camera(scene, keys, profile):
    data = bpy.data.cameras.new("valora_camera")
    data.sensor_fit, data.sensor_width = "AUTO", 36.0  # = geometry.SENSOR_MM on the long side
    data.dof.use_dof = True
    data.clip_start = max(1e-4, 0.005 * profile.radius)
    data.clip_end = 400.0 * profile.radius
    cam = bpy.data.objects.new("valora_camera", data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    prev = None
    for k in keys:
        eul = Matrix(camera_matrix(k.pose)).to_euler("XYZ", prev) if prev else Matrix(camera_matrix(k.pose)).to_euler("XYZ")
        prev = eul  # compatible Euler: no 360-degree flips between keys (they would smear motion blur)
        cam.location, cam.rotation_euler = k.pose.position, eul
        data.lens, data.dof.focus_distance, data.dof.aperture_fstop = k.pose.lens_mm, k.focusM, k.fstop
        cam.keyframe_insert("location", frame=k.frame)
        cam.keyframe_insert("rotation_euler", frame=k.frame)
        for path in ("lens", "dof.focus_distance", "dof.aperture_fstop"):
            data.keyframe_insert(data_path=path, frame=k.frame)
    for owner in (cam, data):  # dense keys already carry the easing; linear stops overshoot at cuts
        for curve in _fcurves(owner.animation_data.action):
            for kp in curve.keyframe_points:
                kp.interpolation = "LINEAR"
    return cam


def setup_timing(scene, script, tier):
    fmt = script["format"]
    scene.render.fps, scene.render.fps_base = fmt["fps"], 1.0
    scene.frame_start, scene.frame_end = 1, frame_count(fmt)
    scene.render.resolution_x, scene.render.resolution_y = resolution(fmt["aspect"], TIERS[tier]["shortSide"])
    scene.render.resolution_percentage = 100
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = SHUTTER
    scene.render.motion_blur_position = "CENTER"


def probe(scene, cam, frames, profile):
    from bpy_extras.object_utils import world_to_camera_view
    from engine.geometry import box_corners
    out = {}
    for f in frames:
        scene.frame_set(f)
        corners = [list(world_to_camera_view(scene, cam, Vector(c)))
                   for c in box_corners(profile.boundsMin, profile.boundsMax)]
        out[str(f)] = {"corners": corners, "lens": cam.data.lens, "focus": cam.data.dof.focus_distance}
    return out


def _refs(script):
    yield "world", script["world"]
    yield "motion", script["subject"]["motion"]
    yield "lighting", script["lighting"]
    for fx in script.get("effects", []):
        yield "effect", fx


def _ctx(scene, script, profile, catalog, root, meshes, keys, hero, kind, ref):
    seed = block_seed(script["seed"], kind, ref["id"])
    return BuildContext(scene, profile, script, ref["params"], seed, random.Random(seed), root, meshes,
                        hero, [k.pose.position for k in keys], catalog)


def build_all(scene, script, profile, catalog, root, meshes, keys, skip_kinds):
    """World, subject motion, lighting, effects in spec §4.5 order. Cameras are the compiler's own."""
    hero = hero_pose(script, profile, catalog)
    built = []
    for kind, ref in _refs(script):
        if kind in skip_kinds:
            continue
        catalog.load_builder(kind, ref["id"])(_ctx(scene, script, profile, catalog, root, meshes, keys, hero, kind, ref))
        built.append(f"{kind}:{ref['id']}")
    return built, hero


def main():
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    out = Path(job["out"])
    profile = SubjectProfile.from_dict(job["profile"])
    objs, meshes = import_subject(job["model"])
    root = place_subject(objs, profile)
    result = {"blender": bpy.app.version_string, "placedBounds": assert_placement(meshes, profile)}
    scene, script, catalog = bpy.context.scene, job["script"], Catalog.load()
    keys = camera_keys(script, profile, catalog)
    setup_timing(scene, script, job["tier"])
    skip = tuple(job.get("skipKinds", ()))
    if job.get("buildBlocks", True):
        result["built"], hero = build_all(scene, script, profile, catalog, root, meshes, keys, skip)
    cam = build_camera(scene, keys, profile)
    result["shutter"], result["frameEnd"] = scene.render.motion_blur_shutter, scene.frame_end
    if job.get("probe"):
        result["probe"] = probe(scene, cam, job["probe"], profile)
    result["objects"] = [{"name": o.name, "type": o.type, "location": list(o.location),
                          "visibleCamera": o.visible_camera, "visibleGlossy": o.visible_glossy}
                         for o in scene.objects]
    haze = scene.get("valora_haze_domain")
    if haze is not None:
        result["hazeDomain"] = [[float(v) for v in corner] for corner in haze]
    result["cameraPositions"] = [list(k.pose.position) for k in keys]
    # Task 24: passes and render.
    if job.get("saveBlend"):
        bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"))
    (out / "compile.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
