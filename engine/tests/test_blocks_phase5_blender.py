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

# slow (chunk 8): every test here is a multi-minute world/weather compile (gust 612 s, snow 409 s in the
# chunk-7 suite; ~5 min each under load 2026-09-25): run with -m slow (or VALORA_SLOW=1)
pytestmark = [pytest.mark.blender, pytest.mark.slow, requires_blender]
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


_FOLLOW = r'''
import sys
sys.path.insert(0, r"{root}")
import bpy
bpy.ops.wm.open_mainfile(filepath=r"{blend}")
scene = bpy.context.scene
motion = bpy.data.objects["valora_motion"]
motion.animation_data_clear()
motion.location = (0.0, 0.0, 0.0)
motion.keyframe_insert("location", frame=1)
motion.location = (6.0, -2.0, 0.0)                     # a slide/drive: the subject moves 6 m, 2 m
motion.keyframe_insert("location", frame=30)
nt = bpy.data.materials["valora_fog"].node_tree
pk = nt.nodes["valora_fog_pocket"]                      # the pocket smoothstep reads the pocket anchor's coords
src = pk.inputs["Value"].links[0].from_node
print("POCKETSRC", src.inputs[0].links[0].from_node.object.name == "{pocket}")
for f in (1, 30):
    scene.frame_set(f)
    pa, fa = bpy.data.objects["{pocket}"], bpy.data.objects["valora_fog_centre"]
    print("AT", f, *pa.matrix_world.translation, *fa.matrix_world.translation)
'''


def test_fog_pocket_rides_the_moving_subject_and_the_layer_stays(tmp_path):     # review chunk 2 #6
    import subprocess
    from engine.ingest.run import BLENDER
    p = _p("sports_car")
    s = fog_script()
    res = compile_scene(s, p, _glb("sports_car"), tmp_path, render=False, save_blend=True)
    fog = res["fog"]
    assert fog["pocketParent"] == "valora_realism_offset"
    script = tmp_path / "follow.py"
    script.write_text(_FOLLOW.format(root=Path(__file__).resolve().parents[2], blend=tmp_path / "scene.blend",
                                     pocket=fog["pocketAnchor"]), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script)],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    at = {int(r[1]): [float(v) for v in r[2:]] for r in (ln.split() for ln in proc.stdout.splitlines()) if r[:1] == ["AT"]}
    assert "POCKETSRC True" in proc.stdout
    cx, cy, cz = p.center
    assert math.dist(at[1][:3], (cx, cy, cz)) < 0.02         # at the centre at rest (+ the realism offset's sag)
    moved = [a - b for a, b in zip(at[30][:3], at[1][:3])]
    assert moved == pytest.approx([6.0, -2.0, 0.0], abs=1e-4)   # carried by the slide, all of it
    assert at[1][3:] == pytest.approx([cx, cy, cz], abs=1e-4) and at[30][3:] == at[1][3:]   # layer fixed


def test_mist_is_taller_and_thinner(tmp_path):
    p = _p("sports_car")
    res = compile_scene(fog_script("mist"), p, _glb("sports_car"), tmp_path, render=False)
    assert res["fog"]["heightM"] == pytest.approx(1.2) and res["fog"]["density"] == pytest.approx(0.16)
    assert res["fog"]["drift"] is False                      # no wind field: no wisps


def test_grade_finishing_carries_the_camera_finish_and_script_finish_adds(tmp_path):     # Task 61 + realism
    """Every grade now carries the camera's own finish (grade_plan.CAMERA_FINISH: render-studio's rain film);
    the script's params only raise it. Grain is display-referred (after AgX, engine/film_grain.py), applied to
    the written frame by render_frames, so it is reported, never a compositor node (realism audit #20)."""
    from engine.compiler.context import block_seed
    p, glb = _p("toycar"), _glb("toycar")
    base = compile_scene(copy.deepcopy(T3), p, glb, tmp_path / "a", render=False)["grade"]
    s = copy.deepcopy(T3)
    s["grade"]["params"].update({"halation": 0.5, "lensDistortion": 0.01, "grain": 0.8})
    g = compile_scene(s, p, glb, tmp_path / "b", render=False)["grade"]
    for r in (base, g):
        assert r["nodeTypes"]["lens"] == "CompositorNodeLensdist" and "halation" in r["nodes"]
        assert not [n for n in r["nodes"] if n.startswith("grain")]
    assert base["finish"]["halationStrength"] == pytest.approx(0.10)      # premium_dark's own .10 > camera .05
    assert base["finish"]["lens"]["Distortion"] == pytest.approx(0.006)
    assert base["finish"]["lens"]["Dispersion"] == pytest.approx(0.0015)  # round 9: a touch of edge CA
    assert base["nodeTypes"]["lens_edge_soft"] == "CompositorNodeBlur"     # round 9: softer toward the edges
    assert base["finish"]["grain"] == {"amount": pytest.approx(0.5), "seed": block_seed(T3["seed"], "grade", "camera") % (1 << 31)}
    assert g["finish"]["halationStrength"] == pytest.approx(0.5)
    assert g["finish"]["lens"]["Distortion"] == pytest.approx(0.01)
    assert g["finish"]["grain"] == {"amount": pytest.approx(0.8), "seed": block_seed(T3["seed"], "grade", "mood_grade") % (1 << 31)}
    assert g["nodeTypes"] == base["nodeTypes"] and g["invalidLinks"] == [] and base["invalidLinks"] == []


def courtyard_script():
    s = copy.deepcopy(T3)
    s["world"] = {"id": "rain_courtyard", "params": {}}
    s["lighting"] = {"id": "hdri_only", "params": {}}             # the courtyard's first pair (Task 72)
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


def street_script(tod="night", neon=0.5):
    s = copy.deepcopy(T3)                    # keeps its haze_volume: T2-07 wants atmosphere outside a studio
    s["world"] = {"id": "night_street", "params": {"timeOfDay": tod, "neonAmount": neon}}
    s["lighting"] = {"id": "rim_neon", "params": {}}              # the street's first pair (Task 72)
    from engine.tests.test_growth_floor import _road_side
    return _road_side(s)                     # script_t3's arcs shoot from the road, not behind the pavement


@pytest.mark.parametrize("model,tod", [("sports_car", "night"), ("sneaker", "dusk")])
@pytest.mark.parametrize("library", ["pinned", "empty"])
def test_night_street_builds_its_contract(model, tod, library, tmp_path, monkeypatch):     # Task 70
    from engine.assets import LIBRARY, LIBRARY_ENV
    if library == "empty":
        monkeypatch.setenv(LIBRARY_ENV, str(tmp_path / "no_assets"))   # every fallback must build
    elif not (LIBRARY / "polyhaven").exists():
        pytest.skip("pinned assets not imported (py tools/assets/import_local.py)")
    p = _p(model)
    res = compile_scene(street_script(tod), p, _glb(model), tmp_path / "c", render=False, skip_kinds=("grade",),
                        realism_probe=[1])
    st = res["street"]
    assert st["asphaltMaps"] == (library == "pinned") and st["timeOfDay"] == tod
    lamps = [o for o in res["objects"] if o["type"] == "LIGHT" and o["block"] == "world/night_street"]
    assert len(lamps) >= 2 and st["lamps"] == len(lamps)
    assert st["neonAllEmissive"] is True
    ground = [o for o in res["objects"] if o["ground"]]
    assert [o["name"] for o in ground] == ["valora_street_road"] and ground[0]["location"][2] == 0.0
    assert abs(res["realismProbe"]["1"]["minZ"]) <= 0.01 * p.longest          # grounded on the road
    assert st["propVertsInExclusion"] == 0 and st["camerasInsideProps"] == 0
    assert res["clearance"]["violations"] == []
    assert st["road"]["length"] >= max(30.0, 8.0 * p.longest) - 1e-6
    assert all(o["block"] is not None for o in res["objects"] if o["name"].startswith("valora_street"))


