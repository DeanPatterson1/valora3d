import copy
import json

from engine.catalog import Catalog
from engine.director.taste import STATS, load_rules, render_taste, validate_rules


def test_committed_rules_validate():
    assert validate_rules(load_rules(), Catalog.load()) == []


def test_bad_cite_block_and_placeholder_are_caught():
    rules = copy.deepcopy(load_rules())
    rules[0]["cites"] = ["X-Y99"]
    rules[1]["blocks"] = ["camera/moon"]
    rules[2]["text"] = "cuts every {stat:all.nope.median} s"
    rules[2]["fallbackText"] = None
    probs = validate_rules(rules, Catalog.load())
    assert any("X-Y99" in p for p in probs) and any("camera/moon" in p for p in probs)
    assert any("fallbackText" in p for p in probs)


def _stats(trusted, n):
    return {"records": n, "recordSetHash": "abc123def456", "families": {
        "all": {"shotsPer10s": {"n": n, "median": 4.37, "trusted": trusted},
                "cameraHeight": {"n": n, "shares": {"low": 0.4, "ground": 0.3, "eye": 0.3}, "trusted": trusted}},
        "vehicle": {"shotLenS": {"n": n, "median": 2.1, "trusted": trusted}}}}


def test_stats_are_quoted_only_when_trusted_and_big_enough():
    rules = load_rules()
    low = render_taste(rules, _stats(True, 3))
    untrusted = render_taste(rules, _stats(False, 50))
    good = render_taste(rules, _stats(True, 50))
    assert "4.37" not in low and "4.37" not in untrusted
    assert "4.37" in good and "n=50" in good and "low 40%" in good


def test_committed_stats_render_without_crashing():
    text = render_taste(load_rules(), json.loads(STATS.read_text(encoding="utf-8")))
    assert text.startswith("# 2. Taste guide") and "TG-01" in text


def test_untrusted_committed_stats_render_craft_only_wording():
    # Chunk 0 marks the shot-level stats untrusted: no corpus number may reach the rulebook.
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    text = render_taste(load_rules(), stats)
    for rule in load_rules():
        if "{stat:" in rule["text"]:
            assert rule["fallbackText"] in text
    assert "n=" not in text
