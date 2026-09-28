"""Phase 6 Task 95: the `sim` manifest contract and the script's `sims` field (pure).

At HEAD before T95 a hand-written `sims` key was neither reserved nor validated, so it was silently
ignored; these tests pin that it is now validated, and that a script without it is unchanged."""
import copy
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog, CatalogError, _check_manifest
from engine.script import validate_and_repair

FIX = Path(__file__).parent / "fixtures"

SIM = {"id": "_t", "kind": "sim", "description": "test", "params": {
          "timeScale": {"type": "number", "min": 0.1, "max": 1.0, "default": 0.5}},
       "subjectSizeM": [0.03, 30.0], "aspects": ["9:16", "16:9", "1:1", "4:5"], "costWeight": 2.0,
       "tags": {"mood": [], "energy": [], "palette": []}, "tierMax": "T4", "directorSelectable": False,
       "capabilities": ["rigid.scatter"],
       "physics": {"taxonomy": ["RB-05"], "state": "baked", "touchesSubject": True, "windDriven": False,
                   "timeScaleParam": "timeScale", "bakeCostS": 0},
       "bake": {"method": "rigid_keys", "costClass": "medium", "prerollS": 0.5, "maxFrames": 240,
                "estimateS": 120, "cacheMBMax": 20}}


def _committed_studio_script():
    return json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))


def test_sim_manifest_requires_baked_state_bake_object_and_time_scale():
    _check_manifest("sim", "_t", SIM)
    for broken in (("physics", "state", "stateless"), ("physics", "timeScaleParam", None),
                   ("bake", "method", "bogus"), ("bake", "costClass", "huge"), ("bake", "maxFrames", 0),
                   ("bake", "estimateS", -1), ("bake", "cacheMBMax", "20"), ("bake", "prerollS", -0.1),
                   ("physics", "timeScaleParam", "nope")):
        m = copy.deepcopy(SIM)
        m[broken[0]][broken[1]] = broken[2]
        with pytest.raises(CatalogError):
            _check_manifest("sim", "_t", m)
    m = copy.deepcopy(SIM)
    del m["bake"]
    with pytest.raises(CatalogError):
        _check_manifest("sim", "_t", m)


def test_a_stateless_sim_uses_bake_method_none_without_a_time_scale():
    m = copy.deepcopy(SIM)
    m["physics"].update(state="stateless", timeScaleParam=None)
    m["bake"] = {"method": "none", "costClass": "cheap"}
    _check_manifest("sim", "_t", m)
    m["bake"]["costClass"] = "huge"
    with pytest.raises(CatalogError):
        _check_manifest("sim", "_t", m)


@pytest.mark.parametrize("zone", [{"kind": "above", "heightFrac": 1.5, "radiusFrac": 0.6},
                                  {"kind": "around", "radiusFrac": 1.4},
                                  {"kind": "above", "heightFrac": 1.2, "radiusFrac": 0.6, "heightParam": "timeScale"}])
def test_spawn_zone_shapes(zone):
    m = copy.deepcopy(SIM)
    m["physics"]["spawnZone"] = zone
    _check_manifest("sim", "_t", m)


@pytest.mark.parametrize("zone", [{"kind": "inside", "heightFrac": 1.5}, {"kind": "above"},
                                  {"kind": "above", "heightFrac": -1}, {"kind": "around", "radiusFrac": 1.4,
                                                                         "heightParam": "missing"}])
def test_bad_spawn_zones_fail(zone):
    m = copy.deepcopy(SIM)
    m["physics"]["spawnZone"] = zone
    with pytest.raises(CatalogError):
        _check_manifest("sim", "_t", m)


def test_the_shipped_catalog_still_loads_with_an_empty_sim_folder():
    assert Catalog.load().ids("sim") == []


def test_sims_key_is_validated_not_ignored():
    cat = Catalog.load()
    s = _committed_studio_script()
    s["sims"] = [{"id": "no_such_sim", "params": {}, "startS": 0, "endS": 2}]
    _, issues = validate_and_repair(s, cat)
    assert any(i.code == "unknown_block" and i.path.startswith("sims[0]") and i.severity == "error" for i in issues)


@pytest.mark.parametrize("sims", ["rain", [1], [{"id": "x", "params": {}, "startS": 0}],
                                  [{"id": "x", "params": {}, "startS": 0, "endS": float("nan")}],
                                  [{"id": "x", "params": {}, "startS": True, "endS": 2}],
                                  [{"id": "x", "params": {}, "startS": 0, "endS": 2, "extra": 1}],
                                  [{"id": "x", "params": {}, "startS": 0, "endS": 2}] * 4])
def test_malformed_sims_are_errors_never_crashes(sims):
    s = _committed_studio_script()
    s["sims"] = sims
    _, issues = validate_and_repair(s, Catalog.load())
    assert any(i.code == "bad_sims" and i.severity == "error" for i in issues)


def test_a_script_without_sims_is_byte_identical_after_the_change():
    cat = Catalog.load()
    s = _committed_studio_script()
    out, _ = validate_and_repair(s, cat)
    assert "sims" not in out
    assert json.dumps(out, sort_keys=True) == json.dumps(validate_and_repair(s, cat)[0], sort_keys=True)
