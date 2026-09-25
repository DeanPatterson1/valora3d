"""Blender-side sampler and posed-bounds checks (review of 4d8bca5..76767a2). Tiny scenes, no renders."""
import collections
import json
import os
import subprocess
from pathlib import Path

import pytest

from engine.ingest.run import BLENDER, ingest

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "assets-in" / "models"

pytestmark = [pytest.mark.blender, pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")]


def _blender(body, tmp_path):
    """Run `body` in headless Blender with the repo importable and the extractor loaded as `bx`."""
    script = tmp_path / "t.py"
    script.write_text(
        "import sys, importlib.util\n"
        f"sys.path.insert(0, r'{ROOT}')\n"
        "import bpy, numpy as np\n"
        f"spec = importlib.util.spec_from_file_location('bx', r'{ROOT / 'engine/ingest/blender_extract.py'}')\n"
        "bx = importlib.util.module_from_spec(spec); spec.loader.exec_module(bx)\n"
        "from engine.blender import scene_io\n"
        "bpy.ops.wm.read_factory_settings(use_empty=True)\n" + body + "\nprint('BX-OK')\n",
        encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0 and "BX-OK" in proc.stdout, proc.stdout[-2000:] + proc.stderr[-2000:]
    return proc.stdout


def _shares(raw):
    mats = raw["materials"]
    total = sum(m["area"] for m in mats)
    counts = collections.Counter(int(r[7]) for r in raw["samples"])
    n = len(raw["samples"])
    return [(m["area"] / total, counts[i] / n) for i, m in enumerate(mats)]


@pytest.mark.parametrize("model", ["flighthelmet", "camera_01", "toycar"])
def test_sampled_material_shares_match_exact_area_shares(model, tmp_path):
    # Samples must be area-weighted: a material's share of samples ~= its share of surface area.
    # Reservoir sampling without replacement made them polygon-count-weighted instead
    # (flighthelmet mat5: exact 0.503, sampled 0.244).
    glb = MODELS / model / f"{model}.glb"
    if not glb.exists():
        pytest.skip(f"{model} not present")
    ingest(glb, workdir=tmp_path)
    raw = json.loads((tmp_path / "raw.json").read_text(encoding="utf-8"))
    for i, (exact, sampled) in enumerate(_shares(raw)):
        assert abs(exact - sampled) <= 0.03, (i, exact, sampled)
    total = sum(m["area"] for m in raw["materials"])
    w = {r[6] for r in raw["samples"]}
    assert len(w) == 1 and abs(w.pop() * len(raw["samples"]) - total) <= 1e-3 * total


def test_sampling_is_deterministic(tmp_path):
    out = _blender(
        "bpy.ops.mesh.primitive_uv_sphere_add(radius=1)\n"
        "o = bpy.context.object\n"
        "deps = bpy.context.evaluated_depsgraph_get()\n"
        "a, _ = bx.surface_samples([o], deps, lambda ob, slot: 0, 500)\n"
        "b, _ = bx.surface_samples([o], deps, lambda ob, slot: 0, 500)\n"
        "assert a.shape == (500, 9) and np.array_equal(a, b)\n"
        "assert abs(a[:, 6].sum() - 4 * np.pi) < 0.2, a[:, 6].sum()\n", tmp_path)
    assert "BX-OK" in out


def test_mirrored_object_keeps_outward_normals(tmp_path):
    # A negative-determinant matrix_world reverses winding, so transformed face normals point
    # inward unless flipped back.
    _blender(
        "bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))\n"
        "o = bpy.context.object; o.scale = (-1, 1, 1)\n"
        "bpy.context.view_layer.update()\n"
        "deps = bpy.context.evaluated_depsgraph_get()\n"
        "s, _ = bx.surface_samples([o], deps, lambda ob, slot: 0, 2000)\n"
        "top = s[(s[:, 2] > 1.999) & (abs(s[:, 0]) < 0.999) & (abs(s[:, 1]) < 0.999)]\n"
        "assert len(top) > 50 and (top[:, 5] > 0.99).all(), top[:5]\n"
        "side = s[(s[:, 0] > 0.999) & (abs(s[:, 1]) < 0.999) & (abs(s[:, 2] - 1) < 0.999)]\n"
        "assert len(side) > 50 and (side[:, 3] > 0.99).all(), side[:5]\n", tmp_path)


def test_posed_bounds_read_nla_strips_shape_keys_and_actual_key_times(tmp_path):
    # Cube A: its only action lives in an NLA strip (no active action), and peaks at frame 50
    # between keys at 1, 51 and 100 (16 evenly spaced frames over 1..100 never land on 50).
    # Cube B: shape-key animation lifts its top. Neither was seen when bounds read only
    # object.animation_data.action.
    _blender(
        "bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))\n"
        "a = bpy.context.object\n"
        "for f, z in ((1, 0), (50, 5), (51, 0), (100, 0)):\n"
        "    a.location.z = z; a.keyframe_insert('location', index=2, frame=f)\n"
        "act = a.animation_data.action\n"
        "tr = a.animation_data.nla_tracks.new(); tr.strips.new('s', 1, act)\n"
        "a.animation_data.action = None\n"
        "bpy.ops.mesh.primitive_cube_add(size=1, location=(10, 0, 0))\n"
        "b = bpy.context.object\n"
        "b.shape_key_add(name='Basis'); k = b.shape_key_add(name='Up')\n"
        "for v in k.data:\n"
        "    v.co.z += 3\n"
        "k.value = 0; k.keyframe_insert('value', frame=1)\n"
        "k.value = 1; k.keyframe_insert('value', frame=30)\n"
        "k.value = 0; k.keyframe_insert('value', frame=60)\n"
        "scene = bpy.context.scene; scene.frame_set(1)\n"
        "lo, hi, posed, animated = scene_io.posed_bounds(scene, [a, b])\n"
        "assert posed and animated\n"
        "assert hi[2] > 5.49, hi\n"
        "lo, hi, posed, animated = scene_io.posed_bounds(scene, [b])\n"
        "assert hi[2] > 3.49, hi  # the shape key's lifted top\n"
        "assert scene.frame_current == 1 and a.animation_data.action is None\n", tmp_path)


def test_openness_is_zero_inside_a_shell_and_on_the_floor_side(tmp_path):
    # A small cube sealed inside a big one: no camera outside can see it, so none of its samples
    # may be open. The big cube's top and sides face the camera's world (open 1); its bottom faces
    # the floor (open 0). This is what keeps detail points off hidden surfaces (t3_attempt).
    _blender(
        "bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1)); big = bpy.context.object\n"
        "bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0, 0, 1)); small = bpy.context.object\n"
        "deps = bpy.context.evaluated_depsgraph_get()\n"
        "s, _ = bx.surface_samples([big, small], deps, lambda ob, slot: 0, 3000)\n"
        "op = bx.openness(s, [big, small], deps, (-1, -1, 0), (1, 1, 2))\n"
        "assert op.shape == (len(s),) and ((op >= 0) & (op <= 1)).all()\n"
        "inner = np.abs(s[:, :3] - (0, 0, 1)).max(axis=1) < 0.21\n"
        "assert inner.sum() > 50 and (op[inner] == 0).all(), op[inner].max()\n"
        "top = (~inner) & (s[:, 5] > 0.99); side = (~inner) & (s[:, 3] > 0.99); bottom = (~inner) & (s[:, 5] < -0.99)\n"
        "assert (op[top] == 1).all() and (op[side] > 0.5).all() and (op[bottom] == 0).all()\n", tmp_path)
