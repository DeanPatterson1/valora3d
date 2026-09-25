import copy
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
    src = (Path("engine/blocks") / kind / bid / "build.py").read_text(encoding="utf-8")
    mods = set(re.findall(r"from engine\.([a-z_]+) import", src))
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
            assert name in m["params"] and m["params"][name]["type"] == "number", (ref, name)
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
    cat = Catalog.load()
    for model in ("pocket_watch", "sneaker"):    # reflection_rig and softbox_three_point subjects
        p = _p(model)
        plain = build_fallback(make_job("", p, cat, seed=4), p, cat, details=False)
        a = build_fallback(make_job("", p, cat, seed=4), p, cat)
        b = build_fallback(make_job("", p, cat, seed=5), p, cat)
        assert check(a, p, cat).ok and a["lighting"] != plain["lighting"]   # layer 1 moved the lights
        assert a["lighting"]["params"] != b["lighting"]["params"]            # ... by the seed
        assert plain == build_fallback(make_job("", p, cat, seed=4), p, cat, details=False)


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
        span_g = DICE["detailParams"]["world/studio_cyc"]["floorGloss"] * (gloss_spec["max"] - gloss_spec["min"])
        span_h = DICE["detailParams"]["effect/haze_volume"]["density"] * (haze_spec["max"] - haze_spec["min"])
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
            lo, hi = spec[name]["min"], spec[name]["max"]
            a, b = {**base, name: lo + 0.25 * (hi - lo)}, {**base, name: lo + 0.75 * (hi - lo)}
            if name == "colorTempK":
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
            else:
                fed[(ref, name)] = False   # a new detail param needs its own behaviour check here
    assert all(fed.values()), [k for k, v in fed.items() if not v]
