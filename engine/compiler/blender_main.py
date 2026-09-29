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

from engine.blender.phase_log import mark, phase, write as write_phase_log  # noqa: E402
from engine.blender.realism_rig import build_rig, fcurves as _fcurves, motion_track, records  # noqa: E402
from engine.blender.render import add_passes, gloss_pass_indices, render_frames, setup_cycles  # noqa: E402
from engine.blender.scene_io import import_subject, rest_animation, world_bounds  # noqa: E402
from engine.catalog import Catalog  # noqa: E402
from engine.compiler.context import BuildContext, block_seed, hero_pose  # noqa: E402
from engine.compiler.tiers import SHUTTER, TIERS, resolution  # noqa: E402
from engine.compiler.timeline import camera_keys, frame_count  # noqa: E402
from engine.geometry import camera_matrix, mist_far  # noqa: E402
from engine.motion_path import frame_shots, is_moving  # noqa: E402
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


def follow_offset(keys, script, catalog):
    """The realism rig lowers the subject (contact_ground's sink, soft_rest's dip) through its offset empty AFTER the
    camera keys were solved against the ingest pose, so a macro aimed at a detail point looked 1.5 cm above the real
    one: 40 % of a sneaker macro's frame (top-loop close-up, 2026-09-29: the loop sat at the bottom edge). Detail
    keys move by the offset's z (camera, aim and target together: framing and focus distance are unchanged); full
    shots keep their ground-relative height."""
    from dataclasses import replace
    from engine.blender.realism_rig import rig
    try:
        dz = rig()[1].location.z
    except KeyError:
        return keys
    if abs(dz) < 1e-9:
        return keys
    out = []
    for k in keys:
        if catalog.get("camera", script["shots"][k.shot]["camera"]["id"])["framing"] != "detail":
            out.append(k)
            continue
        lift = lambda v: (v[0], v[1], v[2] + dz)  # noqa: E731
        out.append(replace(k, pose=replace(k.pose, position=lift(k.pose.position), target=lift(k.pose.target)),
                           target=None if k.target is None else lift(k.target)))
    return out


def build_camera(scene, keys, profile):
    data = bpy.data.cameras.new("valora_camera")
    from engine.geometry import SENSOR_MM, sensor_fit
    # the locked convention: SENSOR_MM on the frame's long side, explicitly (geometry.sensor_fit)
    data.sensor_fit = sensor_fit(scene.render.resolution_x, scene.render.resolution_y)
    data.sensor_width = data.sensor_height = SENSOR_MM
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


def _frame_samples(keys, tier):
    """{frame: sample cap}: a final-tier close detail gets the close-up budget (tiers.frame_samples)."""
    from engine.compiler.tiers import frame_samples
    out = {}
    for k in keys:
        if float(k.frame).is_integer():
            d = None if k.target is None else sum((a - b) ** 2 for a, b in zip(k.pose.position, k.target)) ** 0.5
            field = None if d is None else d * 36.0 / k.pose.lens_mm      # the long side at the target (36 mm)
            out[int(k.frame)] = frame_samples(tier, detail=k.target is not None, field_m=field)
    return out


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
    if motion.rotation_mode == "QUATERNION":         # a roll / topple / toss pose (review amendment 77)
        from mathutils import Quaternion
        q = Quaternion([ev("rotation_quaternion", i, motion.rotation_quaternion[i]) for i in range(4)]).normalized()
        return Matrix.Translation(loc) @ q.to_matrix().to_4x4()
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
        whole = int(math.floor(f))       # a fractional probe frame is a subframe (a contact between frames)
        scene.frame_set(whole, subframe=float(f) - whole)
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
    for sim in script.get("sims", []):     # phase 6: after effects, before realism; builds read their bake only
        yield "sim", sim
    for ref in script.get("realism", []):  # always-on realism defaults (Task 12a), after effects, in order
        yield ref["kind"], ref