def test_night_street_low_hero_camera_stands_clear_of_the_slabs(tmp_path):                  # review chunk 4 #5
    """The low hero camera (distance 2.2, azimuth 0, heightFrac 0.02) lands 3 cm up on the pavement; the street
    cuts a dropped kerb there and the diagnostic counts kerbs and pavements too."""
    s = street_script()
    s["shots"][0]["camera"] = {"id": "low_hero_push", "params": {"distance": 2.2, "azimuthDeg": 0.0,
                                                                 "heightFrac": 0.02, "pushFrac": 0.0}}
    res = compile_scene(s, _p("sports_car"), _glb("sports_car"), tmp_path, render=False, skip_kinds=("grade",))
    assert res["street"]["camerasInsideProps"] == 0 and res["street"]["slabCuts"] > 0     # the case is real


def test_night_street_neon_follows_its_params(tmp_path):
    p = _p("sports_car")
    res = compile_scene(street_script(neon=1.0), p, _glb("sports_car"), tmp_path, render=False, skip_kinds=("grade",))
    assert res["street"]["neonHue"] == 285.0 and res["street"]["neonAllEmissive"] is True


def field_script(tod="golden", wind=None, **params):
    s = copy.deepcopy(T3)                    # keeps its haze_volume: T2-07 wants atmosphere outside a studio
    s["world"] = {"id": "golden_field", "params": {"timeOfDay": tod, **params}}
    s["lighting"] = {"id": "hard_sun", "params": {}}              # the field's first pair (Task 72)
    if wind:
        s["wind"] = {"id": "wind", "params": {"speedMs": wind}}
    return s


@pytest.mark.parametrize("model,tod", [("sports_car", "golden"), ("mid_century_lounge_chair", "overcast")])
def test_golden_field_builds_its_contract(model, tod, tmp_path):                           # Task 71
    p = _p(model)
    res = compile_scene(field_script(tod, wind=3.0), p, _glb(model), tmp_path, render=False, skip_kinds=("grade",),
                        realism_probe=[1, 150])
    f = res["field"]
    assert f["blades"] > 1000 and f["bladeRootSwayMax"] == pytest.approx(0.0, abs=1e-6)
    foliage = [o for o in res["objects"] if o["foliage"]]
    assert [o["name"] for o in foliage] == ["valora_field_blades"]
    assert "foliage_sway" in res["realism"] and "ground_conform" in res["realism"]
    assert all(res["realismProbe"][k]["foliageInSubject"] == 0 for k in res["realismProbe"])
    suns = [o for o in res["objects"] if o["type"] == "LIGHT" and o["name"] == f["sunObject"]]
    assert len(suns) == 1 and sum(1 for o in res["objects"] if o["type"] == "LIGHT" and o.get("lightType") == "SUN") <= 1
    assert f["sun"]["elevationDeg"] == {"golden": 8.0, "overcast": 35.0}[tod]
    wc = res["windCoherent"]
    assert wc["field"]["ok"] is True and wc["foliage_sway"]["ok"] is True, wc
    ground = [o for o in res["objects"] if o["ground"]]
    assert [o["name"] for o in ground] == ["valora_field_ground"]


def test_golden_field_has_exactly_one_sun(tmp_path):
    res = compile_scene(field_script(), _p("sports_car"), _glb("sports_car"), tmp_path, render=False,
                        skip_kinds=("grade",))
    assert sum(1 for o in res["objects"] if o["type"] == "LIGHT" and o.get("lightType") == "SUN") == 1


def _lit(world, lighting, params=None, world_params=None):
    s = copy.deepcopy(T3)
    s["world"] = {"id": world, "params": dict(world_params or {})}
    s["lighting"] = {"id": lighting, "params": dict(params or {})}
    return s


def _suns(res):
    return [o for o in res["objects"] if o["type"] == "LIGHT" and o.get("lightType") == "SUN"]


def test_hard_sun_takes_the_field_sun_over(tmp_path):                                    # Task 72
    from engine.blocks.lighting.hard_sun.build import HARD_ANGLE_DEG, LOW_SUN_W
    from engine.color import kelvin_to_rgb
    res = compile_scene(_lit("golden_field", "hard_sun"), _p("sports_car"), _glb("sports_car"), tmp_path,
                        render=False, skip_kinds=("grade",))
    lt = res["lighting"]
    assert lt["block"] == "hard_sun" and lt["sunTakenOver"] is True
    assert len(_suns(res)) == 1 and lt["sun"] == res["field"]["sunObject"]          # never a second sun
    sun = next(x for x in lt["lights"] if x["type"] == "SUN")
    # round 7: the golden sun (8 degrees) keys at LOW_SUN_W, its rim card in the sun's own colour
    assert sun["energy"] == pytest.approx(LOW_SUN_W) and sun["angleDeg"] == pytest.approx(HARD_ANGLE_DEG, abs=1e-4)
    assert lt["sunKeptSoft"] is False
    areas = [x for x in lt["lights"] if x["type"] == "AREA"]
    assert [x["name"] for x in areas] == ["valora_sun_fill", "valora_sun_rim"]
    k = res["field"]["sun"]["kelvin"]
    assert areas[1]["color"] == pytest.approx(list(kelvin_to_rgb(k)), abs=1e-3)
    # round 9: under the world's low sun the bounce is the sunlit meadow: the fill takes the sun's colour too
    assert areas[0]["color"] == pytest.approx(list(kelvin_to_rgb(k)), abs=1e-3)


def test_hard_sun_keeps_the_overcast_field_soft(tmp_path):                                # review chunk 4 #6
    """Overcast is a soft sky: hard_sun (the field's default lighting) keeps the world sun's strength and
    angular size instead of making it a crisp 4 W/m^2 key. Asserted on the final Blender light."""
    from engine.blocks.world.golden_field.build import SUN
    _, _, strength, angle, _ = SUN["overcast"]
    res = compile_scene(_lit("golden_field", "hard_sun", world_params={"timeOfDay": "overcast"}), _p("sports_car"),
                        _glb("sports_car"), tmp_path, render=False, skip_kinds=("grade",))
    lt = res["lighting"]
    assert lt["sunTakenOver"] is True and lt["sunKeptSoft"] is True and len(_suns(res)) == 1
    sun = next(x for x in lt["lights"] if x["type"] == "SUN")
    assert sun["energy"] == pytest.approx(strength) and sun["angleDeg"] == pytest.approx(angle, abs=1e-4)
    assert res["field"]["sun"]["strength"] == pytest.approx(sun["energy"])      # the metadata tells the truth


