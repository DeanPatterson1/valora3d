"""Phase 6 Task 103: the shared GN point sim (engine/blender/gn_sim.py), baked to disk and read back.

5k points are dropped onto a closed proxy sphere over the ground. After the bake: no point lies inside the
proxy, every point carries a velocity attribute, and a FRESH Blender whose node group has no emitter (so it
could not re-simulate anything) reads frames 40, 1 and 20, out of order, identical to the bake process's own
reads. The bake time per 10k points per 100 frames is recorded in var/probe/gn_sim.json (it calibrates
engine/physics/gn_sim.BAKE_S_PER_10K_100F). Takes the machine bake lock."""
import json
import math
import subprocess
from pathlib import Path

import pytest

from engine.bake.lock import machine_lock
from engine.blender_cli import blender_argv
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]

ROOT = Path(__file__).resolve().parents[2]
PROBE_JSON = ROOT / "var" / "probe" / "gn_sim.json"
R, C = 0.3, (0.0, 0.0, 0.3)

_PRELUDE = r'''
import bpy, json, math, os, random, sys, time
ARGS = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, ARGS[0])
from engine.blender import gn_sim as G
from engine.physics import gn_sim as S
def emit(d):
    print("PROBE_JSON " + json.dumps(d), flush=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24
FR = {"bake_first": int(ARGS[2]), "bake_last": int(ARGS[3])}
def group(spawn, proxy):
    return G.ensure_point_sim("valora_test_sim", spawn=spawn, forces={"gravity": (0, 0, -9.81), "drag": 0.1},
                              collide={"proxy": proxy, "ground": 0.0, "restitution": 0.2, "friction": 0.4},
                              substeps=2)
def reads(ob, frames):
    out = {}
    for f in frames:
        r = G.read_points(ob, f)
        out[str(f)] = {"n": len(r["position"]), "pos": r["position"], "vel": r["velocity"], "age": r["age"]}
    return out
'''

_BAKE = _PRELUDE + r'''
N = int(ARGS[4])
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=0.3, location=(0, 0, 0.3))
proxy = bpy.context.object
rng = random.Random(7)
births = S.burst_frames(N, FR["bake_first"], 10, rng)
parts = []
for b in births:
    a, r = rng.random() * 2 * math.pi, 0.35 * math.sqrt(rng.random())
    parts.append({"birth": b, "pos": (r * math.cos(a), r * math.sin(a), 0.8 + 0.2 * rng.random()),
                  "vel": (0.0, 0.0, -1.0), "size": 0.004, "life": 10.0})
em = G.emitter_object("valora_test_emitter", parts)
ob = G.sim_object("valora_test_sim", group(em, proxy), ARGS[1], FR, "sim/_test_gn")
t = time.perf_counter()
G.bake_sim_object(ob)
bake_s = time.perf_counter() - t
files = [os.path.join(rt, f) for rt, _, fs in os.walk(ARGS[1]) for f in fs]
emit({"bake_s": bake_s, "files": len(files), "bytes": sum(os.path.getsize(f) for f in files),
      "reads": reads(ob, [int(x) for x in ARGS[5].split(",")])})
'''

_READ = _PRELUDE + r'''
ob = G.sim_object("valora_test_sim", group(None, None), ARGS[1], FR, "sim/_test_gn")
mod = ob.modifiers[0]
emit({"reads": reads(ob, [int(x) for x in ARGS[5].split(",")]),
      "guard": [(b.bake_target, b.use_custom_path, bool(b.directory)) for b in mod.bakes]})
'''


def _run(tmp_path, body, *args):
    script = tmp_path / f"gn_{abs(hash(body)) % 10**8}.py"
    script.write_text(body, encoding="utf-8")
    proc = subprocess.run(blender_argv(script, [ROOT, *args]), capture_output=True, text=True, timeout=900)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_JSON ")]
    assert proc.returncode == 0 and lines, f"blender failed ({proc.returncode}):\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}"
    return json.loads(lines[-1][len("PROBE_JSON "):])


def test_points_bake_to_disk_stay_out_of_the_proxy_and_read_back_out_of_order(tmp_path):
    d, n, first, last = tmp_path / "gn", 5000, -9, 50          # 60 frames with 10 of pre-roll below frame 1
    with machine_lock(timeout_s=1800):
        baked = _run(tmp_path, _BAKE, d, first, last, n, "40,1,20,50")
        back = _run(tmp_path, _READ, d, first, last, n, "40,1,20")
    assert baked["files"] > 60
    r50 = baked["reads"]["50"]
    assert r50["n"] == n                                         # every burst particle is alive and kept
    inside = sum(1 for p in r50["pos"] if math.dist(p, C) < R - 1e-3)
    assert inside == 0, inside
    assert min(p[2] for p in r50["pos"]) >= -1e-6               # nothing under the ground
    on_top = sum(1 for p in r50["pos"] if math.dist(p, C) < R + 0.01)
    assert on_top > 0.05 * n                                     # some came to rest on the sphere
    assert r50["vel"] is not None and len(r50["vel"]) == n
    for f in ("40", "1", "20"):
        assert back["reads"][f]["pos"] == baked["reads"][f]["pos"], f      # the cache, not a re-simulation
        assert back["reads"][f]["vel"] == baked["reads"][f]["vel"], f
        assert back["reads"][f]["n"] > 0
    assert all(g == ["DISK", True, True] for g in back["guard"])
    frames = last - first + 1
    rate = baked["bake_s"] / (n / 1e4) / (frames / 100)
    PROBE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROBE_JSON.write_text(json.dumps({"points": n, "frames": frames, "substeps": 2, "bake_s": baked["bake_s"],
                                      "bytes": baked["bytes"], "bake_s_per_10k_100f": rate}, indent=1),
                          encoding="utf-8")
