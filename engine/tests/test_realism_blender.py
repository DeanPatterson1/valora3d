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


from engine.physics import probes  # noqa: E402


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


def test_the_wind_field_stays_in_its_envelope_and_blows_its_way(tmp_path):
    out = _bl(
        "from types import SimpleNamespace as NS\n"
        "from engine.catalog import Catalog\n"
        "from engine.blender.realism_probe import sample_wind\n"
        "b = Catalog.load().load_builder('field', 'wind')\n"
        "b(NS(scene=bpy.context.scene, seed=7, params={'directionDeg': 90.0, 'speedMs': 4.0, 'gustiness': 0.3, 'turbulence': 0.2}))\n"
        "pts = [(x * 0.7, y * 0.7, z * 0.3) for x in range(-4, 5) for y in range(-4, 5) for z in range(3)]\n"
        "for f in (1, 30, 90):\n"
        "    w = np.array(sample_wind(pts, f))\n"
        "    sp = np.linalg.norm(w, axis=1)\n"
        "    assert sp.min() >= 4.0 * (1 - 0.3) - 4.0 * 0.2 - 1e-3 and sp.max() <= 4.0 * (1 + 0.3) + 4.0 * 0.2 + 1e-3, (sp.min(), sp.max())\n"
        "    m = w.mean(axis=0); ang = np.degrees(np.arctan2(m[1], m[0]))\n"
        "    assert abs(ang - 90.0) <= 20.0, ang\n"
        "    assert np.std(sp) > 0.05  # gusts vary in space\n"
        "a, b2 = np.array(sample_wind(pts, 1)), np.array(sample_wind(pts, 30))\n"
        "assert not np.allclose(a, b2)  # and in time\n", tmp_path)


def test_calm_wind_leaves_the_haze_alone_and_a_breeze_makes_it_drift(tmp_path):
    s = _script(effects=[{"id": "haze_volume", "params": {"density": 0.3}}])
    calm = _compile("toycar", tmp_path / "calm", script=s)
    assert calm["wind"]["speedMs"] == 0.0 and calm["hazeDrift"] is False
    s["wind"] = {"id": "wind", "params": {"speedMs": 4.0}}
    windy = _compile("toycar", tmp_path / "windy", script=s)
    assert windy["hazeDrift"] is True and windy["built"][1] == "field:wind"


def test_contact_ground_grounds_the_subject_and_darkens_the_floor(tmp_path):
    res = _compile("toycar", tmp_path)
    assert "contact_ground" in res["realism"] and "realism:contact_ground" in res["built"]
    assert res["realismScene"]["contact_ao_materials"] >= 1 and res["realismScene"]["sink_m"] == 0.0
    assert res["realismScene"]["contact_ao_links_ok"]              # every AO link valid (Mix colour sockets)
    assert probes.grounded_ok(res["realismProbe"]["1"], 0.0)


def test_a_vehicle_contact_seam_reaches_under_its_sills(tmp_path):
    # review fix 7: the AO reach covers 1.5 x the ride height, not 5% of the height (65 mm on a car)
    res = _compile("sports_car", tmp_path)
    ride = _profile("sports_car").vehicle["rideHeightM"]
    assert res["realismScene"]["contact_ao_distance_m"] == pytest.approx(1.5 * ride, rel=1e-4)


from engine.ingest.run import ingest  # noqa: E402
from engine.tests.blender_fixtures import make_glb  # noqa: E402


def _wheeled(tmp_path):
    glb = make_glb("wheeled", tmp_path / "wheeled.glb")
    return glb, ingest(glb, workdir=tmp_path / "ingest")


def _patches_ok(res, prof, frame="1", patch=0.45):
    rec = res["realismProbe"][frame]
    assert len(rec["tyres"]) == len(prof.wheels), rec
    for i, w in enumerate(prof.wheels):
        t = rec["tyres"][str(i)]
        assert probes.tyre_patch_ok(t, w["radius"], patch, 0.0), (i, t, patch * w["radius"])
    assert probes.grounded_ok(rec, 0.0)


def test_tyres_on_the_wheeled_fixture_have_flat_patches(tmp_path):
    glb, prof = _wheeled(tmp_path)
    res = compile_scene(_script(), prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",),
                        realism_probe=[1])
    assert "tyre_contact" in res["realism"] and res["realismScene"]["tyre_objects"] >= 4
    assert res["realismScene"]["tyre_d_m"] == pytest.approx(0.45 ** 2 * 0.35 / 8, rel=0.1)
    _patches_ok(res, prof)