def test_hard_sun_brings_its_own_sun_where_the_world_has_none(tmp_path):
    res = compile_scene(_lit("rain_courtyard", "hard_sun", {"rim": 0.0}, {"timeOfDay": "dusk"}), _p("sports_car"),
                        _glb("sports_car"), tmp_path, render=False, skip_kinds=("grade",))
    lt = res["lighting"]
    assert lt["sunTakenOver"] is False and len(_suns(res)) == 1
    assert [x["name"] for x in lt["lights"] if x["type"] == "AREA"] == ["valora_sun_fill"]


def test_rim_neon_rims_take_the_street_hue(tmp_path):
    import colorsys
    from engine.tests.test_growth_floor import _road_side          # script_t3's arcs stand behind the pavement
    res = compile_scene(_road_side(_lit("night_street", "rim_neon", world_params={"neonHue": 200.0})), _p("sports_car"),
                        _glb("sports_car"), tmp_path, render=False, skip_kinds=("grade",))
    lt = res["lighting"]
    assert lt["hues"] == [125.0, 275.0] and lt["worldHue"] == 200.0
    rims = [x for x in lt["lights"] if x["name"].startswith("valora_neon_rim")]
    assert len(rims) == 2
    for x, hue in zip(rims, lt["hues"]):
        assert x["color"] == pytest.approx(list(colorsys.hsv_to_rgb(hue / 360.0, 1.0, 1.0)), abs=1e-3)
    assert res["street"]["lamps"] >= 2                                    # the world's practicals stay
    assert len([o for o in res["objects"] if o["type"] == "LIGHT" and o["block"] == "world/night_street"])         == res["street"]["lamps"]


def test_hdri_only_lights_from_the_sky_with_a_black_card(tmp_path):
    res = compile_scene(_lit("rain_courtyard", "hdri_only", {"exposure": 1.0, "negFill": 0.3}), _p("sports_car"),
                        _glb("sports_car"), tmp_path, render=False, skip_kinds=("grade",))
    lt = res["lighting"]
    # metered like a camera (audit #6): the sky keeps its strength, the frame is exposed +1 EV
    assert lt["exposureScale"] == pytest.approx(2.0) and lt["meterEv"] == pytest.approx(1.0)
    assert lt["worldStrengths"] == [pytest.approx(1.0)]
    # outdoors each shot also gets the crew's reflection shaping (critique mat-v2 #2, engine/lighting/location_key):
    # one subject-linked area key and one windshield flag, re-rigged per shot; the sky is still the only World light
    # (rounds 8-9: plus the day's paint scrims and the near wheel's dim source, all subject-linked AREA lights)
    assert lt["negFill"] is True and [x["type"] for x in lt["lights"]][:3] == ["CARD", "AREA", "CARD"]
    assert {x["name"] for x in lt["lights"][3:]} <= {"valora_front_scrim", "valora_front_scrim_nose", "valora_wheel_glint"}
    assert all(x["type"] == "AREA" for x in lt["lights"][3:])
    assert len(lt["shaping"]["shots"]) >= 1 and all("keyW" in s for s in lt["shaping"]["shots"])
    rig = [o for o in res["objects"] if o["type"] == "LIGHT" and (o["block"] or "").startswith("lighting/")]
    assert [o["name"] for o in rig][0] == "valora_location_key" and not any(o["visibleCamera"] for o in rig)


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
    a = math.radians(res["wind"]["directionDeg"])
    assert fx["velocityMs"] == pytest.approx([3.0 * math.cos(a), 3.0 * math.sin(a), -fx["speedMs"]], abs=1e-6)  # #3
    assert fx["streakM"] == pytest.approx(R.streak_len(math.hypot(3.0, fx["speedMs"])))
    assert fx["backlightW"] > 0 and "effect:rain" in res["built"]
    v = res["weatherProbe"]["verdicts"]                               # Task 69: report-only verdicts recorded
    assert v["rain"]["noParticlesInSubject"] is True and v["velocityPresent"] is True
    assert _reload_hash(tmp_path / "c" / "scene.blend", "valora_rain", tmp_path) == wp["frames"]["40"]["hash"]


@pytest.mark.parametrize("effect", ["rain", "snow"])
def test_rain_and_snow_carry_the_fields_gusts(effect, tmp_path):                         # review chunk3 #3, #4
    """Measured on the evaluated points: steady wind moves every particle alike at the full mean wind; gustiness
    and turbulence spread the horizontal velocity, and both still move with the wind (wind_coherent).

    Since b225683 (review chunk5 #9) `velocity` is the evaluated trajectory's true derivative (carrier drift +
    the gust term's own rate of change along the path), not a raw local-wind sample, so the gap this margin
    checks is smaller than before the fix. Measured on the current code (deterministic, fixed seeds): rain
    steady/gusty velSpreadXY = 0.0 / 2.816 (gap ~2.82), snow = 0.134 / 0.434 (gap ~0.300, snow's own always-on
    flutter gives steady a nonzero floor unrelated to wind gusts). 0.25 sits comfortably under the smaller
    (snow) gap and comfortably over the gustiness=0 baseline of that same gap, which measures 0.0 for both
    effects when the "gusty" scene is re-run with gustiness=turbulence=0 (i.e. identical to "steady") --
    confirmed by re-running this test with the gusty wind params temporarily set equal to steady's."""
    from engine.physics import wind_calibration as WC
    p, glb = _p("sports_car"), _glb("sports_car")
    got = {}
    for name, gust, turb in (("steady", 0.0, 0.0), ("gusty", 1.0, 1.0)):
        s = courtyard_script()
        s["effects"] = list(s.get("effects", [])) + [{"id": effect, "params": {}}]
        s["wind"] = {"id": "wind", "params": {"speedMs": 3.0, "gustiness": gust, "turbulence": turb}}
        res = compile_scene(s, p, glb, tmp_path / name, render=False, skip_kinds=("grade",), realism_probe=[1])
        a = math.radians(res["wind"]["directionDeg"])
        got[name] = (res["weatherProbe"][effect]["frames"]["1"], res["windCoherent"].get(effect), (math.cos(a), math.sin(a)))
    from engine.catalog import Catalog
    k = WC.perms(Catalog.load(), "effect", effect)
    (steady, coh0, d), (gusty, coh1, _) = got["steady"], got["gusty"]
    want = [3.0 * k * d[0], 3.0 * k * d[1]]
    if effect == "rain":
        assert steady["velMean"][:2] == pytest.approx(want, abs=1e-4)                     # the full wind (#3)
        assert steady["velSpreadXY"] < 1e-4
    else:
        assert steady["velMean"][:2] == pytest.approx(want, abs=0.1)                      # wobble averages out
    assert gusty["velSpreadXY"] > steady["velSpreadXY"] + 0.25, (steady, gusty)           # the gusts arrive (#4)
    assert coh0["ok"] is True and coh1["ok"] is True, (coh0, coh1)