def _ctx(scene, script, profile, catalog, root, meshes, keys, hero, kind, ref):
    seed = block_seed(script["seed"], kind, ref["id"])
    return BuildContext(scene, profile, script, ref["params"], seed, random.Random(seed), root, meshes,
                        hero, [k.pose.position for k in keys], catalog, [k.pose.lens_mm for k in keys], list(keys))


def key_subject_motion(scene, script, profile, catalog, motion_empty):
    """Key valora_motion from engine.motion_path.subject_pose, the pose the checker framed, at the times
    engine/compiler/subject_keys picks: every frame from 0 to n + 1 (review chunk1 #4: a centred shutter exposes
    frame 1 from 1 - SHUTTER/2 and frame n until n + SHUTTER/2), each path break (a bounce contact) exactly,
    more keys where a key interval would stray from the path or turn too far (review chunk5 #3, #4), and a
    perShot drive's held cut keys (review amendment 79). The empty sits at the origin, so the pose's pivot
    goes into its location: loc = pivot + offset - R pivot, rotation_euler 'XYZ' = (roll, pitch, yaw), or
    rotation_quaternion when any pose carries a quaternion (roll, topple, toss: review amendment 77). Linear
    between keys, CONSTANT after a hold key, constant past the ends."""
    from engine.blender.realism_rig import key_series
    from engine.compiler.subject_keys import key_values, subject_keys
    keys, quat = subject_keys(script, profile, catalog)
    frames, locs, rots, holds = key_values(keys, profile, quat)
    motion_empty.rotation_mode = "QUATERNION" if quat else "XYZ"
    for i in range(3):
        key_series(motion_empty, "location", i, frames, [v[i] for v in locs])
    path = "rotation_quaternion" if quat else "rotation_euler"
    for i in range(4 if quat else 3):
        key_series(motion_empty, path, i, frames, [r[i] for r in rots])
    held = [f for f, h in zip(frames, holds) if h]
    if held:   # a perShot cut: hold the outgoing pose until the incoming key, both between exposures
        for c in _fcurves(motion_empty.animation_data.action):
            if c.data_path in ("location", path):
                for kp in c.keyframe_points:
                    if any(abs(kp.co[0] - f) < 1e-4 for f in held):
                        kp.interpolation = "CONSTANT"


def _load_bake(bakes, ref, catalog):
    """ctx.bake for a sim: its verified (size) cache from the host's bake stage, or BakeMissing. A stateless sim
    (bake.method "none") gets None. The compile never simulates: a missing cache is an error, never a re-bake."""
    from engine.bake.run import BakeMissing
    from engine.bake.store import BakeStore, CacheCorrupt
    if (catalog.get("sim", ref["id"]) or {}).get("bake", {}).get("method", "none") == "none":
        return None
    e = (bakes or {}).get(ref["id"])
    if not e:
        raise BakeMissing(f"sim {ref['id']}: the job carries no bake (run the bake stage first)")
    try:
        m = BakeStore(Path(e["dir"]).parent).read(e["key"], verify="size")
    except CacheCorrupt as err:
        raise BakeMissing(f"sim {ref['id']}: cache {e['key']} is corrupt: {err}") from err
    if m is None:
        raise BakeMissing(f"sim {ref['id']}: cache {e['key']} is missing from {Path(e['dir']).parent}")
    return {**e, "manifest": m}


_LIVE_SIM_MODIFIERS = ("CLOTH", "FLUID", "SOFT_BODY", "COLLISION", "DYNAMIC_PAINT")


def assert_no_live_sims(scene):
    """SimInCompile: a compiled scene holds no rigid body world, no CLOTH / FLUID / soft-body modifier and no
    simulation zone that is not baked to disk (the bake stage owns every simulation)."""
    from engine.bake.run import SimInCompile
    bad = []
    if scene.rigidbody_world is not None:
        bad.append("rigidbody_world")
    for o in scene.objects:
        for m in getattr(o, "modifiers", ()):
            if m.type in _LIVE_SIM_MODIFIERS:
                bad.append(f"{o.name}:{m.type}")
            elif m.type == "NODES" and m.node_group is not None and any(
                    n.bl_idname == "GeometryNodeSimulationInput" for n in m.node_group.nodes):
                if not all(bk.bake_target == "DISK" and bk.use_custom_path and bk.directory for bk in m.bakes):
                    bad.append(f"{o.name}:unbaked simulation zone")
    if bad:
        raise SimInCompile(f"a compile never simulates; found {bad}")


