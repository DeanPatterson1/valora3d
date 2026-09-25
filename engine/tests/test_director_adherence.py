import copy
import json

from engine.catalog import Catalog
from engine.director.adherence import drift, enforce_direction
from engine.director.direction import direction_of
from engine.director.floor import cadence_range
from engine.director.rulebook import EXAMPLES_DIR, example_script

AX = {"world": "studio_cyc", "mood": "teal_night", "tone": "black", "pace": "calm", "opener": "low_hero_push",
      "weather": "dry", "wind": "calm"}
S = example_script(json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8")))
CAT = Catalog.load()


def _drifted():
    s = copy.deepcopy(S)
    s["grade"] = {"id": "neutral_film", "params": {}}
    s.setdefault("edit", {"id": "sequence", "params": {}})["params"]["pace"] = "hype"
    s["world"] = {"id": "studio_cyc", "params": {}}          # tone omitted -> catalog default (grey)
    return s


def test_drift_resolves_defaults_and_sees_neutral_film():
    assert set(drift(_drifted(), direction_of(AX, "dice"), CAT)) >= {"mood", "pace", "tone"}


def test_no_drift_on_a_matching_script():
    s = copy.deepcopy(S)
    d = direction_of({**AX, "mood": s["grade"]["params"]["preset"], "pace": s["edit"]["params"]["pace"],
                      "tone": s["world"]["params"]["tone"], "opener": s["shots"][0]["camera"]["id"]}, "dice")
    assert [a for a in drift(s, d, CAT) if a != "cadence"] == []


def test_vague_prompt_swaps_the_grade_and_sets_tone_and_pace():
    s, issues = enforce_direction(_drifted(), direction_of(AX, "dice"), CAT, enforce=True)
    assert s["grade"] == {"id": "mood_grade", "params": {"preset": "teal_night"}}
    assert s["world"]["params"]["tone"] == "black" and s["edit"]["params"]["pace"] == "calm"
    assert "direction_enforced" in {i.code for i in issues}


def test_absent_grade_and_edit_count_as_catalog_defaults():
    s = copy.deepcopy(S)
    s.pop("grade", None)
    s.pop("edit", None)
    default_mood = CAT.get("grade", "mood_grade")["params"]["preset"]["default"]
    want = {**AX, "mood": "vivid" if default_mood != "vivid" else "clean"}
    assert "mood" in drift(s, direction_of(want, "dice"), CAT)
    s, issues = enforce_direction(s, direction_of(want, "dice"), CAT, enforce=True)
    assert s["grade"] == {"id": "mood_grade", "params": {"preset": want["mood"]}}
    if s["format"]["durationS"] >= 6:
        assert s["edit"]["params"]["pace"] == want["pace"]


def test_cadence_is_measured_not_assumed():
    s = _drifted()
    lo, hi = cadence_range("calm", s["format"]["durationS"], CAT)
    if not lo <= len(s["shots"]) <= hi:
        _, issues = enforce_direction(s, direction_of(AX, "dice"), CAT, enforce=True)
        assert any(i.code == "direction_cadence" and i.severity == "error" for i in issues)
    s2 = copy.deepcopy(s)
    s2["shots"] = s2["shots"][:1] * (hi + 2)
    _, issues = enforce_direction(s2, direction_of(AX, "dice"), CAT, enforce=True)
    assert any(i.code == "direction_cadence" and i.severity == "error" for i in issues)


def test_opener_and_world_drift_go_to_repair_when_enforced():
    s = copy.deepcopy(S)
    _, issues = enforce_direction(s, direction_of({**AX, "opener": "arc_orbit"}, "dice"), CAT, enforce=True)
    assert s["shots"][0]["camera"]["id"] != "arc_orbit"
    assert any(i.code == "direction_opener" and i.severity == "error" for i in issues)


def test_long_prompt_only_enforces_pins():
    d = direction_of(AX, "dice", pinned={"mood": "teal_night"})
    s, issues = enforce_direction(_drifted(), d, CAT, enforce=False)
    assert s["grade"]["params"]["preset"] == "teal_night" and s["edit"]["params"]["pace"] == "hype"
    assert any(i.code == "direction_drift" and i.severity == "info" for i in issues)
    assert not any(i.severity == "error" for i in issues)


def test_only_rolled_directions_are_fully_enforced():
    from engine.director.adherence import should_enforce
    assert should_enforce("", direction_of(AX, "dice")) and should_enforce("ad", direction_of(AX, "more_like_this"))
    assert not should_enforce("", direction_of(AX, "interim"))
    assert not should_enforce("a luxurious product film for my watch brand", direction_of(AX, "dice"))


def test_repair_has_hints_for_the_direction_errors():
    from engine.director.repair import ERROR_HINTS
    assert {"direction_cadence", "direction_opener", "direction_world"} <= set(ERROR_HINTS)


def test_first_message_carries_world_and_opener_never_wind():
    from engine.director.request import first_message
    from engine.tests.test_director_package import _p
    msg = first_message(fmt={"aspect": "9:16", "durationS": 10, "fps": 30}, direction=direction_of(AX, "dice"),
                        profile=_p("pocket_watch"), prompt="", markers=[], detected=[])
    job = json.loads(msg.split("<job>")[1].split("</job>")[0])
    assert job["direction"]["opener"] == "low_hero_push" and job["direction"]["world"] == "studio_cyc"
    assert "weather" not in job["direction"] and "wind" not in job["direction"]


def _watch_reply():
    return json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]


def test_pipeline_enforces_the_direction_on_a_vague_prompt():
    from engine.director.llm import FakeProvider
    from engine.director.pipeline import direct
    from engine.tests.test_director_package import _p
    r = direct("", _p("pocket_watch"), provider=FakeProvider([_watch_reply()] * 3), seed=4, duration=10)
    d = r.script["direction"]["id"].split("/")
    assert r.script["grade"]["params"]["preset"] == d[1]


LONG = "a luxurious product film for my watch brand"   # not vague: only pins are enforced


def test_llm_scripts_get_layer_one_details_but_keep_explicit_params():
    """Review #2: vary_details runs on LLM scripts before the checker fills defaults; params the reply
    set are kept."""
    from engine.director.llm import FakeProvider
    from engine.director.pipeline import direct
    from engine.tests.test_director_package import _p
    reply = _watch_reply()
    reply["world"] = {"id": "studio_cyc", "params": {"tone": "black", "floorGloss": 0.33}}
    reply["lighting"] = {"id": reply["lighting"]["id"], "params": {}}
    a = direct(LONG, _p("pocket_watch"), provider=FakeProvider([copy.deepcopy(reply)] * 3), seed=1,
               duration=10)
    b = direct(LONG, _p("pocket_watch"), provider=FakeProvider([copy.deepcopy(reply)] * 3), seed=2,
               duration=10)
    assert a.source.startswith("llm") and b.source.startswith("llm")
    assert a.script["world"]["params"]["floorGloss"] == 0.33 == b.script["world"]["params"]["floorGloss"]
    assert a.script["lighting"]["params"] != b.script["lighting"]["params"]