@pytest.mark.parametrize("with_rain", [False, True])
def test_wet_surface_wraps_the_ground_and_never_the_upload(with_rain, tmp_path):             # Task 65
    from engine.physics import wet as W
    s = courtyard_script()
    fx = [{"id": "wet_surface", "params": {}}]
    s["effects"] = list(s.get("effects", [])) + ([{"id": "rain", "params": {"intensity": "drizzle"}}] if with_rain else []) + fx
    res = compile_scene(s, _p("pocket_watch"), _glb("pocket_watch"), tmp_path, render=False, skip_kinds=("grade",))
    w = res["fx"]["wet_surface"]
    assert w["materials"] == ["valora_court_asphalt"] and w["groupsPerMaterial"] == {"valora_court_asphalt": 1}
    assert res["uploadMaterials"]["before"] == res["uploadMaterials"]["after"]        # spec §4.5
    assert w["rippleLinked"] is with_rain and w["dripLinked"] is (not with_rain)
    assert w["puddleThreshold"] == pytest.approx(W.puddle_threshold(0.4))


_PUDDLE_COVER = r'''
import sys
sys.path.insert(0, r"{root}")
import bpy, numpy as np
from engine.physics import wet as W
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=300, y_subdivisions=300, size=300.0)
ob = bpy.context.active_object
ng = bpy.data.node_groups.new("q", "GeometryNodeTree")
ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
N, L = ng.nodes, ng.links
gi, go, pos = N.new("NodeGroupInput"), N.new("NodeGroupOutput"), N.new("GeometryNodeInputPosition")
m, p = N.new("ShaderNodeTexNoise"), N.new("ShaderNodeTexNoise")        # wet_surface's height field, same constants
m.inputs["Scale"].default_value, m.inputs["Detail"].default_value = 1.0 / W.PUDDLE_SCALE_M, 1.0
p.inputs["Scale"].default_value, p.inputs["Detail"].default_value = W.PATCH_SCALE, W.PATCH_DETAIL
L.new(pos.outputs[0], m.inputs["Vector"]); L.new(pos.outputs[0], p.inputs["Vector"])
st = N.new("GeometryNodeStoreNamedAttribute"); st.data_type = "FLOAT_VECTOR"; st.inputs["Name"].default_value = "h"
cmb = N.new("ShaderNodeCombineXYZ"); L.new(m.outputs["Fac"], cmb.inputs[0]); L.new(p.outputs["Fac"], cmb.inputs[1])
L.new(gi.outputs[0], st.inputs["Geometry"]); L.new(cmb.outputs[0], st.inputs["Value"]); L.new(st.outputs[0], go.inputs[0])
ob.modifiers.new("q", "NODES").node_group = ng
ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
v = np.empty(len(me.vertices) * 3, np.float32); me.attributes["h"].data.foreach_get("vector", v)
v = v.reshape(-1, 3); h = v[:, 0] + W.PATCH_AMP * (v[:, 1] - 0.5)
for share in (0.0, 0.2, 0.5, 0.8, 1.0):
    depth = W.puddle_threshold(share) - h
    x = np.clip(depth / W.PUDDLE_EDGE, 0.0, 1.0); mask = x * x * (3 - 2 * x)    # the group's smoothstep(depth, 0, edge)
    print("COVER", share, float((mask > 0.5).mean()))
'''


def test_puddles_param_is_the_share_of_ground_under_water(tmp_path):                  # review chunk3 #2
    import subprocess
    from engine.ingest.run import BLENDER
    script = tmp_path / "cover.py"
    script.write_text(_PUDDLE_COVER.format(root=Path(__file__).resolve().parents[2]), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script)],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    cover = {float(r[1]): float(r[2]) for r in (ln.split() for ln in proc.stdout.splitlines()) if r[:1] == ["COVER"]}
    assert cover[0.0] == 0.0 and cover[1.0] == 1.0
    for share in (0.2, 0.5, 0.8):
        assert cover[share] == pytest.approx(share, abs=0.04), cover        # the level holds that share of ground
    assert cover[0.2] < cover[0.5] < cover[0.8]


_SHARED_GROUND = r'''
import sys
sys.path.insert(0, r"{root}")
import bpy
from types import SimpleNamespace as NS
from engine.blender.set_parts import mat, tag
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_end = 60
m = mat("valora_shared_ground", (0.3, 0.3, 0.3), 0.6)
for i in range(3):                                   # three ground pieces, one material
    bpy.ops.mesh.primitive_plane_add(size=4.0, location=(4.0 * i, 0.0, 0.0))
    ob = bpy.context.object
    ob.data.materials.append(m)
    tag(ob, "world/test", ground=True)
off = bpy.data.objects.new("valora_realism_offset", None)
scene.collection.objects.link(off)
prof = NS(boundsMin=(-0.5, -0.5, 0.0), boundsMax=(0.5, 0.5, 0.5), center=(0.0, 0.0, 0.25), longest=1.0, radius=0.7)
script = {{"format": {{"fps": 30}}, "effects": [{{"id": "wet_surface"}}], "seed": 1}}
from engine.blocks.effect.wet_surface.build import build as wet
wet(NS(scene=scene, profile=prof, script=script, params={{"wetness": 0.8, "puddles": 0.4, "ripples": "auto", "drips": True}},
       camera_positions=[], camera_lenses_mm=[]))
print("WET", dict(scene["valora_fx_wet_surface"]["groupsPerMaterial"]))
from engine.blocks.effect.snow.build import _coat_ground
print("SNOW", _coat_ground(bpy, 0.5), sum(1 for n in m.node_tree.nodes if n.type == "GROUP" and n.node_tree.name == "valora_snow"))
'''


def test_ground_pieces_sharing_a_material_get_one_wrapper(tmp_path):                  # review chunk3 #9
    import subprocess
    from engine.ingest.run import BLENDER
    script = tmp_path / "shared.py"
    script.write_text(_SHARED_GROUND.format(root=Path(__file__).resolve().parents[2]), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script)],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert "WET {'valora_shared_ground': 1}" in proc.stdout, proc.stdout[-1500:]
    assert "SNOW ['valora_shared_ground'] 1" in proc.stdout, proc.stdout[-1500:]


