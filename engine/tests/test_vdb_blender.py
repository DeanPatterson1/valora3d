"""Phase 6 Task 110 (lane S): engine/blender/vdb.place_vdb plays a Mantaflow OpenVDB sequence on a Volume object.

A tiny gas sequence (res 24, 12 frames; the T94 probe's recipe) is baked into a temp dir under the machine lock.
Then, in the same Blender: frames 9, 5 and 13 (out of order) of a play starting at frame 5 show files 5, 1 and 9
with a 'velocity' grid; a retime of 0.5 holds each file two frames (keyed frame_offset) with velocity_scale 0.5;
and the world bounds about the anchor scale exactly with scale_m."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.bake.lock import machine_lock
from engine.blender_cli import blender_argv
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]

ROOT = Path(__file__).resolve().parents[2]

_SCRIPT = r'''
import bpy, json, os, sys, time
from mathutils import Vector
ARGS = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, ARGS[0])
d = ARGS[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.frame_start = 1; sc.frame_end = 12
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1)); dom = bpy.context.object
fm = dom.modifiers.new("Fluid", "FLUID"); fm.fluid_type = "DOMAIN"; ds = fm.domain_settings
ds.domain_type = "GAS"; ds.resolution_max = 24
ds.cache_type = "ALL"; ds.cache_data_format = "OPENVDB"; ds.cache_directory = d
ds.cache_frame_start = 1; ds.cache_frame_end = 12
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25, location=(0, 0, 0.3)); fl = bpy.context.object
f2 = fl.modifiers.new("Fluid", "FLUID"); f2.fluid_type = "FLOW"
f2.flow_settings.flow_type = "SMOKE"; f2.flow_settings.flow_behavior = "INFLOW"
with bpy.context.temp_override(object=dom, active_object=dom, scene=sc):
    bpy.ops.fluid.bake_all()
files = sorted(os.path.join(d, "data", f) for f in os.listdir(os.path.join(d, "data")) if f.endswith(".vdb"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.frame_start = 1; sc.frame_end = 40
from engine.blender import vdb as VB
seq = {"files": files, "native": {"widthM": 2.0, "baseM": [1.0, 1.0, 0.0]}}
ob = VB.place_vdb(seq, anchor=(0.5, -0.3, 0.1), start_frame=5, name="valora_vdb_a", block="effect/_t")
seen = {f: VB.grids_at(ob, f) for f in (9, 5, 13, 4, 17)}
def world_bounds(o, f):
    sc.frame_set(f)
    bpy.context.view_layer.update()
    e = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    pts = [o.matrix_world @ Vector(c) for c in e.bound_box]
    return [min(p[i] for p in pts) for i in range(3)] + [max(p[i] for p in pts) for i in range(3)]
b1 = world_bounds(ob, 13)
ob2 = VB.place_vdb(seq, anchor=(0.5, -0.3, 0.1), scale_m=4.0, start_frame=5, name="valora_vdb_b")
b2 = world_bounds(ob2, 13)
ob3 = VB.place_vdb(seq, anchor=(0.0, 0.0, 0.0), start_frame=5, retime=0.5, name="valora_vdb_c")
slow = {f: VB.grids_at(ob3, f)["file"] for f in range(5, 30)}
print("PROBE_JSON " + json.dumps({"n": len(files), "seen": seen, "b1": b1, "b2": b2, "slow": slow,
      "vel": [ob.data.velocity_grid, ob.data.velocity_unit, ob.data.velocity_scale, ob3.data.velocity_scale],
      "block": ob.get("valora_block"), "play": dict(ob3["valora_vdb"])}), flush=True)
'''


@pytest.fixture(scope="module")
def probe(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("vdb")
    script = tmp / "vdb_probe.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    with machine_lock(timeout_s=1800):
        proc = subprocess.run(blender_argv(script, [ROOT, tmp / "gas"]), capture_output=True, text=True,
                              timeout=900)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_JSON ")]
    assert proc.returncode == 0 and lines, f"{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}"
    return json.loads(lines[-1][len("PROBE_JSON "):])


def test_frames_play_out_of_order_with_a_velocity_grid(probe):
    seen = {int(k): v for k, v in probe["seen"].items()}
    assert probe["n"] == 12
    assert seen[9]["file"] == "fluid_data_0005.vdb" and seen[5]["file"] == "fluid_data_0001.vdb"
    assert seen[13]["file"] == "fluid_data_0009.vdb"
    assert seen[4]["grids"] == [] and seen[17]["grids"] == []          # CLIP: empty before and after
    assert ["velocity", "VECTOR_FLOAT"] in seen[13]["grids"] and ["density", "FLOAT"] in seen[13]["grids"]
    assert probe["vel"][:3] == ["velocity", "FRAME", 1.0] and probe["block"] == "effect/_t"


def test_bounds_scale_exactly_about_the_anchor(probe):
    a = (0.5, -0.3, 0.1)
    b1, b2 = probe["b1"], probe["b2"]
    for i in range(6):
        assert b2[i] - a[i % 3] == pytest.approx(2.0 * (b1[i] - a[i % 3]), abs=1e-4), (i, b1, b2)
    assert b1[5] - b1[2] > 0.2                                          # a real plume, not an empty box
    vox = 2.0 / 24
    assert (b1[0] + b1[3]) / 2 == pytest.approx(a[0], abs=vox) and (b1[1] + b1[4]) / 2 == pytest.approx(a[1], abs=vox)
    assert b1[2] == pytest.approx(a[2], abs=vox)                       # the domain floor lands on the anchor


def test_a_half_speed_retime_holds_each_file_two_frames(probe):
    slow = {int(k): v for k, v in probe["slow"].items()}
    assert [slow[f] for f in (5, 6, 7, 8, 9)] == ["fluid_data_0001.vdb"] * 2 + ["fluid_data_0002.vdb"] * 2 + \
        ["fluid_data_0003.vdb"]
    assert slow[5 + 23] == "fluid_data_0012.vdb" and slow[5 + 24] is None
    assert probe["vel"][3] == 0.5 and probe["play"]["span"] == 24
