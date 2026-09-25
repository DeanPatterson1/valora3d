import json
import threading

import pytest

from engine.catalog import Catalog
from engine.director.distance import script_distance
from engine.director.floor import _RANK, floor_tier, script_tier
from engine.director.llm import FakeProvider
from engine.director.memory import MemoryBusy, VarietyMemory
from engine.director.pipeline import direct
from engine.director.variety import ReplayStale, replay, subject_key
from engine.tests.test_director_package import _p

REFUSE = [{"stop_reason": "refusal", "text": ""}]


class NoCalls:
    def generate(self, **kw):
        raise AssertionError("replay must never call the provider")


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.delenv("VALORA_VARIETY_SECRET", raising=False)


def _run(seed, **kw):
    return direct(kw.pop("prompt", ""), _p("pocket_watch"), provider=FakeProvider(REFUSE * 3), seed=seed, **kw)


def test_replay_returns_the_saved_script_without_calling_the_provider():
    a = _run(5)
    b = replay(a.replay, _p("pocket_watch"), Catalog.load(), provider=NoCalls())
    assert b.script == a.script and b.source == "replay" and b.direction["id"] == a.direction["id"]
    assert b.script["assumptions"] == a.script["assumptions"]


def test_replay_survives_a_json_round_trip():
    a = _run(6)
    rec = json.loads(json.dumps(a.replay))
    assert replay(rec, _p("pocket_watch"), Catalog.load()).script == a.script


def test_replay_of_a_tampered_or_stale_record_is_refused():
    a = _run(5)
    bad = {**a.replay, "script": {**a.replay["script"], "world": {"id": "moon", "params": {}}}}
    with pytest.raises(ReplayStale):
        replay(bad, _p("pocket_watch"), Catalog.load())
    with pytest.raises(ReplayStale):
        replay({**a.replay, "seed": a.replay["seed"] + 1}, _p("pocket_watch"), Catalog.load())
    for junk in (None, "x", {}, {**a.replay, "schema": "other/1"}, {**a.replay, "script": "x"}):
        with pytest.raises(ReplayStale):
            replay(junk, _p("pocket_watch"), Catalog.load())


def test_layer_one_same_direction_and_duration_still_differs():
    a = _run(1)
    b = _run(2, like=a.script)
    assert b.direction["id"] == a.direction["id"]
    assert b.script["format"]["durationS"] == a.script["format"]["durationS"]
    assert b.script["lighting"]["params"] != a.script["lighting"]["params"]         # seeded details
    assert script_distance(a.script, b.script, Catalog.load()) > 0


def _watch():
    from engine.director.rulebook import EXAMPLES_DIR
    return json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]


def test_below_floor_llm_script_is_replaced_by_a_fallback_that_meets_the_floor(monkeypatch):
    import engine.director.pipeline as pl
    fb_real = pl.build_fallback
    made = []
    monkeypatch.setattr(pl, "build_fallback", lambda *a, **k: made.append(fb_real(*a, **k)) or made[-1])
    monkeypatch.setattr(pl, "floor_tier", lambda *a: "T3")
    monkeypatch.setattr(pl, "script_tier", lambda s, p, c: "T3" if any(s is m for m in made) else "T1")
    r = direct("luxury", _p("pocket_watch"), provider=FakeProvider([_watch()]), seed=11, duration=10)
    assert r.source.endswith("+floor") and any(r.script is m for m in made)


def test_a_valid_t2_llm_reply_does_not_bypass_a_t3_floor():
    """Review #1, no monkeypatching: a checker-valid but weak (T2) reply on a T3-floor subject is gated."""
    from engine.director.job import make_job
    weak = json.loads(open("engine/tests/fixtures/script_valid.json", encoding="utf-8").read())
    cat, p = Catalog.load(), _p("pocket_watch")
    r = direct("a nice product film for my brand of watches", p, provider=FakeProvider([weak] * 3), seed=0,
               duration=10, catalog=cat)
    need = floor_tier(make_job("", p, cat, seed=0, duration=10), p, cat)
    assert need == "T3" and script_tier(r.script, p, cat) == "T3"
    assert "+floor" in r.source or "+phase3" in r.source or r.source == "fallback"


def test_when_nothing_meets_the_floor_the_pin_keeping_default_is_delivered(monkeypatch):
    import engine.director.pipeline as pl
    sentinel = {}
    real = pl.floor_default
    monkeypatch.setattr(pl, "floor_default", lambda *a, **k: sentinel.setdefault("s", real(*a, **k)))
    monkeypatch.setattr(pl, "floor_tier", lambda *a: "T3")
    monkeypatch.setattr(pl, "script_tier", lambda s, p, c: "T3" if s is sentinel.get("s", (None,))[0] else "T1")
    r = direct("luxury", _p("pocket_watch"), provider=FakeProvider([_watch()]), seed=11, duration=10)
    assert r.script is sentinel["s"][0] and r.source.endswith("+phase3")
    assert "floor_phase3_default" in r.direction["flags"]
    assert r.script["grade"]["params"]["preset"] == "premium_dark"         # the 'luxury' pin survived


