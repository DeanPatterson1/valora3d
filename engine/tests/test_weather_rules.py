"""Phase 5 Task 57: weather, coupling and effect-world rules (pure). Fixture effects (rain, wet_surface,
droplets, snow, ground_fog, lens_drops, test_spray) are written into a temp catalog, so this does not depend
on the real weather blocks of Tasks 64-68."""
import copy
import dataclasses
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.issues import Issue
from engine.script import validate_and_repair
from engine.tests.realism_catalog import catalog_with_fixtures
from engine.tests.test_director_package import _p
from engine.weather_rules import (_needs_world, apply_weather_rules, effect_off_screen, spawn_in_subject,
                                  surface_state_continuity, wind_rules)

FIX = Path(__file__).parent / "fixtures"
_TAGS = {"mood": [], "energy": [], "palette": []}


def _fx(bid, params=None, physics=None, **extra):
    return {"id": bid, "kind": "effect", "description": f"TEST ONLY {bid}", "params": params or {},
            "subjectSizeM": [0.02, 30.0], "aspects": ["9:16", "16:9", "1:1", "4:5"], "costWeight": 1.0,
            "tags": _TAGS, "tierMax": "T3", "physics": physics or {}, **extra}


OUTDOOR = {"outdoor": True, "hasGround": True}
FX = {
    "rain": _fx("rain", {"amount": {"type": "number", "min": 0, "max": 1, "default": 0.5}},
                {"couplings": ["wet_surface", "droplets"], "excludes": ["snow"], "requiresWorld": OUTDOOR},
                maxPerClip=1),
    "wet_surface": _fx("wet_surface", {"wetness": {"type": "number", "min": 0, "max": 1, "default": 0.8}},
                       {"requiresWorld": {"hasGround": True}}),
    "droplets": _fx("droplets", {"amount": {"type": "number", "min": 0, "max": 1, "default": 0.4}}, {},
                    requiresProfile=["upFacing"]),
    "snow": _fx("snow", {}, {"excludes": ["rain"], "requiresWorld": OUTDOOR}),
    "ground_fog": _fx("ground_fog", {}, {"requiresWorld": {"hasGround": True}}),
    "lens_drops": _fx("lens_drops", {"shot": {"type": "number", "min": 0, "max": 20, "default": 0}},
                      {"requiresWorld": {"outdoor": True}}, maxPerClip=1),
    "test_spray": _fx("test_spray", {"lanePosition": {"type": "number", "min": 0, "max": 30, "default": 2.0}}),
}


def _write_fx(root, fx):
    for bid, m in fx.items():
        d = Path(root) / "effect" / bid
        d.mkdir(parents=True, exist_ok=True)
        (d / "block.json").write_text(json.dumps(m), encoding="utf-8")
        (d / "build.py").write_text("def build(ctx):\n    pass\n", encoding="utf-8")


@pytest.fixture(scope="module")
def fx_catalog(tmp_path_factory):
    cat = catalog_with_fixtures(tmp_path_factory.mktemp("wx"))
    _write_fx(cat.root, FX)
    return Catalog.load(cat.root)


def profile_car():
    return _p("sports_car")


def _base(world):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["world"] = {"id": world, "params": {}}
    return s


def _maker(world):
    def make(effects, removed=()):
        s = _base(world)
        s["effects"] = copy.deepcopy(effects) + [{"id": r, "params": {}, "remove": True} for r in removed]
        return s
    return make


@pytest.fixture
def outdoor_script():
    return _maker("test_street")


@pytest.fixture
def studio_script():
    return _maker("studio_cyc")


