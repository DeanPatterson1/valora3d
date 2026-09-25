"""Runs INSIDE Blender. Builds the scene for an already-checked script and renders the requested
frames. Launch only through engine/compiler/run.py, which runs the checker first."""
import json
import math
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))  # phase-1 carry-forward: the engine package is importable here

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from engine.blender.realism_rig import build_rig, fcurves as _fcurves, motion_track, records  # noqa: E402
from engine.blender.render import add_passes, gloss_pass_indices, render_frames, setup_cycles  # noqa: E402
from engine.blender.scene_io import import_subject, rest_animation, world_bounds  # noqa: E402
from engine.catalog import Catalog  # noqa: E402
from engine.compiler.context import BuildContext, block_seed, hero_pose  # noqa: E402
from engine.compiler.tiers import SHUTTER, TIERS, resolution  # noqa: E402
from engine.compiler.timeline import camera_keys, frame_count  # noqa: E402
from engine.geometry import camera_matrix, mist_far  # noqa: E402
from engine.motion_path import is_moving, pivot as motion_pivot, rotate, subject_pose  # noqa: E402
from engine.physics import events  # noqa: E402
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


CLEAR_CLIP = 10.0      # the nearest surface must be > 10 x clip_start ...
CLEAR_APERTURE = 0.25  # ... and the lens disc (thin-lens DoF samples it) < 1/4 of that distance
TARGET_TOL = 0.05      # a detail target is hidden if the view ray hits geometry > 5% short of it
INSIDE_DIRS = ((0.3, 0.2, 1.0), (1.0, -0.4, 0.1), (-0.5, 1.0, -0.2))


def _subject_bvh(meshes, local_to=None):
    """One world-space BVH over the placed subject's evaluated meshes, or, with local_to (an object), one in
    that object's local space. The inverse comes from the SAME evaluated depsgraph as the meshes (review
    chunk1 #3): an original object's matrix_world can be stale right after its keys were inserted."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    space = None if local_to is None else local_to.evaluated_get(dg).matrix_world.inverted()
    verts, polys = [], []
    for o in meshes:
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        base = len(verts)
        mw = eo.matrix_world if space is None else space @ eo.matrix_world
        verts += [mw @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        eo.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def _crossings(bvh, p, d, limit):
    n, o = 0, p.copy()
    for _ in range(256):
        loc, _nrm, _i, dist = bvh.ray_cast(o, d, limit)
        if loc is None:
            return n
        n, o = n + 1, loc + d * max(1e-7, 1e-6 * dist)
    return n


def _motion_matrix(frame):
    """valora_motion's transform at a (fractional) frame, from its F-curves (no depsgraph, no frame_set)."""
    from engine.blender.realism_rig import rig
    motion = rig()[0]
    ad = motion.animation_data
    curves = {(c.data_path, c.array_index): c for c in _fcurves(ad.action)} if ad and ad.action else {}
    ev = lambda path, i, d: float(curves[(path, i)].evaluate(frame)) if (path, i) in curves else float(d)  # noqa: E731
    loc = [ev("location", i, motion.location[i]) for i in range(3)]
    rot = [ev("rotation_euler", i, motion.rotation_euler[i]) for i in range(3)]
    from mathutils import Euler
    return Matrix.Translation(loc) @ Euler(rot, "XYZ").to_matrix().to_4x4()


