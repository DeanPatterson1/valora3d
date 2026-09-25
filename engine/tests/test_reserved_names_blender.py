"""Review chunk1 #1: an upload can never claim an engine name. The engine finds valora_motion, valora_wind_field,
valora_wind, valora_rz_* ... by name and reads valora_* custom properties; a GLB whose objects, meshes,
materials or glTF extras use those names must not hijack them."""
import subprocess
from pathlib import Path

import pytest

from engine.ingest.run import BLENDER
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]
ROOT = Path(__file__).resolve().parents[2]

_HOSTILE = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
names = ("valora_wind_field", "valora_motion", "valora_realism_offset", "valora_subject", "valora_rz_dust", "Body")
for i, n in enumerate(names):
    bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0.3 * i, 0, 0.1))
    o = bpy.context.object
    o.name, o.data.name = n, n
    o["valora_ground"] = 1
    o["valora_block"] = "field/wind"
    m = bpy.data.materials.new("valora_grade"); o.data.materials.append(m)
bpy.context.scene["valora_wind"] = {"directionDeg": 1.0, "speedMs": 99.0}
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_extras=True)
'''

_CHECK = r'''
import sys
sys.path.insert(0, r"{root}")
import bpy
from engine.blender.scene_io import import_subject
from engine.blender.realism_rig import build_rig, rig
from engine.blender.wind_field import ensure_force_field
objs, meshes = import_subject(r"{glb}")
assert len(meshes) == 6, [o.name for o in meshes]
for kind in ("objects", "meshes", "materials"):
    bad = [i.name for i in getattr(bpy.data, kind) if i.name.startswith("valora_")]
    assert not bad, (kind, bad)
assert not [k for o in objs for k in o.keys() if k.startswith("valora_")]
assert [k for k in bpy.context.scene.keys() if k.startswith("valora_")] == ["valora_import_fps"], list(bpy.context.scene.keys())
root = bpy.data.objects.new("valora_subject", None)
bpy.context.scene.collection.objects.link(root)
assert root.name == "valora_subject"
build_rig(bpy.context.scene, root)
motion, offset = rig()
assert motion.type == "EMPTY" and offset.type == "EMPTY" and root.parent == offset
ob = ensure_force_field({{"speedMs": 4.0, "gustiness": 0.2, "directionDeg": 90.0}}, 7)
assert ob.type == "EMPTY" and ob.field.type == "WIND" and ob not in objs
assert all(not o.hide_render for o in meshes)          # the upload's geometry is untouched
assert len(set(len(o.data.vertices) for o in meshes)) == 1 and len(meshes[0].data.vertices) >= 8
print("RN-OK")
'''


def _run(script, *args):
    return subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script), "--", *map(str, args)], capture_output=True, text=True, timeout=300)


def test_an_upload_cannot_claim_engine_names(tmp_path):
    make, glb = tmp_path / "make.py", tmp_path / "hostile.glb"
    make.write_text(_HOSTILE, encoding="utf-8")
    proc = _run(make, glb)
    assert proc.returncode == 0 and glb.exists(), proc.stderr[-2000:]
    check = tmp_path / "check.py"
    check.write_text(_CHECK.format(root=ROOT, glb=glb), encoding="utf-8")
    proc = _run(check)
    assert proc.returncode == 0 and "RN-OK" in proc.stdout, proc.stdout[-3000:] + proc.stderr[-3000:]