def test_real_pipeline_never_delivers_below_the_floor():
    """No monkeypatching: nine subjects x 2 seeds, refusing provider and a valid LLM reply."""
    from engine.director.baseline_phase3 import MODELS
    from engine.director.job import make_job
    cat = Catalog.load()
    for m in MODELS:
        p = _p(m)
        for seed in (0, 1):
            for prov in (FakeProvider(REFUSE * 3), FakeProvider([_watch()] * 3)):
                r = direct("", p, provider=prov, seed=seed, duration=10, catalog=cat)
                job = make_job("", p, cat, seed=seed, duration=10)
                assert _RANK[script_tier(r.script, p, cat)] >= _RANK[floor_tier(job, p, cat)], (m, seed)


def test_llm_script_with_unset_params_gets_layer_one_variation():
    a = direct("luxury", _p("pocket_watch"), provider=FakeProvider([_watch()]), seed=21, duration=10)
    b = direct("luxury", _p("pocket_watch"), provider=FakeProvider([_watch()]), seed=22, duration=10,
               like=a.script)
    if not _watch()["lighting"].get("params"):
        assert a.script["lighting"]["params"] != b.script["lighting"]["params"]


def test_memory_rotates_under_the_lock(tmp_path):
    mem = VarietyMemory(tmp_path)
    u = mem.issue_user_token()
    ids = [_run(s, memory=mem, user=u).direction["id"] for s in range(5)]
    assert len(set(ids)) == 5 and mem.recent(u, subject_key(_p("pocket_watch"))) == ids


def test_concurrent_jobs_same_user_and_subject_get_distinct_directions(tmp_path):
    mem, out = VarietyMemory(tmp_path), []
    u = mem.issue_user_token()
    ts = [threading.Thread(target=lambda s=s: out.append(_run(s, memory=mem, user=u).direction["id"]))
          for s in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(out) == 6 and len(set(out)) == 6
    assert len(mem.recent(u, subject_key(_p("pocket_watch")))) == 6


def test_less_like_this_is_remembered(tmp_path):
    mem = VarietyMemory(tmp_path)
    u = mem.issue_user_token()
    mood = _run(1, memory=mem, user=u).direction["axes"]["mood"]
    _run(2, memory=mem, user=u, avoid={"mood": [mood]})
    for s in range(3, 8):
        assert _run(s, memory=mem, user=u).direction["axes"]["mood"] != mood


def test_bad_user_or_subject_is_input_error_and_memory_failure_never_fails_the_job(tmp_path, monkeypatch):
    from engine.director.job import DirectorInputError
    mem = VarietyMemory(tmp_path)
    with pytest.raises(DirectorInputError):
        _run(1, memory=mem, user="alice@example.com")
    with pytest.raises(DirectorInputError):
        _run(1, memory=mem, user=mem.issue_user_token(), subject_id="../../etc")
    u = mem.issue_user_token()

    def disk_full(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(mem, "record", disk_full)
    r = _run(1, memory=mem, user=u)
    assert r.script and "memory_write_failed" in r.direction["flags"]


def test_memory_busy_fails_only_the_memory_step(tmp_path, monkeypatch):
    import contextlib
    mem = VarietyMemory(tmp_path)
    u = mem.issue_user_token()

    @contextlib.contextmanager
    def busy(*a, **k):
        raise MemoryBusy("busy")
        yield  # noqa: unreachable
    monkeypatch.setattr(mem, "locked", busy)
    r = _run(1, memory=mem, user=u)
    assert r.script and "memory_busy" in r.direction["flags"]
    assert any("history" in a for a in r.script["assumptions"])
    monkeypatch.undo()
    assert mem.recent(u, subject_key(_p("pocket_watch"))) == []           # nothing written without the lock


def test_result_reports_the_direction_and_replay_record():
    r = _run(1)
    assert set(r.direction) == {"id", "source", "axes", "pinned", "flags"}
    assert r.replay["schema"] == "valora.replay/1" and r.replay["script"] == r.script


def test_the_memory_lock_holds_no_fallback_builds(tmp_path, monkeypatch):
    """Viability is computed outside the lock; inside it only read -> pick (cache hits) -> record."""
    import contextlib

    import engine.director.floor as fl
    mem, inside, builds = VarietyMemory(tmp_path), [False], []
    u = mem.issue_user_token()
    real_locked, real_build = mem.locked, fl.build_fallback

    @contextlib.contextmanager
    def watched(*a, **k):
        with real_locked(*a, **k):
            inside[0] = True
            try:
                yield
            finally:
                inside[0] = False
    monkeypatch.setattr(mem, "locked", watched)
    monkeypatch.setattr(fl, "build_fallback", lambda *a, **k: (builds.append(inside[0]), real_build(*a, **k))[1])
    fl._VIABLE.clear()
    for s in range(3):
        _run(s, memory=mem, user=u, prompt="a 10 second clip")
    assert builds and not any(builds)
    assert len(mem.recent(u, subject_key(_p("pocket_watch")))) == 3
