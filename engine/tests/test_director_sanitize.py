import json

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.director.job import DirectorInputError, make_job
from engine.director.rulebook import EXAMPLES_DIR
from engine.director.sanitize import parse_output, sanitize
from engine.tests.test_director_package import _p

WATCH_REPLY = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]


def _job(prompt="luxury", markers=None, name="pocket_watch", seed=7):
    return make_job(prompt, _p(name), Catalog.load(), seed=seed, markers=markers)


def _marker(text="the crown", i=0):
    return {"id": f"m{i}", "text": text, "anchor": {"space": "placed", "point": _p("pocket_watch").detailPoints[i]["point"]}}


def test_parse_output():
    assert parse_output('{"a": 1}')[0] == {"a": 1}
    for bad in ("nope", "[1]", ""):
        raw, issues = parse_output(bad)
        assert raw is None and issues[0].code == "llm_not_json"


def test_owned_fields_overwritten_and_unknown_keys_dropped():
    job = _job(markers=[_marker()])
    evil = {**WATCH_REPLY, "seed": 1, "prompt": "hacked", "format": {"aspect": "16:9"}, "markers": [],
            "schema": "x", "bpy": "import os", "audio": {"id": "x"}}
    s, issues = sanitize(evil, job, Catalog.load(), _p("pocket_watch"))
    assert s["seed"] == 7 and s["prompt"] == "luxury" and s["format"] == job.fmt
    assert [m["id"] for m in s["markers"]] == ["m0"] and "bpy" not in s and "audio" not in s
    codes = [i.code for i in issues]
    assert codes.count("owned_field_overwritten") == 5 and codes.count("llm_key_dropped") == 2
    assert check(s, _p("pocket_watch"), Catalog.load()).ok


def test_detected_unsupported_is_never_dropped_and_llm_can_add():
    job = _job(prompt="luxury with rain")
    s, issues = sanitize({**WATCH_REPLY, "unsupported": []}, job, Catalog.load(), _p("pocket_watch"))
    assert [u["capability"] for u in s["unsupported"]] == ["weather.rain"]
    assert "Rain isn't available yet, so the video is dry." in s["assumptions"]
    assert any(i.code == "unsupported_merged" for i in issues)
    s, _ = sanitize({**WATCH_REPLY, "unsupported": [{"ask": "sparkles", "capability": "sim.particles"}]},
                    job, Catalog.load(), _p("pocket_watch"))
    assert [u["capability"] for u in s["unsupported"]] == ["weather.rain", "sim.particles"]


def test_times_snap_to_frames_and_defaults_fill():
    reply = json.loads(json.dumps(WATCH_REPLY))
    reply["shots"][0]["endS"] = reply["shots"][1]["startS"] = 2.0123
    s, issues = sanitize(reply, _job(), Catalog.load(), _p("pocket_watch"))
    assert s["shots"][0]["endS"] == s["shots"][1]["startS"] == 2.0
    assert all(sh["focus"] == "subject" and sh["transitionIn"] == "cut" for sh in s["shots"])
    assert any(i.code == "shot_time_snapped" for i in issues)


def test_assumptions_cleaned_capped_system_notes_first():
    reply = {**WATCH_REPLY, "assumptions": ["x‮evil"] + [f"line {i}" for i in range(20)]}
    s, _ = sanitize(reply, _job(prompt="luxury"), Catalog.load(), _p("pocket_watch"))
    assert s["assumptions"][0].startswith("no format given")
    assert "‮" not in "".join(s["assumptions"]) and len(s["assumptions"]) <= 12


def test_non_selectable_block_is_an_error():
    reply = json.loads(json.dumps(WATCH_REPLY))
    reply["shots"][2]["camera"] = {"id": "turntable", "params": {}}
    _, issues = sanitize(reply, _job(), Catalog.load(), _p("pocket_watch"))
    assert any(i.code == "director_block_forbidden" and i.severity == "error" for i in issues)


@pytest.mark.parametrize("markers,prompt", [
    ([{"id": "m0", "text": "bad\u0007", "anchor": {"space": "placed", "point": [0, 0, 0.03]}}], ""),
    ([{"id": "m0", "text": "far away", "anchor": {"space": "placed", "point": [9, 9, 9]}}], ""),
    (None, "x" * 2001), (None, "evil‮text"),
])
def test_bad_job_input_is_rejected_before_any_call(markers, prompt):
    with pytest.raises(DirectorInputError):
        _job(prompt=prompt, markers=markers)


def test_malformed_shapes_are_errors_not_crashes():
    job = _job()
    s, _ = sanitize({"subject": "x", "effects": 3, "shots": 5, "world": [1]}, job, Catalog.load(), _p("pocket_watch"))
    assert not check(s, _p("pocket_watch"), Catalog.load()).ok


def test_marker_asks_are_detected_with_their_source():
    job = _job(prompt="", markers=[_marker("water dripping down here")])
    assert job.detected[0]["capability"] == "sim.liquid" and job.detected[0]["source"] == "marker:m0"
