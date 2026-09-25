import json

import pytest

from engine.director.baseline_phase3 import (BASELINE, MODELS, PINNED_REV, PROMPTS, SEEDS, T2_MODELS, T2_PROMPTS,
                                             T2_REFS, T2_SEEDS, content_sha, main, profile_key)

# Content hashes of the frozen files. Any edit to a fixture fails here; a deliberate re-freeze (owner's OK)
# updates the hash in the same commit.
TIERS_SHA = "ee2ca034359173b35db03afaa10bfe3665198c0fa606842c57f5fa01791db63b"
T2_REFS_SHA = "304b5e13765e509a9ce95d1e0af9c601f5cdc633935e08f64a2c312d509ba454"


def _doc(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_baseline_is_frozen_and_complete():
    doc = _doc(BASELINE)
    assert doc["schema"] == "valora.baseline/1" and doc["frozenAt"] == PINNED_REV
    assert len(doc["cases"]) == 90 == len(MODELS) * len(PROMPTS) * len(SEEDS)
    keys = [(c["model"], c["prompt"], c["seed"]) for c in doc["cases"]]
    assert len(set(keys)) == len(keys), "duplicate cases"
    assert set(keys) == {(m, p, s) for m in MODELS for p in PROMPTS for s in SEEDS}
    assert all(c["tier"] in ("T1", "T2", "T3") and c["shots"] >= 2 for c in doc["cases"])


def test_frozen_files_are_unchanged():
    assert content_sha(_doc(BASELINE)) == TIERS_SHA
    assert content_sha(_doc(T2_REFS)) == T2_REFS_SHA


def test_t2_references_are_genuine_t2_from_the_pinned_revision():
    doc = _doc(T2_REFS)
    assert doc["frozenAt"] == PINNED_REV and doc["provider"] == "weak_reply"
    keys = [(c["model"], c["prompt"], c["seed"]) for c in doc["cases"]]
    assert len(set(keys)) == len(keys) == len(T2_MODELS) * len(T2_PROMPTS) * len(T2_SEEDS)
    assert {c["tier"] for c in doc["cases"]} == {"T2"} and {c["source"] for c in doc["cases"]} == {"llm"}


def test_generator_refuses_to_overwrite():
    with pytest.raises(SystemExit):
        main([])            # without --force an existing baseline is never regenerated
    with pytest.raises(SystemExit):
        main(["--which", "t2refs"])


def test_generator_refuses_outside_the_pinned_revision(tmp_path, monkeypatch):
    """Without --rev it only builds when HEAD is the pinned phase-3 revision with a clean tracked tree."""
    import engine.director.baseline_phase3 as b
    out = tmp_path / "x.json"
    monkeypatch.setattr(b, "_git", lambda *a, **k: "0" * 40 if a[0] == "rev-parse" else "")
    with pytest.raises(SystemExit, match="pinned phase-3 revision"):
        main(["--out", str(out)])
    monkeypatch.setattr(b, "_git", lambda *a, **k: PINNED_REV if a[0] == "rev-parse" else " M engine/x.py")
    with pytest.raises(SystemExit, match="uncommitted"):
        main(["--out", str(out)])
    assert not out.exists()


def test_profile_key_is_stable():
    from engine.tests.test_director_package import _p
    assert profile_key(_p("pocket_watch")) == profile_key(_p("pocket_watch"))
