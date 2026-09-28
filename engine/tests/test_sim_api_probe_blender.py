"""Task 94: probe the Blender 5.0.1 simulation cache APIs and pin one portable format per method.

Each test runs a tiny scene in headless Blender (no render), asserts the fact the phase-6 bake stage
relies on, and records its measurements in var/probe/sim_api.json. engine/bake/formats.py cites these
tests. Every probe here bakes in seconds, so none is `slow`. Run serially: nothing else may bake."""
import json
import math
import subprocess
from pathlib import Path

import pytest

from engine.blender_cli import BLENDER, blender_argv
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]

ROOT = Path(__file__).resolve().parents[2]
PROBE_JSON = ROOT / "var" / "probe" / "sim_api.json"
PROPS_DIR = ROOT / "var" / "fixtures" / "sim"
MAKE_PROPS = Path(__file__).resolve().parent / "fixtures" / "sim" / "make_props.py"

# Every probe script starts with this: argv after "--", the repo on sys.path (engine is stdlib-only),
# and emit(), which prints the one line the host parses.
_PRELUDE = r'''
import bpy, json, math, os, sys, time
ARGS = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, ARGS[0])
def emit(d):
    print("PROBE_JSON " + json.dumps(d), flush=True)
def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene
'''


def _run(tmp_path, body, *args, timeout=600):
    script = tmp_path / f"probe_{abs(hash(body)) % 10**8}.py"
    script.write_text(_PRELUDE + body, encoding="utf-8")
    proc = subprocess.run(blender_argv(script, [ROOT, *args]), capture_output=True, text=True, timeout=timeout)
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


@pytest.fixture(scope="module")
def props():
    names = ("can.glb", "glass.glb", "plate.glb", "cube.glb")
    if not all((PROPS_DIR / n).exists() for n in names):
        subprocess.run([BLENDER, "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
                        "--python", str(MAKE_PROPS), "--", str(PROPS_DIR)], check=True, capture_output=True, timeout=300)
    assert all((PROPS_DIR / n).stat().st_size > 0 for n in names)
    return PROPS_DIR


# 1. Bullet stepped with frame_set --------------------------------------------------------------------
_BULLET = r'''
cube_glb = ARGS[1]
def run(default_margin):
    sc = fresh()
    bpy.ops.mesh.primitive_plane_add(size=4)
    plane = bpy.context.object
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    bpy.ops.import_scene.gltf(filepath=cube_glb)
    cube = [o for o in sc.objects if o.type == "MESH" and o is not plane][0]
    cube.location.z = 0.55                       # the prop sits on z=0; lift its base 0.5 m
    bpy.context.view_layer.objects.active = cube
    for o in sc.objects: o.select_set(o is cube)
    bpy.ops.rigidbody.object_add(type="ACTIVE")
    cube.rigid_body.collision_shape = "CONVEX_HULL"
    if not default_margin:
        for o in (cube, plane):
            o.rigid_body.use_margin = True; o.rigid_body.collision_margin = 0.0
    rbw = sc.rigidbody_world
    rbw.substeps_per_frame = 60; rbw.solver_iterations = 20
    pc = rbw.point_cache
    mats = []
    for f in range(pc.frame_start, pc.frame_start + 96):
        sc.frame_set(f)
        mats.append([c for row in cube.matrix_world for c in row])
    return sc, cube, pc, mats
sc, cube, pc, a = run(False)
_, _, _, b = run(False)
_, _, _, d = run(True)
zs = [m[11] for m in a]
out = {"frame_start": pc.frame_start, "zs": zs, "bit_identical": a == b, "rest_z": zs[-1],
       "rest_z_default_margin": d[-1][11], "default_margin": 0.04}
sc, cube, pc, _ = run(False)
try:
    with bpy.context.temp_override(selected_objects=[cube], active_object=cube, object=cube):
        out["bake_to_keyframes"] = str(bpy.ops.rigidbody.bake_to_keyframes(frame_start=1, frame_end=48))
except Exception as e:
    why = [ln.strip() for ln in str(e).splitlines() if "RuntimeError" in ln]
    out["bake_to_keyframes"] = "fails: " + (why[-1] if why else str(e))[:200]
emit(out)
'''


