"""Follow-up to review chunk5 #10: a drip lets go where (and how fast) it hung even when the realism offset keeps
changing while it falls (landing_settle's overshoot after a stop). The drip tree used to correct its release
by the offset's shift read at the CURRENT frame, exact only while the offset held still in flight; the droplets
finalizer (run after every realism block is keyed) now re-samples each drip's release position and velocity
from the keyed motion and offset curves at its release frame, so the flight is ballistic from the attached
state at release."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.tests.conftest import requires_blender

ROOT = Path(__file__).resolve().parents[2]


def test_release_states_read_the_segment_the_drip_rides():
    from importlib import util

    import numpy as np
    spec = util.spec_from_file_location("_droplets_build", ROOT / "engine" / "blocks" / "effect" / "droplets" / "build.py")
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.release_window(10.5, [10.0, 11.0]) == mod.RELEASE_DF             # no key in the last 0.05 frame
    assert mod.release_window(10.03, [10.0, 11.0]) == pytest.approx(0.03)        # stay on the key's segment
    assert mod.release_window(10.005, [10.0, 11.0]) == mod.RELEASE_DF            # on the key: the previous one
    # a rigid slide at 2 m/frame plus a lift keyed piecewise linear: exact position, the segment's velocity
    def world_at(f):
        m = np.eye(4)
        m[0, 3] = 2.0 * f
        m[2, 3] = 0.1 * max(0.0, f - 10.0)
        return m
    (pos, vel), = mod.release_states([(0.0, 0.0, 0.5)], [10.4], 30.0, world_at, [10.0, 11.0])
    assert np.allclose(pos, [20.8, 0.0, 0.54]) and np.allclose(vel, [60.0, 0.0, 3.0])


_PROBE = r'''
import sys, math, json
sys.path.insert(0, r"{root}")
import bpy, numpy as np
from engine.blender.realism_rig import fcurves
bpy.ops.wm.open_mainfile(filepath=r"{blend}")
scene = bpy.context.scene
fps, n, G = scene.render.fps, scene.frame_end, 9.81
ob = bpy.data.objects["valora_drips"]
ob.modifiers["valora_drips_drops"].show_viewport = False
off = bpy.data.objects["valora_realism_offset"]
mot = bpy.data.objects["valora_motion"]
keys = sorted({{kp.co[0] for o in (mot, off) if o.animation_data and o.animation_data.action
               for c in fcurves(o.animation_data.action) for kp in c.keyframe_points}})
tds = sorted({{round(v.value, 6) for v in ob.data.attributes["valora_td"].data}})

def at(x):
    whole = int(math.floor(x))
    scene.frame_set(whole, subframe=x - whole)
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    k = len(me.vertices)
    td = np.empty(k, np.float32); me.attributes["valora_td"].data.foreach_get("value", td)
    co = np.empty(k * 3); me.vertices.foreach_get("co", co)
    vel = np.empty(k * 3, np.float32); me.attributes["velocity"].data.foreach_get("vector", vel)
    ev.to_mesh_clear()
    return td, co.reshape(-1, 3), vel.reshape(-1, 3)

def one(x, t):
    td, co, vel = at(x)
    i = np.where(np.abs(td - t) < 1e-5)[0]
    return (co[i[0]], vel[i[0]]) if len(i) == 1 else (None, None)

def offset_at(x):
    whole = int(math.floor(x))
    scene.frame_set(whole, subframe=x - whole)
    return np.array(off.matrix_local, float)

rows, eps, dlt = [], 1e-3, 0.05
for t in tds:
    f = t * fps
    if not 2.0 <= f <= n - 3.0 or any(f - 0.07 <= k <= f for k in keys):
        continue                     # the attached velocity is read over [f - 0.05, f]: no key inside it
    a0, _ = one(f - eps - dlt, t)
    a1, _ = one(f - eps, t)
    f0, v0 = one(f + eps, t)
    if a0 is None or a1 is None or f0 is None:
        continue
    va = (a1 - a0) * fps / dlt                                    # the attached drip's velocity at release
    att = a1 + va * eps / fps
    drift, moved, k = 0.0, 0.0, 1.0
    while f + k <= n:
        fk, _ = one(f + k, t)
        if fk is None:
            break
        u = (k - eps) / fps
        want = f0 + v0 * u - np.array([0.0, 0.0, 0.5 * G * u * u])
        drift = max(drift, float(np.linalg.norm(fk - want)))
        moved = max(moved, float(np.abs(offset_at(f + k) - offset_at(f)).max()))
        k += 1.0
    rows.append({{"td": t, "pos": float(np.linalg.norm(f0 - att)), "vel": float(np.linalg.norm(v0 - va)) / fps,
                 "drift": drift, "offsetMoved": moved, "frames": k - 1.0}})
print("SETTLE " + json.dumps(rows))
'''


@pytest.mark.blender
@requires_blender
def test_a_drip_released_during_a_settle_flies_on_from_its_attached_state(tmp_path):
    from engine.compiler.run import compile_scene
    from engine.ingest.run import BLENDER, ingest
    from engine.tests.blender_fixtures import make_glb
    from engine.tests.test_realism_blender import _script
    glb = make_glb("strap", tmp_path / "strap.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    s = _script("slide_in")
    s["subject"]["motion"]["params"] = {"startS": 0.2, "durationS": 0.8}
    s["effects"] = [{"id": "droplets", "params": {"density": 1.0}}]
    res = compile_scene(s, prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), save_blend=True)
    assert "landing_settle" in res["realism"] and res["realismScene"]["settle_stops"] >= 1, res["realism"]
    assert res["fx"]["droplets"]["dripEvents"] > 0
    py = tmp_path / "settle.py"
    py.write_text(_PROBE.format(root=ROOT, blend=tmp_path / "c" / "scene.blend"), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(py)],
                          capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    rows = json.loads(next(ln[7:] for ln in proc.stdout.splitlines() if ln.startswith("SETTLE ")))
    moving = [r for r in rows if r["offsetMoved"] > 5e-4 and r["frames"] >= 1]
    assert len(rows) >= 3 and moving, rows              # some drips fall while the settle moves the offset
    # 0.2 mm: the release jump, the velocity mismatch over one frame, and the stray from the ballistic flight
    assert max(r["pos"] for r in rows) < 2e-4, rows
    assert max(r["vel"] for r in rows) < 2e-4, rows
    assert max(r["drift"] for r in rows) < 2e-4, rows
