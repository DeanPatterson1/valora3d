import copy
import json

from engine.catalog import Catalog
from engine.checker import check
from engine.director.job import make_job
from engine.director.llm import FakeProvider
from engine.director.reroll import reroll_shot, shots_for_failures
from engine.director.rulebook import EXAMPLES_DIR, example_script
from engine.tests.test_director_package import _p

EX = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))


def _checked():
    return check(example_script(EX), _p("pocket_watch"), Catalog.load()).script


def test_frames_map_to_shots():
    s = _checked()  # 30 fps; shots start 0, 2.0, 3.5, 5.5, 7.0
    got = shots_for_failures(s, {"T3-06": [1, 106, 107], "B-02": [220]})
    assert got == {0: ["T3-06"], 2: ["T3-06"], 4: ["B-02"]}


def test_llm_reroll_splices_only_that_shot():
    s = _checked()
    reply = copy.deepcopy(EX["script"])
    reply["shots"][2]["camera"]["params"]["startAzimuthDeg"] = -140
    reply["world"]["params"]["tone"] = "white"          # outside the shot: must be ignored
    job = make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=s["seed"])
    out, how = reroll_shot(s, 2, ["T3-06"], profile=_p("pocket_watch"), provider=FakeProvider([reply]), job=job)
    assert how == "llm" and out["shots"][2]["camera"]["params"]["startAzimuthDeg"] == -140
    assert out["world"] == s["world"] and [sh["startS"] for sh in out["shots"]] == [sh["startS"] for sh in s["shots"]]


def test_a_detail_shot_can_be_rerolled_too():
    s = _checked()
    job = make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=s["seed"])
    out, how = reroll_shot(s, 1, ["T3-22"], profile=_p("pocket_watch"), provider=FakeProvider(["nope"]), job=job)
    assert how == "deterministic" and out["shots"][1]["camera"] != s["shots"][1]["camera"]


def test_deterministic_reroll_when_the_model_fails():
    s = _checked()
    job = make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=s["seed"])
    out, how = reroll_shot(s, 2, ["T3-06"], profile=_p("pocket_watch"), provider=FakeProvider(["nope"]), job=job)
    assert how == "deterministic" and out["shots"][2] != s["shots"][2]
    assert check(out, _p("pocket_watch"), Catalog.load()).ok


def test_reroll_resends_with_the_compact_schema_when_the_full_one_is_rejected(monkeypatch):
    from engine.director.output_schema import scene_output_schema
    monkeypatch.setenv("VALORA_DIRECTOR_SCHEMA", "full")
    s = _checked()
    reply = copy.deepcopy(EX["script"])
    reply["shots"][2]["camera"]["params"]["startAzimuthDeg"] = -140
    job = make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=s["seed"])
    p = FakeProvider([{"error": "schema too complex", "kind": "schema_too_complex"}, reply])
    out, how = reroll_shot(s, 2, ["T3-06"], profile=_p("pocket_watch"), provider=p, job=job)
    assert how == "llm" and len(p.calls) == 2
    assert p.calls[1]["schema"] == scene_output_schema(Catalog.load(), compact=True)


def test_reroll_default_sends_only_the_compact_schema(monkeypatch):
    from engine.director.output_schema import scene_output_schema
    monkeypatch.delenv("VALORA_DIRECTOR_SCHEMA", raising=False)
    s = _checked()
    job = make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=s["seed"])
    p = FakeProvider([{"error": "schema too complex", "kind": "schema_too_complex"}])
    out, how = reroll_shot(s, 2, ["T3-06"], profile=_p("pocket_watch"), provider=p, job=job)
    assert len(p.calls) == 1 and p.calls[0]["schema"] == scene_output_schema(Catalog.load(), compact=True)
    assert how == "deterministic"


def test_reroll_never_accepts_an_off_menu_camera():
    """Chunk 3 review HIGH 3: the harness-only turntable passes the checker but is not on the menu."""
    s = _checked()
    reply = copy.deepcopy(EX["script"])
    reply["shots"][2]["camera"] = {"id": "turntable", "params": {}}
    job = make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=s["seed"])
    out, how = reroll_shot(s, 2, ["T3-06"], profile=_p("pocket_watch"), provider=FakeProvider([reply]), job=job)
    assert how != "llm" and out["shots"][2]["camera"]["id"] != "turntable"
    assert check(out, _p("pocket_watch"), Catalog.load()).ok


def test_reroll_survives_a_junk_reply():
    s = _checked()
    reply = copy.deepcopy(EX["script"])
    reply["shots"][2]["camera"] = {"id": ["x"], "params": 7}
    job = make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=s["seed"])
    out, how = reroll_shot(s, 2, ["T3-06"], profile=_p("pocket_watch"), provider=FakeProvider([reply]), job=job)
    assert how in ("deterministic", "unchanged") and check(out, _p("pocket_watch"), Catalog.load()).ok


def test_reroll_honours_the_schema_mode_the_director_used(monkeypatch):
    """Chunk 3 review LOW 10: pass DirectorResult.compactSchema; it wins over the environment."""
    from engine.director.output_schema import scene_output_schema
    monkeypatch.setenv("VALORA_DIRECTOR_SCHEMA", "full")
    s = _checked()
    job = make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=s["seed"])
    p = FakeProvider(["nope"])
    reroll_shot(s, 2, ["T3-06"], profile=_p("pocket_watch"), provider=p, job=job, compact=True)
    assert p.calls[0]["schema"] == scene_output_schema(Catalog.load(), compact=True)
    monkeypatch.delenv("VALORA_DIRECTOR_SCHEMA")
    p = FakeProvider(["nope"])
    reroll_shot(s, 2, ["T3-06"], profile=_p("pocket_watch"), provider=p, job=job, compact=False)
    assert p.calls[0]["schema"] == scene_output_schema(Catalog.load())