def test_bullet_frame_set_is_deterministic_and_rests_on_the_plane(tmp_path, props):
    first = _run(tmp_path, _BULLET, props / "cube.glb")
    second = _run(tmp_path, _BULLET, props / "cube.glb")
    zs = first["zs"]
    contact = next(i for i, z in enumerate(zs) if z < 0.06)
    assert all(zs[i + 1] <= zs[i] for i in range(contact)), "z must fall monotonically until contact"
    assert abs(first["rest_z"] - 0.05) <= 0.001, first["rest_z"]
    assert first["bit_identical"], "two runs in one process differ"
    assert first["zs"] == second["zs"], "two Blender processes differ"
    _record("rigid_keys", {"frame_start": first["frame_start"], "rest_z": first["rest_z"],
                           "rest_z_default_margin": first["rest_z_default_margin"], "contact_frame": contact + 1,
                           "deterministic_in_process": first["bit_identical"], "deterministic_across_processes": True,
                           "bake_to_keyframes_headless": first["bake_to_keyframes"]})


# 2. Cloth -> PC2 -> Mesh Cache -------------------------------------------------------------------------
_CLOTH = r'''
from engine.bake.formats import pc2_header, pc2_frame_bytes
pc2 = ARGS[1]; OFF = int(ARGS[2])
sc = fresh()
bpy.ops.mesh.primitive_grid_add(x_subdivisions=20, y_subdivisions=20, size=1, location=(0, 0, 1))
g = bpy.context.object
vg = g.vertex_groups.new(name="pin")
vg.add([v.index for v in g.data.vertices if v.co.y > 0.49], 1.0, "REPLACE")
cm = g.modifiers.new("Cloth", "CLOTH"); cm.settings.vertex_group_mass = "pin"
frames = list(range(1, 31))
rec = {}
for f in frames:
    sc.frame_set(f)
    ev = g.evaluated_get(bpy.context.evaluated_depsgraph_get())
    rec[f] = [tuple(v.co) for v in ev.data.vertices]
n = len(g.data.vertices)
with open(pc2, "wb") as fh:
    fh.write(pc2_header(n, 7.0, 1.0, len(frames)))       # header start 7: proves the modifier ignores it
    for f in frames:
        fh.write(pc2_frame_bytes(rec[f]))
bpy.ops.mesh.primitive_grid_add(x_subdivisions=20, y_subdivisions=20, size=1, location=(0, 0, 1))
h = bpy.context.object
mc = h.modifiers.new("MC", "MESH_CACHE")
mc.cache_format = "PC2"; mc.filepath = pc2; mc.frame_start = OFF
err = {}
for f in (30, 1, 15):                                    # out of order
    sc.frame_set(OFF + f - 1)                            # sample i plays at scene frame frame_start + i
    ev = h.evaluated_get(bpy.context.evaluated_depsgraph_get())
    got = [tuple(v.co) for v in ev.data.vertices]
    err[f] = max(abs(a - b) for p, q in zip(got, rec[f]) for a, b in zip(p, q))
moved = max(abs(a - b) for p, q in zip(rec[30], rec[1]) for a, b in zip(p, q))
emit({"n": n, "bytes": os.path.getsize(pc2), "err": err, "moved": moved,
      "deform_motion_prop": hasattr(h, "cycles") and "use_deform_motion" in h.cycles.bl_rna.properties,
      "frame_start_default": h.modifiers.new("MC2", "MESH_CACHE").frame_start})
'''


def test_cloth_pc2_round_trips_through_mesh_cache_with_an_offset(tmp_path):
    off = 100
    r = _run(tmp_path, _CLOTH, tmp_path / "cloth.pc2", off)
    assert r["moved"] > 0.05, "the cloth must actually move"
    assert r["bytes"] == 32 + 30 * r["n"] * 12
    assert all(e <= 1e-6 for e in r["err"].values()), r["err"]
    _record("cloth_pc2", {"verts": r["n"], "bytes": r["bytes"], "max_err": max(r["err"].values()),
                          "offset_rule": "sample i plays at scene frame modifier.frame_start + i; the PC2 header "
                                         "start is ignored in time_mode FRAME",
                          "frame_start_default": r["frame_start_default"],
                          "cycles_use_deform_motion": r["deform_motion_prop"]})


