"""Phase 6 Task 95: the sim checker rules (pure). Fixture sims are written into a temp catalog, so this does
not depend on the real sim blocks of Tasks 100-117."""
import copy
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog, CatalogError
from engine.checker import check
from engine.script import validate_and_repair
from engine.sim_rules import bake_range, check_sims, couple_sims
from engine.tests.realism_catalog import catalog_with_fixtures
from engine.tests.test_director_package import _p

FIX = Path(__file__).parent / "fixtures"
_TAGS = {"mood": [], "energy": [], "palette": []}


def _sim(bid, cost="medium", physics=None, bake=None, params=None):
    ps = {"timeScale": {"type": "number", "min": 0.1, "max": 1.0, "default": 0.5}}
    ps.update(params or {})
    ph = {"taxonomy": ["RB-05"], "state": "baked", "timeScaleParam": "timeScale", "touchesSubject": True}
    ph.update(physics or {})
    bk = {"method": "rigid_keys", "costClass": cost, "prerollS": 0.5, "maxFrames": 240, "estimateS": 120,
          "cacheMBMax": 20}
    bk.update(bake or {})
    return {"id": bid, "kind": "sim", "description": f"TEST ONLY {bid}", "params": ps,
            "subjectSizeM": [0.02, 30.0], "aspects": ["9:16", "16:9", "1:1", "4:5"], "costWeight": 1.0,
            "tags": _TAGS, "tierMax": "T4", "directorSelectable": False, "physics": ph, "bake": bk}


SIMS = {
    "t_drop": _sim("t_drop", physics={"spawnZone": {"kind": "above", "heightFrac": 1.5, "radiusFrac": 0.6,
                                                     "heightParam": "drop"}},
                   params={"drop": {"type": "number", "min": 0.3, "max": 2.0, "default": 1.5}}),
    "t_heavy": _sim("t_heavy", cost="heavy", bake={"method": "gas_vdb", "prerollS": 2.0, "maxFrames": 180}),
    "t_heavy2": _sim("t_heavy2", cost="heavy", bake={"method": "liquid_abc", "maxFrames": 150}),
    "t_points": _sim("t_points", bake={"method": "gn_disk", "prerollS": 0.5}),
    "t_outdoor": _sim("t_outdoor", physics={"requiresWorld": {"outdoor": True}}),
    "t_wheels": _sim("t_wheels", physics={}),
    "t_can": _sim("t_can", physics={"requiresSimFacts": ["container"]}),
    "t_parent": _sim("t_parent", physics={"couplings": ["t_child", "t_fx"]}),
    "t_child": _sim("t_child", cost="cheap", bake={"method": "none"}, physics={"state": "stateless",
                                                                               "timeScaleParam": None}),
}
SIMS["t_wheels"]["requiresProfile"] = ["wheels"]
FX = {"t_fx": {"id": "t_fx", "kind": "effect", "description": "TEST ONLY t_fx",
               "params": {"amount": {"type": "number", "min": 0, "max": 1, "default": 0.4}},
               "subjectSizeM": [0.02, 30.0], "aspects": ["9:16", "16:9", "1:1", "4:5"], "costWeight": 1.0,
               "tags": _TAGS, "tierMax": "T3", "physics": {}}}


def _write(root, kind, blocks):
    for bid, m in blocks.items():
        d = Path(root) / kind / bid
        d.mkdir(parents=True, exist_ok=True)
        (d / "block.json").write_text(json.dumps(m), encoding="utf-8")
        (d / "build.py").write_text("def build(ctx):\n    pass\n", encoding="utf-8")


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    c = catalog_with_fixtures(tmp_path_factory.mktemp("sim"))
    _write(c.root, "sim", SIMS)
    _write(c.root, "effect", FX)
    return Catalog.load(c.root)


def _script(*sims, world="studio_cyc"):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["world"] = {"id": world, "params": {}}
    s["sims"] = copy.deepcopy(list(sims))
    return s


def _run(cat, s, profile=None):
    s, issues = validate_and_repair(s, cat)
    assert not [i for i in issues if i.severity == "error"], issues
    couple_sims(s, cat, profile or _p("sneaker"), issues)
    check_sims(s, cat, profile or _p("sneaker"), issues)
    return s, issues


