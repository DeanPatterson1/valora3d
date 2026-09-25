"""Block recipe step 4: compile each phase-5 block's fixture headless (no render) and assert its probe
conditions from compile.json."""
import copy
import json
import math
from pathlib import Path

import pytest

from engine.compiler.run import compile_scene
from engine.tests.conftest import requires_blender
from engine.tests.test_director_package import _p

pytestmark = [pytest.mark.blender, requires_blender]
FIX = Path(__file__).parent / "fixtures"
MODELS = Path(__file__).resolve().parents[2] / "assets-in" / "models"
T3 = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))


def _glb(model):
    glb = MODELS / model / f"{model}.glb"
    if not glb.exists():
        pytest.skip(f"{model} not present")
    return glb


def fog_script(mode="fog", wind=None):
    s = copy.deepcopy(T3)
    s["effects"] = [{"id": "ground_fog", "params": {"heightM": 0.4, "mode": mode}}]
    if wind:
        s["wind"] = {"id": "wind", "params": {"speedMs": wind}}
    return s


def test_ground_fog_is_one_tagged_volume_with_a_clear_pocket(tmp_path):     # Task 60
    from engine.physics import fog as F
    p = _p("sports_car")
    res = compile_scene(fog_script(wind=3.0), p, _glb("sports_car"), tmp_path, render=False)
    vols = [o for o in res["objects"] if o["volume"]]
    tagged = [o for o in vols if o["block"] == "effect/ground_fog"]
    assert len(tagged) == 1 and tagged[0]["name"] == "valora_fog", vols
    fog = res["fog"]
    assert fog["pocketRadiusM"] == pytest.approx(F.POCKET * p.radius)
    assert fog["heightM"] == pytest.approx(0.4) and fog["sigma0"] == pytest.approx(0.4 * F.FOG_SIGMA)
    # the pocket holds the subject centre: its distance from the fog centre is 0 < pocket radius
    assert math.dist(fog["centre"], p.center) == pytest.approx(0.0, abs=1e-6)
    far = max(math.dist(c, p.center) for c in res["cameraPositions"])
    width = fog["domainMax"][0] - fog["domainMin"][0]
    assert width == pytest.approx(F.domain_width(p.longest, far)) and fog["domainMin"][2] == 0.0
    assert fog["drift"] is True and "effect:ground_fog" in res["built"]


def test_mist_is_taller_and_thinner(tmp_path):
    p = _p("sports_car")
    res = compile_scene(fog_script("mist"), p, _glb("sports_car"), tmp_path, render=False)
    assert res["fog"]["heightM"] == pytest.approx(1.2) and res["fog"]["density"] == pytest.approx(0.16)
    assert res["fog"]["drift"] is False                      # no wind field: no wisps


FINISH = {"lens": "CompositorNodeLensdist", "grain_noise": "ShaderNodeTexWhiteNoise", "grain": "ShaderNodeMix",
          "grain_coords": "CompositorNodeImageCoordinates", "grain_luma": "CompositorNodeRGBToBW"}


def test_grade_finishing_is_off_by_default_and_adds_its_nodes_when_set(tmp_path):     # Task 61
    from engine.compiler.context import block_seed
    from engine.grade_plan import GRAIN_W_MOD
    p, glb = _p("toycar"), _glb("toycar")
    base = compile_scene(copy.deepcopy(T3), p, glb, tmp_path / "a", render=False)["grade"]
    s = copy.deepcopy(T3)
    s["grade"]["params"].update({"halation": 0.5, "lensDistortion": 0.006, "grain": 0.5})
    g = compile_scene(s, p, glb, tmp_path / "b", render=False)["grade"]
    assert not set(FINISH) & set(base["nodes"]) and base["finish"].get("halationStrength") == pytest.approx(0.10)
    extra = {k: v for k, v in g["nodeTypes"].items() if k not in base["nodeTypes"]}
    assert {k: extra[k] for k in FINISH} == FINISH, extra               # lens + the grain chain
    assert {k: v for k, v in g["nodeTypes"].items() if k in base["nodeTypes"]} == base["nodeTypes"]
    assert g["finish"]["halationStrength"] == pytest.approx(0.5)        # premium_dark's 0.10 replaced
    assert g["finish"]["lens"]["Distortion"] == pytest.approx(0.006)
    assert g["finish"]["lens"]["Dispersion"] == pytest.approx(0.00035, abs=1e-6)
    w0 = float(block_seed(T3["seed"], "grade", "mood_grade") % GRAIN_W_MOD)
    assert g["finish"]["grainW"] == pytest.approx([w0 + 1, w0 + 2])    # a fresh pattern every frame
    assert g["invalidLinks"] == [] and base["invalidLinks"] == []