def build_all(scene, script, profile, catalog, root, meshes, keys, hero, skip_kinds, bakes=None):
    """World, subject motion, lighting, effects, realism (spec §4.5 order). Cameras are the compiler's own.
    A motion with a path.py that moves the subject has valora_motion keyed from the shared pose function
    first (key_subject_motion); its build.py adds only what the path cannot express. A build.py may also define
    finalize(ctx), run once every block is built, to read what later blocks keyed (droplets: each drip's release
    from the final realism offset)."""
    built, finals = [], []
    for kind, ref in _refs(script):
        if kind in skip_kinds:
            continue
        if kind == "motion" and is_moving(script, profile, catalog):
            from engine.blender.realism_rig import rig
            key_subject_motion(scene, script, profile, catalog, rig()[0])
        ctx = _ctx(scene, script, profile, catalog, root, meshes, keys, hero, kind, ref)
        if kind == "sim":
            ctx.bake = _load_bake(bakes, ref, catalog)
        with phase(f"build:{kind}:{ref['id']}"):
            catalog.load_builder(kind, ref["id"])(ctx)
        built.append(f"{kind}:{ref['id']}")
        fin = catalog._module_attr(kind, ref["id"], "build.py", "finalize")
        if fin is not None:
            finals.append((fin, kind, ref))
    for fin, kind, ref in finals:
        with phase(f"finalize:{kind}:{ref['id']}"):
            fin(_ctx(scene, script, profile, catalog, root, meshes, keys, hero, kind, ref))
    return built