_CROWN_RIPPLE = r'''
import sys, json
sys.path.insert(0, r"{root}")
import bpy, numpy as np
bpy.ops.wm.open_mainfile(filepath=r"{blend}")
scene = bpy.context.scene
lat = json.loads(r'{lat}')
S, (ox, oy) = lat["cellM"], lat["offset"]
mat = bpy.data.materials["valora_court_asphalt"]
rv = mat.node_tree.nodes["valora_wet_impacts"]                   # the ripple shader's Voronoi
clock = mat.node_tree.nodes["valora_wet_clock"]
imp = bpy.data.objects["valora_rain_impacts"]
for f in (10, 25):
    scene.frame_set(f)
    ev = imp.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    red = np.empty(n, np.float32); me.attributes["valora_red"].data.foreach_get("value", red)
    age = np.empty(n, np.float32); me.attributes["valora_age"].data.foreach_get("value", age)
    ev.to_mesh_clear()
    keys = np.unique(np.round(red, 6))[:12]
    crowns = [(co[np.round(red, 6) == k][:, :2].mean(axis=0), float(k), float(age[np.round(red, 6) == k][0])) for k in keys]
    # evaluate the SHADER's Voronoi settings at each crown centre with a probe tree (same node type, same values)
    me2 = bpy.data.meshes.new("p"); me2.from_pydata([(c[0] / S + ox, c[1] / S + oy, 0.0) for c, _, _ in crowns], [], [])
    ob = bpy.data.objects.new("p", me2); scene.collection.objects.link(ob)
    ng = bpy.data.node_groups.new("p", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go, pos = N.new("NodeGroupInput"), N.new("NodeGroupOutput"), N.new("GeometryNodeInputPosition")
    v = N.new("ShaderNodeTexVoronoi"); v.voronoi_dimensions, v.feature, v.distance = rv.voronoi_dimensions, rv.feature, rv.distance
    v.inputs["Scale"].default_value, v.inputs["Randomness"].default_value = rv.inputs["Scale"].default_value, rv.inputs["Randomness"].default_value
    L.new(pos.outputs[0], v.inputs["Vector"])
    a = N.new("GeometryNodeStoreNamedAttribute"); a.data_type = "FLOAT"; a.inputs["Name"].default_value = "d"
    b = N.new("GeometryNodeStoreNamedAttribute"); b.data_type = "FLOAT_COLOR"; b.inputs["Name"].default_value = "c"
    L.new(gi.outputs[0], a.inputs["Geometry"]); L.new(v.outputs["Distance"], a.inputs["Value"])
    L.new(a.outputs[0], b.inputs["Geometry"]); L.new(v.outputs["Color"], b.inputs["Value"]); L.new(b.outputs[0], go.inputs[0])
    ob.modifiers.new("p", "NODES").node_group = ng
    e = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); m = e.to_mesh()
    d = np.empty(len(m.vertices), np.float32); m.attributes["d"].data.foreach_get("value", d)
    c = np.empty(len(m.vertices) * 4, np.float32); m.attributes["c"].data.foreach_get("color", c)
    now = clock.outputs[0].default_value
    for (xy, r, ag), dd, cr in zip(crowns, d, c.reshape(-1, 4)[:, 0]):
        shader_age = ((now / lat["periodS"]) + float(cr)) % 1.0
        print("CR", f, float(dd), abs(float(cr) - r), abs(shader_age * lat["periodS"] / lat["lifeS"] - ag), now - f / scene.render.fps)
    e.to_mesh_clear()
'''


def test_rain_crowns_sit_on_the_ripples_of_the_same_impacts(tmp_path):                # review chunk3 #6
    import subprocess
    from engine.ingest.run import BLENDER
    s = rain_script("downpour", extra=[{"id": "wet_surface", "params": {}}])
    res = compile_scene(s, _p("pocket_watch"), _glb("pocket_watch"), tmp_path / "c", render=False, skip_kinds=("grade",),
                        save_blend=True)
    lat = res["fx"]["rain"]["impactLattice"]
    assert lat and res["fx"]["wet_surface"]["impactLattice"] == lat and res["fx"]["wet_surface"]["rippleLinked"]
    script = tmp_path / "cr.py"
    script.write_text(_CROWN_RIPPLE.format(root=Path(__file__).resolve().parents[2], blend=tmp_path / "c" / "scene.blend",
                                           lat=json.dumps(lat)), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script)],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    rows = [[float(v) for v in r[2:]] for r in (ln.split() for ln in proc.stdout.splitlines()) if r[:1] == ["CR"]]
    assert len(rows) >= 6, proc.stdout[-1500:]
    for dist, dred, dage, dclock in rows:
        assert dist < 0.02 and dred < 1e-5 and dage < 1e-3 and abs(dclock) < 1e-4, rows   # one impact, one age


def test_droplets_sit_on_the_surface_and_leave_the_upload_alone(tmp_path):                 # Task 66
    p, glb = _p("pocket_watch"), _glb("pocket_watch")
    s = copy.deepcopy(T3)
    s["effects"] = list(s.get("effects", [])) + [{"id": "droplets", "params": {"zone": "up_facing"}}]
    res = compile_scene(s, p, glb, tmp_path / "d", render=False, skip_kinds=("grade",), realism_probe=[1])
    bare = compile_scene(copy.deepcopy(T3), p, glb, tmp_path / "b", render=False, skip_kinds=("grade",))
    wp = res["weatherProbe"]["droplets"]
    # the lower band's side faces carry beads too (nz > -0.05, mat-v2 #3), and since round 9 every side face (sparser):
    # the face normal selects, the smooth normal at a rounded edge dips further below it (-0.35 on the watch case)
    assert wp["frames"]["1"]["n"] > 0 and wp["surfaceMaxM"] <= 0.001 and wp["minNz"] >= -0.4, wp
    assert "effect:droplets" in res["built"] and res["fx"]["droplets"]["dripEmitters"] > 0
    upload = lambda r: {o["name"]: o["modifiers"] for o in r["objects"] if o["name"] in {x["name"] for x in bare["objects"]}}  # noqa: E731
    assert upload(res) == upload(bare)                                     # no modifier on the upload
    assert res["uploadMaterials"]["before"] == res["uploadMaterials"]["after"]


_DRIPS = r'''
import sys, math
sys.path.insert(0, r"{root}")
import bpy, numpy as np
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=r"{blend}")
scene = bpy.context.scene
fps = scene.render.fps
ob, off = bpy.data.objects["valora_drips"], bpy.data.objects["valora_realism_offset"]
base = ob.data
rest = {{i: Vector(v.co) for i, v in enumerate(base.vertices)}}
ob.modifiers["valora_drips_drops"].show_viewport = False
for f in {frames}:
    scene.frame_set(f)
    now = f / fps
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    td = np.empty(len(me.vertices), np.float32); me.attributes["valora_td"].data.foreach_get("value", td)
    pd = np.empty(len(me.vertices) * 3, np.float32); me.attributes["valora_pd"].data.foreach_get("vector", pd)
    vd = np.empty(len(me.vertices) * 3, np.float32); me.attributes["valora_vd"].data.foreach_get("vector", vd)
    pts = [tuple(v.co) for v in me.vertices]
    ev.to_mesh_clear()
    for k, (p, t_d, a, b) in enumerate(zip(pts, td, pd.reshape(-1, 3), vd.reshape(-1, 3))):
        if now <= t_d:
            continue
        # which rest vertex: the one whose flight from its own detach state lands here
        u = now - float(t_d)
        want = a + b * u - np.array([0.0, 0.0, 0.5 * 9.81 * u * u])
        src = next(i for i, v in enumerate(base.vertices)
                   if abs(base.attributes["valora_td"].data[i].value - t_d) < 1e-6)
        scene.frame_set(int(math.floor(t_d * fps)), subframe=t_d * fps - math.floor(t_d * fps))
        at_detach = off.matrix_world @ rest[src]
        scene.frame_set(f)
        carried = off.matrix_world @ rest[src]
        print("DRIP", f, float(np.linalg.norm(np.array(p) - want)), float((at_detach - Vector(a)).length),
              float((Vector(p) - carried).xy.length))
'''


_TURN_STOP = ("import math\nfrom engine.motion_path import SubjectPose\n\n"
              "def sample(params, profile, t, duration):\n"
              "    u = min(max(t / 2.0, 0.0), 1.0)\n"
              "    return SubjectPose(offset=(0.8 * u, 0.0, 0.0), yaw=math.radians(90.0) * u)\n")