def courtyard_script():
    s = copy.deepcopy(T3)
    s["world"] = {"id": "rain_courtyard", "params": {}}
    s["lighting"] = {"id": "softbox_three_point", "params": {}}   # hdri_only lands in Task 72
    return s


@pytest.mark.parametrize("model", ["sports_car", "pocket_watch"])
@pytest.mark.parametrize("library", ["pinned", "empty"])
def test_rain_courtyard_builds_its_contract(model, library, tmp_path, monkeypatch):     # Task 63
    from engine.assets import LIBRARY, LIBRARY_ENV
    if library == "empty":
        monkeypatch.setenv(LIBRARY_ENV, str(tmp_path / "no_assets"))   # every fallback must build
    elif not (LIBRARY / "polyhaven").exists():
        pytest.skip("pinned assets not imported (py tools/assets/import_local.py)")
    p = _p(model)
    res = compile_scene(courtyard_script(), p, _glb(model), tmp_path / "c", render=False, skip_kinds=("grade",),
                        realism_probe=[1])
    c = res["courtyard"]
    assert (c["hdri"], c["asphaltMaps"], c["grass"]) == ((True, True, "asset") if library == "pinned"
                                                         else (False, False, "procedural"))
    ground = [o for o in res["objects"] if o["ground"]]
    assert [o["name"] for o in ground] == ["valora_court_ground"] and ground[0]["location"][2] == 0.0
    foliage = [o for o in res["objects"] if o["foliage"]]
    assert len(foliage) >= 1 and c["grassIslandRootSwayMax"] == pytest.approx(0.0, abs=1e-6)
    assert "ground_conform" in res["realism"] and "foliage_sway" in res["realism"]
    assert abs(res["realismProbe"]["1"]["minZ"]) <= 0.01 * p.longest          # grounded on the court
    assert c["propVertsInExclusion"] == 0 and c["props"] > 0
    assert (c["trees"] > 0) == (library == "pinned")
    need = max(14.0, 6.0 * p.longest)
    assert c["court"]["width"] >= need and c["court"]["length"] >= need


def rain_script(intensity="steady", wind=None, extra=()):
    s = courtyard_script()
    s["effects"] = list(s.get("effects", [])) + [{"id": "rain", "params": {"intensity": intensity}}, *extra]
    if wind:
        s["wind"] = {"id": "wind", "params": {"speedMs": wind}}
    return s


_RELOAD = r'''
import sys, hashlib
sys.path.insert(0, r"{root}")
import bpy, numpy as np
bpy.ops.wm.open_mainfile(filepath=r"{blend}")
from engine.blender.weather_probe import POINT_OBJECTS, _points, _digest
scene = bpy.context.scene
ob = bpy.data.objects["{name}"]
scene.frame_set(60)
scene.frame_set(40)
print("HASH", _digest(_points(ob, POINT_OBJECTS["{name}"][1])[0]))
'''


def _reload_hash(blend, name, tmp_path):
    import subprocess
    from engine.ingest.run import BLENDER
    script = tmp_path / "reload.py"
    script.write_text(_RELOAD.format(root=Path(__file__).resolve().parents[2], blend=blend, name=name), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script)],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    return next(line.split()[1] for line in proc.stdout.splitlines() if line.startswith("HASH"))


def test_rain_is_stateless_sheltered_and_carries_velocity(tmp_path):                       # Task 64
    from engine.physics import rain as R
    p = _p("sports_car")
    res = compile_scene(rain_script(wind=3.0), p, _glb("sports_car"), tmp_path / "c", render=False,
                        skip_kinds=("grade",), realism_probe=[1, 40], save_blend=True)
    fx, wp = res["fx"]["rain"], res["weatherProbe"]["rain"]
    assert fx["count"] == R.drop_count(R.INTENSITY["steady"]["rateMmH"], fx["side"] ** 2 * fx["height"])
    assert wp["preShelter"] == fx["count"]                          # the count before the shelter delete
    for f in ("1", "40"):
        rec = wp["frames"][f]
        assert rec["velocity"] and rec["inside"] == 0 and 0 < rec["n"] <= fx["count"], rec
    assert fx["slantDeg"] == pytest.approx(R.slant_deg(3.0, fx["speedMs"]), abs=1e-6) and fx["impactSlots"] > 0
    assert fx["backlightW"] > 0 and "effect:rain" in res["built"]
    assert _reload_hash(tmp_path / "c" / "scene.blend", "valora_rain", tmp_path) == wp["frames"]["40"]["hash"]


