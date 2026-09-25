import json

import pytest

from engine.catalog import Catalog
from engine.director.axes import axis_values
from engine.director.baseline_phase3 import BASELINE, baseline_case
from engine.director.dice import candidates
from engine.director.direction import interim_direction
from engine.director.fallback import build_fallback
from engine.director.floor import (_RANK, cadence_ok, cadence_range, floor_tier, make_viable, phase3_default,
                                   script_tier)
from engine.director.job import make_job
from engine.tests.test_director_package import _p

CASES = json.loads(BASELINE.read_text(encoding="utf-8"))["cases"]


def _job(model, seed=2, prompt="a 10 second clip"):
    cat, p = Catalog.load(), _p(model)
    return make_job(prompt, p, cat, seed=seed), p, cat


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['model']}-{c['prompt'] or 'empty'}-{c['seed']}")
def test_phase3_default_still_reproduces_the_frozen_baseline(case):
    cat, p = Catalog.load(), _p(case["model"])
    job = make_job(case["prompt"], p, cat, seed=case["seed"], direction=interim_direction(case["seed"], p, cat))
    assert job.fmt["durationS"] == case["durationS"]   # make_job gains a duration argument in Task 44
    s = phase3_default(job, p, cat)
    assert (script_tier(s, p, cat), len(s["shots"]), s["direction"]["id"]) == \
           (case["tier"], case["shots"], case["directionId"])


def test_floor_is_met_by_the_phase3_default_by_definition():
    for m in ("pocket_watch", "sports_car", "cesium_man"):
        job, p, cat = _job(m)
        assert _RANK[script_tier(phase3_default(job, p, cat), p, cat)] >= _RANK[floor_tier(job, p, cat)]
        assert _RANK[floor_tier(job, p, cat)] <= _RANK["T3"]


def test_cadence_is_measured_from_the_shots():
    cat = Catalog.load()
    lo, hi = cadence_range("calm", 10, cat)
    s = {"format": {"durationS": 10}, "shots": [{}] * lo}
    assert cadence_ok(s, "calm", cat) and not cadence_ok({**s, "shots": [{}] * (hi + 1)}, "calm", cat)
    assert cadence_ok({"format": {"durationS": 5}, "shots": [{}] * 2}, "hype", cat)  # short plan: exempt


def test_viable_is_cached_across_jobs_and_checks_cadence(monkeypatch):
    import engine.director.floor as fl
    fl._VIABLE.clear()
    job, p, cat = _job("pocket_watch", seed=2)
    c = candidates(axis_values(p, cat, job.fmt))[0]
    v1 = make_viable(job, p, cat)
    first = v1(c)
    job2, _, _ = _job("pocket_watch", seed=77)
    assert make_viable(job2, p, cat)(c) == first and len(fl._VIABLE) == 1   # canonical seed: one entry
    fl._VIABLE.clear()
    monkeypatch.setattr(fl, "cadence_ok", lambda s, pace, catalog: False)
    assert make_viable(job, p, cat)(c) is False


def test_non_honoured_opener_is_not_viable(monkeypatch):
    import engine.director.floor as fl
    fl._VIABLE.clear()
    monkeypatch.setattr(fl, "opener_of", lambda s: "something_else")
    job, p, cat = _job("pocket_watch")
    assert make_viable(job, p, cat)(candidates(axis_values(p, cat, job.fmt))[0]) is False
    fl._VIABLE.clear()


def test_script_tier_matches_the_harness_definition_and_baseline_lookup():
    from harness.director_eval import s_tier
    job, p, cat = _job("pocket_watch")
    s = build_fallback(job, p, cat)
    assert script_tier(s, p, cat) == s_tier(s, p, cat)
    assert baseline_case("pocket_watch", "", 0)["tier"] in ("T1", "T2", "T3")
    assert baseline_case("pocket_watch", "", 999) is None
