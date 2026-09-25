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