def test_sports_car_tyres_have_flat_patches(tmp_path):
    res = _compile("sports_car", tmp_path, frames=(1,))
    assert "tyre_contact" in res["realism"]
    _patches_ok(res, _profile("sports_car"))


def test_soft_ground_sinks_the_subject(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = _script(world={"id": "test_lawn", "params": {}})
    res = _compile("toycar", tmp_path / "c", script=s, catalog=cat)
    sink = res["realismScene"]["sink_m"]
    assert sink == pytest.approx(min(0.012, 0.1 * _profile("toycar").sizeM[2]), rel=1e-4)
    rec = res["realismProbe"]["1"]
    assert probes.grounded_ok(rec, sink) and rec["minZ"] < -0.5 * sink


def _pin(script, bid, **params):
    s = json.loads(json.dumps(script))
    s["realism"] = [{"kind": "realism", "id": bid, "params": params}]
    return s


def test_the_body_sits_on_its_springs(tmp_path):
    glb, prof = _wheeled(tmp_path)
    a = compile_scene(_pin(_script(), "suspension", sagFracR=0.0), prof, glb, tmp_path / "a", render=False,
                      skip_kinds=("grade",), realism_probe=[1])
    b = compile_scene(_script(), prof, glb, tmp_path / "b", render=False, skip_kinds=("grade",), realism_probe=[1])
    gap = lambda r: r["realismProbe"]["1"]["bodyMeanZ"] - r["realismProbe"]["1"]["unsprungMeanZ"]
    assert gap(a) - gap(b) == pytest.approx(0.015 * 0.35, rel=0.15)     # sagFracR x r
    assert probes.grounded_ok(b["realismProbe"]["1"], 0.0)                # the wheels never leave the ground


def test_the_body_pitches_and_settles_after_a_stop(tmp_path):
    glb, prof = _wheeled(tmp_path)
    cat = catalog_with_fixtures(tmp_path)
    s = _script("test_slide_stop")
    res = compile_scene(s, prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), catalog=cat,
                        realism_probe=[1])
    stop = res["motionEvents"]["stops"][0]["frame"]
    res = compile_scene(s, prof, glb, tmp_path / "d", render=False, skip_kinds=("grade",), catalog=cat,
                        realism_probe=[stop, stop + 4, 90])
    body = lambda f: res["realismProbe"][str(f)]["drivers"]["valora_rz_body"][0]
    assert abs(body(stop)) > 0.0 and abs(body(stop + 4)) > 0.0
    assert abs(body(90)) < 0.05 * abs(body(stop))                         # settled by the end


def test_wheels_roll_without_slipping_and_keep_their_patch(tmp_path):
    glb, prof = _wheeled(tmp_path)
    cat = catalog_with_fixtures(tmp_path)
    s = _script("test_slide_stop")
    res = compile_scene(s, prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), catalog=cat,
                        realism_probe=[1, 30, 90])
    assert "wheel_roll" in res["realism"] and res["realismScene"]["wheel_slip"] < 0.02
    ang = lambda f, i: res["realismProbe"][str(f)]["drivers"][f"valora_rz_wheel_{i}"][0]
    travelled = 0.3 * prof.longest                                # test_slide_stop distanceFrac default
    assert abs(ang(90, 0) - ang(1, 0)) * prof.wheels[0]["radius"] == pytest.approx(travelled, rel=0.03)
    _patches_ok(res, prof, frame="30")                            # mid-roll: the patch is still at the bottom


def test_a_stop_overshoots_once_and_settles(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = _script("test_slide_stop")
    first = _compile("toycar", tmp_path / "a", script=s, catalog=cat)
    stop = first["motionEvents"]["stops"][0]["frame"]
    res = _compile("toycar", tmp_path / "b", script=s, catalog=cat, frames=(stop, stop + 3, 90))
    off = lambda f: res["realismProbe"][str(f)]["offset"]["loc"]
    ax = 0 if _profile("toycar").sizeM[0] >= _profile("toycar").sizeM[1] else 1
    assert abs(off(stop + 3)[ax]) > 0.0 and abs(off(90)[ax]) < 1e-4


def test_a_soft_subject_squashes_on_landing(tmp_path):
    glb = make_glb("plush", tmp_path / "plush.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    cat = catalog_with_fixtures(tmp_path)
    s = _script("test_drop")
    first = compile_scene(s, prof, glb, tmp_path / "a", render=False, skip_kinds=("grade",), catalog=cat)
    land = first["motionEvents"]["landings"][0]["frame"]
    res = compile_scene(s, prof, glb, tmp_path / "b", render=False, skip_kinds=("grade",), catalog=cat,
                        realism_probe=[land, 90])
    sc = lambda f: res["realismProbe"][str(f)]["offset"]["scale"]
    assert sc(land)[2] == pytest.approx(0.92, abs=0.01) and sc(land)[0] > 1.0
    assert sc(90)[2] == pytest.approx(1.0, abs=1e-3)


def test_a_soft_subject_dips_into_its_footprint(tmp_path):
    glb = make_glb("plush", tmp_path / "plush.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    res = compile_scene(_script(), prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), realism_probe=[1])
    assert "soft_rest" in res["realism"]
    rec, dip = res["realismProbe"]["1"], res["realismScene"]["soft_dip_m"]
    assert dip == pytest.approx(0.06 * prof.sizeM[2], rel=1e-3) and probes.grounded_ok(rec, 0.0)
    want = 2 * (2 * 0.15 * dip - dip * dip) ** 0.5                    # sphere chord at depth dip
    assert rec["footprintM"] == pytest.approx(want, rel=0.3)


def _angle(a, b):
    import math
    return math.degrees(math.acos(max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) /
                                             ((math.hypot(*a[:2]) * math.hypot(*b[:2])) or 1.0)))))