def test_rain_couples_wet_surface_and_droplets(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "rain", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert [e["id"] for e in s["effects"]][:3] == ["rain", "wet_surface", "droplets"]
    assert [i.code for i in issues].count("coupled_added") == 2
    assert s["effects"][1]["params"] == {"wetness": 0.8}                  # a coupled child gets block defaults
    assert all(i.severity == "repaired" for i in issues if i.code == "coupled_added")


def test_coupled_children_follow_their_parent_in_declared_order(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "ground_fog", "params": {}}, {"id": "rain", "params": {}},
                                        {"id": "droplets", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert [e["id"] for e in s["effects"]] == ["ground_fog", "rain", "wet_surface", "droplets"]
    assert [i.code for i in issues].count("coupled_added") == 1


def test_a_coupled_child_that_does_not_fit_the_subject_is_skipped_not_failed(fx_catalog, outdoor_script):
    bare = dataclasses.replace(profile_car(), surfaceSamples=[])            # no up-facing samples
    s, issues = outdoor_script(effects=[{"id": "rain", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, bare, issues)
    assert [e["id"] for e in s["effects"]] == ["rain", "wet_surface"]
    assert any(i.code == "coupled_skipped" and i.severity == "info" for i in issues)
    assert not any(i.severity == "error" for i in issues)


def test_rain_and_snow_exclude(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "rain", "params": {}}, {"id": "snow", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "exclusive_effects" and i.severity == "error" for i in issues)


def test_rain_in_the_studio_needs_an_outdoor_world(fx_catalog, studio_script):
    s, issues = studio_script(effects=[{"id": "rain", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "effect_needs_world" and i.severity == "error" for i in issues)


def test_max_per_clip(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "rain", "params": {}}, {"id": "rain", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "effect_max_per_clip" for i in issues)


def test_coupled_block_cannot_be_removed_while_parent_present(fx_catalog, outdoor_script):
    s = outdoor_script(effects=[{"id": "rain", "params": {}}], removed=["wet_surface"])
    issues = []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "coupling_removed" for i in issues)
    assert all(not e.get("remove") for e in s["effects"])


def test_weather_time_scale_must_be_one(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "rain", "params": {"timeScale": 0.5}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "time_scale_weather" for i in issues)


def test_effect_needs_profile_when_requested_directly(fx_catalog, outdoor_script):
    bare = dataclasses.replace(profile_car(), surfaceSamples=[])
    s, issues = outdoor_script(effects=[{"id": "droplets", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, bare, issues)
    assert any(i.code == "effect_needs_profile" and i.severity == "error" for i in issues)


def test_fog_in_strong_wind_is_a_warning(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "ground_fog", "params": {}}]), []
    s["wind"] = {"id": "wind", "params": {"speedMs": 9.0}}
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert [(i.code, i.severity) for i in issues] == [("wind_implausible", "warning")]


def test_dry_scripts_are_untouched(fx_catalog, studio_script):
    s = studio_script(effects=[{"id": "haze_volume", "params": {}}])
    before, issues = repr(s), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert repr(s) == before and issues == []
    bare = _base("studio_cyc")
    bare.pop("effects", None)
    before = repr(bare)
    apply_weather_rules(bare, fx_catalog, profile_car(), issues)
    assert repr(bare) == before and issues == []


def test_needs_world_rule():
    assert _needs_world({"outdoor": True, "hasGround": True}, {"outdoor": False, "hasGround": True}) == ["outdoor"]
    assert _needs_world({"groundType": ["asphalt"], "temperature": ["cold"]},
                        {"groundType": "grass", "temperature": "mild"}) == ["groundType", "temperature"]
    assert _needs_world({}, {}) == []


def test_spawn_inside_the_subject_is_an_error(fx_catalog, outdoor_script):
    car = profile_car()
    s, issues = outdoor_script(effects=[{"id": "test_spray", "params": {"lanePosition": 0.5}}]), []
    spawn_in_subject(s, car, fx_catalog, issues)
    assert [i.code for i in issues] == ["spawn_in_subject"] and issues[0].severity == "error"
    s, issues = outdoor_script(effects=[{"id": "test_spray", "params": {"lanePosition": 4.0}}]), []
    spawn_in_subject(s, car, fx_catalog, issues)
    assert issues == []


def test_lens_drops_must_land_in_a_shot(outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "lens_drops", "params": {"shot": 5}}]), []
    effect_off_screen(s, issues)
    assert [i.code for i in issues] == ["effect_off_screen"]
    s, issues = outdoor_script(effects=[{"id": "lens_drops", "params": {"shot": 1}}]), []
    effect_off_screen(s, issues)
    assert issues == []


def test_surface_state_continuity():
    s = _base("test_street")
    s["surfaceState"] = "wet"
    s["shots"][1]["surfaceState"] = "dry"
    issues = []
    surface_state_continuity(s, issues)
    assert [(i.code, i.severity) for i in issues] == [("surface_state_continuity", "error")]


def test_script_rejects_per_shot_surface_state():
    s = _base("studio_cyc")
    s["shots"][0]["surfaceState"] = "wet"
    _, issues = validate_and_repair(s, Catalog.load())
    assert any(i.code == "surface_state_continuity" and i.severity == "error" for i in issues)


def test_check_runs_the_weather_rules(fx_catalog):
    s = _maker("test_street")([{"id": "rain", "params": {}}])
    r = check(s, profile_car(), fx_catalog)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
    assert [e["id"] for e in r.script["effects"]] == ["rain", "wet_surface", "droplets"]
    r = check(_maker("studio_cyc")([{"id": "rain", "params": {}}]), profile_car(), fx_catalog)
    assert not r.ok and "effect_needs_world" in {i.code for i in r.issues}


def test_an_llm_reply_that_omits_a_coupled_child_is_repaired_not_failed(tmp_path):
    """Sanitize keeps the LLM's effects as written; an omitted coupled child is re-added by the checker
    (coupled_added, repaired), never an error. Only an explicit remove entry is coupling_removed."""
    from engine.director.llm import FakeProvider
    from engine.director.pipeline import direct
    from engine.director.rulebook import EXAMPLES_DIR
    cat = catalog_with_fixtures(tmp_path)
    free = {"rain": {**FX["rain"], "physics": {"couplings": ["wet_surface"]}},   # no world requirement here
            "wet_surface": {**FX["wet_surface"], "physics": {}}}
    _write_fx(cat.root, free)
    cat = Catalog.load(cat.root)
    watch = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]
    from engine.tests.dice_seeds import seed_matching
    reply = {**watch, "effects": [{"id": "rain", "params": {}}]}
    for w in ("rain_courtyard", "night_street", "golden_field"):  # studio-only dice: the reply is a studio one
        if ("world", w) in cat._blocks:
            cat._blocks[("world", w)]["directorSelectable"] = False
    seed = seed_matching(reply, "", duration=10, catalog=cat)   # a roll the canned reply already follows
    r = direct("", _p("pocket_watch"), provider=FakeProvider([reply]), catalog=cat, seed=seed, duration=10)
    assert r.source.startswith("llm"), r.source
    assert [e["id"] for e in r.script["effects"]] == ["rain", "wet_surface"]


def test_issue_type_is_the_engine_issue():
    assert Issue("coupled_added", "effects[1]", "x", "repaired").severity == "repaired"


def test_couplings_expand_to_closure_and_a_second_check_changes_nothing(tmp_path):
    """Review chunk1 #8: A -> B -> C adds B and C in one pass (C right after B); a cycle ends; the checker is
    idempotent on its own output."""
    cat = catalog_with_fixtures(tmp_path)
    chain = {"test_a": _fx("test_a", {}, {"couplings": ["test_b"]}),
             "test_b": _fx("test_b", {}, {"couplings": ["test_c"]}),
             "test_c": _fx("test_c", {"k": {"type": "number", "min": 0, "max": 1, "default": 0.3}}),
             "test_x": _fx("test_x", {}, {"couplings": ["test_y"]}),
             "test_y": _fx("test_y", {}, {"couplings": ["test_x"]})}
    _write_fx(cat.root, chain)
    cat = Catalog.load(cat.root)
    s, issues = _maker("test_street")([{"id": "test_a", "params": {}}, {"id": "test_x", "params": {}}]), []
    apply_weather_rules(s, cat, profile_car(), issues)
    assert [e["id"] for e in s["effects"]] == ["test_a", "test_b", "test_c", "test_x", "test_y"]
    assert s["effects"][2]["params"] == {"k": 0.3}
    once = check(_maker("test_street")([{"id": "test_a", "params": {}}]), profile_car(), cat)
    assert once.ok, [i.to_dict() for i in once.issues if i.severity == "error"]
    twice = check(copy.deepcopy(once.script), profile_car(), cat)
    assert twice.script == once.script and not [i for i in twice.issues if i.code == "coupled_added"]


# ---- Task 67: the Task 57 coupling rules on the REAL weather blocks (not fixtures) ----

def test_real_rain_couples_wet_surface_and_droplets_and_excludes_snow():
    cat = Catalog.load()
    s, issues = _maker("rain_courtyard")([{"id": "rain", "params": {}}]), []
    apply_weather_rules(s, cat, profile_car(), issues)
    assert [e["id"] for e in s["effects"]] == ["rain", "wet_surface", "droplets"]
    assert s["effects"][1]["params"] == {"wetness": 0.8, "puddles": 0.4, "ripples": "auto", "drips": True}
    s, issues = _maker("rain_courtyard")([{"id": "rain", "params": {}}, {"id": "snow", "params": {}}]), []
    apply_weather_rules(s, cat, profile_car(), issues)
    assert {i.code for i in issues if i.severity == "error"} == {"exclusive_effects"}
    s, issues = _maker("rain_courtyard")([{"id": "rain", "params": {}}], removed=("wet_surface",)), []
    apply_weather_rules(s, cat, profile_car(), issues)
    assert "coupling_removed" in {i.code for i in issues}


def test_real_rain_on_a_subject_without_up_faces_skips_droplets():
    from engine.tests.test_catalog_growth import profile_of
    s, issues = _maker("rain_courtyard")([{"id": "rain", "params": {}}]), []
    apply_weather_rules(s, Catalog.load(), profile_of("bare_tube"), issues)
    assert [e["id"] for e in s["effects"]] == ["rain", "wet_surface"]
    assert any(i.code == "coupled_skipped" and i.severity == "info" for i in issues)


def test_real_weather_needs_an_outdoor_world():
    cat = Catalog.load()
    for fx in ("rain", "snow", "wet_surface"):
        s, issues = _maker("studio_cyc")([{"id": fx, "params": {}}]), []
        apply_weather_rules(s, cat, profile_car(), issues)
        assert "effect_needs_world" in {i.code for i in issues}, fx


def test_a_blizzard_is_a_warning():
    s = _maker("rain_courtyard")([{"id": "snow", "params": {}}])
    s["wind"] = {"id": "wind", "params": {"speedMs": 12.0}}
    issues = []
    wind_rules(s, issues)
    assert [(i.code, i.severity) for i in issues] == [("wind_implausible", "warning")]
    s["wind"]["params"]["speedMs"] = 10.0
    issues = []
    wind_rules(s, issues)
    assert issues == []


def test_snow_counts_as_cold_for_realism_and_nothing_else_changes():
    from engine.physics.applies import match, temperature
    cat, car = Catalog.load(), profile_car()
    court = cat.get("world", "rain_courtyard")
    snowy = _maker("rain_courtyard")([{"id": "snow", "params": {}}])
    dry = _maker("rain_courtyard")([])
    assert temperature(snowy, court) == "cold" and temperature(dry, court) == "mild"
    m = {"appliesWhen": {"world": {"temperature": ["cold"]}}}
    assert match(m, snowy, car, cat)[0] and not match(m, dry, car, cat)[0]
