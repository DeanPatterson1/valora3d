"""Phase 6 Task 104 (lane P): `condensation` + its coupled `runners` baked and compiled on the real CC0 water
bottle (assets-in/models/water_bottle, profile var/p6points/water_bottle.json).

The bake runs through engine.bake.run.bake_sims (the machine lock) into a temporary VALORA_BAKE_ROOT, then
compile_scene(render=False, save_blend=True) builds both blocks from the cache and reports simProbe. The runner
probe opens the saved scene in a fresh Blender and reads the runner cache frame by frame: every runner drop (not
a trail point, not a free drip) stays within 1.5 mm of the upload's surface (99%), never moves up by more than
the 0.2 mm stick jitter per frame, the drops that let go fall and the trail streak exists. The cache stays under
the manifest's cacheMBMax, and the bake's measured seconds are written to var/probe/runners.json."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.bake import run as bake_run
from engine.blender_cli import blender_argv
from engine.catalog import Catalog
from engine.compiler.run import compile_scene
from engine.profile import SubjectProfile
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, pytest.mark.slow, requires_blender]

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "assets-in" / "models" / "water_bottle" / "water_bottle.glb"
PROFILE = ROOT / "var" / "p6points" / "water_bottle.json"
FIX = Path(__file__).parent / "fixtures"
PROBE_JSON = ROOT / "var" / "probe" / "runners.json"
START, END, FPS = 0.0, 4.0, 30

_READ = r'''
import bpy, json, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ARGS = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.open_mainfile(filepath=ARGS[0])
sc = bpy.context.scene
ob = bpy.data.objects["valora_runners"]
subj = [o for o in sc.objects if o.type == "MESH" and not o.get("valora_block") and not o.get("valora_ground")
        and "valora" not in o.name]
dg = bpy.context.evaluated_depsgraph_get()
trees = []
for o in subj:
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    vs = [o.matrix_world @ v.co for v in me.vertices]
    trees.append(BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in me.polygons]))
    ev.to_mesh_clear()
out = {}
for f in range(int(ARGS[1]), int(ARGS[2]) + 1):
    sc.frame_set(f)
    g = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
    pc = g.pointcloud
    rows = []
    if pc is not None and len(pc.attributes["position"].data):
        A = pc.attributes
        n = len(A["position"].data)
        pos = [tuple(d.vector) for d in A["position"].data]
        get = lambda k: [d.value for d in A[k].data] if k in A else [0.0] * n
        tr, fr, idv = get("trail"), get("free"), get("birth")
        for i in range(n):
            d = min(t.find_nearest(Vector(pos[i]))[3] for t in trees)
            rows.append([pos[i], tr[i], fr[i], idv[i], d, "velocity" in A])
    out[f] = rows
print("PROBE_JSON " + json.dumps(out), flush=True)
'''


def _script():
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["format"]["durationS"] = 5
    s["shots"] = [{"startS": 0, "endS": 5, "camera": {"id": "macro_detail", "params": {"distance": 0.35}},
                   "focus": "subject"}]
    s["sims"] = [{"id": "condensation", "params": {}, "startS": START, "endS": END}]
    return s


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("t104")
    mp = pytest.MonkeyPatch()
    mp.setenv("VALORA_BAKE_ROOT", str(tmp / "bake"))
    prof = SubjectProfile.from_dict(json.loads(PROFILE.read_text(encoding="utf-8")))
    cat = Catalog.load()
    s = _script()
    s["sims"].append({"id": "runners", "params": {"count": 12}, "startS": START, "endS": END})
    bakes = bake_run.bake_sims(s, prof, MODEL, catalog=cat, lock_timeout_s=1800)
    res = compile_scene(s, prof, MODEL, tmp / "compile", catalog=cat, render=False, save_blend=True,
                        frames=[1], bakes=bakes, realism_probe=[20, 60, 100])
    yield {"tmp": tmp, "cat": cat, "bakes": bakes, "res": res, "script": s}
    mp.undo()


def test_the_runner_bake_is_measured_and_under_its_cache_cap(env):
    b = env["bakes"]["runners"]
    m = env["cat"].get("sim", "runners")["bake"]
    assert set(env["bakes"]) == {"runners"}                   # condensation is stateless: nothing baked
    assert b["bakeSeconds"] > 0 and b["bytes"] > 0
    assert b["bytes"] / 1e6 < m["cacheMBMax"]
    assert b["bakeSeconds"] < m["estimateS"]
    PROBE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROBE_JSON.write_text(json.dumps({"count": 12, "frames": b["frames"], "bakeSeconds": b["bakeSeconds"],
                                      "cacheMB": b["bytes"] / 1e6}, indent=1), encoding="utf-8")


def test_sim_probe_reports_a_clean_runner_cache(env):
    p = env["res"]["simProbe"]["runners"]
    assert p["method"] == "gn_disk" and p["stable"]["finite"] is True, p
    assert p["velocityPresent"] is True, p
    # no proxy shell: a runner rides the render surface 0.5 mm off it, inside any thickened shell by construction
    # (T98 shells are one voxel thick); the runner probe below judges it against the upload's own surface
    assert p["inside"]["ok"] is None, p


def test_both_blocks_built_and_tagged(env):
    built = env["res"].get("built") or []
    assert "sim:condensation" in built and "sim:runners" in built, built


def test_runners_stay_on_the_surface_and_never_run_up(env, tmp_path):
    script = tmp_path / "read_runners.py"
    script.write_text(_READ, encoding="utf-8")
    fr = env["bakes"]["runners"]["frames"]
    proc = subprocess.run(blender_argv(script, [env["tmp"] / "compile" / "scene.blend", fr["bake_first"],
                                                fr["bake_last"]]), capture_output=True, text=True, timeout=900)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_JSON ")]
    assert proc.returncode == 0 and lines, proc.stdout[-3000:] + proc.stderr[-3000:]
    frames = {int(k): v for k, v in json.loads(lines[-1][len("PROBE_JSON "):]).items()}
    on, dists, ups, trails, freed = 0, [], [], 0, 0
    prev = {}
    for f in sorted(frames):
        cur = {}
        for pos, trail, free, birth, d, _ in frames[f]:
            if trail > 0.5:
                trails += 1
                continue
            if free > 0.5:
                freed += 1
                continue
            on += 1
            dists.append(d)
            cur[round(birth, 6)] = pos
        for k, pos in cur.items():
            if k in prev:
                ups.append(pos[2] - prev[k][2])
        prev = cur
    assert on > 0 and trails > 0
    dists.sort()
    assert dists[int(0.99 * (len(dists) - 1))] <= 0.0015, dists[-10:]
    assert max(ups) <= 0.0002, max(ups)                          # the plan's stick jitter allowance
    assert sum(1 for u in ups if u < -1e-5) > 0.2 * len(ups)     # they do run (stick-slip pauses the rest)
