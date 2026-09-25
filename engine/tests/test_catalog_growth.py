"""Phase-5 growth contract: a director-selectable block outside the phase-1..4 set ships only with taste
rules that reference it, registered gate codes, eval prompts that exercise it (and an unsupported ask
where the block has a profile requirement, or a world requirement some catalog world fails), and a floor
test. golden stays null until the owner grades a render (spec §4.3); the harness reports ungraded blocks."""
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.director.taste import load_rules
from engine.gates import CODES
from engine.weather_rules import _needs_world

ROOT = Path(__file__).resolve().parents[2]
GROWTH = json.loads((ROOT / "engine" / "catalog_growth.json").read_text(encoding="utf-8"))
PROMPTS = {p["id"]: p for p in json.loads((ROOT / "harness" / "prompts" / "v1.json").read_text(encoding="utf-8"))["prompts"]}
KINDS = ("world", "lighting", "camera", "motion", "effect", "grade", "field")


def _selectable(cat):
    return {f"{k}/{b}" for k in KINDS for b in cat.selectable_ids(k)}


def _world_fails(req, world):
    """True when this world cannot host a block with physics.requiresWorld `req` (the checker's own rule)."""
    return bool(_needs_world(req, world))


def _needs_unsupported_prompt(m, cat):
    if m.get("requiresProfile"):
        return True
    req = (m.get("physics") or {}).get("requiresWorld")
    return bool(req) and any(_world_fails(req, cat.get("world", w)) for w in cat.ids("world"))


def test_baseline_is_the_phase4_selectable_set():
    assert GROWTH["schema"] == "valora.growth/1"
    assert GROWTH["baselineBlocks"] == sorted(set(GROWTH["baselineBlocks"]))
    assert not set(GROWTH["baselineBlocks"]) & set(GROWTH["blocks"])


def test_every_new_selectable_block_is_under_the_contract():
    cat = Catalog.load()
    new = _selectable(cat) - set(GROWTH["baselineBlocks"])
    assert not sorted(new - set(GROWTH["blocks"])), "add these to engine/catalog_growth.json"


@pytest.mark.parametrize("ref", sorted(GROWTH["blocks"]))
def test_contract_links_resolve(ref):
    cat, entry = Catalog.load(), GROWTH["blocks"][ref]
    kind, bid = ref.split("/")
    m = cat.get(kind, bid)
    assert m is not None, ref
    rules = {r["id"]: r for r in load_rules()}
    assert entry["taste"], f"{ref}: at least one taste rule"
    for rid in entry["taste"]:
        assert rid in rules and any(b.split(".")[0] == ref for b in rules[rid]["blocks"]), (ref, rid)
    assert entry["gates"] and all(g in CODES for g in entry["gates"]), (ref, entry["gates"])
    assert entry["prompts"] and all(p in PROMPTS for p in entry["prompts"]), (ref, entry["prompts"])
    assert any(ref in PROMPTS[p].get("exercises", []) for p in entry["prompts"]), ref
    if _needs_unsupported_prompt(m, cat):
        assert entry.get("unsupportedPrompt") in PROMPTS, f"{ref}: needs an unsupported-ask prompt"
    assert entry["floor"].startswith("engine/tests/") and "::" in entry["floor"]
    assert entry.get("golden") in (None,) or isinstance(entry["golden"], str)


def test_turntable_is_never_under_growth_or_selectable():
    cat = Catalog.load()
    assert "camera/turntable" not in GROWTH["blocks"] and "turntable" not in cat.selectable_ids("camera")
