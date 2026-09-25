"""Phase-5 growth contract: a director-selectable block outside the phase-1..4 set ships only with taste
rules that reference it, registered gate codes, eval prompts that exercise it (and an unsupported ask
where the block has a profile requirement, or a world requirement some catalog world fails), and a floor
test. golden stays null until the owner grades a render (spec §4.3); the harness reports ungraded blocks.

Every link is checked for meaning, not just existence (review of chunk 0):
- baselineBlocks must equal the frozen phase-4 set below, so growing it cannot exempt a block;
- a delivered prompt must name the block in `exercises` AND expect one of the block's capabilities that
  the vocabulary really reads in its text; an unsupported prompt must expect such a capability AND carry
  the subject (`models`) or world (`pins.world`) that blocks it by the checker's own rule;
- the floor must be a pytest node id pytest really collects, whose test proves the block is present,
  `check(...).ok` and `script_tier == "T3"`."""
import ast
import functools
import json
import subprocess
import sys
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.director.capabilities import detect
from engine.director.taste import load_rules
from engine.gates import CODES
from engine.tests.test_growth_floor import floor_outcome
from engine.weather_rules import _missing, _needs_world

ROOT = Path(__file__).resolve().parents[2]
GROWTH = json.loads((ROOT / "engine" / "catalog_growth.json").read_text(encoding="utf-8"))
PROMPTS = {p["id"]: p for p in json.loads((ROOT / "harness" / "prompts" / "v1.json").read_text(encoding="utf-8"))["prompts"]}
KINDS = ("world", "lighting", "camera", "motion", "effect", "grade", "field")

# The director-selectable set at Task 51 (phase 4 end), frozen here independently of the JSON.
PHASE4_SELECTABLE = (
    "camera/arc_orbit", "camera/low_hero_push", "camera/macro_detail", "effect/haze_volume", "grade/mood_grade",
    "grade/neutral_film", "lighting/reflection_rig", "lighting/softbox_three_point", "motion/play_clip",
    "motion/static", "world/studio_cyc",
)


def _selectable(cat):
    return {f"{k}/{b}" for k in KINDS for b in cat.selectable_ids(k)}


def _world_fails(req, world):
    """True when this world cannot host a block with physics.requiresWorld `req` (the checker's own rule)."""
    return bool(_needs_world(req, world))


def _needs_unsupported_prompt(m, cat):
    if m.get("requiresProfile") or m.get("requiresMotion"):     # requiresMotion: a still subject blocks it (Task 84)
        return True
    req = (m.get("physics") or {}).get("requiresWorld")
    return bool(req) and any(_world_fails(req, cat.get("world", w)) for w in cat.ids("world"))


def baseline_problems(baseline, blocks):
    out = []
    if list(baseline) != list(PHASE4_SELECTABLE):
        out.append(f"baselineBlocks differs from the frozen phase-4 set: +{sorted(set(baseline) - set(PHASE4_SELECTABLE))}"
                   f" -{sorted(set(PHASE4_SELECTABLE) - set(baseline))}")
    if set(baseline) & set(blocks):
        out.append("a growth block is also in the baseline")
    return out


def _detected(prompt):
    return {a["capability"] for a in detect(prompt.get("prompt", ""))}


def delivered_problems(ref, m, prompt_ids, prompts):
    """Every linked prompt names the block in `exercises`; at least one is a real delivered ask."""
    out = [f"{pid}: unknown prompt" for pid in prompt_ids if pid not in prompts]
    linked = [prompts[pid] for pid in prompt_ids if pid in prompts]
    out += [f"{p['id']}: does not list {ref} in exercises" for p in linked if ref not in p.get("exercises", [])]
    caps = set(m.get("capabilities", []))
    if not any(set(p.get("expectDelivered", [])) & caps & _detected(p) for p in linked):
        out.append(f"{ref}: no linked prompt expects one of {sorted(caps)} that its own text asks for")
    return out