# 3. GN simulation zone baked to disk -------------------------------------------------------------------
_GN_LIB = r'''
def tree(speed):
    ng = bpy.data.node_groups.new("sim", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    go = N.new("NodeGroupOutput")
    pts = N.new("GeometryNodePoints"); pts.inputs["Count"].default_value = 10
    si = N.new("GeometryNodeSimulationInput"); so = N.new("GeometryNodeSimulationOutput"); si.pair_with_output(so)
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = -speed
    cxyz = N.new("ShaderNodeCombineXYZ")
    sp = N.new("GeometryNodeSetPosition")
    st = N.new("GeometryNodeStoreNamedAttribute"); st.data_type = "FLOAT_VECTOR"
    st.inputs["Name"].default_value = "velocity"; st.inputs["Value"].default_value = (0, 0, -speed)
    L.new(pts.outputs["Points"], si.inputs["Geometry"])
    L.new(si.outputs["Delta Time"], mul.inputs[0]); L.new(mul.outputs[0], cxyz.inputs["Z"])
    L.new(si.outputs["Geometry"], sp.inputs["Geometry"]); L.new(cxyz.outputs[0], sp.inputs["Offset"])
    L.new(sp.outputs[0], st.inputs["Geometry"])
    L.new(st.outputs[0], so.inputs["Geometry"])           # by name: inputs[0] is "Skip"
    L.new(so.outputs["Geometry"], go.inputs["Geometry"])
    return ng
def obj(ng, d, fs, fe):
    o = bpy.data.objects.new("gn", bpy.data.meshes.new("m")); bpy.context.scene.collection.objects.link(o)
    m = o.modifiers.new("GN", "NODES"); m.node_group = ng
    b = m.bakes[0]; b.bake_target = "DISK"; b.use_custom_path = True; b.directory = d
    b.use_custom_simulation_frame_range = True; b.frame_start = fs; b.frame_end = fe
    return o, m, b
def read(o, f):
    bpy.context.scene.frame_set(f)
    g = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()   # hold g while reading
    pc = g.pointcloud
    if pc is None or not len(pc.attributes["position"].data):
        return None
    return [pc.attributes["position"].data[0].vector.z, tuple(pc.attributes["velocity"].data[0].vector)]
'''

_GN_BAKE = _GN_LIB + r'''
d, fs, fe = ARGS[1], int(ARGS[2]), int(ARGS[3])
sc = fresh(); sc.frame_start = fs
o, m, b = obj(tree(1.0), d, fs, fe)
t = time.time()
with bpy.context.temp_override(object=o, active_object=o):
    r = bpy.ops.object.geometry_node_bake_single(session_uid=o.session_uid, modifier_name=m.name, bake_id=b.bake_id)
files = sorted(os.path.relpath(os.path.join(rt, f), d) for rt, _, fs_ in os.walk(d) for f in fs_)
emit({"op": str(r), "bake_s": time.time() - t, "files": files})
'''

_GN_READ = _GN_LIB + r'''
d, fs, fe = ARGS[1], int(ARGS[2]), int(ARGS[3])
fresh()
o, m, b = obj(tree(5.0), d, fs, fe)          # a different fall speed: a re-simulation would show it
emit({str(f): read(o, f) for f in map(int, ARGS[4].split(","))})
'''


def test_gn_sim_zone_bakes_to_disk_and_a_fresh_scene_reads_it_out_of_order(tmp_path):
    d = tmp_path / "gn"
    bake = _run(tmp_path, _GN_BAKE, d, 1, 60)
    assert bake["op"] == "{'FINISHED'}"
    assert sum(f.startswith("meta") for f in bake["files"]) == 60 and any(f.startswith("blobs") for f in bake["files"])
    got = _run(tmp_path, _GN_READ, d, 1, 60, "1,40,20")
    for f in (1, 40, 20):
        z, vel = got[str(f)]
        assert math.isclose(z, -(f - 1) / 24, abs_tol=1e-5), (f, z)       # speed 1 m/s: the bake, not a re-sim
        assert vel == [0.0, 0.0, -1.0]
    # No offset API: a reader whose bake range is 101..160 does not shift 1..60, it holds the last frame.
    shifted = _run(tmp_path, _GN_READ, d, 101, 160, "101,120")
    assert shifted["101"][0] == shifted["120"][0] == pytest.approx(-59 / 24, abs=1e-5)
    # Pre-roll before the clip: negative scene frames bake and read back on the same numbering.
    dn = tmp_path / "gn_neg"
    neg = _run(tmp_path, _GN_BAKE, dn, -11, 48)
    assert any(Path(f).name.startswith("-0011_") for f in neg["files"]), neg["files"][:5]
    back = _run(tmp_path, _GN_READ, dn, -11, 48, "28,-11,1")
    for f in (-11, 1, 28):
        assert math.isclose(back[str(f)][0], -(f + 11) / 24, abs_tol=1e-5), (f, back[str(f)])
    _record("gn_disk", {"operator": "object.geometry_node_bake_single(session_uid, modifier_name, bake_id) under "
                                    "temp_override(object, active_object)",
                        "layout": "meta/<frame:05d>_<subframe:05d>.json + blobs/", "bake_s_60f": bake["bake_s"],
                        "offset_rule": "none: frames are absolute scene frames; a reader range 101..160 over a "
                                       "1..60 bake holds frame 60",
                        "preroll_rule": "bake from clip_start - preroll; negative frames work (-11..48 read back "
                                        "exactly)",
                        "reads_without_resim": True})