def test_detached_drips_leave_a_moving_subject(tmp_path):                                # review chunk3 #5
    import subprocess
    from engine.ingest.run import BLENDER
    from engine.tests.realism_catalog import catalog_with_fixtures
    cat = catalog_with_fixtures(tmp_path / "cat")
    import shutil
    d = Path(cat.root) / "motion" / "test_turn_stop"          # drives and turns for 2 s, then holds (detail shots)
    shutil.copytree(Path(cat.root) / "motion" / "test_glide", d)
    m = json.loads((Path(cat.root) / "motion" / "test_glide" / "block.json").read_text(encoding="utf-8"))
    (d / "block.json").write_text(json.dumps({**m, "id": "test_turn_stop"}), encoding="utf-8")
    (d / "path.py").write_text(_TURN_STOP, encoding="utf-8")
    cat = type(cat).load(cat.root)
    s = courtyard_script()
    s["subject"]["motion"] = {"id": "test_turn_stop", "params": {"metres": 0.0, "yawDeg": 0.0}}
    s["effects"] = list(s.get("effects", [])) + [{"id": "droplets", "params": {"density": 1.0}}]
    res = compile_scene(s, _p("sports_car"), _glb("sports_car"), tmp_path / "c", render=False, skip_kinds=("grade",),
                        save_blend=True, catalog=cat)
    assert res["fx"]["droplets"]["dripEvents"] > res["fx"]["droplets"]["dripEmitters"] > 0
    script = tmp_path / "drips.py"
    script.write_text(_DRIPS.format(root=Path(__file__).resolve().parents[2], blend=tmp_path / "c" / "scene.blend",
                                    frames=[20, 40, 64, 68, 72]), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script)],
                          capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    rows = [[float(v) for v in r[2:]] for r in (ln.split() for ln in proc.stdout.splitlines()) if r[:1] == ["DRIP"]]
    assert rows, proc.stdout[-2000:]
    assert max(r[0] for r in rows) < 1e-4                    # ballistic from its detach state
    assert max(r[1] for r in rows) < 0.01                    # that state is where the keyed subject was at detach
    assert max(r[2] for r in rows) > 0.03                    # not carried: the subject stopped, its drips fly on


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
    # up-facing faces only, by area. The shell's edge is rounded on purpose (audit #19: its depth rolls off to the
    # paint as the surface turns past UP_DOT, snow.cover_depth_mm), so a rim of the LIFTED faces tilts past 0.7:
    # 0.9963 of the area stays > 0.7 on sports_car (measured 2026-09-25, depth blurred 40 passes; a flat lift read
    # 0.9999+), so the bound is 0.99 - a lift that kept side faces would read far lower
    assert wp["coverFaces"] > 0 and wp["coverUpShare"] >= 0.99
    assert res["uploadMaterials"]["before"] == res["uploadMaterials"]["after"]


@pytest.mark.parametrize("grade", [True, False])
def test_lens_drops_show_only_in_their_shot(grade, tmp_path):                             # Task 68
    s = rain_script("drizzle")
    s["effects"].append({"id": "lens_drops", "params": {"shot": 2, "amount": 0.3}})
    res = compile_scene(s, _p("toycar"), _glb("toycar"), tmp_path, render=False, skip_kinds=() if grade else ("grade",))
    ld = res["fx"]["lens_drops"]
    assert ld["shot"] == 2 and ld["factorInside"] == 1.0 and ld["amount"] == pytest.approx(0.3) and not ld.get("bypassed")
    assert ld["factorBefore"] == 0.0 and ld["factorAfter"] == 0.0 and ld["targets"] >= 1


def test_lens_drops_at_amount_zero_leave_the_image_alone(tmp_path):                     # review chunk3 #10
    s = rain_script("drizzle")
    s["effects"].append({"id": "lens_drops", "params": {"shot": 2, "amount": 0.0}})
    res = compile_scene(s, _p("toycar"), _glb("toycar"), tmp_path, render=False)
    ld = res["fx"]["lens_drops"]
    assert ld["bypassed"] is True and ld["targets"] == 0 and ld["factorInside"] == 0.0


def _motion_script(bid, params=None, world=None, lighting=None):
    s = copy.deepcopy(T3)
    s["subject"]["motion"] = {"id": bid, "params": dict(params or {})}
    if world:
        s["world"], s["lighting"] = {"id": world, "params": {}}, {"id": lighting, "params": {}}
    return s


def _keyed_matches_the_path(res, s, p, frames):
    """valora_motion's evaluated transform at each probe frame (fractional ones are subframes) moves four
    affinely independent points of the subject where motion_path says (review chunk5 #13: the origin alone
    misses a turn about a pivot at the origin, a plinth spin). A keyed frame (every integer frame, every path
    break) matches exactly; between keys the compiler keeps the stray under KEY_TOL x longest."""
    from engine.catalog import Catalog
    from engine.compiler.subject_keys import KEY_TOL, pose_mismatch
    from engine.motion_path import pose_breaks, subject_pose
    cat, fps = Catalog.load(), s["format"]["fps"]
    keyed = [1.0 + t * fps for t in pose_breaks(s, p, cat)]
    for f in frames:
        m = res["probe"][str(f)]["motionMatrix"]
        exact = float(f).is_integer() or any(abs(f - k) < 1e-6 for k in keyed)
        tol = 1e-5 if exact else KEY_TOL * p.longest + 1e-5
        err = pose_mismatch(m, subject_pose(s, p, cat, (f - 1) / fps), p)
        assert err <= tol, (f, err, tol)


def _between(f):
    """A subframe a third of the way to the next frame (never a key unless a break lands there)."""
    return float(f) + 1.0 / 3.0


def test_drop_settle_keys_the_bounces_and_landing_settle_follows_the_last_contact(tmp_path):   # Task 74
    from engine.catalog import Catalog
    from engine.checker import check
    p, cat = _p("sneaker"), Catalog.load()
    s = check(_motion_script("drop_settle", {"bounces": 2}), p, cat).script
    mod = cat.motion_module("drop_settle")
    fps = s["format"]["fps"]
    cs = mod.contacts(s["subject"]["motion"]["params"], p)
    frames = sorted({1, int(cs[0] * fps), int((cs[0] + cs[1]) / 2 * fps) + 1, int(cs[-1] * fps) + 2, 200,
                     *(1.0 + c * fps for c in cs), _between(int(cs[0] * fps)), _between(int(cs[1] * fps))})
    res = compile_scene(s, p, _glb("sneaker"), tmp_path, render=False, skip_kinds=("grade",), probe=frames)
    _keyed_matches_the_path(res, s, p, frames)
    rz = res["realismScene"]
    assert "landing_settle" in res["realism"] and rz["settle_landings"] >= 1
    assert abs(rz["settle_landing_frames"][-1] - (cs[-1] * fps + 1)) <= 2      # the settle starts at the last contact


def test_plinth_spin_stands_on_a_grounded_plinth_and_turns_as_keyed(tmp_path):            # Task 75
    from engine.catalog import Catalog
    from engine.checker import check
    p, cat = _p("sneaker"), Catalog.load()
    s = check(_motion_script("plinth_spin"), p, cat).script
    prm, fps = s["subject"]["motion"]["params"], s["format"]["fps"]
    mid = int((prm["startS"] + prm["turnS"] / 2) * fps) + 1     # mid-turn: a missing rotation shows here
    frames = [1, 60, mid, _between(mid), 120, 200, 290]
    res = compile_scene(s, p, _glb("sneaker"), tmp_path, render=False, skip_kinds=("grade",), probe=frames)
    _keyed_matches_the_path(res, s, p, frames)
    pl = [o for o in res["objects"] if o["name"] == "valora_plinth"]
    assert pl and pl[0]["block"] == "motion/plinth_spin" and pl[0]["ground"] is True
    mod = cat.motion_module("plinth_spin")
    assert res["fx"]["plinth"]["material"] == "satin" and res["fx"]["plinth"]["heightM"] == pytest.approx(mod.plinth_height(p))
    rz = res["realismScene"]
    assert rz["sink_m"] == 0.0 and rz["contact_ao_materials"] == 2      # the cyc and the plinth top both get the seam
    assert mod.plinth_height(p) == pytest.approx(0.04 * p.longest)


