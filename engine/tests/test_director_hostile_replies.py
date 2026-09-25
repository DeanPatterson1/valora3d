"""Chunk 3 review (2026-09-25): hostile or malformed model replies. The fallback never fails, so no
reply - however broken - may raise out of direct(); each one ends as a checker-valid script."""
import copy
import json

from engine.catalog import Catalog
from engine.checker import check
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from engine.director.rulebook import EXAMPLES_DIR
from engine.tests.test_director_package import _p

WATCH = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]


def _direct(replies, prompt="luxury", model="pocket_watch", **kw):
    p = FakeProvider(replies)
    r = direct(prompt, _p(model), provider=p, seed=kw.pop("seed", 11), **kw)
    assert check(r.script, _p(model), Catalog.load()).ok
    return r, p


def _watch(**shot0):
    w = copy.deepcopy(WATCH)
    w["shots"][0].update(shot0)
    return w


def test_non_finite_and_huge_shot_times_do_not_crash():
    for bad in (float("nan"), float("inf"), -float("inf"), 1e308):
        text = json.dumps(_watch(startS=bad))            # json.dumps writes NaN / Infinity tokens
        r, _ = _direct([text] * 3)
        assert r.source == "fallback", bad
        assert "bad_shot_times" in r.rounds[0]["errors"], (bad, r.rounds[0])


def _nested(depth):
    v = 1.0
    for _ in range(depth):
        v = {"x": v}
    return v


def test_deeply_nested_replies_do_not_crash():
    deep_text = '{"shots": ' + "[" * 100000 + "]" * 100000 + "}"
    r, _ = _direct([deep_text] * 3)
    assert r.source == "fallback" and r.rounds[0]["errors"] == ["llm_not_json"]
    w = copy.deepcopy(WATCH)
    w["world"]["params"]["tone"] = _nested(900)
    r, _ = _direct([json.dumps(w)] * 3)
    assert r.source == "fallback" and r.rounds[0]["errors"]


def test_non_string_block_ids_do_not_crash():
    for bad in (["studio_cyc"], {"a": 1}, 3, None, True):
        w = copy.deepcopy(WATCH)
        w["world"]["id"] = bad
        w["shots"][1]["camera"]["id"] = bad
        r, _ = _direct([w] * 3)
        assert r.source == "fallback" and r.rounds[0]["errors"], bad
        assert "llm_bad_reply" not in r.rounds[0]["errors"], (bad, r.rounds[0])  # handled, not caught


def test_any_crash_while_evaluating_a_reply_becomes_llm_bad_reply(monkeypatch):
    import engine.director.pipeline as pl

    def boom(*a, **k):
        raise KeyError("surprise")
    monkeypatch.setattr(pl, "sanitize", boom)
    r, _ = _direct([WATCH] * 3)
    assert r.source == "fallback" and r.rounds[0]["errors"] == ["llm_bad_reply"]


def test_seed_must_be_an_int_in_range():
    import pytest

    from engine.director.job import DirectorInputError, make_job
    for bad in (-1, 2 ** 31, 1.5, "7", True, float("nan")):
        with pytest.raises(DirectorInputError):
            make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=bad)
    for ok in (0, 2 ** 31 - 1):
        assert make_job("luxury", _p("pocket_watch"), Catalog.load(), seed=ok).seed == ok
