import copy
import json
from pathlib import Path
from engine.catalog import Catalog
from engine.script import validate_and_repair

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()


def _script():
    return json.loads((FIX / "script_valid.json").read_text())


def codes(issues, severity=None):
    return sorted(i.code for i in issues if severity is None or i.severity == severity)


def test_valid_script_only_fills_defaults():
    out, issues = validate_and_repair(_script(), CAT)
    assert codes(issues, "error") == []
    assert out["lighting"]["params"]["fillRatio"] == 0.35  # default filled
    assert set(codes(issues)) == {"param_default"}


def test_input_not_mutated():
    s = _script()
    before = copy.deepcopy(s)
    validate_and_repair(s, CAT)
    assert s == before


def test_clamp_drop_and_bad_enum():
    s = _script()
    s["shots"][0]["camera"]["params"]["lensMm"] = 500
    s["shots"][0]["camera"]["params"]["wobble"] = 3
    s["world"]["params"]["tone"] = "purple"
    out, issues = validate_and_repair(s, CAT)
    assert out["shots"][0]["camera"]["params"]["lensMm"] == 135.0
    assert "wobble" not in out["shots"][0]["camera"]["params"]
    assert out["world"]["params"]["tone"] == "grey"
    assert {"param_clamped", "param_unknown_dropped", "param_bad_enum"} <= set(codes(issues, "repaired"))


def test_unknown_block_and_reserved_audio_are_errors():
    s = _script()
    s["world"]["id"] = "moon"
    s["audio"] = {"id": "synthwave"}
    _, issues = validate_and_repair(s, CAT)
    assert {"unknown_block", "reserved_not_in_v1"} <= set(codes(issues, "error"))


def test_small_shot_gap_snapped_large_gap_error():
    s = _script()
    s["shots"][1]["startS"] = 5.03
    s["shots"][1]["endS"] = 9.9
    out, issues = validate_and_repair(s, CAT)
    assert out["shots"][1]["startS"] == 5 and out["shots"][1]["endS"] == 10
    assert codes(issues, "error") == []
    s["shots"][1]["startS"] = 6
    _, issues = validate_and_repair(s, CAT)
    assert "shots_not_contiguous" in codes(issues, "error")


def test_malformed_input_is_error_not_crash():
    s = _script()
    s["format"] = "9:16"
    s["seed"] = True
    s["shots"][0].pop("startS")
    _, issues = validate_and_repair(s, CAT)
    assert {"bad_format", "bad_seed", "bad_shot_times"} <= set(codes(issues, "error"))


def test_bad_format_values():
    s = _script()
    s["format"] = {"aspect": "2:1", "durationS": 90, "fps": 12}
    _, issues = validate_and_repair(s, CAT)
    assert {"bad_aspect", "bad_duration", "bad_fps"} <= set(codes(issues, "error"))
