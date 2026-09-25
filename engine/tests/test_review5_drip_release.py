"""Review chunk5 #10: a drip lets go where it hung. While it hangs it rides valora_realism_offset (sink, tyre
deflection, landing settle); its flight started from the motion path's pose alone, so on a car whose tyres
drop it 9 mm it jumped up by that at release. Pure: droplets.detach_state; Blender: the compiled drip's
position is continuous across its release."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.physics import droplets as D
from engine.tests.conftest import requires_blender

ROOT = Path(__file__).resolve().parents[2]


def test_detach_state_moves_the_shifted_emitter_rigidly():
    import math
    from engine.motion_path import SubjectPose, apply
    from engine.tests.motion_helpers import synthetic
    prof = synthetic("can")
    pose_at = lambda t: SubjectPose(offset=(0.3 * t, 0.1 * t * t, 0.0), yaw=0.8 * t)  # noqa: E731
    p, shift = [0.05, 0.02, 0.01], [0.0, 0.004, -0.009]
    ev = D.drip_events([(p, 1.0, 0.0)], pose_at, prof, 3.0)[1]
    pos, vel = D.detach_state(ev, shift)
    q = [p[i] + shift[i] for i in range(3)]
    want = apply(q, pose_at(ev["td"]), prof)
    h = 1e-4
    a, b = apply(q, pose_at(ev["td"] - h), prof), apply(q, pose_at(ev["td"] + h), prof)
    assert max(abs(pos[i] - want[i]) for i in range(3)) < 1e-9
    assert max(abs(vel[i] - (b[i] - a[i]) / (2 * h)) for i in range(3)) < 1e-5
    assert math.dist(D.detach_state(ev, [0.0, 0.0, 0.0])[0], ev["pd"]) == 0.0


_RELEASE = r'''
import sys, math, json
sys.path.insert(0, r"{root}")
import bpy, numpy as np
bpy.ops.wm.open_mainfile(filepath=r"{blend}")
scene = bpy.context.scene
fps, n = scene.render.fps, scene.frame_end
ob = bpy.data.objects["valora_drips"]
ob.modifiers["valora_drips_drops"].show_viewport = False
tds = sorted({{round(v.value, 6) for v in ob.data.attributes["valora_td"].data}})

def at(x):
    whole = int(math.floor(x))
    scene.frame_set(whole, subframe=x - whole)
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    td = np.empty(len(me.vertices), np.float32); me.attributes["valora_td"].data.foreach_get("value", td)
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    return td, co.reshape(-1, 3)

rows, eps = [], 1e-3          # frames either side of the release
for t in tds:
    f = t * fps
    if not 2.0 <= f <= n - 1.0:
        continue
    (ta, ca), (tb, cb) = at(f - eps), at(f + eps)
    ia, ib = np.where(np.abs(ta - t) < 1e-5)[0], np.where(np.abs(tb - t) < 1e-5)[0]
    if len(ia) == 1 and len(ib) == 1:
        rows.append(float(np.linalg.norm(ca[ia[0]] - cb[ib[0]])))
off = bpy.data.objects["valora_realism_offset"]
scene.frame_set(1)
print("REL " + json.dumps({{"jumps": rows, "offsetZ": off.matrix_world.translation.z}}))
'''


@pytest.mark.blender
@requires_blender
def test_a_drip_leaves_from_where_it_hung(tmp_path):
    from engine.compiler.run import compile_scene
    from engine.ingest.run import BLENDER, ingest
    from engine.tests.blender_fixtures import make_glb
    from engine.tests.test_realism_blender import _script
    glb = make_glb("wheeled", tmp_path / "wheeled.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    s = _script()
    s["effects"] = [{"id": "droplets", "params": {"density": 1.0}}]
    res = compile_scene(s, prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), save_blend=True)
    assert "tyre_contact" in res["realism"] and res["realismScene"]["tyre_d_m"] > 0.005   # the car drops
    assert res["fx"]["droplets"]["dripEvents"] > 0
    py = tmp_path / "rel.py"
    py.write_text(_RELEASE.format(root=ROOT, blend=tmp_path / "c" / "scene.blend"), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(py)],
                          capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    got = json.loads(next(ln[4:] for ln in proc.stdout.splitlines() if ln.startswith("REL ")))
    assert got["offsetZ"] < -0.005 and len(got["jumps"]) >= 3, got
    # 2e-3 frames of fall is micrometres: anything past 0.2 mm is the release jump
    assert max(got["jumps"]) < 2e-4, got