# 4. Mantaflow gas -> OpenVDB -> Volume object ----------------------------------------------------------
_GAS = r'''
d = ARGS[1]; START = int(ARGS[2])
sc = fresh(); sc.frame_start = 1; sc.frame_end = 20
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1)); dom = bpy.context.object
fm = dom.modifiers.new("Fluid", "FLUID"); fm.fluid_type = "DOMAIN"; ds = fm.domain_settings
ds.domain_type = "GAS"; ds.resolution_max = 32
ds.cache_type = "ALL"; ds.cache_data_format = "OPENVDB"; ds.cache_directory = d
ds.cache_frame_start = 1; ds.cache_frame_end = 20
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.2, location=(0, 0, 0.3)); fl = bpy.context.object
f2 = fl.modifiers.new("Fluid", "FLUID"); f2.fluid_type = "FLOW"
f2.flow_settings.flow_type = "SMOKE"; f2.flow_settings.flow_behavior = "INFLOW"
t = time.time()
with bpy.context.temp_override(object=dom, active_object=dom, scene=sc):
    r = bpy.ops.fluid.bake_all()
bake_s = time.time() - t
vdbs = sorted(f for f in os.listdir(os.path.join(d, "data")) if f.endswith(".vdb"))
sc2 = fresh()
v = bpy.data.volumes.new("smoke"); v.filepath = os.path.join(d, "data", vdbs[0])
o = bpy.data.objects.new("smoke", v); sc2.collection.objects.link(o)
v.is_sequence = True; v.frame_duration = len(vdbs); v.frame_start = START; v.frame_offset = 0
v.sequence_mode = "CLIP"
def at(f):
    sc2.frame_set(f)
    g = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.grids; g.load()
    return {"file": os.path.basename(g.frame_filepath), "grids": sorted((x.name, x.data_type) for x in g)}
seen = {f: at(f) for f in (START + 9, START, START + 19, START + 20, START - 1)}
v.frame_offset = 5
off5 = at(START)["file"]
emit({"op": str(r), "bake_s": bake_s, "vdbs": vdbs, "seen": seen, "off5": off5,
      "velocity_grid": v.velocity_grid, "velocity_scale": v.velocity_scale, "velocity_unit": v.velocity_unit,
      "velocity_unit_enum": [i.identifier for i in v.bl_rna.properties["velocity_unit"].enum_items]})
'''


def test_gas_bakes_vdb_and_a_volume_plays_it_with_a_frame_offset(tmp_path):
    start = 101
    r = _run(tmp_path, _GAS, tmp_path / "gas", start)
    assert r["op"] == "{'FINISHED'}" and len(r["vdbs"]) == 20
    seen = {int(k): v for k, v in r["seen"].items()}
    assert seen[start]["file"] == "fluid_data_0001.vdb" and seen[start + 9]["file"] == "fluid_data_0010.vdb"
    assert seen[start + 19]["file"] == "fluid_data_0020.vdb"
    assert seen[start + 20]["grids"] == [] and seen[start - 1]["grids"] == []      # CLIP: empty outside
    names = [n for n, _ in seen[start + 9]["grids"]]
    assert "density" in names and "velocity" in names
    assert ["velocity", "VECTOR_FLOAT"] in seen[start + 9]["grids"]
    assert r["off5"] == "fluid_data_0006.vdb"
    _record("gas_vdb", {"bake_s_res32_20f": r["bake_s"], "files": "data/fluid_data_####.vdb (+ config/*.uni)",
                        "grids": seen[start + 9]["grids"],
                        "offset_rule": "file index = scene_frame - Volume.frame_start + 1 + Volume.frame_offset; "
                                       "sequence_mode CLIP is empty outside",
                        "velocity_grid": r["velocity_grid"], "velocity_scale": r["velocity_scale"],
                        "velocity_unit": r["velocity_unit"], "velocity_unit_enum": r["velocity_unit_enum"]})