def test_grass_bends_downwind_and_is_still_in_calm_air(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = _script(world={"id": "test_lawn", "params": {}})
    s["wind"] = {"id": "wind", "params": {"speedMs": 4.0, "directionDeg": 30.0}}
    s["realism"] = [{"kind": "realism", "id": "ground_conform", "params": {"leanFrac": 0.0}}]  # sway only
    res = _compile("toycar", tmp_path / "w", script=s, catalog=cat, frames=(1, 45))
    assert "foliage_sway" in res["realism"]
    for f in ("1", "45"):
        sw = res["realismProbe"][f]["sway"]
        assert sw["n"] > 0 and _angle(sw["meanDisp"], (0.866, 0.5)) <= 45.0     # wind_coherent (BLOCKS §5)
    s["wind"]["params"]["speedMs"] = 0.0
    calm = _compile("toycar", tmp_path / "c", script=s, catalog=cat, frames=(1,))
    assert abs(calm["realismProbe"]["1"]["sway"]["meanDisp"][0]) < 1e-4


def test_grass_under_the_subject_is_pressed_flat_and_nearby_blades_lean_away(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = _script(world={"id": "test_lawn", "params": {}})
    res = _compile("toycar", tmp_path, script=s, catalog=cat, frames=(1,))
    sc = res["realismScene"]
    assert "ground_conform" in res["realism"]
    assert sc["conform_pressed_blades"] >= 20 and sc["conform_leaning_blades"] > 0
    assert res["realismProbe"]["1"]["foliageInSubject"] == 0     # no blade pokes through the subject


def test_a_hanging_strap_swings_downwind_and_the_body_does_not_move(tmp_path):
    glb = make_glb("strap", tmp_path / "strap.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    s = _script()
    s["wind"] = {"id": "wind", "params": {"speedMs": 5.0, "directionDeg": 0.0}}
    res = compile_scene(s, prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), realism_probe=[1, 60])
    assert "dangling_sway" in res["realism"]
    tagged = res["realismScene"]["dangling_verts"]
    assert 0 < tagged < res["realismScene"]["dangling_total_verts"] / 2      # only the strap
    for f in ("1", "60"):
        sw = res["realismProbe"][f]["sway"]
        assert sw["n"] > 0 and _angle(sw["meanDisp"], (1.0, 0.0)) <= 45.0
        assert sw["maxStretchFrac"] < 0.01                                   # rotated about the pivot, not sheared
        assert res["realismProbe"][f]["rigidMaxDispM"] < 1e-6                # untagged vertices never move
    s["wind"]["params"]["speedMs"] = 15.0                                    # past the 25 deg cap
    cap = compile_scene(s, prof, glb, tmp_path / "s", render=False, skip_kinds=("grade",), realism_probe=[1])
    sw = cap["realismProbe"]["1"]["sway"]
    assert sw["maxStretchFrac"] < 0.01 and 20.0 < sw["maxAngleDeg"] <= 25.0 + 0.05   # flutter stays under the cap


def test_dust_motes_stay_outside_the_subject_and_never_glow(tmp_path):
    s = _script(effects=[{"id": "haze_volume", "params": {"density": 0.3}}])
    res = _compile("toycar", tmp_path, script=s, frames=(1, 45, 90))
    sc = res["realismScene"]
    assert sc["dust_points"] == int(4000 * 0.2) and not sc["dust_emissive"]
    for f in ("1", "45", "90"):
        d = res["realismProbe"][f]["dust"]
        assert d["visible"] > 0 and d["visibleInSubject"] == 0               # PH-03 [C]
