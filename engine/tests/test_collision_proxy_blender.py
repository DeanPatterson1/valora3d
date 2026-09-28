"""Phase 6 Task 97: closed collision shells from the upload (Blender). Each subject runs in its own headless
Blender: the proxy is watertight, under its triangle cap, covers the profile's surface samples within 1.5
voxels, thickens a single-sided glass into a wall, leaves the upload's materials untouched, and is a hidden
render-less object tagged proxy/<purpose>. The measurements go to var/probe/collision_proxy.json (register)."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.blender_cli import BLENDER, blender_argv
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "assets-in" / "models"
PROFILES = Path(__file__).resolve().parent / "fixtures" / "profiles"
PROPS_DIR = ROOT / "var" / "fixtures" / "sim"
MAKE_PROPS = Path(__file__).resolve().parent / "fixtures" / "sim" / "make_props.py"
PROBE_JSON = ROOT / "var" / "probe" / "collision_proxy.json"

_SCRIPT = r'''
import bpy, json, sys, types
ARGS = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, ARGS[0])
from engine.blender import collision_proxy as cp
from engine.compiler.blender_main import material_digest, place_subject
from engine.blender.scene_io import import_subject
from engine.profile import SubjectProfile
glb, prof, purpose = ARGS[1], ARGS[2], ARGS[3]
if prof == "-":                                    # a procedural prop: measure a stand-in profile here
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    pts = [tuple(o.matrix_world @ v.co) for o in meshes for v in o.data.vertices]
    dims = [max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)]
    profile = types.SimpleNamespace(longest=max(dims), surfaceSamples=pts[::max(1, len(pts) // 2000)])
else:
    profile = SubjectProfile.from_dict(json.loads(open(prof, encoding="utf-8").read()))
    objs, meshes = import_subject(glb)
    place_subject(objs, profile)
before = material_digest(meshes)
n_before = {o.name: len(o.data.vertices) for o in meshes}
if len(ARGS) > 4:                                  # through the BakeStore twice: build, then read proxy.ply
    from engine.bake.store import BakeStore
    st = BakeStore(ARGS[4])
    first, r1 = cp.cached_proxy(meshes, profile, purpose, st, "m" * 64)
    out, report = cp.cached_proxy(meshes, profile, purpose, st, "m" * 64)
    report["firstFromCache"], report["trisBuilt"] = r1["fromCache"], cp.tri_count(first)
    report["trisRead"], report["watertightRead"] = cp.tri_count(out), cp.watertight(out)
else:
    out, report = cp.build_proxy(meshes, profile, purpose)
obs = out if isinstance(out, list) else [out]
report["tags"] = sorted({o.get("valora_block") for o in obs})
report["hideRender"] = all(o.hide_render for o in obs)
report["uploadUntouched"] = material_digest(meshes) == before and all(
    len(o.data.vertices) == n_before[o.name] for o in meshes)
report["voxelRule"] = cp.voxel_m(profile, purpose)
report["thicknessRule"] = cp.thickness_m(profile)
report["maxTrisRule"] = cp.max_tris(purpose)
print("PROBE_JSON " + json.dumps(report), flush=True)
'''


def _run(tmp_path, glb, prof, purpose, *extra):
    script = tmp_path / "proxy_probe.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    proc = subprocess.run(blender_argv(script, [ROOT, glb, prof, purpose, *extra]), capture_output=True, text=True, timeout=900)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_JSON ")]
    assert proc.returncode == 0 and lines, f"blender failed ({proc.returncode}):\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}"
    return json.loads(lines[-1][len("PROBE_JSON "):])


def _record(name, data):
    PROBE_JSON.parent.mkdir(parents=True, exist_ok=True)
    try:
        allp = json.loads(PROBE_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        allp = {}
    allp[name] = data
    PROBE_JSON.write_text(json.dumps(allp, indent=1, sort_keys=True), encoding="utf-8")


def _glass():
    if not (PROPS_DIR / "glass.glb").exists():
        subprocess.run([BLENDER, "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
                        "--python", str(MAKE_PROPS), "--", str(PROPS_DIR)], check=True, capture_output=True, timeout=300)
    return PROPS_DIR / "glass.glb"


@pytest.mark.parametrize("model", ["sports_car", "pocket_watch", "flighthelmet"])
def test_shell_is_closed_capped_covering_and_leaves_the_upload_alone(tmp_path, model):
    r = _run(tmp_path, MODELS / model / f"{model}.glb", PROFILES / f"{model}.json", "shell")
    _record(f"shell/{model}", r)
    assert r["watertight"], r
    assert r["tris"] <= r["maxTrisRule"] == 20000
    assert r["coverage95M"] <= 1.5 * r["voxelM"], r
    assert r["excess95M"] <= 2.5 * r["voxelM"], r                  # it hugs the model, not a blob round it
    assert r["uploadUntouched"] and r["hideRender"] and r["tags"] == ["proxy/shell"]


def test_a_single_sided_glass_becomes_a_closed_wall(tmp_path):
    r = _run(tmp_path, _glass(), "-", "shell")
    _record("shell/glass", r)
    assert r["watertight"], r
    assert r["minWallM"] >= r["thicknessRule"], r
    assert r["coverage95M"] <= 1.5 * r["voxelM"], r


def test_bullet_hulls_for_an_active_subject(tmp_path):
    r = _run(tmp_path, MODELS / "sneaker" / "sneaker.glb", PROFILES / "sneaker.json", "bullet_hull")
    _record("bullet_hull/sneaker", r)
    assert 1 <= r["hulls"] <= 16 and r["watertight"], r
    assert r["hullVolumeM3"] >= 0.9 * r["shellVolumeM3"], r
    assert r["uploadUntouched"] and r["tags"] == ["proxy/bullet_hull"]


def test_a_proxy_is_cached_in_the_bake_store_and_read_back(tmp_path):
    r = _run(tmp_path, _glass(), "-", "shell", tmp_path / "bake")
    assert r["firstFromCache"] is False and r["fromCache"] is True, r
    assert r["trisRead"] == r["trisBuilt"] and r["watertightRead"], r
    keys = [p.name for p in (tmp_path / "bake").iterdir() if p.name.startswith("proxy-")]
    assert len(keys) == 1