def unsupported_problems(ref, m, pid, prompts, cat, profile_of):
    p = prompts.get(pid)
    if p is None:
        return [f"{ref}: unsupportedPrompt {pid!r} is not a prompt"]
    out = []
    exp = p.get("expectUnsupported") or []
    exp = set(exp if isinstance(exp, list) else [c for v in exp.values() for c in v])
    if not exp & set(m.get("capabilities", [])) & _detected(p):
        out.append(f"{pid}: expects none of {ref}'s capabilities that its text asks for")
    req = (m.get("physics") or {}).get("requiresWorld") or {}
    world = (p.get("pins") or {}).get("world")
    world_blocks = bool(req) and world is not None and _world_fails(req, cat.get("world", world) or {})
    profile_blocks = bool(m.get("requiresProfile")) and any(_missing(profile_of(x), m) for x in p.get("models", []))
    motion_blocks = bool(m.get("requiresMotion")) and not _asks_motion(p, m, cat)
    if not (world_blocks or profile_blocks or motion_blocks):
        out.append(f"{pid}: carries no subject or world that blocks {ref}")
    return out


def _asks_motion(p, m, cat):
    """The prompt asks for (or pins) a motion that gives the subject what `m.requiresMotion` needs (a tracking
    camera needs a subject that translates): then a still subject does not block it."""
    need = set(m.get("requiresMotion") or [])
    pinned = (p.get("pins") or {}).get("motion")
    motions = [pinned] if pinned else [b for b in cat.ids("motion")
                                       if set(cat.get("motion", b).get("capabilities", [])) & _detected(p)]
    return any(need <= {k for k, v in (cat.get("motion", b) or {}).get("subjectMotion", {}).items() if v}
               for b in motions)


FLOOR_TEST = "engine/tests/test_growth_floor.py::test_block_reaches_the_floor"
SYNTHETIC = ROOT / "engine" / "tests" / "fixtures" / "synthetic_profiles"


def profile_of(name):
    """An eval model's profile, or a TEST ONLY synthetic one (fixtures/synthetic_profiles: e.g. bare_tube, a
    watch with no up-facing surface, for a requiresProfile block that every eval model satisfies)."""
    from engine.profile import SubjectProfile
    from engine.tests.test_director_package import _p
    f = SYNTHETIC / f"{name}.json"
    return SubjectProfile.from_dict(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else _p(name)


@functools.lru_cache(maxsize=None)
def _collected(rel):
    """Node ids pytest itself collects from one test file (a subprocess, so this run's selection is moot)."""
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", rel],
                       cwd=ROOT, capture_output=True, text=True)
    return frozenset(line.strip() for line in r.stdout.splitlines() if "::" in line)


def floor_problems(ref, node):
    if not (isinstance(node, str) and node.startswith("engine/tests/") and "::" in node):
        return [f"{ref}: floor {node!r} is not an engine/tests node id"]
    rel, name = node.split("::", 1)
    if not (ROOT / rel).exists() or node not in _collected(rel):
        return [f"{ref}: pytest does not collect {node}"]
    base, _, param = name.partition("[")
    fn = next((n for n in ast.walk(ast.parse((ROOT / rel).read_text(encoding="utf-8")))
               if isinstance(n, ast.FunctionDef) and n.name == base), None)
    src = ast.unparse(fn) if fn else ""
    out = [f"{ref}: floor test lacks {need}" for need in ("check(", ".ok", "script_tier(", "'T3'") if need not in src]
    if param.rstrip("]") != ref and ref.split("/")[1] not in src:
        out.append(f"{ref}: floor test does not name the block (param id or source)")
    if "_has_block" not in src and ref.split("/")[1] not in src:
        out.append(f"{ref}: floor test does not assert the block is present")
    return out


def test_baseline_is_the_frozen_phase4_selectable_set():
    assert GROWTH["schema"] == "valora.growth/1"
    assert baseline_problems(GROWTH["baselineBlocks"], GROWTH["blocks"]) == []


