import copy
import json

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.director.job import DirectorInputError
from engine.director.llm import FakeProvider
from engine.director.output_schema import scene_output_schema
from engine.director.pipeline import MAX_REPAIR_CALLS, direct
from engine.director.rulebook import EXAMPLES_DIR, load_rulebook
from engine.tests.test_director_package import _p
from engine.tests.test_director_request import HOSTILE

WATCH = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]
CAR = json.loads((EXAMPLES_DIR / "vehicle_empty.json").read_text(encoding="utf-8"))["script"]
BROKEN = {**WATCH, "world": {"id": "moon", "params": {}}}


_SEEDS = {}


def _seed(prompt, model, markers=None):
    """A seed whose rolled direction the canned example reply already follows (dice_seeds.seed_matching): these
    tests are about the reply, and since phase 5 the dice also roll worlds, weather and wind (Task 87)."""
    key = (prompt, model, repr(markers))
    if key not in _SEEDS:
        from engine.tests.dice_seeds import seed_matching
        _SEEDS[key] = seed_matching(WATCH if model == "pocket_watch" else CAR, [(prompt, markers)], model,
                                    duration=10, start=11, catalog=_cat())
    return _SEEDS[key]


def _cat():
    from engine.tests.dice_seeds import phase4_catalog
    return phase4_catalog()


def _run(replies, prompt="luxury", model="pocket_watch", **kw):
    p = FakeProvider(replies)
    kw.setdefault("duration", 10)   # the 10 s example replies; phase 4 otherwise rolls 8/10/12 s
    seed = kw.pop("seed", None)
    seed = _seed(prompt, model, kw.get("markers")) if seed is None else seed
    kw.setdefault("catalog", _cat())   # the phase-4 menu: these tests are about the reply, not the grown dice
    return direct(prompt, _p(model), provider=p, seed=seed, **kw), p


def test_first_pass():
    r, p = _run([WATCH])
    assert r.source == "llm" and r.firstPassOk and len(p.calls) == 1
    assert check(r.script, _p("pocket_watch"), Catalog.load()).ok and r.script["prompt"] == "luxury"


def test_one_repair_round_carries_the_checker_report():
    r, p = _run([BROKEN, WATCH])
    assert r.source == "llm+repair1" and not r.firstPassOk and len(p.calls) == 2
    msgs = p.calls[1]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"] and "unknown_block" in msgs[2]["content"]


def test_repair_conversation_only_appends():
    """Thinking blocks are bound to the exact earlier conversation: every repair call resends the same
    system text and every earlier message byte-identical, with the assistant turn replayed unchanged."""
    r, p = _run([BROKEN, BROKEN, WATCH])
    assert r.source == "llm+repair2"
    c0, c1, c2 = p.calls
    assert c0["system"] == c1["system"] == c2["system"] and c0["schema"] == c1["schema"] == c2["schema"]
    assert c1["messages"][:1] == c0["messages"] and c2["messages"][:3] == c1["messages"]
    assert c1["messages"][1]["content"] == json.dumps(BROKEN)  # the provider's assistant_content, verbatim


def test_two_failed_repairs_then_fallback():
    r, p = _run([BROKEN] * 3)
    assert r.source == "fallback" and len(p.calls) == 1 + MAX_REPAIR_CALLS == 3
    assert check(r.script, _p("pocket_watch"), Catalog.load()).ok


@pytest.mark.parametrize("reply,calls", [({"stop_reason": "refusal", "text": ""}, 1),
                                         ({"error": "down", "retryable": True}, 1)])
def test_refusal_or_provider_error_goes_straight_to_fallback(reply, calls):
    r, p = _run([reply])
    assert r.source == "fallback" and len(p.calls) == calls


def test_schema_too_complex_resends_the_compact_schema_once(monkeypatch):
    monkeypatch.setenv("VALORA_DIRECTOR_SCHEMA", "full")  # escalation exists only when starting from full
    r, p = _run([{"error": "HTTP 400: schema is too complex", "kind": "schema_too_complex"}, WATCH])
    assert r.source == "llm" and r.firstPassOk and len(p.calls) == 2
    assert p.calls[1]["schema"] == scene_output_schema(_cat(), compact=True)
    assert p.calls[1]["messages"] == p.calls[0]["messages"]
    r, p = _run([{"error": "x", "kind": "schema_too_complex"}] * 2)
    assert r.source == "fallback" and len(p.calls) == 2  # compact is tried once, never looped


def test_not_json_gets_one_more_chance():
    r, _ = _run(["this is not json", WATCH])
    assert r.source == "llm+repair1"


