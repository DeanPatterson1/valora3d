import copy
import json
from pathlib import Path
import pytest
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


# --- adversarial LLM output: malformed shapes are errors, never crashes -------------------


def test_non_dict_script_is_single_bad_script_error():
    for bad in ([], None, "a scene", 5):
        _, issues = validate_and_repair(bad, CAT)
        assert codes(issues) == ["bad_script"], bad


def test_shots_not_a_list_is_no_shots():
    for bad in (5, None, "abc", {"startS": 0}):
        s = _script()
        s["shots"] = bad
        _, issues = validate_and_repair(s, CAT)
        assert "no_shots" in codes(issues, "error"), bad


def test_effects_not_a_list_is_bad_effects():
    for bad in (5, None, "glow", {"id": "x"}):
        s = _script()
        s["effects"] = bad
        _, issues = validate_and_repair(s, CAT)
        assert "bad_effects" in codes(issues, "error"), bad


def test_block_params_not_a_dict_is_bad_block_ref():
    for bad in ([1, 2], None, "tone=black"):
        s = _script()
        s["world"]["params"] = bad
        _, issues = validate_and_repair(s, CAT)
        assert "bad_block_ref" in codes(issues, "error"), bad


def test_block_id_not_a_string_is_bad_block_ref():
    for bad in (["studio_cyc"], {"a": 1}, 7, None):
        s = _script()
        s["world"]["id"] = bad
        _, issues = validate_and_repair(s, CAT)
        assert "bad_block_ref" in codes(issues, "error"), bad


def test_non_finite_number_param_uses_default():
    for bad in (float("nan"), float("inf"), float("-inf"), 10 ** 400):
        s = _script()
        s["world"]["params"]["floorGloss"] = bad
        out, issues = validate_and_repair(s, CAT)
        assert codes(issues, "error") == [], bad
        assert "param_bad_type" in codes(issues, "repaired"), bad
        assert out["world"]["params"]["floorGloss"] == CAT.get("world", "studio_cyc")["params"]["floorGloss"]["default"]


def test_non_finite_duration_and_shot_times_are_errors():
    for bad in (float("nan"), float("inf"), float("-inf")):
        s = _script()
        s["format"]["durationS"] = bad
        _, issues = validate_and_repair(s, CAT)
        assert "bad_duration" in codes(issues, "error"), bad
        for key in ("startS", "endS"):
            s = _script()
            s["shots"][1][key] = bad
            _, issues = validate_and_repair(s, CAT)
            assert "bad_shot_times" in codes(issues, "error"), (key, bad)


def test_json_nan_and_infinity_literals_do_not_pass():
    s = json.loads(json.dumps(_script()).replace('"durationS": 10', '"durationS": NaN'))
    _, issues = validate_and_repair(s, CAT)
    assert "bad_duration" in codes(issues, "error")


def test_shot_shorter_than_one_frame_is_error():
    s = _script()
    s["shots"][0]["endS"] = 0.02  # < 1/30
    s["shots"][1]["startS"] = 0.02
    _, issues = validate_and_repair(s, CAT)
    assert "shot_too_short" in codes(issues, "error")
    s = _script()
    s["shots"][0]["endS"] = 1 / 30  # one frame: no in-shot motion to blur or ease
    s["shots"][1]["startS"] = 1 / 30
    _, issues = validate_and_repair(s, CAT)
    assert "shot_too_short" in codes(issues, "error")
    s = _script()
    s["shots"][0]["endS"] = 2 / 30  # two frames is the minimum
    s["shots"][1]["startS"] = 2 / 30
    _, issues = validate_and_repair(s, CAT)
    assert codes(issues, "error") == []


@pytest.mark.parametrize("edge", ["cut", "end"])
def test_shot_boundaries_must_land_on_frames(edge):
    s = _script()
    if edge == "cut":  # 5.02 s * 30 fps = 150.6 frames: the cut would fall mid-frame
        s["format"]["durationS"] = 10
        s["shots"][0]["endS"] = s["shots"][1]["startS"] = 5.02
    else:  # a 10.01 s clip ends mid-frame too
        s["format"]["durationS"] = s["shots"][1]["endS"] = 10.01
    _, issues = validate_and_repair(s, CAT)
    assert "shot_not_frame_aligned" in codes(issues, "error")


def test_frame_aligned_boundaries_tolerate_float_noise():
    s = _script()
    s["shots"][0]["endS"] = s["shots"][1]["startS"] = 0.1 * 3 * 10 / 3 * 5  # 5.000000000000001
    _, issues = validate_and_repair(s, CAT)
    assert "shot_not_frame_aligned" not in codes(issues)


def test_shot_too_short_skipped_when_fps_invalid():
    s = _script()
    s["format"]["fps"] = 0
    s["shots"][0]["endS"] = 0.02
    s["shots"][1]["startS"] = 0.02
    _, issues = validate_and_repair(s, CAT)
    assert "bad_fps" in codes(issues, "error")
    assert "shot_too_short" not in codes(issues)


def test_fps_must_be_a_real_int():
    for bad in (30.0, True, "30", 24.5):
        s = _script()
        s["format"]["fps"] = bad
        _, issues = validate_and_repair(s, CAT)
        assert "bad_fps" in codes(issues, "error"), bad


@pytest.mark.parametrize("field,value,code", [
    ("purpose", "vibes", "bad_purpose"),
    ("transitionIn", "whip", "transition_not_available"),
    ("transitionIn", "teleport", "bad_transition"),
    ("target", {"marker": "a", "detail": 0}, "bad_target"),
    ("target", {"detail": -1}, "bad_target"),
    ("target", {"detail": True}, "bad_target"),
    ("target", "badge", "bad_target"),
    ("target", {"marker": "Bad Id!"}, "bad_target"),
    ("target", {"marker": "x" * 33}, "bad_target"),
])
def test_bad_shot_fields_are_errors(field, value, code):
    s = _script()
    s["shots"][1][field] = value
    _, issues = validate_and_repair(s, CAT)
    assert code in {i.code for i in issues if i.severity == "error"}


def test_good_shot_fields_pass():
    s = _script()
    s["shots"][0].update({"purpose": "hook", "transitionIn": "cut"})
    s["shots"][1].update({"purpose": "hero", "target": {"detail": 0}})
    _, issues = validate_and_repair(s, CAT)
    assert not [i for i in issues if i.severity == "error"]


def test_unknown_edit_block_is_an_error():
    s = _script()
    s["edit"] = {"id": "montage", "params": {}}
    _, issues = validate_and_repair(s, CAT)
    assert "unknown_block" in {i.code for i in issues}


def test_edit_null_is_treated_as_absent():
    s = _script()
    s["edit"] = None
    _, issues = validate_and_repair(s, CAT)
    assert codes(issues, "error") == []
    assert "bad_block_ref" not in codes(issues)