def test_growing_the_baseline_is_caught():
    grown = sorted(PHASE4_SELECTABLE + ("world/rain_courtyard",))
    assert baseline_problems(grown, {}) and baseline_problems(PHASE4_SELECTABLE[1:], {})
    assert baseline_problems(PHASE4_SELECTABLE, {"camera/arc_orbit": {}})


def test_every_new_selectable_block_is_under_the_contract():
    cat = Catalog.load()
    new = _selectable(cat) - set(PHASE4_SELECTABLE)
    assert not sorted(new - set(GROWTH["blocks"])), "add these to engine/catalog_growth.json"


@pytest.mark.parametrize("ref", sorted(GROWTH["blocks"]))
def test_contract_links_resolve(ref):
    from engine.tests.test_director_package import _p
    cat, entry = Catalog.load(), GROWTH["blocks"][ref]
    kind, bid = ref.split("/")
    m = cat.get(kind, bid)
    assert m is not None, ref
    rules = {r["id"]: r for r in load_rules()}
    assert entry["taste"], f"{ref}: at least one taste rule"
    for rid in entry["taste"]:
        assert rid in rules and any(b.split(".")[0] == ref for b in rules[rid]["blocks"]), (ref, rid)
    assert entry["gates"] and all(g in CODES for g in entry["gates"]), (ref, entry["gates"])
    assert delivered_problems(ref, m, entry["prompts"], PROMPTS) == []
    if _needs_unsupported_prompt(m, cat) or "unsupportedPrompt" in entry:
        assert unsupported_problems(ref, m, entry.get("unsupportedPrompt"), PROMPTS, cat, profile_of) == []
    assert floor_problems(ref, entry["floor"]) == []
    assert entry["floor"] == f"{FLOOR_TEST}[{ref}]", "the floor is the central parametrized floor case"
    assert floor_outcome(ref) == []                                   # executed here, not read as tokens
    assert entry.get("golden") in (None,) or isinstance(entry["golden"], str)


# --- negative fixtures: the validators reject what the review showed slipping through ---------------------

WIND = {"capabilities": ["wind.breeze", "wind.strong"]}
FOG = {"capabilities": ["atmosphere.fog"], "physics": {"requiresWorld": {"outdoor": True}}}
ROLL = {"capabilities": ["motion.roll"], "requiresProfile": ["roundish"]}


def test_unrelated_or_mislabelled_delivered_prompts_are_rejected():
    ps = {"empty": {"id": "empty", "prompt": "", "exercises": ["field/wind"], "expectDelivered": ["wind.breeze"]},
          "cool": {"id": "cool", "prompt": "make it look cool", "exercises": ["field/wind"]},
          "wrongcap": {"id": "wrongcap", "prompt": "windy", "exercises": ["field/wind"], "expectDelivered": ["weather.rain"]},
          "unlabelled": {"id": "unlabelled", "prompt": "windy", "expectDelivered": ["wind.breeze"]},
          "ok": {"id": "ok", "prompt": "windy", "exercises": ["field/wind"], "expectDelivered": ["wind.breeze"]}}
    for ids in (["empty"], ["cool"], ["wrongcap"], ["unlabelled"], ["ok", "unlabelled"], ["missing"]):
        assert delivered_problems("field/wind", WIND, ids, ps), ids
    assert delivered_problems("field/wind", WIND, ["ok"], ps) == []


def test_unrelated_unsupported_prompts_are_rejected():
    cat = Catalog.load()
    studio = next(w for w in cat.ids("world") if not cat.get("world", w).get("outdoor"))
    ps = {"empty": {"id": "empty", "prompt": ""},
          "nocond": {"id": "nocond", "prompt": "foggy", "expectUnsupported": ["atmosphere.fog"]},
          "wrongcap": {"id": "wrongcap", "prompt": "foggy", "expectUnsupported": ["weather.rain"],
                       "pins": {"world": studio}},
          "ok": {"id": "ok", "prompt": "foggy", "expectUnsupported": ["atmosphere.fog"], "pins": {"world": studio}}}
    for pid in ("empty", "nocond", "wrongcap", "absent"):
        assert unsupported_problems("effect/x", FOG, pid, ps, cat, lambda _: None), pid
    if "atmosphere.fog" in {a["capability"] for a in detect("foggy")}:
        assert unsupported_problems("effect/x", FOG, "ok", ps, cat, lambda _: None) == []


