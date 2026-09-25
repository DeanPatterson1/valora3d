import json

from engine.director.baseline_phase3 import BASELINE, MODELS, PROMPTS, SEEDS, profile_key


def test_baseline_is_frozen_and_complete():
    doc = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert doc["schema"] == "valora.baseline/1" and len(doc["frozenAt"]) >= 7
    keys = {(c["model"], c["prompt"], c["seed"]) for c in doc["cases"]}
    assert keys == {(m, p, s) for m in MODELS for p in PROMPTS for s in SEEDS}
    assert all(c["tier"] in ("T1", "T2", "T3") and c["shots"] >= 2 for c in doc["cases"])


def test_generator_refuses_to_overwrite():
    import pytest
    from engine.director.baseline_phase3 import main
    with pytest.raises(SystemExit):
        main([])            # without --force an existing baseline is never regenerated


def test_profile_key_is_stable():
    from engine.tests.test_director_package import _p
    assert profile_key(_p("pocket_watch")) == profile_key(_p("pocket_watch"))