def _codes(issues, sev=None):
    return [i.code for i in issues if sev is None or i.severity == sev]


# --- sim_window --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("a,b,want", [(-1.0, 3.0, (0.0, 3.0)), (8.0, 12.0, (8.0, 10.0))])
def test_window_outside_the_clip_is_clamped(cat, a, b, want):
    s, issues = _run(cat, _script({"id": "t_drop", "params": {}, "startS": a, "endS": b}))
    assert (s["sims"][0]["startS"], s["sims"][0]["endS"]) == want
    assert "sim_window_clamped" in _codes(issues, "repaired") and "sim_window_truncated" not in _codes(issues)


def test_window_is_snapped_to_whole_frames(cat):
    s, issues = _run(cat, _script({"id": "t_drop", "params": {}, "startS": 1.01, "endS": 3.0}))
    assert s["sims"][0]["startS"] == 1.0 and "sim_window_clamped" in _codes(issues, "repaired")


@pytest.mark.parametrize("a,b", [(2.0, 2.0), (3.0, 2.0), (11.0, 12.0)])
def test_a_zero_length_window_is_an_error(cat, a, b):
    _, issues = _run(cat, _script({"id": "t_drop", "params": {}, "startS": a, "endS": b}))
    assert "sim_window_empty" in _codes(issues, "error")


def test_a_window_over_max_frames_is_truncated_keeping_the_preroll(cat):
    s, issues = _run(cat, _script({"id": "t_heavy", "params": {}, "startS": 0.0, "endS": 10.0}))   # 180 f cap
    assert "sim_window_truncated" in _codes(issues, "repaired")
    r = bake_range(s, s["sims"][0], cat.get("sim", "t_heavy"))
    assert r.preroll == 60 and r.bake_last - r.bake_first + 1 <= 180 and not r.truncated


def test_bake_range_adds_the_preroll(cat):
    s, _ = _run(cat, _script({"id": "t_drop", "params": {}, "startS": 1.0, "endS": 4.0}))
    r = bake_range(s, s["sims"][0], cat.get("sim", "t_drop"))
    assert (r.bake_first, r.clip_first, r.clip_last, r.preroll) == (1, 31, 121, 15)
    assert r.clip_last <= 4.0 * 30 + 1


def test_gn_sims_preroll_before_the_clip_on_render_frames(cat):
    s, _ = _run(cat, _script({"id": "t_points", "params": {}, "startS": 0.0, "endS": 2.0}))
    r = bake_range(s, s["sims"][0], cat.get("sim", "t_points"))
    assert (r.bake_first, r.offset) == (-14, 0)


# --- sim_budget, duplicates ----------------------------------------------------------------------------------

def test_two_heavy_sims_are_an_error(cat):
    _, issues = _run(cat, _script({"id": "t_heavy", "params": {}, "startS": 0, "endS": 2},
                                  {"id": "t_heavy2", "params": {}, "startS": 2, "endS": 4}))
    assert "sim_budget" in _codes(issues, "error")


def test_one_heavy_and_one_medium_pass(cat):
    _, issues = _run(cat, _script({"id": "t_heavy", "params": {}, "startS": 0, "endS": 2},
                                  {"id": "t_drop", "params": {}, "startS": 2, "endS": 4}))
    assert not _codes(issues, "error")


def test_the_same_sim_twice_is_an_error(cat):
    _, issues = _run(cat, _script({"id": "t_drop", "params": {}, "startS": 0, "endS": 2},
                                  {"id": "t_drop", "params": {}, "startS": 2, "endS": 4}))
    assert "sim_duplicate" in _codes(issues, "error")


# --- time scale ----------------------------------------------------------------------------------------------

def test_time_scale_outside_the_range_is_clamped(cat):
    s, issues = validate_and_repair(_script({"id": "t_drop", "params": {"timeScale": 5.0}, "startS": 0, "endS": 2}), cat)
    assert s["sims"][0]["params"]["timeScale"] == 1.0
    assert any(i.code == "param_clamped" and i.path == "sims[0].params.timeScale" for i in issues)


# --- spawn zone ----------------------------------------------------------------------------------------------