def test_profile_blocked_unsupported_prompt_needs_a_blocking_model():
    from types import SimpleNamespace
    cat = Catalog.load()
    ps = {"nomodel": {"id": "nomodel", "prompt": "roll it", "expectUnsupported": ["motion.roll"]},
          "fits": {"id": "fits", "prompt": "roll it", "expectUnsupported": ["motion.roll"], "models": ["can"]}}
    fits = lambda _: SimpleNamespace(roundish=True)        # noqa: E731  every model has the fact
    assert unsupported_problems("motion/x", ROLL, "nomodel", ps, cat, fits)
    assert any("blocks" in s for s in unsupported_problems("motion/x", ROLL, "fits", ps, cat, fits))


def test_floor_links_must_resolve_to_a_real_floor_test():
    assert floor_problems("field/wind", "engine/tests/missing.py::test_nonexistent")
    assert floor_problems("field/wind", "engine/tests/test_growth_floor.py::test_nonexistent")
    assert floor_problems("field/wind", "engine/tests/test_growth_floor.py::test_block_reaches_the_floor[effect/zz]")
    # a real test that never checks ok / T3 is not a floor
    assert floor_problems("field/wind", "engine/tests/test_director_wind.py::test_llm_wind_survives_sanitize_and_is_pinned")
    assert floor_problems("field/wind", "harness/tests/test_budget.py::test_budget_reserves_and_never_refunds")
    assert floor_problems("field/wind", "engine/tests/test_growth_floor.py::test_block_reaches_the_floor[field/wind]") == []


def test_the_central_floor_rejects_a_dropped_block_an_invalid_script_a_low_tier_and_no_fixture():
    from engine.tests.test_growth_floor import FLOORS
    ok_make, model = FLOORS["effect/rain"]

    def variant(edit):
        def make():
            s = ok_make()
            edit(s)
            return s
        return {"effect/rain": (make, model)}

    assert floor_outcome("effect/rain", {"effect/rain": (ok_make, model)}) == []
    dropped = variant(lambda s: s.update(effects=[e for e in s["effects"] if e["id"] != "rain"]))
    assert any("dropped" in x for x in floor_outcome("effect/rain", dropped))
    studio = variant(lambda s: s.update(world={"id": "studio_cyc", "params": {}}))       # rain needs outdoors
    assert any("check not ok" in x for x in floor_outcome("effect/rain", studio))
    one_shot = variant(lambda s: s.update(shots=s["shots"][:1]))                          # T2 at script level
    assert any("T3" in x for x in floor_outcome("effect/rain", one_shot))
    assert floor_outcome("effect/zz_missing", {})


def test_turntable_is_never_under_growth_or_selectable():
    cat = Catalog.load()
    assert "camera/turntable" not in GROWTH["blocks"] and "turntable" not in cat.selectable_ids("camera")


def test_motion_blocked_unsupported_prompt_needs_a_still_subject():
    """A camera that needs a moving subject (requiresMotion) is blocked by a prompt that asks for no travelling
    motion ('tracking shot of the parked watch'), never by one that asks the subject to drive."""
    cat = Catalog.load()
    TRACK = {"capabilities": ["camera.tracking"], "requiresMotion": ["translates"]}
    ps = {"still": {"id": "still", "prompt": "tracking shot of the parked watch", "expectUnsupported": ["camera.tracking"]},
          "moving": {"id": "moving", "prompt": "tracking shot of the car driving", "expectUnsupported": ["camera.tracking"]}}
    assert _needs_unsupported_prompt(TRACK, cat)
    assert unsupported_problems("camera/x", TRACK, "still", ps, cat, lambda _: None) == []
    assert any("blocks" in x for x in unsupported_problems("camera/x", TRACK, "moving", ps, cat, lambda _: None))
