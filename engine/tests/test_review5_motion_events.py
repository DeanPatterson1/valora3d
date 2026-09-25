"""Review chunk5 #2: stops and landings of a pivoted motion (roll, topple, toss; amendment 77).

valora_motion's location carries pivot + offset - R pivot, so the bare location of a rolling can climbs and
dips with the rotation: it read as a stop half-way through the roll and a landing, and a topple's landing
(the bottle's side hitting the ground) never showed. The event track follows the subject's placed centre
through the FULL transform (events.reference_track), in pure form here and in Blender below."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.compiler.timeline import frame_count
from engine.motion_path import pose_pivot, rotate, rotation_matrix, subject_pose
from engine.physics import events
from engine.tests.conftest import requires_blender
from engine.tests.motion_helpers import CAT, defaults, module, script, synthetic

ROOT = Path(__file__).resolve().parents[2]


def _keyed(bid, prof, duration=6):
    """(fps, per-frame (loc, R)) exactly as the compiler keys valora_motion (key_subject_motion)."""
    s = script(bid, defaults(bid), duration=duration)
    fps, n = s["format"]["fps"], frame_count(s["format"])
    out = []
    for f in range(1, n + 1):
        p = subject_pose(s, prof, CAT, (f - 1) / fps)
        pv = pose_pivot(p, prof)
        r = rotate(pv, p)
        out.append(([pv[i] + p.offset[i] - r[i] for i in range(3)], rotation_matrix(p)))
    return s, fps, out


def _rest_frame(bid, prof, s):
    return module(bid).rest_s(defaults(bid), prof, s["format"]["durationS"]) * s["format"]["fps"] + 1


def test_a_roll_stops_once_at_its_rest_and_never_lands():
    prof = synthetic("can")
    s, fps, tr = _keyed("roll", prof)
    pos = events.reference_track(tr, prof.center)
    st = events.stops(pos, fps, prof.longest)
    assert len(st) == 1 and abs(st[0]["frame"] - _rest_frame("roll", prof, s)) <= 2, st
    assert events.landings(pos, fps, prof.longest) == []
    bare = [loc for loc, _ in tr]                   # the old track: a false stop and a false landing
    assert events.landings(bare, fps, prof.longest) or events.stops(bare, fps, prof.longest) != st


def test_a_topple_lands_on_its_side():
    prof = synthetic("bottle")
    s, fps, tr = _keyed("topple", prof)
    pos = events.reference_track(tr, prof.center)
    lands = events.landings(pos, fps, prof.longest)
    assert len(lands) == 1 and abs(lands[0]["frame"] - _rest_frame("topple", prof, s)) <= 2, lands
    assert lands[0]["impactMs"] > 0.5                        # the side slams down, it does not ease in
    assert events.landings([loc for loc, _ in tr], fps, prof.longest) == []   # the old track missed it


@pytest.mark.parametrize("name", ["can", "bottle"])
def test_a_toss_lands_once_at_its_rest(name):
    prof = synthetic(name)
    s, fps, tr = _keyed("toss_tumble", prof)
    lands = events.landings(events.reference_track(tr, prof.center), fps, prof.longest)
    assert len(lands) == 1 and abs(lands[0]["frame"] - _rest_frame("toss_tumble", prof, s)) <= 2, lands


def test_a_yaw_about_the_centre_line_reads_as_the_bare_offset():
    loc, yaw = (0.4, -0.2, 0.0), 0.7
    import math
    R = [[math.cos(yaw), -math.sin(yaw), 0.0], [math.sin(yaw), math.cos(yaw), 0.0], [0.0, 0.0, 1.0]]
    got = events.reference_track([(loc, R)], (0.0, 0.0, 0.3))[0]
    assert max(abs(a - b) for a, b in zip(got, loc)) < 1e-12


_BODY = r'''
import sys, json
sys.path.insert(0, r"{root}")
import bpy
from engine.blender.realism_rig import build_rig, motion_track
from engine.catalog import Catalog
from engine.compiler import blender_main as bm
from engine.physics import events
from engine.profile import SubjectProfile
job = json.loads(open(r"{job}", encoding="utf-8").read())
out = {{}}
for name, case in job["cases"].items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    prof = SubjectProfile.from_dict(case["profile"])
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=prof.center)
    cube = bpy.context.object
    cube.scale = prof.sizeM
    root = bpy.data.objects.new("valora_subject", None)
    scene.collection.objects.link(root)
    cube.parent = root
    build_rig(scene, root)
    s = case["script"]
    bm.setup_timing(scene, s, "preview")
    bm.key_subject_motion(scene, s, prof, Catalog.load(), bpy.data.objects["valora_motion"])
    pos, _ = motion_track(scene)
    fps = s["format"]["fps"]
    out[name] = {{"stops": [e["frame"] for e in events.stops(pos, fps, prof.longest)],
                  "landings": [e["frame"] for e in events.landings(pos, fps, prof.longest)]}}
print("EV " + json.dumps(out))
'''


@pytest.mark.blender
@requires_blender
def test_motion_track_reads_pivoted_motions_in_blender(tmp_path):
    from engine.ingest.run import BLENDER
    cases, want = {}, {}
    for bid, name in (("roll", "can"), ("topple", "bottle")):
        prof = synthetic(name)
        s = script(bid, defaults(bid), duration=6)
        cases[bid] = {"profile": json.loads((ROOT / "engine" / "tests" / "fixtures" / "synthetic_profiles"
                                              / f"{name}.json").read_text(encoding="utf-8")), "script": s}
        want[bid] = _rest_frame(bid, prof, s)
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    py = tmp_path / "ev.py"
    py.write_text(_BODY.format(root=ROOT, job=job), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(py)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    got = json.loads(next(ln[3:] for ln in proc.stdout.splitlines() if ln.startswith("EV ")))
    assert got["roll"]["landings"] == [], got
    assert len(got["roll"]["stops"]) == 1 and abs(got["roll"]["stops"][0] - want["roll"]) <= 2, (got, want)
    assert len(got["topple"]["landings"]) == 1 and abs(got["topple"]["landings"][0] - want["topple"]) <= 2, (got, want)
