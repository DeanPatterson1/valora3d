"""Paired tier regressions against the frozen phase-3 files (spec §9: no run is worse than phase 3).
The fallback cases are all T3, so the T2 references are what exercise a T2 -> T1 drop."""
import copy
import json

from engine.catalog import Catalog
from engine.director.baseline_phase3 import BASELINE, T2_REFS, regression_gate, tier_regressions
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from harness.director_eval import _profile, s_tier

REFS = json.loads(T2_REFS.read_text(encoding="utf-8"))
REPLY = json.loads(open(REFS["reply"], encoding="utf-8").read())


def _observe(case, cat, degrade=False):
    p = _profile(case["model"])
    r = direct(case["prompt"], p, provider=FakeProvider([copy.deepcopy(REPLY)] * 3), seed=case["seed"], catalog=cat)
    s = r.script
    if degrade:   # the T1 failure signature: a constant-speed turntable on every shot (TIERS T1-X1)
        s, tt = copy.deepcopy(s), {k: v["default"] for k, v in cat.get("camera", "turntable")["params"].items()}
        for sh in s["shots"]:
            sh["camera"] = {"id": "turntable", "params": dict(tt)}
    return {"model": case["model"], "prompt": case["prompt"], "seed": case["seed"], "tier": s_tier(s, p, cat)}


def test_t2_references_still_reproduce_and_pass_the_gate():
    cat = Catalog.load()
    observed = [_observe(c, cat) for c in REFS["cases"]]
    assert [o["tier"] for o in observed] == ["T2"] * len(REFS["cases"])
    assert regression_gate(observed, REFS["cases"]) == (True, [])


def test_a_real_t2_to_t1_drop_is_a_regression_and_fails_the_gate():
    cat, case = Catalog.load(), REFS["cases"][0]
    bad = _observe(case, cat, degrade=True)
    assert bad["tier"] == "T1"
    ok, reg = regression_gate([bad], REFS["cases"])
    assert not ok and reg == [(case["model"], case["prompt"], case["seed"], "T2", "T1")]


def test_pairing_is_per_case():
    frozen = [{"model": "m", "prompt": "", "seed": 0, "tier": "T2"}, {"model": "m", "prompt": "", "seed": 1, "tier": "T3"}]
    assert tier_regressions([{"model": "m", "prompt": "", "seed": 0, "tier": "T3"}], frozen) == []   # better: fine
    assert tier_regressions([{"model": "m", "prompt": "", "seed": 1, "tier": "T2"}], frozen) == [("m", "", 1, "T3", "T2")]
    assert tier_regressions([{"model": "x", "prompt": "", "seed": 0, "tier": "T1"}], frozen) == []   # unpaired
    t3 = json.loads(BASELINE.read_text(encoding="utf-8"))["cases"]
    assert regression_gate([{**t3[0], "tier": "T2"}], t3)[0] is False