def camera_clearance(keys, meshes, cam, profile, moving=False):
    """Every camera key must sit outside the subject with room for its lens, and a detail shot must
    see its target. The checker only knows the bounding box; this is the mesh-level guard.
    moving: the BVH is built in valora_motion's local space and each key's camera (and target) is taken
    into that space with the motion's transform at the key's frame, so the posed subject is tested."""
    to_local = None
    if moving:
        from engine.blender.realism_rig import rig
        to_local = lambda f, v: _motion_matrix(f).inverted() @ v  # noqa: E731
        bvh = _subject_bvh(meshes, local_to=rig()[0])
    else:
        bvh = _subject_bvh(meshes)
    clip = cam.data.clip_start
    far = 4.0 * profile.radius + max(abs(v) for v in list(profile.boundsMin) + list(profile.boundsMax))
    out = {"keys": len(keys), "detailKeys": 0, "clipStartM": clip, "minSurfaceM": math.inf,
           "maxApertureM": 0.0, "violations": []}
    for k in keys:
        p = Vector(k.pose.position) if to_local is None else to_local(k.frame, Vector(k.pose.position))
        near = bvh.find_nearest(p)[3]
        aperture = k.pose.lens_mm / 1000.0 / (2.0 * k.fstop)
        out["minSurfaceM"] = min(out["minSurfaceM"], near)
        out["maxApertureM"] = max(out["maxApertureM"], aperture)
        why = []
        if sum(_crossings(bvh, p, Vector(d).normalized(), far) % 2 for d in INSIDE_DIRS) >= 2:
            why.append("inside the subject")
        if near <= CLEAR_CLIP * clip:
            why.append(f"{near:.4g} m from the surface (clip_start {clip:.3g})")
        if aperture >= CLEAR_APERTURE * near:
            why.append(f"lens aperture {aperture:.4g} m vs {near:.4g} m clearance")
        if k.target is not None:
            out["detailKeys"] += 1
            to = (Vector(k.target) if to_local is None else to_local(k.frame, Vector(k.target))) - p
            hit = bvh.ray_cast(p, to.normalized(), to.length)
            if hit[0] is not None and hit[3] < (1.0 - TARGET_TOL) * to.length:
                why.append(f"detail target hidden: geometry at {hit[3]:.4g} of {to.length:.4g} m")
        if why:
            out["violations"].append({"frame": k.frame, "shot": k.shot, "why": why})
    return out


def setup_timing(scene, script, tier):
    fmt = script["format"]
    scene.render.fps, scene.render.fps_base = fmt["fps"], 1.0
    scene.frame_start, scene.frame_end = 1, frame_count(fmt)
    scene.render.resolution_x, scene.render.resolution_y = resolution(fmt["aspect"], TIERS[tier]["shortSide"])
    scene.render.resolution_percentage = 100
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = SHUTTER
    scene.render.motion_blur_position = "CENTER"


PROBE_GRID = (10, 16)  # rays across x, y of the frame (edges included)


def _visible_hit(scene, origin, direction, skip):
    """Distance to the first camera-visible surface along a unit ray, or None."""
    dg, travelled, o = bpy.context.evaluated_depsgraph_get(), 0.0, origin.copy()
    for _ in range(64):
        hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, o, direction)
        if not hit:
            return None
        step = (loc - o).length
        travelled += step
        if ob.original.name not in skip and ob.original.visible_camera:
            return travelled
        o = loc + direction * 1e-7 * max(1.0, travelled)
    return None


def _frame_rays(scene, cam):
    """Unit world directions through a PROBE_GRID of points spanning the camera frame."""
    corners = [cam.matrix_world @ v for v in cam.data.view_frame(scene=scene)]  # tr, br, bl, tl
    origin = cam.matrix_world.translation
    tr, br, bl, tl = corners
    nx, ny = PROBE_GRID
    for i in range(nx):
        for j in range(ny):
            a, b = i / (nx - 1), j / (ny - 1)
            top, bottom = tl.lerp(tr, a), bl.lerp(br, a)
            yield origin, (bottom.lerp(top, b) - origin).normalized()