def test_float_drift_floats_and_bobs_as_keyed(tmp_path):
    from engine.catalog import Catalog
    from engine.checker import check
    p, cat = _p("pocket_watch"), Catalog.load()
    r = check(_motion_script("float_drift"), p, cat)
    assert r.script["subject"]["placement"] == "float"
    frames = [1, 45, _between(45), 150, 299]
    res = compile_scene(r.script, p, _glb("pocket_watch"), tmp_path, render=False, skip_kinds=("grade",), probe=frames)
    _keyed_matches_the_path(res, r.script, p, frames)
    assert "contact_ground" not in res["realism"]


def test_slide_in_is_keyed_from_its_path_and_capped_in_the_studio(tmp_path):              # Task 76
    from engine.catalog import Catalog
    from engine.checker import check
    p, cat = _p("sneaker"), Catalog.load()
    r = check(_motion_script("slide_in", {"distanceFrac": 2.0}), p, cat)
    assert "motion_travel_capped" in {i.code for i in r.issues}
    frames = [1, 7, 20, _between(20), 49, 200]
    res = compile_scene(r.script, p, _glb("sneaker"), tmp_path, render=False, skip_kinds=("grade",), probe=frames)
    _keyed_matches_the_path(res, r.script, p, frames)
    x0 = res["probe"]["1"]["motionMatrix"][0][3]
    assert abs(x0) == pytest.approx(r.script["subject"]["motion"]["params"]["distanceFrac"] * p.longest, rel=0.02)


def test_topple_is_keyed_as_a_quaternion_about_its_edge(tmp_path):                       # Task 77
    from engine.catalog import Catalog
    from engine.checker import check
    p, cat = _p("vintage_microscope"), Catalog.load()
    s = _motion_script("topple", {"rock": True})
    s.pop("edit", None)                                   # full shots only: a macro shot of a subject lying on its
    for sh in s["shots"]:                                 # side meets the ground (a compile test, not a T3 one)
        if sh["camera"]["id"] == "macro_detail":
            sh["camera"], sh["purpose"] = {"id": "arc_orbit", "params": {}}, "motion"
    r = check(s, p, cat)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    from engine.motion_path import pose_breaks
    brk = [1.0 + t * r.script["format"]["fps"] for t in pose_breaks(r.script, p, cat)]   # release, landing, rocks
    frames = sorted({1, 16, 20, _between(20), 25, 40, 200, *brk})
    res = compile_scene(r.script, p, _glb("vintage_microscope"), tmp_path, render=False, skip_kinds=("grade",),
                        probe=frames)
    _keyed_matches_the_path(res, r.script, p, frames)
    assert "landing_settle" in res["realism"]


def test_toss_tumble_is_keyed_about_its_centroid(tmp_path):                             # Task 78
    from engine.catalog import Catalog
    from engine.checker import check
    p, cat = _p("sneaker"), Catalog.load()
    r = check(_motion_script("toss_tumble"), p, cat)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    prm = r.script["subject"]["motion"]["params"]
    T = cat.motion_module("toss_tumble").air_s(prm, p)
    fps = r.script["format"]["fps"]
    frames = sorted({1, int(prm["startS"] * fps) + 2, int((prm["startS"] + T / 2) * fps), int((prm["startS"] + T) * fps) + 3, 250,
                     1.0 + prm["startS"] * fps, 1.0 + (prm["startS"] + T) * fps, _between(int((prm["startS"] + T / 2) * fps))})
    res = compile_scene(r.script, p, _glb("sneaker"), tmp_path, render=False, skip_kinds=("grade",), probe=frames)
    _keyed_matches_the_path(res, r.script, p, frames)
    assert "landing_settle" in res["realism"]


def test_drive_arc_rolls_each_wheel_its_own_path_and_leans_out(tmp_path):                 # Task 79 (H5)
    """sports_car, rain_courtyard, arc_left, 40 km/h (the checker may lower it for the lane / the 80 deg/s
    camera sweep). Full shots only: this is a compile probe, not a T3 script. The courtyard, not night_street:
    on the street's 7.3 m road the anchor orbits stand on or behind the pavement slab once the car has driven
    and yawed (camera_view_blocked, even swung down the road), and this test is about the wheels."""
    from engine.catalog import Catalog
    from engine.checker import check
    from engine.motion_path import apply, subject_pose
    p, cat = _p("sports_car"), Catalog.load()
    s = _motion_script("drive", {"path": "arc_left", "speedKmh": 40.0, "facing": "forward"}, "rain_courtyard",
                       "hdri_only")
    s.pop("edit", None)
    for sh in s["shots"]:
        if sh["camera"]["id"] == "macro_detail":
            # down the court, not broadside: from the default 0 deg bearing the orbit only frames the moving car
            # from beyond the courtyard's curb (camera_view_blocked)
            sh["camera"] = {"id": "arc_orbit", "params": {"startAzimuthDeg": -90.0}}
            sh["purpose"] = "motion"
    r = check(s, p, cat)
    assert r.ok and r.script["subject"]["motion"]["params"]["path"] == "arc_left", \
        [(i.code, i.message) for i in r.issues if i.severity == "error"]
    prm, fps = r.script["subject"]["motion"]["params"], r.script["format"]["fps"]
    apex = int(round((prm["startS"] + prm["driveS"] / 2) * fps)) + 1
    frames = [apex - 2, apex + 2, 200]
    res = compile_scene(r.script, p, _glb("sports_car"), tmp_path, render=False, skip_kinds=("grade",),
                        realism_probe=frames)
    rp = res["realismProbe"]
    assert res["realismScene"]["wheel_roll_form"] == "contact"
    a, b = rp[str(apex - 2)]["wheelVerts"], rp[str(apex + 2)]["wheelVerts"]
    pa, pb = (subject_pose(r.script, p, cat, (f - 1) / fps) for f in (apex - 2, apex + 2))
    for i, w in enumerate(p.wheels):
        rad = w["radius"]
        # the wheel's turn between the two frames, fitted rigidly (2D Kabsch in the plane across the axle
        # x): independent of where exactly the hub centre sits in the motion-local frame
        A, B = a[str(i)], b[str(i)]
        ay_, az_ = sum(q[1] for q in A) / len(A), sum(q[2] for q in A) / len(A)
        by_, bz_ = sum(q[1] for q in B) / len(B), sum(q[2] for q in B) / len(B)
        cross = sum((u[1] - ay_) * (v[2] - bz_) - (u[2] - az_) * (v[1] - by_) for u, v in zip(A, B))
        dot = sum((u[1] - ay_) * (v[1] - by_) + (u[2] - az_) * (v[2] - bz_) for u, v in zip(A, B))
        rolled = abs(math.atan2(cross, dot)) * rad
        c = (w["center"][0], w["center"][1], w["center"][2] - rad)
        ca, cb = apply(c, pa, p), apply(c, pb, p)
        travelled = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
        keyed = abs(rp[str(apex + 2)]["drivers"][f"valora_rz_wheel_{i}"][0]
                    - rp[str(apex - 2)]["drivers"][f"valora_rz_wheel_{i}"][0]) * rad
        assert abs(rolled - keyed) / keyed < 0.02, (i, rolled, keyed)                 # the mesh turns as keyed
        # the keyed turn is the rolling part of this wheel's own contact path (curvature-aware, H5)
        ax = w["axis"]
        steps = [subject_pose(r.script, p, cat, (f - 1) / fps) for f in range(apex - 2, apex + 3)]
        cps = [apply(c, q, p) for q in steps]
        roll = 0.0
        for q, c0, c1 in zip(steps[1:], cps, cps[1:]):
            cs, sn = math.cos(q.yaw), math.sin(q.yaw)
            axw = (cs * ax[0] - sn * ax[1], sn * ax[0] + cs * ax[1])
            roll += abs(-(c1[1] - c0[1]) * axw[0] + (c1[0] - c0[0]) * axw[1])
        assert abs(keyed - roll) / roll < 0.01, (i, keyed, roll)          # contact-point slip < 1%
        assert roll <= travelled * 1.001 + 1e-9 or roll <= sum(math.dist(u, v) for u, v in zip(cps, cps[1:])) + 1e-9
    assert max(res["realismScene"]["wheel_scrub"][:2]) < 0.01          # the trailing (rear) wheels do not scrub
    assert res["realismScene"]["suspension_roll_deg_per_g"] == 2.0          # sport class
    body = rp[str(apex + 2)]["drivers"]["valora_rz_body"]
    assert body[1] > 0.0, body                          # a left arc: the body rolls right (+X side down)
    for f in frames:                                    # tyre_patch_present at every probe frame
        tyres = rp[str(f)]["tyres"]
        assert len(tyres) == len(p.wheels) and all(t["flatN"] > 0 for t in tyres.values()), (f, tyres)


