"""Task 90: delivered recall, exercises coverage, the phase-5 physics prompts (refusing provider, offline)."""
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.director.llm import FakeProvider
from harness.director_eval import expected_delivered, load_prompt_set, run_director_eval

ROOT = Path(__file__).resolve().parents[2]
V1 = json.loads((ROOT / "harness" / "prompts" / "v1.json").read_text(encoding="utf-8"))["prompts"]


def _refuse(cid):
    return FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3)


def _flat(exp):
    return set(exp if isinstance(exp, list) else sum((v for v in (exp or {}).values()), []))


def test_expect_delivered_is_scored_as_recall(tmp_path):
    s = run_director_eval("v1", models=["sports_car"], prompt_ids=["parked_rain"], provider_factory=_refuse,
                          out_root=tmp_path, run_id="t")
    c = s["cases"][0]
    assert c["expectedDelivered"] == ["weather.rain"] and c["deliveredRecall"] == 1.0
    assert s["metrics"]["deliveredRecall"]["value"] == 1.0
    assert "weather" in c["direction"] and "wind" in c["direction"]
    assert "Delivered asks" in (tmp_path / "t" / "summary.md").read_text(encoding="utf-8")


def test_ungraded_growth_blocks_are_listed_per_run(tmp_path):
    s = run_director_eval("v1", models=["sports_car"], prompt_ids=["parked_rain", "snowy"], provider_factory=_refuse,
                          out_root=tmp_path, run_id="t")
    cases = {c["case"].split("__")[1]: c for c in s["cases"]}      # sports_car__<prompt id>__<run>
    # the owner graded rain on 2026-09-27 (realism round 16, catalog_growth.json golden); snow's golden is still null
    assert "effect/rain" not in cases["parked_rain"]["ungradedBlocks"]
    assert "effect/snow" in cases["snowy"]["ungradedBlocks"]


def test_expected_delivered_takes_per_profile_variants():
    cat = Catalog.load()
    from harness.director_eval import _profile
    case = {"id": "x", "prompt": "p", "expectDelivered": {"default": ["a"], "animated": ["b"]}}
    assert expected_delivered(case, _profile("pocket_watch"), cat) == ["a"]
    assert expected_delivered({"id": "y", "prompt": "p"}, _profile("pocket_watch"), cat) is None


def test_unsupported_and_delivered_never_overlap():
    for c in V1:
        assert not _flat(c.get("expectUnsupported")) & _flat(c.get("expectDelivered")), c["id"]


def test_every_growth_block_is_exercised_by_a_prompt():
    g = json.loads((ROOT / "engine" / "catalog_growth.json").read_text(encoding="utf-8"))
    ex = {b for c in V1 for b in c.get("exercises", [])}
    assert set(g["blocks"]) <= ex


PHYSICS = {  # BLOCKS §6 physics prompts -> (delivered, unsupported) in phase 5 (amendment 85/90: burnout = a drive)
    "a car parked in the rain": (["weather.rain"], []),
    "leaves blowing past the chair": ([], ["particles.leaves"]),
    "a tumbleweed rolls by the truck": ([], ["rigid.tumbleweed"]),
    "the can drips with condensation": ([], ["liquid.condensation"]),
    "liquid running down the can": ([], ["liquid.run_down"]),
    "the sneaker drops and bounces": (["motion.drop"], []),
    "smoke rolls around the car": ([], ["smoke.plume"]),
    "a silk sheet slides off the watch": ([], ["cloth.drape_reveal"]),
    "sparks fly": ([], ["particles.sparks"]),
    "confetti falls on the sofa": ([], ["particles.confetti"]),
    "windy": (["wind.breeze"], []),
    "ice-cold drink": ([], ["liquid.condensation"]),
    "burnout": (["motion.drive"], ["vehicle.tyre_smoke"]),
}


@pytest.mark.parametrize("prompt", sorted(PHYSICS))
def test_the_physics_prompts_are_present_with_phase5_expectations(prompt):
    case = next((c for c in V1 if c["prompt"].lower() == prompt), None)
    assert case is not None, prompt
    dl, un = PHYSICS[prompt]
    assert set(dl) <= _flat(case.get("expectDelivered")), case["id"]
    assert set(un) <= _flat(case.get("expectUnsupported")), case["id"]


def test_the_physics_prompts_score_full_recall_offline(tmp_path):
    """The refusing provider (fallback only): every physics prompt reports what it expects unsupported and
    delivers what it expects delivered."""
    ids = [c["id"] for c in V1 if c["prompt"].lower() in PHYSICS]
    s = run_director_eval("v1", prompt_ids=ids, models=["sports_car", "sneaker", "pocket_watch",
                                                        "mid_century_lounge_chair"],
                          provider_factory=_refuse, out_root=tmp_path, run_id="p")
    bad = [(c["case"], c.get("error") or (c["unsupported"], c["deliveredMissing"])) for c in s["cases"]
           if "error" in c or (c["unsupportedRecall"] not in (None, 1.0)) or (c["deliveredRecall"] not in (None, 1.0))]
    assert not bad