# 5. Mantaflow liquid -> Alembic -> Mesh Sequence Cache ------------------------------------------------
_LIQUID = r'''
d, abc, fmt = ARGS[1], ARGS[2], ARGS[3]
sc = fresh(); sc.frame_start = 1; sc.frame_end = 20
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5)); dom = bpy.context.object
fm = dom.modifiers.new("Fluid", "FLUID"); fm.fluid_type = "DOMAIN"; ds = fm.domain_settings
ds.domain_type = "LIQUID"; ds.resolution_max = 32; ds.use_mesh = True; ds.use_speed_vectors = True
ds.cache_type = "ALL"; ds.cache_data_format = fmt; ds.cache_directory = d
ds.cache_frame_start = 1; ds.cache_frame_end = 20
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(0, 0, 0.7)); fl = bpy.context.object
f2 = fl.modifiers.new("Fluid", "FLUID"); f2.fluid_type = "FLOW"
f2.flow_settings.flow_type = "LIQUID"; f2.flow_settings.flow_behavior = "INFLOW"
t = time.time()
with bpy.context.temp_override(object=dom, active_object=dom, scene=sc):
    r = bpy.ops.fluid.bake_all()
bake_s = time.time() - t
sc.frame_set(15)
e = dom.evaluated_get(bpy.context.evaluated_depsgraph_get())
vel = [tuple(x.vector) for x in e.data.attributes["velocity"].data]
out = {"op": str(r), "bake_s": bake_s, "mesh_files": sorted(os.listdir(os.path.join(d, "mesh")))[:3],
       "n_mesh_files": len(os.listdir(os.path.join(d, "mesh"))), "n15": len(vel),
       "maxv15": max(math.sqrt(sum(c * c for c in v)) for v in vel), "first15": vel[:3]}
if abc:
    fl.hide_render = True; fl.hide_viewport = True
    for x in sc.objects: x.select_set(x is dom)         # the exporter reads the real selection flags
    bpy.context.view_layer.objects.active = dom
    with bpy.context.temp_override(selected_objects=[dom], active_object=dom, object=dom):
        out["export"] = str(bpy.ops.wm.alembic_export(filepath=abc, start=1, end=20, selected=True,
                                                      evaluation_mode="RENDER"))
    out["abc_bytes"] = os.path.getsize(abc)
emit(out)
'''

_ABC_READ = r'''
abc = ARGS[1]
sc = fresh()
bpy.ops.wm.alembic_import(filepath=abc)
o = [x for x in sc.objects if x.type == "MESH"][0]
mod = [x for x in o.modifiers if x.type == "MESH_SEQUENCE_CACHE"][0]
cf = mod.cache_file
def at(f):
    sc.frame_set(f)
    e = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    a = e.data.attributes.get("velocity")
    vs = [tuple(x.vector) for x in a.data] if a else []
    return {"n": len(e.data.vertices), "maxv": max((math.sqrt(sum(c * c for c in v)) for v in vs), default=None),
            "first": vs[:3]}
out = {"f15": at(15), "f5": at(5), "velocity_name": cf.velocity_name, "velocity_unit": cf.velocity_unit,
       "read_data": sorted(mod.read_data)}
cf.frame_offset = 100
out["off100_at115"] = at(115)
cf.frame_offset = 0
emit(out)
'''


