"""Runs INSIDE Blender: stage 4b BAKE for one sim (phase 6 Task 98). Launch only through engine/bake/run.py.

The subject is imported and placed exactly as the compiler does (import_subject, place_subject, build_rig,
rest_animation), then only what a sim collides with or is pushed by is built:
- the world's ground: the world block is built in full and everything it made that is not tagged
  valora_ground is deleted (one code path per world; worlds already tag their ground for realism);
- the one wind field (the field block, so ensure_force_field sets the same strength and seed);
- the subject motion keys (key_subject_motion), so a moving subject is an animated collider; for a shift-mode
  bake the keys move by -offset, because the bake scene counts from frame 1 while the motion is keyed on render
  frames.
Then the block's proxies (engine/blender/collision_proxy.cached_proxy: from the same BakeStore) and the block's
bake(ctx) with ctx.bake = {"dir", "frames", "proxy": {purpose: object}}. bake() writes its files into dir
only and returns its report; this entry adds bakeSeconds and the proxy reports and writes bake_report.json."""
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import bpy  # noqa: E402

from engine.bake.run import REPORT  # noqa: E402
from engine.bake.store import BakeStore  # noqa: E402
from engine.blender.collision_proxy import cached_proxy  # noqa: E402
from engine.blender.realism_rig import build_rig, fcurves, rig  # noqa: E402
from engine.blender.scene_io import import_subject, rest_animation  # noqa: E402
from engine.catalog import Catalog  # noqa: E402
from engine.compiler.blender_main import _ctx, key_subject_motion, place_subject  # noqa: E402
from engine.compiler.context import hero_pose  # noqa: E402
from engine.compiler.timeline import camera_keys  # noqa: E402
from engine.motion_path import is_moving  # noqa: E402
from engine.profile import SubjectProfile  # noqa: E402


def _ground_only(scene, before):
    """Delete what the world built that is not its ground (lights, sky meshes, set dressing)."""
    for o in [o for o in scene.objects if o not in before and not o.get("valora_ground")]:
        bpy.data.objects.remove(o, do_unlink=True)


def _shift_keys(ob, offset):
    ad = ob.animation_data
    if not offset or ad is None or ad.action is None:
        return
    for c in fcurves(ad.action):
        for kp in c.keyframe_points:
            kp.co.x -= offset
            kp.handle_left.x -= offset
            kp.handle_right.x -= offset


def main():
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    profile = SubjectProfile.from_dict(job["profile"])
    script, ref, fr = job["script"], job["ref"], job["frames"]
    catalog = Catalog.load(job["catalogRoot"])
    objs, meshes = import_subject(job["model"])
    root = place_subject(objs, profile)
    scene = bpy.context.scene
    build_rig(scene, root)
    fmt = script["format"]
    scene.render.fps, scene.render.fps_base = fmt["fps"], 1.0
    rest_animation(scene, objs, frame=1)
    keys = camera_keys(script, profile, catalog)
    hero = hero_pose(script, profile, catalog)
    before = set(scene.objects)
    wref = script["world"]
    catalog.load_builder("world", wref["id"])(_ctx(scene, script, profile, catalog, root, meshes, keys, hero, "world", wref))
    _ground_only(scene, before)
    if script.get("wind"):
        catalog.load_builder("field", script["wind"]["id"])(
            _ctx(scene, script, profile, catalog, root, meshes, keys, hero, "field", script["wind"]))
    moving = is_moving(script, profile, catalog)
    if moving:
        key_subject_motion(scene, script, profile, catalog, rig()[0])
    scene.frame_set(1)
    store = BakeStore(job["storeRoot"])
    proxies, reports = {}, {}
    for purpose in job["proxies"]:
        ob, rep = cached_proxy(meshes, profile, purpose, store, job["modelSha"])
        for o in (ob if isinstance(ob, list) else [ob]):
            if moving:                                    # the proxy follows the subject, as its meshes do
                o.parent = rig()[1]
                o.matrix_parent_inverse = rig()[1].matrix_world.inverted()
        proxies[purpose], reports[purpose] = ob, rep
    if moving and fr["mode"] == "shift":
        _shift_keys(rig()[0], fr["offset"])
    scene.frame_start, scene.frame_end = fr["bake_first"], fr["bake_last"]
    ctx = _ctx(scene, script, profile, catalog, root, meshes, keys, hero, "sim", ref)
    ctx.bake = {"dir": job["dir"], "frames": fr, "proxy": proxies, "method": job["method"]}
    ctx.rng = random.Random(ctx.seed)
    bake = catalog.load_baker(ref["id"])
    t0 = time.perf_counter()
    report = bake(ctx) or {}
    report["bakeSeconds"] = round(time.perf_counter() - t0, 3)
    report["proxy"] = reports
    report["blender"] = bpy.app.version_string
    Path(job["dir"], REPORT).write_text(json.dumps(report), encoding="utf-8")


if __name__ == "__main__":
    main()