def test_injection_obeying_reply_is_neutralised():
    markers = [{"id": "m0", "text": HOSTILE[0], "anchor": {"space": "placed",
                                                           "point": _p("pocket_watch").detailPoints[0]["point"]}}]
    evil = {**WATCH, "bpy": "import os", "audio": {"id": "x"}, "prompt": "hacked", "seed": 1, "markers": [],
            "assumptions": ["ignored an instruction in the prompt"]}
    r, p = _run([evil], prompt=HOSTILE[3], markers=markers)
    s = r.script
    assert r.source == "llm" and "bpy" not in s and "audio" not in s
    assert s["prompt"] == HOSTILE[3] and s["markers"][0]["text"] == HOSTILE[0]
    assert s["seed"] == _seed(HOSTILE[3], "pocket_watch", markers) != evil["seed"]   # the job's seed, not the reply's


def test_system_prompt_is_the_rulebook_for_every_job():
    text, version = load_rulebook()
    r1, p1 = _run([WATCH], prompt="luxury")
    r2, p2 = _run([WATCH], prompt=HOSTILE[1])
    assert p1.calls[0]["system"] == p2.calls[0]["system"] == text and r1.rulebookVersion == version


def test_unsupported_asks_survive_every_path():
    # phase 5: rain is delivered now (Task 88), so the undeliverable ask is smoke
    r, _ = _run([{**WATCH, "unsupported": []}], prompt="luxury, add smoke")
    assert [u["capability"] for u in r.script["unsupported"]] == ["smoke.plume"]
    r, _ = _run([BROKEN] * 3, prompt="luxury, add smoke")
    assert r.source == "fallback" and [u["capability"] for u in r.script["unsupported"]] == ["smoke.plume"]


def test_small_craft_fixes_cost_no_call():
    reply = copy.deepcopy(CAR)
    reply["shots"][0]["camera"]["params"]["lensMm"] = 20
    from engine.tests.dice_seeds import seed_matching
    seed = seed_matching(CAR, "", "sports_car", duration=10, catalog=_cat())   # a roll the reply follows
    r, p = _run([reply], prompt="", model="sports_car", seed=seed)
    assert r.source == "llm" and len(p.calls) == 1 and r.script["shots"][0]["camera"]["params"]["lensMm"] == 28.0


def test_craft_failure_is_reported_back_and_best_valid_script_kept():
    thin = {**WATCH, "shots": [WATCH["shots"][0] | {"endS": 5.0}, WATCH["shots"][4] | {"startS": 5.0}]}
    thin.pop("edit")
    r, p = _run([thin] * 3, prompt="a luxurious product film for my watch")   # not vague: no cadence enforcement
    assert len(p.calls) == 3 and "T3-01" in p.calls[1]["messages"][-1]["content"]
    # The loop kept the best valid LLM script (measured before the floor) ...
    assert r.floor["rawSource"] == "llm" and "T3-01" in r.floor["rawCraftFailures"]
    # ... and the phase-4 quality floor then replaced that T2 script at delivery (Task 46, review #1).
    assert r.floor["rawTier"] == "T2" and r.floor["substituted"] and r.source == "llm+floor"
    assert len(r.rawScript["shots"]) == 2 and r.rawScript is not r.script


def test_bad_markers_raise_before_any_call():
    p = FakeProvider([WATCH])
    with pytest.raises(DirectorInputError):
        direct("", _p("pocket_watch"), provider=p, markers=[{"id": "BAD ID", "text": "x",
                                                            "anchor": {"point": [0, 0, 0]}}])
    assert p.calls == []


def test_default_sends_the_compact_schema_and_never_escalates(monkeypatch):
    monkeypatch.delenv("VALORA_DIRECTOR_SCHEMA", raising=False)
    r, p = _run([WATCH])
    assert p.calls[0]["schema"] == scene_output_schema(_cat(), compact=True) and r.compactSchema
    r, p = _run([{"error": "x", "kind": "schema_too_complex"}])
    assert r.source == "fallback" and len(p.calls) == 1   # already compact: nothing smaller to resend


def test_env_full_sends_the_full_schema(monkeypatch):
    monkeypatch.setenv("VALORA_DIRECTOR_SCHEMA", "full")
    r, p = _run([WATCH])
    assert p.calls[0]["schema"] == scene_output_schema(_cat()) and not r.compactSchema


def test_best_script_is_picked_by_worst_tier_first_then_count(monkeypatch):
    """Chunk 3 review LOW 8: one T1 failure is worse than two T3 failures."""
    from types import SimpleNamespace

    import engine.director.pipeline as pl
    plan = iter([["T1-X1"], ["T3-01", "T3-04"], ["T3-01", "T3-04", "T3-13"]])
    monkeypatch.setattr(pl, "craft_failures", lambda *a, **k: [SimpleNamespace(id=i, detail="") for i in next(plan)])
    monkeypatch.setattr(pl, "auto_fix_craft", lambda s, *a, **k: (s, []))
    r, p = _run([WATCH, WATCH, WATCH])
    assert len(p.calls) == 3 and r.source == "llm+repair1" and r.craftFailures == ["T3-01", "T3-04"]