def test_liquid_speed_vectors_need_uni_data_and_survive_alembic_with_an_offset(tmp_path):
    vdb = _run(tmp_path, _LIQUID, tmp_path / "liq_vdb", "", "OPENVDB")
    assert vdb["op"] == "{'FINISHED'}" and vdb["n_mesh_files"] == 20 and vdb["n15"] > 100
    # 5.0.1 fact: with OpenVDB data the mesh speed vectors are silently dropped (no lVelMesh files, all zero).
    assert vdb["maxv15"] == 0.0
    abc = tmp_path / "liq.abc"
    uni = _run(tmp_path, _LIQUID, tmp_path / "liq_uni", abc, "UNI")
    assert uni["n_mesh_files"] == 40 and any(f.startswith("fluid_mesh_") for f in uni["mesh_files"])
    assert uni["maxv15"] > 0.1
    assert uni["export"] == "{'FINISHED'}" and uni["abc_bytes"] > 100_000, uni.get("abc_bytes")
    got = _run(tmp_path, _ABC_READ, abc)
    assert got["f15"]["n"] == uni["n15"] and got["f15"]["first"] == uni["first15"]
    assert got["f15"]["maxv"] == pytest.approx(uni["maxv15"], rel=1e-6)
    assert got["f5"]["n"] != got["f15"]["n"]
    assert got["off100_at115"]["n"] == got["f15"]["n"] and got["off100_at115"]["first"] == got["f15"]["first"]
    _record("liquid_abc", {"bake_s_res32_20f_uni": uni["bake_s"], "abc_bytes_20f": uni["abc_bytes"],
                           "speed_vectors": "need cache_data_format='UNI': OPENVDB silently drops them "
                                            "(no lVelMesh_####.uni, velocity all zero)",
                           "velocity_attribute": "mesh POINT attribute 'velocity', kept exactly by Alembic "
                                                 "export/import (not CacheFile.velocity_name "
                                                 f"{got['velocity_name']!r})",
                           "velocity_unit_default": got["velocity_unit"], "maxv15_raw": uni["maxv15"],
                           "velocity_units_note": "max 11 at res 32 for a < 0.7 m drop: not m/s; calibrate in T114",
                           "offset_rule": "abc frame = scene_frame - CacheFile.frame_offset",
                           "read_data": got["read_data"]})


# 6. Force-field seed range and wind strength -----------------------------------------------------------
_FIELD = r'''
def scene(strength, mass):
    sc = fresh(); sc.render.fps = 24; sc.use_gravity = False
    bpy.ops.object.effector_add(type="WIND", location=(0, 0, 0), rotation=(0, math.pi / 2, 0))   # blows +x
    w = bpy.context.object; w.field.strength = strength; w.field.flow = 0.0
    bpy.ops.mesh.primitive_plane_add(size=0.01)
    e = bpy.context.object
    st = e.modifiers.new("P", "PARTICLE_SYSTEM").particle_system.settings
    st.count = 1; st.frame_start = 1; st.frame_end = 1; st.lifetime = 500; st.normal_factor = 0.0
    st.mass = mass; st.effector_weights.gravity = 0.0
    return sc, w, e
sc, w, e = scene(1.0, 1.0)
p = w.field.bl_rna.properties["seed"]
w.field.seed = 200; hi = w.field.seed
w.field.seed = 0; lo = w.field.seed
drift = {}
for S in (1.0, 2.0, 5.0):
    for mass in (1.0, 2.0):
        sc, w, e = scene(S, mass)
        xs = {}
        for f in range(1, 27):
            sc.frame_set(f)
            xs[f] = e.evaluated_get(bpy.context.evaluated_depsgraph_get()).particle_systems[0].particles[0].location.x
        drift[f"{S}/{mass}"] = xs[26] - xs[2]            # 24 frames = 1 s after emission
emit({"range": [p.hard_min, p.hard_max], "seed200": hi, "seed0": lo, "drift": drift})
'''


def test_wind_seed_clamps_to_1_128_and_strength_is_a_force(tmp_path):
    r = _run(tmp_path, _FIELD)
    assert r["range"] == [1, 128] and r["seed200"] == 128 and r["seed0"] == 1   # clamped, never rejected
    for key, dx in r["drift"].items():
        s, m = map(float, key.split("/"))
        assert dx == pytest.approx(s / (2 * m), rel=0.01), (key, dx)          # a = S/m, x = a t^2 / 2
    _record("force_field", {"seed_range": r["range"], "seed_out_of_range": "clamped (200 -> 128, 0 -> 1)",
                            "wind_flow0_drift_1s": r["drift"],
                            "rule": "WIND flow=0 on a legacy particle is a constant force: a = strength / mass "
                                    "(m/s^2), so drift over 1 s = strength / (2 mass) m (input to T107)"})
