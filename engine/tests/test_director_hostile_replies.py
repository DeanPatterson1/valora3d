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