def test_dutch_hero_compiles_a_rolled_camera(tmp_path):                                    # Task 81
    from engine.tests.test_growth_floor import FLOORS
    make, model = FLOORS["camera/dutch_hero"]
    res = compile_scene(make(), _p(model), _glb(model), tmp_path, render=False, skip_kinds=("grade",))
    rolls = res["cameraRollDeg"]
    assert rolls[2] == pytest.approx(12.0, abs=0.05)                   # rollSide right: the top tilts right
    assert all(abs(r) < 0.05 for i, r in enumerate(rolls) if i != 2)  # every other camera stays level


def test_profile_slide_builds_its_foreground_card_outdoors_only(tmp_path):                  # Task 83
    from engine.tests.test_growth_floor import FLOORS
    make, model = FLOORS["camera/profile_slide"]
    s = make()
    s["shots"][2]["camera"]["params"]["foreground"] = True
    res = compile_scene(s, _p(model), _glb(model), tmp_path / "out", render=False, skip_kinds=("grade",),
                        probe=None)
    fg = res["foreground"]
    assert [c["shot"] for c in fg] == [2] and fg[0]["kind"] == "post"
    assert fg[0]["visibleInShot"] is True and fg[0]["hiddenOutside"] is True
    obj = next(o for o in res["objects"] if o["name"] == fg[0]["name"])
    assert obj["block"] == "camera/profile_slide" and obj["visibleGlossy"] is False
    studio = make()
    studio["world"], studio["lighting"] = {"id": "studio_cyc", "params": {}}, {"id": "reflection_rig", "params": {}}
    studio["shots"][2]["camera"]["params"]["foreground"] = True
    res2 = compile_scene(studio, _p(model), _glb(model), tmp_path / "studio", render=False, skip_kinds=("grade",))
    assert "foreground" not in res2 and not any(o["name"].startswith("valora_foreground") for o in res2["objects"])


def test_rolling_track_compiles_a_camera_car_down_the_street(tmp_path):                    # Task 84
    """The hook tracks a 40 km/h drive: the compile keys the camera from the subject's track, the camera car
    clears the subject (clearance) and the street keeps its set pieces off the camera car's path."""
    from engine.tests.test_growth_floor import FLOORS
    make, model = FLOORS["camera/rolling_track"]
    res = compile_scene(make(), _p(model), _glb(model), tmp_path, render=False, skip_kinds=("grade",))
    assert res["clearance"]["violations"] == [] and res["street"]["camerasInsideProps"] == 0
    assert all(abs(r) < 0.05 for r in res["cameraRollDeg"])


def test_per_shot_drive_restarts_each_shot_with_held_cut_keys(tmp_path):                  # review chunk5 #11
    """Four rolling_track shots of one perShot drive: every shot sees the drive from its start. At each cut the
    outgoing pose is held from f - 1 + SHUTTER/2 until the incoming one at f - SHUTTER/2, so the jump lands
    between the two exposures and neither blurs across it."""
    from engine.catalog import Catalog
    from engine.compiler.subject_keys import pose_mismatch
    from engine.compiler.tiers import SHUTTER
    from engine.motion_path import subject_pose
    from engine.tests.test_growth_floor import FLOORS
    make, model = FLOORS["camera/rolling_track"]
    s = make()
    s.pop("edit", None)
    s["subject"]["motion"]["params"]["perShot"] = True
    track = copy.deepcopy(s["shots"][0])
    s["shots"] = [dict(copy.deepcopy(track), startS=a, endS=a + 2.5) for a in (0.0, 2.5, 5.0, 7.5)]
    p, cat = _p(model), Catalog.load()
    fps = s["format"]["fps"]
    cut = int(round(2.5 * fps)) + 1                      # frame 76 opens shot 1
    pre, post = cut - 1 + SHUTTER / 2, cut - SHUTTER / 2
    frames = [cut - 1, pre, (pre + post) / 2, post, cut, _between(cut)]
    from engine.checker import check
    r = check(s, p, cat)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    sc = r.script
    res = compile_scene(sc, p, _glb(model), tmp_path, render=False, skip_kinds=("grade",), probe=frames)
    out_pose = subject_pose(sc, p, cat, (pre - 1) / fps, 0)
    in_pose = subject_pose(sc, p, cat, (post - 1) / fps, 1)
    assert math.dist(out_pose.offset, in_pose.offset) > 1.0                      # the drive restarts at the cut
    m = lambda f: res["probe"][str(f)]["motionMatrix"]  # noqa: E731
    assert pose_mismatch(m(cut - 1), subject_pose(sc, p, cat, (cut - 2) / fps, 0), p) < 1e-5
    assert pose_mismatch(m(pre), out_pose, p) < 1e-5
    assert pose_mismatch(m((pre + post) / 2), out_pose, p) < 1e-5              # held (CONSTANT) across the gap
    assert pose_mismatch(m(post), in_pose, p) < 1e-5
    assert pose_mismatch(m(cut), subject_pose(sc, p, cat, (cut - 1) / fps, 1), p) < 1e-5
    assert res["clearance"]["violations"] == []