def test_a_spawn_zone_above_the_subject_passes(cat):
    _, issues = _run(cat, _script({"id": "t_drop", "params": {}, "startS": 0, "endS": 2}))
    assert "sim_spawn_in_subject" not in _codes(issues)


def test_a_spawn_zone_inside_the_subject_bounds_is_an_error(cat):
    _, issues = _run(cat, _script({"id": "t_drop", "params": {"drop": 0.5}, "startS": 0, "endS": 2}))
    assert "sim_spawn_in_subject" in _codes(issues, "error")


# --- world / profile needs -----------------------------------------------------------------------------------

def test_a_sim_that_needs_an_outdoor_world_fails_in_the_studio(cat):
    _, issues = _run(cat, _script({"id": "t_outdoor", "params": {}, "startS": 0, "endS": 2}))
    assert "sim_needs_world" in _codes(issues, "error")


def test_a_sim_that_needs_wheels_fails_on_a_sneaker(cat):
    _, issues = _run(cat, _script({"id": "t_wheels", "params": {}, "startS": 0, "endS": 2}))
    assert "sim_needs_profile" in _codes(issues, "error")
    _, issues = _run(cat, _script({"id": "t_wheels", "params": {}, "startS": 0, "endS": 2}), _p("sports_car"))
    assert "sim_needs_profile" not in _codes(issues)


def test_a_sim_that_needs_a_container_fails_without_a_confident_one(cat):
    _, issues = _run(cat, _script({"id": "t_can", "params": {}, "startS": 0, "endS": 2}))
    assert "sim_needs_profile" in _codes(issues, "error")
    s = _script({"id": "t_can", "params": {}, "startS": 0, "endS": 2})
    s["markers"] = [{"id": "rim", "text": "the rim", "anchor": {"space": "placed", "point": [0.0, 0.0, 0.1]}}]
    s2, issues = validate_and_repair(s, cat)
    couple_sims(s2, cat, _p("sneaker"), issues)
    check_sims(s2, cat, _p("sneaker"), issues)
    assert "sim_needs_profile" not in _codes(issues)


# --- wind params ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["windSpeed", "windDir", "gustiness"])
def test_a_wind_param_on_a_sim_is_an_error(cat, name):
    _, issues = validate_and_repair(_script({"id": "t_drop", "params": {name: 3}, "startS": 0, "endS": 2}), cat)
    assert "sim_param_wind" in _codes(issues, "error")


def test_a_sim_manifest_cannot_own_wind_params(tmp_path):
    c = catalog_with_fixtures(tmp_path)
    _write(c.root, "sim", {"t_w": _sim("t_w", params={"windSpeed": {"type": "number", "min": 0, "max": 9, "default": 1}})})
    with pytest.raises(CatalogError):
        Catalog.load(c.root)


# --- couplings -----------------------------------------------------------------------------------------------

def test_a_sim_couples_effects_and_light_sims_with_its_window(cat):
    s, issues = _run(cat, _script({"id": "t_parent", "params": {}, "startS": 1.0, "endS": 3.0}))
    assert [x["id"] for x in s["sims"]] == ["t_parent", "t_child"]
    assert (s["sims"][1]["startS"], s["sims"][1]["endS"]) == (1.0, 3.0)
    assert [e["id"] for e in s["effects"]] == ["t_fx"]
    assert _codes(issues).count("coupled_added") == 2


def test_a_sim_may_never_couple_a_heavy_sim(tmp_path):
    c = catalog_with_fixtures(tmp_path)
    _write(c.root, "sim", {"t_big": _sim("t_big", cost="heavy"),
                           "t_p": _sim("t_p", physics={"couplings": ["t_big"]})})
    with pytest.raises(CatalogError):
        Catalog.load(c.root)


# --- the checker ---------------------------------------------------------------------------------------------

def test_the_checker_runs_the_sim_rules(cat):
    r = check(_script({"id": "t_outdoor", "params": {}, "startS": 0, "endS": 2}), _p("sneaker"), cat)
    assert not r.ok and "sim_needs_world" in _codes(r.issues, "error")
    r = check(_script({"id": "t_drop", "params": {}, "startS": 0, "endS": 2}), _p("sneaker"), cat)
    assert r.ok, [i for i in r.issues if i.severity == "error"]
    assert r.script["sims"][0]["id"] == "t_drop"