@pytest.mark.parametrize("with_rain", [False, True])
def test_wet_surface_wraps_the_ground_and_never_the_upload(with_rain, tmp_path):             # Task 65
    s = courtyard_script()
    fx = [{"id": "wet_surface", "params": {}}]
    s["effects"] = list(s.get("effects", [])) + ([{"id": "rain", "params": {"intensity": "drizzle"}}] if with_rain else []) + fx
    res = compile_scene(s, _p("pocket_watch"), _glb("pocket_watch"), tmp_path, render=False, skip_kinds=("grade",))
    w = res["fx"]["wet_surface"]
    assert w["materials"] == ["valora_court_asphalt"] and w["groupsPerMaterial"] == {"valora_court_asphalt": 1}
    assert res["uploadMaterials"]["before"] == res["uploadMaterials"]["after"]        # spec §4.5
    assert w["rippleLinked"] is with_rain and w["dripLinked"] is (not with_rain)
    assert w["puddleThreshold"] == pytest.approx(0.6)


def test_droplets_sit_on_the_surface_and_leave_the_upload_alone(tmp_path):                 # Task 66
    p, glb = _p("pocket_watch"), _glb("pocket_watch")
    s = copy.deepcopy(T3)
    s["effects"] = list(s.get("effects", [])) + [{"id": "droplets", "params": {"zone": "up_facing"}}]
    res = compile_scene(s, p, glb, tmp_path / "d", render=False, skip_kinds=("grade",), realism_probe=[1])
    bare = compile_scene(copy.deepcopy(T3), p, glb, tmp_path / "b", render=False, skip_kinds=("grade",))
    wp = res["weatherProbe"]["droplets"]
    assert wp["frames"]["1"]["n"] > 0 and wp["surfaceMaxM"] <= 0.001 and wp["minNz"] >= 0.0, wp     # smooth corner normals: >= 0, the plan's bound
    assert "effect:droplets" in res["built"] and res["fx"]["droplets"]["dripEmitters"] > 0
    upload = lambda r: {o["name"]: o["modifiers"] for o in r["objects"] if o["name"] in {x["name"] for x in bare["objects"]}}  # noqa: E731
    assert upload(res) == upload(bare)                                     # no modifier on the upload
    assert res["uploadMaterials"]["before"] == res["uploadMaterials"]["after"]


def test_snow_flakes_drift_and_cover_only_up_faces(tmp_path):                             # Task 67
    p = _p("sports_car")
    s = courtyard_script()
    s["effects"] = list(s.get("effects", [])) + [{"id": "snow", "params": {}}]
    s["wind"] = {"id": "wind", "params": {"speedMs": 2.0}}
    res = compile_scene(s, p, _glb("sports_car"), tmp_path, render=False, skip_kinds=("grade",), realism_probe=[1, 40])
    wp, fx = res["weatherProbe"]["snow"], res["fx"]["snow"]
    for f in ("1", "40"):
        assert wp["frames"][f]["velocity"] and wp["frames"][f]["inside"] == 0 and wp["frames"][f]["n"] > 0
    assert wp["preShelter"] == fx["count"] and fx["cover"] and fx["groundMaterials"] == ["valora_court_asphalt"]
    # up-facing faces only, by area: on sports_car 42 of 461k faces (6e-7 of the area) read n.z < 0.7 in Python
    # though Geometry Nodes kept them at > 0.7 (measured 2026-09-25; toycar: 0), so the share is the verdict
    assert wp["coverFaces"] > 0 and wp["coverUpShare"] >= 0.9999
    assert res["uploadMaterials"]["before"] == res["uploadMaterials"]["after"]


@pytest.mark.parametrize("grade", [True, False])
def test_lens_drops_show_only_in_their_shot(grade, tmp_path):                             # Task 68
    s = rain_script("drizzle")
    s["effects"].append({"id": "lens_drops", "params": {"shot": 2, "amount": 0.3}})
    res = compile_scene(s, _p("toycar"), _glb("toycar"), tmp_path, render=False, skip_kinds=() if grade else ("grade",))
    ld = res["fx"]["lens_drops"]
    assert ld["shot"] == 2 and ld["factorInside"] == pytest.approx(0.3)
    assert ld["factorBefore"] == 0.0 and ld["factorAfter"] == 0.0 and ld["targets"] >= 1
