"""Realism defaults in Blender: compile probes at <= 3 frames, no renders unless a test says so."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.compiler.run import compile_scene
from engine.ingest.run import BLENDER
from engine.profile import SubjectProfile
from engine.tests.conftest import requires_blender
from engine.tests.realism_catalog import catalog_with_fixtures

pytestmark = [pytest.mark.blender, requires_blender]
ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
MODELS = ROOT / "assets-in" / "models"


def _profile(name):
    return SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))


def _script(motion="static", **over):
    s = json.loads((FIX / "script_realism.json").read_text(encoding="utf-8"))
    s["subject"]["motion"] = {"id": motion, "params": {}}
    s.update(over)
    return s


def _glb(name):
    glb = MODELS / name / f"{name}.glb"
    if not glb.exists():
        pytest.skip(f"{name} model not present (local-only)")
    return glb


def _compile(name, tmp, script=None, catalog=None, frames=(1,), skip=("grade",), **kw):
    return compile_scene(script or _script(), _profile(name), _glb(name), tmp, render=False, skip_kinds=skip,
                         catalog=catalog, realism_probe=list(frames), **kw)


def _bl(body, tmp_path):
    """Run `body` in headless Blender with the repo importable; must print nothing special, just not fail."""
    script = tmp_path / "t.py"
    script.write_text("import sys\n" f"sys.path.insert(0, r'{ROOT}')\n"
                      "import bpy, numpy as np\nbpy.ops.wm.read_factory_settings(use_empty=True)\n"
                      + body + "\nprint('RB-OK')\n", encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0 and "RB-OK" in proc.stdout, proc.stdout[-2000:] + proc.stderr[-2000:]
    return proc.stdout


def test_every_scene_has_the_subject_rig_and_a_motion_record(tmp_path):
    res = _compile("toycar", tmp_path)
    names = {o["name"] for o in res["objects"]}
    assert {"valora_motion", "valora_realism_offset", "valora_subject"} <= names
    assert res["built"][0] == "world:studio_cyc"
    assert res["motionEvents"] == {"stops": [], "landings": []}


def test_placed_space_round_trips_through_the_rig(tmp_path):
    _bl(
        "from engine.blender.realism_rig import build_rig, placed_points\n"
        "from engine.blender import gn\n"
        "root = bpy.data.objects.new('valora_subject', None); bpy.context.scene.collection.objects.link(root)\n"
        "motion, offset = build_rig(bpy.context.scene, root)\n"
        "motion.location = (1.0, -2.0, 0.3); motion.rotation_euler = (0, 0, 0.7)\n"
        "offset.location = (0.0, 0.0, -0.01); offset.scale = (1.02, 1.02, 0.95)\n"
        "root.scale = (0.5, 0.5, 0.5); root.location = (0.1, 0.2, 0.0)\n"
        "bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.3, 0.1, 0.5)); c = bpy.context.object\n"
        "c.rotation_euler = (0.2, 0.1, 0.3); c.parent = root\n"
        "bpy.context.view_layer.update()\n"
        "want = placed_points(c)\n"
        "t = gn.Tree('probe'); P, back = gn.placed(t, offset)\n"
        "t.store('p', P, 'FLOAT_VECTOR'); t.set_position(back(P)); gn.add_modifier(c, t.finish(), 'p')\n"
        "bpy.context.view_layer.update()\n"
        "ev = c.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()\n"
        "got = np.empty(len(me.vertices) * 3); me.attributes['p'].data.foreach_get('vector', got)\n"
        "co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)\n"
        "orig = np.empty(len(c.data.vertices) * 3); c.data.vertices.foreach_get('co', orig)\n"
        "assert np.allclose(got.reshape(-1, 3), want, atol=1e-5), (got[:6], want[:2])\n"
        "assert np.allclose(co, orig, atol=1e-5)  # back(P) is the identity\n", tmp_path)


def test_motion_events_come_from_the_motion_track(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    slide = _compile("toycar", tmp_path / "s", script=_script("test_slide_stop"), catalog=cat)
    assert len(slide["motionEvents"]["stops"]) == 1
    assert abs(slide["motionEvents"]["stops"][0]["frame"] - 54) <= 3          # 60% of 90 frames
    drop = _compile("toycar", tmp_path / "d", script=_script("test_drop"), catalog=cat)
    assert len(drop["motionEvents"]["landings"]) == 1