def probe(scene, cam, frames, profile, meshes=()):
    from bpy_extras.object_utils import world_to_camera_view
    from engine.geometry import box_corners, ray_box_exit
    out = {}
    haze = scene.get("valora_haze_domain")
    for f in frames:
        scene.frame_set(f)
        corners = [list(world_to_camera_view(scene, cam, Vector(c)))
                   for c in box_corners(profile.boundsMin, profile.boundsMax)]
        rec = {"corners": corners, "lens": cam.data.lens, "focus": cam.data.dof.focus_distance}
        if haze is not None:  # a ray that leaves the box before any surface, where haze is not zero
            lo, hi = [list(v) for v in haze]
            fade = scene.get("valora_haze_fade")
            centre, r_zero = (Vector(fade[:3]), fade[4]) if fade is not None else (None, None)
            rays = exposed = 0
            for o, d in _frame_rays(scene, cam):
                rays += 1
                hit, leave = _visible_hit(scene, o, d, {"valora_haze"}), ray_box_exit(o, d, lo, hi)
                seen = leave is None or (hit is None or leave < hit)
                if seen and leave is not None and centre is not None:
                    seen = (o + d * leave - centre).length < r_zero  # the density is zero out there
                exposed += seen
            rec["rays"], rec["hazeFaceRays"] = rays, exposed
        mo = bpy.data.objects.get("valora_motion")
        if mo is not None:   # the moving subject's transform this frame (Task 56 proof against motion_path)
            rec["motionMatrix"] = [[float(v) for v in row] for row in mo.matrix_world]
        if meshes:  # the subject's evaluated world bounds this frame (play_clip moves them)
            rec["subjectBounds"] = [list(map(float, v)) for v in world_bounds(meshes, bpy.context.evaluated_depsgraph_get())]
        out[str(f)] = rec
    return out


def _refs(script):
    yield "world", script["world"]
    if script.get("wind"):
        yield "field", script["wind"]     # before every consumer (METHODS §2.9)
    yield "motion", script["subject"]["motion"]
    yield "lighting", script["lighting"]
    for fx in script.get("effects", []):
        yield "effect", fx
    for ref in script.get("realism", []):  # always-on realism defaults (Task 12a), after effects, in order
        yield ref["kind"], ref


def _ctx(scene, script, profile, catalog, root, meshes, keys, hero, kind, ref):
    seed = block_seed(script["seed"], kind, ref["id"])
    return BuildContext(scene, profile, script, ref["params"], seed, random.Random(seed), root, meshes,
                        hero, [k.pose.position for k in keys], catalog, [k.pose.lens_mm for k in keys])


def key_subject_motion(scene, script, profile, catalog, motion_empty):
    """Key valora_motion at every frame from engine.motion_path.subject_pose, the pose the checker framed.
    The empty sits at the origin, so the pose's pivot (cx, cy, 0) goes into its location:
    loc = pivot + offset - R pivot, rotation_euler 'XYZ' = (roll, pitch, yaw). Linear between frames,
    constant past the ends. Keys run from frame 0 to n + 1 (review chunk1 #4), like the camera's: a centred
    shutter exposes frame 1 from 1 - SHUTTER/2 and frame n until n + SHUTTER/2, so those exposures see the
    path's own pose there (a path that ends at rest returns its rest pose; one still moving keeps moving)."""
    from engine.blender.realism_rig import key_series
    fps, n = script["format"]["fps"], frame_count(script["format"])
    frames = list(range(0, n + 2))
    poses = [subject_pose(script, profile, catalog, (f - 1) / fps) for f in frames]
    pv = motion_pivot(profile)
    motion_empty.rotation_mode = "XYZ"
    locs = []
    for p in poses:
        r = rotate(pv, p)
        locs.append([pv[i] + p.offset[i] - r[i] for i in range(3)])
    for i in range(3):
        key_series(motion_empty, "location", i, frames, [v[i] for v in locs])
    for i, name in enumerate(("roll", "pitch", "yaw")):
        key_series(motion_empty, "rotation_euler", i, frames, [getattr(p, name) for p in poses])


def build_all(scene, script, profile, catalog, root, meshes, keys, hero, skip_kinds):
    """World, subject motion, lighting, effects, realism (spec §4.5 order). Cameras are the compiler's own.
    A motion with a path.py that moves the subject has valora_motion keyed from the shared pose function
    first (key_subject_motion); its build.py adds only what the path cannot express."""
    built = []
    for kind, ref in _refs(script):
        if kind in skip_kinds:
            continue
        if kind == "motion" and is_moving(script, profile, catalog):
            from engine.blender.realism_rig import rig
            key_subject_motion(scene, script, profile, catalog, rig()[0])
        catalog.load_builder(kind, ref["id"])(_ctx(scene, script, profile, catalog, root, meshes, keys, hero, kind, ref))
        built.append(f"{kind}:{ref['id']}")
    return built