def camera_roll_deg(scene, cam, script):
    """The compiled camera's roll off level (degrees, + = the picture's up turned to its left) at each shot's
    middle frame, read back from the keyed rotation (dutch_hero, Task 81; 0 for a level camera)."""
    import math
    fps, out, keep = script["format"]["fps"], [], scene.frame_current
    for sh in script["shots"]:
        scene.frame_set(int(round((sh["startS"] + sh["endS"]) / 2 * fps)) + 1)
        m = cam.matrix_world.to_3x3()
        right, up = m.col[0], m.col[1]
        out.append(round(math.degrees(math.atan2(right.z, up.z)), 4))
    scene.frame_set(keep)
    return out


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
    with phase("import_subject"):
        objs, meshes = import_subject(job["model"])
    root = place_subject(objs, profile)
    result = {"blender": bpy.app.version_string, "placedBounds": assert_placement(meshes, profile)}
    build_rig(bpy.context.scene, root)
    scene, script = bpy.context.scene, job["script"]
    catalog = Catalog.load(job["catalogRoot"])  # the catalog the host checker used, never a default
    keys = camera_keys(script, profile, catalog)
    hero = hero_pose(script, profile, catalog)
    setup_timing(scene, script, job["tier"])
    scene["valora_tier"] = job["tier"]      # worlds pick tier assets (courtyard: 8k sky at final)
    # Every motion starts from the ingest pose with the imported animation off (a leftover active action
    # would play once and hold its last pose); play_clip re-adds the one clip it plays (review 2026-09-25).
    rest_animation(scene, objs, frame=1)
    scene.render.engine = "CYCLES"  # before any block: render-layer pass sockets (grade) follow the engine
    skip = tuple(job.get("skipKinds", ()))
    painted = []
    if job.get("paint"):                     # re-validated here too: only hex + enum ever reach the node values
        from engine.blender.paint import apply_paint
        from engine.blender.subject_prep import paint_targets
        from engine.paint import validate_paint
        result["paint"], painted = apply_paint(meshes, validate_paint({k: job["paint"][k] for k in ("color", "finish")}),
                                               paint_targets(meshes, profile))
    if job.get("subjectPrep", True):         # realism pass: the upload's materials calibrated by role, before blocks
        from engine.blender.subject_prep import prepare_subject
        _prep = phase("subject_prep"); _prep.__enter__()
        outdoor = bool((catalog.get("world", script["world"]["id"]) or {}).get("outdoor", True))
        result["subjectPrep"] = prepare_subject(meshes, script, profile, painted=painted, outdoor=outdoor,
                                                moving=is_moving(script, profile, catalog))
        _prep.__exit__(None, None, None)
    if painted:
        from engine.blender.paint import paint_readback
        result["paint"]["shaders"] = paint_readback(painted)
    upload_before = material_digest(meshes)  # the prepared upload: blocks never edit it (spec 4.5 guard)
    if job.get("buildBlocks", True):
        with phase("build_all"):
            result["built"] = build_all(scene, script, profile, catalog, root, meshes, keys, hero, skip,
                                        bakes=job.get("bakes"))
        assert_no_live_sims(scene)
        if job.get("bakes"):
            result["sims"] = {k: {"key": v["key"], "frames": v["frames"], "fromCache": True}
                              for k, v in job["bakes"].items()}
    pos, _yaw = motion_track(scene)
    takes = frame_shots(script, range(1, scene.frame_end + 1))   # a perShot replay's cut is no stop
    result["motionEvents"] = {"stops": events.stops(pos, script["format"]["fps"], profile.longest, takes),
                              "landings": events.landings(pos, script["format"]["fps"], profile.longest, takes)}
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
    keys = follow_offset(keys, script, catalog)   # a detail shot aims at the subject where the realism rig left it
    cam = build_camera(scene, keys, profile)
    result["cameraRollDeg"] = camera_roll_deg(scene, cam, script)
    if job.get("buildBlocks", True):            # a camera's foreground card (profile_slide, Task 83)
        from engine.blender.foreground import build_foreground
        fg = build_foreground(scene, script, profile, catalog)
        if fg:
            result["foreground"] = fg
    moving = ("motion" not in skip and job.get("buildBlocks", True) and is_moving(script, profile, catalog))
    with phase("camera_clearance"):
        result["clearance"] = camera_clearance(keys, meshes, cam, profile, moving=moving)
    if result["clearance"]["violations"]:
        bad = result["clearance"]["violations"]
        raise SystemExit(f"camera clearance: {len(bad)} camera key(s) fail, first: {bad[:5]}")
    if job.get("buildBlocks", True) and "grade" not in skip:  # the grade builds after the camera
        from engine.blender.grade import describe
        ref = script["grade"]
        with phase("build:grade"):
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
    with phase("setup_cycles"):
        device = setup_cycles(scene, job["tier"])
    result["device"] = device
    if job.get("passes", TIERS[job["tier"]]["passes"]):
        gloss_pass_indices(meshes)
        corners = [tuple(o.matrix_world @ Vector(b)) for o in scene.objects
                   if o.type == "MESH" and not o.hide_render for b in o.bound_box]
        far = mist_far([k.pose.position for k in keys], corners)  # the whole set, not subject + 2r
        result["mistFar"] = far
        add_passes(scene, out, far)
    mark("scene_ready")
    if job.get("render"):
        with phase("render_frames"):
            result["renderLog"] = render_frames(scene, job["frames"], out, job["tier"], device,
                                                samples_by_frame=_frame_samples(keys, job["tier"]))
    if job.get("saveBlend"):
        bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"))
    (out / "compile.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_phase_log(out, {"tier": job["tier"], "device": device, "gpu": _gpu_name()})


def _gpu_name():
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        return [d.name for d in prefs.devices if d.use]
    except Exception:  # noqa: BLE001 - informational only
        return []


if __name__ == "__main__":
    main()
