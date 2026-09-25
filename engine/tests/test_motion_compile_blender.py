"""Review chunk1 #3 and #4, inside Blender without a full compile:

#3 camera clearance on a moving subject reads the motion transform and the evaluated meshes from ONE
depsgraph: right after keying, valora_motion's original matrix_world is stale, and a subject that starts
off the origin (here: hovering 0.3 m up) was tested 0.3 m away from where it is.
#4 valora_motion is keyed through the shutter interval: frame n + 1/4 (the second half of frame n's centred
exposure) and frame 3/4 carry the path's own pose, not a frozen end pose."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.ingest.run import BLENDER
from engine.tests.conftest import requires_blender
from engine.tests.realism_catalog import catalog_with_fixtures

pytestmark = [pytest.mark.blender, requires_blender]
ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"

_HOVER = ("import math\nfrom engine.motion_path import SubjectPose\n\n"
          "def sample(params, profile, t, duration):\n"
          "    return SubjectPose(offset=(0.0, 0.0, 0.3))\n")

_BODY = r'''
import sys, json, math
sys.path.insert(0, r"{root}")
sys.argv = [sys.argv[0], "--", r"{job}"]
import bpy
from types import SimpleNamespace as NS
from mathutils import Vector
from engine.blender.realism_rig import build_rig
from engine.catalog import Catalog
from engine.compiler import blender_main as bm
from engine.compiler.timeline import frame_count
from engine.motion_path import apply, subject_pose
from engine.profile import SubjectProfile
job = json.loads(open(r"{job}", encoding="utf-8").read())
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0, 0, 0.1))
cube = bpy.context.object
root = bpy.data.objects.new("valora_subject", None)
scene.collection.objects.link(root)
cube.parent = root
build_rig(scene, root)
cat = Catalog.load(job["catalog"])
prof = SubjectProfile.from_dict(job["profile"])
cam = NS(data=NS(clip_start=1e-3))
pose = NS(position=(0.6, 0.0, 0.4), lens_mm=50.0)          # 0.5 m in front of the HOVERING cube's +X face
key = NS(frame=1, shot=0, pose=pose, fstop=8.0, target=None)
# 3: hover keys, then clearance with no depsgraph update in between (as build_all -> camera_clearance)
s = job["hover"]
bm.setup_timing(scene, s, "preview")
bm.key_subject_motion(scene, s, prof, cat, bpy.data.objects["valora_motion"])
out = bm.camera_clearance([key], [cube], cam, prof, moving=True)
assert abs(out["minSurfaceM"] - 0.5) < 1e-4, out["minSurfaceM"]
# 4: glide keys cover the shutter interval at both ends
g = job["glide"]
motion = bpy.data.objects["valora_motion"]
motion.animation_data_clear()
bm.key_subject_motion(scene, g, prof, cat, motion)
fps, n = g["format"]["fps"], frame_count(g["format"])
for f in (0.75, n + 0.25):
    m = bm._motion_matrix(f)
    want = apply((0.1, 0.2, 0.3), subject_pose(g, prof, cat, (f - 1) / fps), prof)
    got = m @ Vector((0.1, 0.2, 0.3))
    assert (Vector(want) - got).length < 1e-5, (f, list(got), want)
assert (bm._motion_matrix(n + 0.25).translation - bm._motion_matrix(n).translation).length > 1e-6
print("MC-OK")
'''


def test_clearance_and_boundary_keys_follow_the_motion(tmp_path):
    cat = catalog_with_fixtures(tmp_path / "cat")
    d = Path(cat.root) / "motion" / "test_hover"
    d.mkdir()
    m = json.loads((Path(cat.root) / "motion" / "test_glide" / "block.json").read_text(encoding="utf-8"))
    (d / "block.json").write_text(json.dumps({**m, "id": "test_hover"}), encoding="utf-8")
    (d / "path.py").write_text(_HOVER, encoding="utf-8")
    base = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    hover = {**base, "subject": {**base["subject"], "motion": {"id": "test_hover", "params": {}}}}
    glide = {**base, "subject": {**base["subject"], "motion": {"id": "test_glide", "params": {"metres": 2.0, "yawDeg": 30.0}}}}
    prof = json.loads((FIX / "profiles" / "pocket_watch.json").read_text(encoding="utf-8"))
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"catalog": str(cat.root), "profile": prof, "hover": hover, "glide": glide}), encoding="utf-8")
    script = tmp_path / "t.py"
    script.write_text(_BODY.format(root=ROOT, job=job), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0 and "MC-OK" in proc.stdout, proc.stdout[-3000:] + proc.stderr[-3000:]


_QUAT_PATH = ("import math\nfrom engine.motion_path import SubjectPose\n\n"
              "def sample(params, profile, t, duration):\n"
              "    th = 3.0 * t\n"
              "    ax = (0.6, 0.8, 0.0)\n"
              "    return SubjectPose(offset=(0.2 * t, 0.0, 0.0), pivot=(0.01, 0.0, 0.02),\n"
              "                       quat=(math.cos(th / 2), *(math.sin(th / 2) * a for a in ax)))\n")

_QUAT_BODY = r'''
import sys, json
sys.path.insert(0, r"{root}")
import bpy
from mathutils import Vector
from engine.blender.realism_rig import build_rig
from engine.catalog import Catalog
from engine.compiler import blender_main as bm
from engine.compiler.timeline import frame_count
from engine.motion_path import apply, subject_pose
from engine.profile import SubjectProfile
job = json.loads(open(r"{job}", encoding="utf-8").read())
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
root = bpy.data.objects.new("valora_subject", None)
scene.collection.objects.link(root)
build_rig(scene, root)
cat = Catalog.load(job["catalog"])
prof = SubjectProfile.from_dict(job["profile"])
s = job["script"]
bm.setup_timing(scene, s, "preview")
motion = bpy.data.objects["valora_motion"]
bm.key_subject_motion(scene, s, prof, cat, motion)
assert motion.rotation_mode == "QUATERNION", motion.rotation_mode
fps, n = s["format"]["fps"], frame_count(s["format"])
worst = 0.0
for f in (1, 7.5, 40, 91.25, n, n + 0.25):
    m = bm._motion_matrix(f)
    for p in ((0.1, 0.2, 0.3), (0.01, 0.0, 0.02)):
        want = apply(p, subject_pose(s, prof, cat, (f - 1) / fps), prof)
        worst = max(worst, (Vector(want) - m @ Vector(p)).length)
scene.frame_set(40)
m = motion.matrix_world
want = apply((0.1, 0.2, 0.3), subject_pose(s, prof, cat, 39 / fps), prof)
worst = max(worst, (Vector(want) - m @ Vector((0.1, 0.2, 0.3))).length)
print("WORST", worst)
'''


def test_a_quaternion_pose_about_its_own_pivot_is_keyed_exactly(tmp_path):         # review amendment 77
    cat = catalog_with_fixtures(tmp_path / "cat")
    d = Path(cat.root) / "motion" / "test_quat"
    d.mkdir()
    m = json.loads((Path(cat.root) / "motion" / "test_glide" / "block.json").read_text(encoding="utf-8"))
    (d / "block.json").write_text(json.dumps({**m, "id": "test_quat", "params": {}}), encoding="utf-8")
    (d / "path.py").write_text(_QUAT_PATH, encoding="utf-8")
    (d / "build.py").write_text("def build(ctx):\n    return None\n", encoding="utf-8")
    base = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s = {**base, "subject": {**base["subject"], "motion": {"id": "test_quat", "params": {}}}}
    prof = json.loads((FIX / "profiles" / "pocket_watch.json").read_text(encoding="utf-8"))
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"catalog": str(cat.root), "profile": prof, "script": s}), encoding="utf-8")
    script = tmp_path / "q.py"
    script.write_text(_QUAT_BODY.format(root=ROOT, job=job), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    worst = float(next(ln.split()[1] for ln in proc.stdout.splitlines() if ln.startswith("WORST")))
    assert worst < 1e-3, worst            # linear per-frame quaternion keys: sub-mm between frames at 3 rad/s