def material_digest(meshes):
    """A digest of every material the upload's meshes use: node types, names, links and input defaults (spec
    §4.5 guard: blocks never edit the upload's shaders; compared before and after every block builds)."""
    import hashlib
    rows = []
    for m in sorted({m for o in meshes for m in o.data.materials if m is not None}, key=lambda m: m.name):
        nt = m.node_tree if m.use_nodes else None
        nodes = sorted((n.bl_idname, n.name, tuple((i.identifier, repr(getattr(i, "default_value", None))
                                                     if not hasattr(getattr(i, "default_value", None), "__len__")
                                                     else repr(tuple(i.default_value))) for i in n.inputs))
                       for n in (nt.nodes if nt else ()))
        links = sorted((ln.from_node.name, ln.from_socket.identifier, ln.to_node.name, ln.to_socket.identifier)
                       for ln in (nt.links if nt else ()))
        rows.append((m.name, nodes, links))
    return hashlib.sha256(repr(rows).encode()).hexdigest()[:16]


def main():
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    out = Path(job["out"])
    profile = SubjectProfile.from_dict(job["profile"])
    objs, meshes = import_subject(job["model"])
    root = place_subject(objs, profile)
    result = {"blender": bpy.app.version_string, "placedBounds": assert_placement(meshes, profile)}
    build_rig(bpy.context.scene, root)
    scene, script = bpy.context.scene, job["script"]
    catalog = Catalog.load(job["catalogRoot"])  # the catalog the host checker used, never a default
    keys = camera_keys(script, profile, catalog)
    hero = hero_pose(script, profile, catalog)
    setup_timing(scene, script, job["tier"])
    # Every motion starts from the ingest pose with the imported animation off (a leftover active action
    # would play once and hold its last pose); play_clip re-adds the one clip it plays (review 2026-09-25).
    rest_animation(scene, objs, frame=1)
    scene.render.engine = "CYCLES"  # before any block: render-layer pass sockets (grade) follow the engine
    skip = tuple(job.get("skipKinds", ()))
    upload_before = material_digest(meshes)
    if job.get("buildBlocks", True):
        result["built"] = build_all(scene, script, profile, catalog, root, meshes, keys, hero, skip)
    pos, _yaw = motion_track(scene)
    result["motionEvents"] = {"stops": events.stops(pos, script["format"]["fps"], profile.longest),
                              "landings": events.landings(pos, script["format"]["fps"], profile.longest)}
    result["realism"] = [r["id"] for r in script.get("realism", [])]
    result["realismScene"] = records(scene)   # facts each realism block recorded (realism_rig.record)
    if scene.get("valora_wind") is not None:
        result["wind"] = {k: float(v) for k, v in scene["valora_wind"].items()}
    result["hazeDrift"] = bool(scene.get("valora_haze_drift"))
    if scene.get("valora_courtyard") is not None:   # rain_courtyard (Task 63): fallbacks used, layout facts
        result["courtyard"] = scene["valora_courtyard"].to_dict()
    for key, name in (("valora_street", "street"), ("valora_field", "field"),   # Tasks 70-71: world facts
                      ("valora_lighting", "lighting")):                         # Task 72: the rig's lights
        if scene.get(key) is not None:
            result[name] = scene[key].to_dict()
    if scene.get("valora_fog") is not None:   # ground_fog (Task 60): its sizes and the drift flag
        result["fog"] = {**scene["valora_fog"].to_dict(), "drift": bool(scene.get("valora_fog_drift"))}
    fx = {k[len("valora_fx_"):]: scene[k].to_dict() for k in scene.keys() if k.startswith("valora_fx_")}
    if fx:   # the weather package (Tasks 64-68): what each block built, its sizes and counts
        result["fx"] = fx
    cam = build_camera(scene, keys, profile)
    moving = ("motion" not in skip and job.get("buildBlocks", True) and is_moving(script, profile, catalog))
    result["clearance"] = camera_clearance(keys, meshes, cam, profile, moving=moving)
    if result["clearance"]["violations"]:
        bad = result["clearance"]["violations"]
        raise SystemExit(f"camera clearance: {len(bad)} camera key(s) fail, first: {bad[:5]}")
    if job.get("buildBlocks", True) and "grade" not in skip:  # the grade builds after the camera
        from engine.blender.grade import describe
        ref = script["grade"]
        tree = catalog.load_builder("grade", ref["id"])(
            _ctx(scene, script, profile, catalog, root, meshes, keys, hero, "grade", ref))
        result["built"].append(f"grade:{ref['id']}")
        result["grade"] = describe(scene, tree)
    if scene.get("valora_fx_lens_drops") is not None:   # Task 68: the optical stage, after camera and grade
        from engine.blender.lens_drops import apply as lens_drops
        result.setdefault("fx", {})["lens_drops"] = lens_drops(scene)
    if job.get("realismProbe"):
        from engine.blender.realism_probe import realism_probe
        result["realismProbe"] = realism_probe(scene, meshes, profile, job["realismProbe"])
        from engine.blender.realism_probe import wind_coherent   # beside realismProbe: its values are frames
        result["windCoherent"] = wind_coherent(scene, result["realismProbe"], profile, job["realismProbe"])
        from engine.blender.weather_probe import weather_probe
        wp = weather_probe(scene, profile, job["realismProbe"], meshes)
        if wp:
            result["weatherProbe"] = wp
    result["uploadMaterials"] = {"before": upload_before, "after": material_digest(meshes)}
    wf = bpy.data.objects.get("valora_wind_field")
    if wf is not None:   # the one force field (H4): where it blows and how hard
        z = wf.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
        result["windField"] = {"type": wf.field.type, "strength": float(wf.field.strength),
                               "noise": float(wf.field.noise), "seed": int(wf.field.seed), "axis": list(z)}
    result["shutter"], result["frameEnd"] = scene.render.motion_blur_shutter, scene.frame_end
    if job.get("probe"):
        result["probe"] = probe(scene, cam, job["probe"], profile, meshes)
    result["objects"] = [{"name": o.name, "type": o.type, "location": list(o.location),
                          "visibleCamera": o.visible_camera, "visibleGlossy": o.visible_glossy,
                          "block": o.get("valora_block"), "modifiers": [m.name for m in o.modifiers],
                          "lightType": o.data.type if o.type == "LIGHT" else None,
                          "ground": bool(o.get("valora_ground")), "foliage": bool(o.get("valora_foliage")),
                          "volume": o.type == "MESH" and any(m and m.node_tree and any(
                              k.to_socket.name == "Volume" for k in m.node_tree.links) for m in o.data.materials)}
                         for o in scene.objects]
    haze = scene.get("valora_haze_domain")
    if haze is not None:
        result["hazeDomain"] = [[float(v) for v in corner] for corner in haze]
    result["cameraPositions"] = [list(k.pose.position) for k in keys]
    device = setup_cycles(scene, job["tier"])
    result["device"] = device
    if TIERS[job["tier"]]["passes"]:
        gloss_pass_indices(meshes)
        corners = [tuple(o.matrix_world @ Vector(b)) for o in scene.objects
                   if o.type == "MESH" and not o.hide_render for b in o.bound_box]
        far = mist_far([k.pose.position for k in keys], corners)  # the whole set, not subject + 2r
        result["mistFar"] = far
        add_passes(scene, out, far)
    if job.get("render"):
        result["renderLog"] = render_frames(scene, job["frames"], out, job["tier"], device)
    if job.get("saveBlend"):
        bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"))
    (out / "compile.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
