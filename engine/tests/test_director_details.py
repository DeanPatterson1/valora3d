import copy
import functools
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.director.axes import DICE
from engine.director.details import vary_details
from engine.director.rulebook import EXAMPLES_DIR, example_script

S = example_script(json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8")))


def _call_path_source(kind, bid):
    """build.py plus every engine module it imports: the REAL call path of its params
    (softbox_three_point -> engine/softbox.py, reflection_rig -> engine/reflect.py)."""
    import re
    if kind == "camera":   # a camera's params reach Blender through its path (pose) and the timeline (fstop)
        src = (Path("engine/blocks") / kind / bid / "path.py").read_text(encoding="utf-8")
        # a path that loads another camera's path file (dutch_hero -> low_hero_push/path.py) reads its params too
        src += "".join((Path("engine/blocks/camera") / o / "path.py").read_text(encoding="utf-8")
                       for o in sorted(set(re.findall(r'"([a-z_]+)" / "path\.py"', src))))
        return src + Path("engine/compiler/timeline.py").read_text(encoding="utf-8")
    src = (Path("engine/blocks") / kind / bid / "build.py").read_text(encoding="utf-8")
    mods = set(re.findall(r"from engine\.([a-z_]+) import", src))
    # package imports too ("from engine.physics import rain as R": engine/physics/rain.py, Task 89)
    mods |= {f"{pkg}/{name}" for pkg, name in re.findall(r"from engine\.([a-z_]+) import ([a-z_]+)", src)}
    return src + "".join((Path("engine") / f"{m}.py").read_text(encoding="utf-8")
                         for m in sorted(mods) if (Path("engine") / f"{m}.py").exists())


def test_every_detail_param_reaches_its_builder():
    cat = Catalog.load()
    for ref, params in DICE["detailParams"].items():
        kind, bid = ref.split("/")
        m = cat.get(kind, bid)
        assert m is not None, ref
        src = _call_path_source(kind, bid)
        for name in params:
            t = m["params"][name]["type"] if name in m["params"] else None
            assert t == "number" or (t == "enum" and params[name].get("choice")), (ref, name)
            assert f'"{name}"' in src or f"'{name}'" in src, f"{ref}: nothing on its call path reads {name}"


def test_layout_params_really_move_lights():
    """Behaviour, not text: the pure layout functions the builders call change when the param changes."""
    from engine.reflect import rig_layout
    from engine.softbox import softbox_layout
    from engine.tests.test_director_package import _p
    cat, p = Catalog.load(), _p("pocket_watch")
    cam = (p.center[0] + 4 * p.radius, p.center[1] - 2 * p.radius, p.center[2] + p.radius)
    sb = {k: v["default"] for k, v in cat.get("lighting", "softbox_three_point")["params"].items()}
    assert softbox_layout(p, cam, sb) != softbox_layout(p, cam, {**sb, "keyAzimuthDeg": sb["keyAzimuthDeg"] + 5})
    rr = {k: v["default"] for k, v in cat.get("lighting", "reflection_rig")["params"].items()}
    assert rig_layout(p, cam, rr) != rig_layout(p, cam, {**rr, "rimElevationDeg": rr["rimElevationDeg"] + 5})


def test_seeded_in_range_and_deterministic():
    cat = Catalog.load()
    a, b = vary_details(copy.deepcopy(S), 1, cat), vary_details(copy.deepcopy(S), 1, cat)
    c = vary_details(copy.deepcopy(S), 2, cat)
    assert a == b and a != c
    for key in ("world", "lighting"):
        spec = cat.get(key, a[key]["id"])["params"]
        for n, v in a[key]["params"].items():
            if spec[n]["type"] == "number":
                assert spec[n]["min"] <= v <= spec[n]["max"]


def test_values_the_script_set_are_kept():
    cat, s = Catalog.load(), copy.deepcopy(S)
    s["world"]["params"]["floorGloss"] = 0.4
    assert vary_details(s, 9, cat)["world"]["params"]["floorGloss"] == 0.4


def test_the_fallback_applies_layer_1_unless_told_not_to():
    from engine.checker import check
    from engine.director.fallback import build_fallback
    from engine.director.job import make_job
    from engine.tests.test_director_package import _p
    cat = Catalog.load()   # "studio" pins the world (phase 5 rolls outdoor worlds too)
    for model in ("pocket_watch", "sneaker"):    # reflection_rig and softbox_three_point subjects
        p = _p(model)
        plain = build_fallback(make_job("studio", p, cat, seed=4), p, cat, details=False)
        a = build_fallback(make_job("studio", p, cat, seed=4), p, cat)
        b = build_fallback(make_job("studio", p, cat, seed=5), p, cat)
        assert check(a, p, cat).ok and a["lighting"] != plain["lighting"]   # layer 1 moved the lights
        assert a["lighting"]["params"] != b["lighting"]["params"]            # ... by the seed
        assert plain == build_fallback(make_job("studio", p, cat, seed=4), p, cat, details=False)


def test_fallback_varies_floor_gloss_and_haze_around_the_phase3_constants():
    from engine.director.direction import direction_of
    from engine.director.fallback import FALLBACK_FLOOR_GLOSS, FALLBACK_HAZE, build_fallback
    from engine.director.job import make_job
    from engine.tests.test_director_package import _p
    import dataclasses
    cat, p = Catalog.load(), _p("pocket_watch")
    d = direction_of({"world": "studio_cyc", "mood": "premium_dark", "tone": "black", "pace": "medium",
                      "opener": "low_hero_push", "weather": "dry", "wind": "calm"}, "dice")
    gloss_spec = cat.get("world", "studio_cyc")["params"]["floorGloss"]
    haze_spec = cat.get("effect", "haze_volume")["params"]["density"]
    gl, hz = set(), set()
    for seed in range(4):
        job = dataclasses.replace(make_job("a 10 second clip", p, cat, seed=seed), direction=d)
        s = build_fallback(job, p, cat)
        g, h = s["world"]["params"]["floorGloss"], s["effects"][0]["params"]["density"]
        span_g = DICE["detailParams"]["world/studio_cyc"]["floorGloss"]["pm"]
        span_h = DICE["detailParams"]["effect/haze_volume"]["density"]["pm"]
        assert gloss_spec["min"] <= g <= gloss_spec["max"] and haze_spec["min"] <= h <= haze_spec["max"]
        assert abs(g - FALLBACK_FLOOR_GLOSS) <= span_g + 1e-9 and abs(h - FALLBACK_HAZE) <= span_h + 1e-9
        gl.add(g)
        hz.add(h)
        plain = build_fallback(job, p, cat, details=False)
        assert plain["world"]["params"]["floorGloss"] == FALLBACK_FLOOR_GLOSS
        assert plain["effects"][0]["params"]["density"] == FALLBACK_HAZE
    assert len(gl) > 1 and len(hz) > 1


class _Input:
    def __init__(self):
        self.default_value = None


class _Bsdf:
    type = "BSDF_PRINCIPLED"

    def __init__(self):
        self.inputs = {"Base Color": _Input(), "Roughness": _Input()}


class _FakeBpy:
    """Just enough of bpy for studio_cyc's _cyc_material: the floor material a floorGloss feeds."""

    class data:
        class materials:
            @staticmethod
            def new(name):
                m = type("Mat", (), {})()
                m.node_tree = type("NT", (), {"nodes": [_Bsdf()]})()
                return m


def _builder(kind, bid):
    import importlib.util
    path = Path("engine/blocks") / kind / bid / "build.py"
    spec = importlib.util.spec_from_file_location(f"_t_{kind}_{bid}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_varied_param_changes_the_value_it_feeds():
    """Behaviour per detail param: a change moves a layout, a light colour, a material or a volume value.
    anisotropy is assigned straight onto the volume shader input (Blender-only), so it is checked on the
    builder's assignment line."""
    import re

    from engine.color import kelvin_to_rgb
    from engine.reflect import rig_layout
    from engine.softbox import softbox_layout
    from engine.tests.test_director_package import _p
    cat, p = Catalog.load(), _p("pocket_watch")
    cam = (p.center[0] + 4 * p.radius, p.center[1] - 2 * p.radius, p.center[2] + p.radius)
    fed = {}
    for ref, params in DICE["detailParams"].items():
        kind, bid = ref.split("/")
        spec = cat.get(kind, bid)["params"]
        base = {k: v["default"] for k, v in spec.items()}
        for name in params:
            if spec[name]["type"] == "enum":                    # Task 89: enum choices (timeOfDay, intensity)
                a, b = {**base, name: spec[name]["values"][0]}, {**base, name: spec[name]["values"][-1]}
            else:
                lo, hi = spec[name]["min"], spec[name]["max"]
                a, b = {**base, name: lo + 0.25 * (hi - lo)}, {**base, name: lo + 0.75 * (hi - lo)}
            if kind == "camera" and name == "fstop":   # the aperture the timeline keys into Blender
                from engine.geometry import set_fstop
                fed[(ref, name)] = set_fstop(a[name], p.radius) != set_fstop(b[name], p.radius)
            elif kind == "camera":   # the pose the camera path hands the renderer, over the shot
                sample = cat.load_camera_path(bid)
                mv = {"move": "push" if name == "pushFrac" else "slide"} if bid == "macro_detail" else {}
                fed[(ref, name)] = any(sample({**a, **mv}, p, u) != sample({**b, **mv}, p, u) for u in (0.0, 0.5, 1.0))
            elif name == "colorTempK":
                fed[(ref, name)] = kelvin_to_rgb(a[name]) != kelvin_to_rgb(b[name])
                src = _call_path_source(kind, bid)
                assert 'params["colorTempK"]' in src, ref
            elif ref == "lighting/softbox_three_point":
                fed[(ref, name)] = softbox_layout(p, cam, a) != softbox_layout(p, cam, b)
            elif ref == "lighting/reflection_rig":
                fed[(ref, name)] = rig_layout(p, cam, a) != rig_layout(p, cam, b)
            elif ref == "world/studio_cyc" and name == "floorGloss":
                mod = _builder(kind, bid)
                ra = mod._cyc_material(_FakeBpy, 0.5, a[name]).node_tree.nodes[0].inputs["Roughness"].default_value
                rb = mod._cyc_material(_FakeBpy, 0.5, b[name]).node_tree.nodes[0].inputs["Roughness"].default_value
                fed[(ref, name)] = ra != rb
            elif ref == "effect/haze_volume" and name == "density":
                mod = _builder(kind, bid)
                fed[(ref, name)] = mod.sigma_per_m(a[name], p.radius) != mod.sigma_per_m(b[name], p.radius)
            elif ref == "effect/haze_volume" and name == "anisotropy":
                src = (Path("engine/blocks") / kind / bid / "build.py").read_text(encoding="utf-8")
                fed[(ref, name)] = re.search(r'inputs\["Anisotropy"\]\.default_value\s*=\s*p\["anisotropy"\]',
                                             src) is not None
            elif ref == "effect/rain" and name == "intensity":        # Task 89: the drop rate and size it sets
                from engine.physics.rain import resolve
                fed[(ref, name)] = resolve(a) != resolve(b)
            elif ref == "effect/ground_fog" and name == "heightM":
                from engine.physics.fog import mode_params
                fed[(ref, name)] = mode_params(a["mode"], a[name], a["density"]) != \
                    mode_params(b["mode"], b[name], b["density"])
            elif ref == "field/wind" and name == "directionDeg":
                from engine.physics.wind import vector
                fed[(ref, name)] = vector(a[name], 3.0) != vector(b[name], 3.0)
            elif kind == "world" and name in ("neonHue", "windowsLit", "sunAzimuthDeg", "timeOfDay"):
                # Blender-only world builders: the param is read off the params dict on the build path
                src = (Path("engine/blocks") / kind / bid / "build.py").read_text(encoding="utf-8")
                fed[(ref, name)] = re.search(r'(?:p|params|ctx\.params)\["' + name + r'"\]', src) is not None
            elif kind in ("world", "effect", "lighting"):
                # phase-5 held variety (chunk 8): Blender-only builders read the param off the params dict, in the
                # block's build.py or, for the outdoor lights, in the shared rig layouts (engine/lighting/rigs.py)
                srcs = [(Path("engine/blocks") / kind / bid / "build.py").read_text(encoding="utf-8")]
                if kind == "lighting":
                    srcs.append(Path("engine/lighting/rigs.py").read_text(encoding="utf-8"))
                fed[(ref, name)] = any(re.search(r'(?:p|params|ctx\.params)\["' + name + r'"\]', t) for t in srcs)
            else:
                fed[(ref, name)] = False   # a new detail param needs its own behaviour check here
    assert all(fed.values()), [k for k, v in fed.items() if not v]


# --- Task 40a widening (2026-09-25): layer 1 must be VISIBLE with the direction held ---------------------
HELD = {"world": "studio_cyc", "mood": "premium_dark", "tone": "black", "pace": "medium",
        "opener": "low_hero_push", "weather": "dry", "wind": "calm"}


def _held_scripts(model, seeds=range(5), axes=HELD):
    return _held_cached(model, tuple(seeds), tuple(sorted(axes.items())))


@functools.lru_cache(maxsize=None)
def _held_cached(model, seeds, axes):
    axes = dict(axes)
    import dataclasses

    from engine.director.direction import direction_of
    from engine.director.fallback import build_fallback
    from engine.director.job import make_job
    from engine.tests.test_director_package import _p
    cat, p = Catalog.load(), _p(model)
    d = direction_of(axes, "dice")
    out = []
    for seed in seeds:
        job = dataclasses.replace(make_job("a 10 second clip", p, cat, seed=seed), direction=d)
        out.append((build_fallback(job, p, cat), build_fallback(job, p, cat, details=False)))
    return cat, p, out


def test_held_direction_scripts_are_clearly_not_near_duplicates():
    import itertools
    import statistics

    from engine.director.distance import script_distance
    thr = DICE["nearDuplicateScript"]
    ds = []
    for model in ("pocket_watch", "sports_car", "cesium_man"):
        cat, _, runs = _held_scripts(model)
        assert len({s["direction"]["id"] for s, _ in runs}) == 1
        ds += [script_distance(a, b, cat) for (a, _), (b, _) in itertools.combinations(runs, 2)]
    assert statistics.median(ds) >= 1.25 * thr, statistics.median(ds)   # the median pair: clearly not a near-dup
    assert sum(d < thr for d in ds) <= len(ds) // 5


def test_layer1_never_costs_a_tier_the_cadence_or_the_opener():
    from engine.director.floor import cadence_ok, script_tier
    for model in ("pocket_watch", "sports_car", "cesium_man", "mid_century_lounge_chair", "sneaker"):
        cat, p, runs = _held_scripts(model)
        for s, plain in runs:
            assert script_tier(s, p, cat) == script_tier(plain, p, cat) == "T3", model
            assert cadence_ok(s, HELD["pace"], cat)                  # any count the pace's cadence allows
            assert s["shots"][0]["camera"]["id"] == plain["shots"][0]["camera"]["id"]
            assert s["shots"][0]["purpose"] == "hook" and s["shots"][-1]["purpose"] == "hero"


def test_every_param_family_varies_by_seed():
    """Lights, world, haze, every camera's path params, the travel direction and the cut points."""
    seen = {}
    for model in ("pocket_watch", "cesium_man"):          # reflection_rig and softbox_three_point
        _, _, runs = _held_scripts(model, seeds=range(8))
        for s, _ in runs:
            for k, v in s["lighting"]["params"].items():
                seen.setdefault(("lighting", s["lighting"]["id"], k), set()).add(v)
            seen.setdefault(("world", "floorGloss"), set()).add(s["world"]["params"]["floorGloss"])
            seen.setdefault(("haze", "density"), set()).add(s["effects"][0]["params"]["density"])
            seen.setdefault(("cuts",), set()).add(tuple(sh["endS"] for sh in s["shots"][:-1]))
            for i, sh in enumerate(s["shots"]):
                for k, v in sh["camera"]["params"].items():
                    seen.setdefault((i, sh["camera"]["id"], k), set()).add(v)
                if sh["purpose"] == "motion":
                    seen.setdefault(("travel",), set()).add(sh["camera"]["params"]["sweepDeg"] > 0)
    want = [("lighting", "softbox_three_point", k) for k in ("keyAzimuthDeg", "keyElevationDeg", "fillRatio",
                                                                 "rimStrength", "colorTempK")]
    want += [("lighting", "reflection_rig", k) for k in ("rimElevationDeg", "overheadScale", "stripLength",
                                                             "keyFill", "darkShare", "colorTempK")]
    want += [("world", "floorGloss"), ("haze", "density"), ("cuts",), ("travel",)]
    want += [(0, "low_hero_push", k) for k in ("azimuthDeg", "distance", "heightFrac", "pushFrac", "lensMm")]
    want += [(1, "macro_detail", k) for k in ("azimuthOffsetDeg", "elevationOffsetDeg", "lensMm")]
    missing = [k for k in want if len(seen.get(k, ())) < 2]
    assert not missing, missing


def test_colour_temperature_stays_inside_the_grade_window():
    import dataclasses
    for mood in ("warm_golden", "teal_night", "clean"):
        tone = DICE["toneByMood"][mood][0]
        _, _, runs = _held_scripts("cesium_man", seeds=range(6), axes={**HELD, "mood": mood, "tone": tone})
        lo, hi = DICE["colorTempByMood"][mood]
        assert all(lo <= s["lighting"]["params"]["colorTempK"] <= hi for s, _ in runs), mood


def test_camera_params_the_script_set_are_kept_unset_ones_vary():
    cat, s = Catalog.load(), copy.deepcopy(S)
    cam = s["shots"][0]["camera"]
    cam["params"] = {"lensMm": 61.0}
    a = vary_details(copy.deepcopy(s), 3, cat)["shots"][0]["camera"]["params"]
    b = vary_details(copy.deepcopy(s), 4, cat)["shots"][0]["camera"]["params"]
    assert a["lensMm"] == b["lensMm"] == 61.0
    assert a != b and set(a) > {"lensMm"}


def test_vehicle_full_frames_keep_tg10_lenses_and_detail_lenses_stay_in_band():
    for seed_runs in (_held_scripts("sports_car", seeds=range(8))[2],):
        for s, _ in seed_runs:
            for sh in s["shots"]:
                lens = sh["camera"]["params"]["lensMm"]
                assert lens >= 28 if sh["camera"]["id"] != "macro_detail" else 85 <= lens <= 135


def test_llm_path_layer1_never_costs_a_tier():
    """The WATCH probe reply passes at T3 plain; its unset camera params varied must not trip a craft rule
    (measured: T3-14 on seed 1 before the guard), or the pipeline burns a repair round on our own jitter."""
    from engine.director.details import checked_details
    from engine.director.floor import script_tier
    from engine.checker import check
    from engine.director.sanitize import sanitize
    from engine.director.job import make_job
    from engine.tests.test_director_package import _p
    from harness.tests.test_director_eval import WATCH
    cat, p = Catalog.load(), _p("pocket_watch")
    for seed in range(6):
        job = make_job("luxury", p, cat, seed=seed, duration=10)
        raw, _ = sanitize(copy.deepcopy(WATCH), job, cat, p)
        plain = check(copy.deepcopy(raw), p, cat)
        r = checked_details(copy.deepcopy(raw), seed, cat, p)
        assert r.ok and script_tier(r.script, p, cat) == script_tier(plain.script, p, cat) == "T3", seed


# --- phase 5 Task 89: layer-1 windows for the new worlds, weather, wind and handheld -------------------------

NEW_RULES = ("world/night_street", "world/golden_field", "world/rain_courtyard", "effect/rain", "effect/ground_fog",
             "field/wind", "camera/handheld_operator")


def _outdoor(world, mood, pace="medium", weather="dry", wind="calm", model="sports_car", seed=0):
    from engine.director.direction import direction_of, interim_direction, parse_id
    from engine.director.fallback import build_fallback
    from engine.director.job import make_job
    from engine.tests.test_director_package import _p
    cat, p = Catalog.load(), _p(model)
    axes = {**parse_id(interim_direction(seed, p, cat).id), "world": world, "tone": "na", "mood": mood, "pace": pace,
            "weather": weather, "wind": wind}
    job = make_job("", p, cat, seed=seed, direction=direction_of(axes, "dice"), duration=10)
    return build_fallback(job, p, cat), p, cat


def test_every_new_rule_stays_inside_the_catalog_range():
    from engine.director.axes import DICE
    from engine.director.details import rule_value, _rng
    cat = Catalog.load()
    for ref in NEW_RULES:
        kind, bid = ref.split("/")
        m = cat.get(kind, bid)
        for name, rule in DICE["detailParams"][ref].items():
            spec = m["params"][name]
            for seed in range(40):
                for mood in ("clean", "warm_golden"):
                    for pace in ("calm", "medium", "hype"):
                        v = rule_value(rule, spec["default"], spec, _rng(seed, "p", name), mood=mood, pace=pace)
                        if spec["type"] == "enum":
                            assert v in spec["values"], (ref, name, v)
                        else:
                            assert spec["min"] <= v <= spec["max"], (ref, name, v)


def test_enum_choices_follow_mood_and_pace():
    from engine.director.axes import DICE
    from engine.director.details import rule_value, _rng
    cat = Catalog.load()
    tod, tspec = DICE["detailParams"]["world/golden_field"]["timeOfDay"], cat.get("world", "golden_field")["params"]["timeOfDay"]
    picks = {rule_value(tod, None, tspec, _rng(s, "w", "t"), mood="warm_golden") for s in range(60)}
    assert "overcast" not in picks and len(picks) >= 2
    assert "overcast" in {rule_value(tod, None, tspec, _rng(s, "w", "t"), mood="clean") for s in range(60)}
    rain, rspec = DICE["detailParams"]["effect/rain"]["intensity"], cat.get("effect", "rain")["params"]["intensity"]
    by = {pace: {rule_value(rain, None, rspec, _rng(s, "e", "i"), pace=pace) for s in range(60)}
          for pace in ("calm", "medium", "hype")}
    assert by["medium"] == {"steady"} and "downpour" in by["hype"] and "downpour" not in by["calm"]
    ns = {rule_value(DICE["detailParams"]["camera/handheld_operator"]["noiseSeed"], 0.0,
                     cat.get("camera", "handheld_operator")["params"]["noiseSeed"], _rng(s, "c", "n")) for s in range(30)}
    assert all(float(v).is_integer() for v in ns) and len(ns) > 20


def test_new_windows_vary_the_fallback_by_seed_and_keep_script_values():
    import copy
    from engine.director.details import vary_details
    a, _, cat = _outdoor("night_street", "teal_night", seed=1)
    b, _, _ = _outdoor("night_street", "teal_night", seed=2)
    a2, _, _ = _outdoor("night_street", "teal_night", seed=1)
    assert a == a2                                                        # same seed, same values
    assert a["world"]["params"]["neonHue"] != b["world"]["params"]["neonHue"]
    assert 180 <= a["world"]["params"]["neonHue"] <= 330
    s = {"world": {"id": "night_street", "params": {"neonHue": 200.0, "timeOfDay": "dusk"}}}
    out = vary_details(copy.deepcopy(s), 5, cat)
    assert out["world"]["params"]["neonHue"] == 200.0 and out["world"]["params"]["timeOfDay"] == "dusk"
    assert "windowsLit" in out["world"]["params"]


def test_wind_blows_back_to_front_toward_the_hero_camera():
    from engine.craft_rules import shot_pose
    import math
    s, p, cat = _outdoor("golden_field", "warm_golden", wind="breeze", seed=3)
    pos = shot_pose(s["shots"][-1], 1.0, p, cat).position
    toward = math.degrees(math.atan2(pos[1], pos[0])) % 360.0
    d = s["wind"]["params"]["directionDeg"]
    assert abs((d - toward + 180.0) % 360.0 - 180.0) <= 60.0 + 1e-6


def test_the_studio_fallback_and_the_phase3_default_are_untouched(legacy_fps30):
    """New windows touch only new blocks: studio fallbacks stay byte-identical (Task 88 fixtures), and the frozen
    phase-3 default has details off."""
    import json
    from engine.tests.fallback_phase4_cases import case, path
    for m, sd in (("pocket_watch", 0), ("sports_car", 3), ("cesium_man", 4)):
        assert case(m, sd) == json.loads(path(m, sd).read_text(encoding="utf-8"))


def test_choice_rules_back_off_to_the_centre_at_a_smaller_scale():
    """review chunk7 #8: at scale < 1 a choice rule stops re-rolling the same seeded value; it returns the centre
    (the author's value or the default) when that is an allowed value, so the back-off can shrink it."""
    import random
    from engine.director.details import rule_value
    spec = {"type": "enum", "values": ["a", "b", "c", "d"], "default": "a"}
    picks = {rule_value({"choice": True}, "a", spec, random.Random(s)) for s in range(40)}
    assert len(picks) > 1                                                    # full scale still varies
    assert {rule_value({"choice": True}, "c", spec, random.Random(s), scale=0.5) for s in range(40)} == {"c"}
    # an excluded centre is not used: the first allowed value is, the same at every seed
    rule = {"choice": True, "exclude": ["a"]}
    assert {rule_value(rule, "a", spec, random.Random(s), scale=0.5) for s in range(40)} == {"b"}
    num = {"type": "number", "min": 0, "max": 99, "default": 7}
    assert {rule_value({"choice": True}, 7, num, random.Random(s), scale=0.5) for s in range(20)} == {7.0}
