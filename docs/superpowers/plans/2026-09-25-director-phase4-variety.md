# Director Layer Phase 4 — Variety: Dice, Variety Memory, "More Like This", Variety Score

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The same model and prompt, run twice, give two clearly different videos (spec §1 success
criterion 2). No run is ever worse than the phase-3 default for the same case. Every delivered script
can be replayed exactly. The harness measures all of this.

**Revision 2 (2026-09-24, after independent review + coordinator decisions):** replay re-uses the saved
checked script and never calls the provider; the quality floor gates the FINAL script against a frozen
phase-3 baseline fixture; rotation runs over the VIABLE pool (unseen first); pins cover world and opener
too and survive every fallback; pace is enforced by measured cut cadence; layer 1 is real (seeded detail
params); memory stores only catalog-validated ids under issued random user tokens with a per
user+subject lock; `like`/`less-like` are validated with an explicit incompatibility error; the render
budget is TOTAL ≤ 3 frames per invocation, enforced in code; the harness reports paired tier regressions.
`macro_detail` is no longer an opener: the sequence checker requires a full-framing hook
(`engine/sequence.py` `seq_bad_hook`).

**Architecture:**

- **The dice are deterministic code (spec §3 stage 2), not the LLM.** `engine/director/dice.py` rolls a
  direction over seven axes: world, mood, tone, pace, opener, weather, wind. Values come from the catalog
  (worlds, grade presets, selectable full-framing hook cameras) intersected with
  `engine/director/dice.json`, so the dice cannot pick a block the menu does not offer. A roll is a pure
  function of (seed, pins, history snapshot, avoid list, viability).
- **Spec §6 layers.** Layer 1, details: `details.py` adds seeded, in-range offsets to a whitelist of
  look params the script left unset (lighting key angle and colour temperature, floor gloss, haze).
  The pipeline applies them to LLM and fallback scripts alike, so the lighting and world builders get
  seed-driven variation through their params, and the script still fully describes the render (replay
  and farm consistency). Layer 2, direction: the dice. Layer 3, variety memory: a file store per
  (issued user token, subject) that keeps catalog-validated direction ids and dislikes. Rotation is
  computed against the **viable pool**: never-used viable directions come first (weighted random),
  then used ones least-recently-used first. Every eligible direction is used before any repeat.
- **An explicit request beats the dice, everywhere.** `pins.py` reads world, mood, tone, pace and
  opener phrases (only values the catalog supports) and is negation-aware. Pins survive dice
  exhaustion, the interim fallback, floor substitution and "more like this". Adherence (`adherence.py`):
  - On vague prompts the rolled direction is enforced. Mood is enforced even by swapping
    `neutral_film` for `mood_grade`. Tone is set in place. Pace is set and then validated by the
    measured cut count (`shotsPer10s`). World, opener and cadence mismatches go back to the LLM
    through the repair loop.
  - On long prompts only pinned axes are enforced; everything else is measured drift (`info`).
- **Quality floor (novelty never costs quality).** A direction is viable for a subject only when its
  safe fallback passes the checker, keeps the opener, has a measured cut cadence inside its pace's
  range, and reaches the floor tier on the script-level [S] items. The floor is
  `min(T3, the best tier the FROZEN phase-3 baseline reached for this subject)`
  (`engine/director/baseline/phase3_tiers.json`, frozen in Task 34 before any phase-4 code). For
  subjects not in the fixture, it is the live interim-direction tier. The pipeline also gates the
  **final** script: an LLM script below the floor is replaced by the direction's qualifying fallback.
- **Replay = the saved checked script + replay metadata** (`valora.replay/1`: script, seed,
  direction with pins and flags, format, assumptions, prompt, markers, rulebook version). `replay()`
  re-checks the saved script against today's catalog and returns it byte-identical. It never calls the
  provider (providers have no seed control).
- **"More like this" / "less like this".** `like` keeps a direction and its duration with a new seed,
  so only layer 1 changes. `less-like` / `avoid` excludes values and is stored as a dislike. Both are
  validated against the current subject and catalog (and `like` against the floor). An incompatible
  request raises `DirectionIncompatible`, which the CLI shows as exit 5 with a plain reason.
- **Harness variety score (spec §9).** `py -m harness variety`: N runs per model × prompt. It
  reports direction distance, script distance, exact repeats, near-duplicates, catalog honesty
  (computed with the group's own pins, format and viability), and **paired tier regressions** against
  a no-dice run of the same case (must be 0). `--hold-direction` proves layer 1. Frame difference is
  opt-in and capped at a TOTAL of 3 rendered frames per invocation, enforced in code.

**Ownership.** The LLM never writes `realism`, `wind` or any `field`. The pipeline does
(`sanitize.OWNED`, and `realism_defaults` in sanitize/fallback), and those writes are expected. Task
50's ownership test checks the LLM-side rule: a reply that contains them is overwritten or dropped, and
the final `realism` equals `realism_defaults(profile, catalog)`. The weather and wind axes exist only
so memory records them from day one (`research/physics/PHASING.md` §2 Phase 4). Only `dry` and `calm`
are rollable, and neither is ever written into a script. `turntable` is a harness negative control:
it is never a dice value or an opener, and a test proves that.

**Tech Stack:** Python 3.12 dev (engine stays stdlib-only at import time, runs in Blender 3.11 too).
pytest 8. Harness keeps numpy + Pillow (frame distance). No new dependencies. No network.

**Spec:** `docs/superpowers/specs/2026-09-24-director-layer-design.md` §2/§2a (D3, D4, D5, tiers), §3
(dice = stage 2, variety not from the LLM), §4.2 (`seed`, `direction`, `assumptions`), §5 (the worked
example: "excluding this user's last 5 directions"), §6 (uniqueness, the three layers, rules), §9
(variety score), §10 step 4, §11 (risk: "LLM output converges on one safe look").
`research/physics/PHASING.md` §2 Phase 4 (weather/wind axes). Previous plans (style and what exists):
`docs/superpowers/plans/2026-09-25-director-phase3-director.md` (Task 16 interim direction, Task 23
fallback, Task 31 eval) and `docs/superpowers/plans/2026-09-25-phase3-5-realism-defaults.md`.

**Task numbering** continues after phase 3's highest task (Task 33): this plan uses **Tasks 34–50** (plus 40a).

**Conventions (same as phases 1–3½):**

- Run every command from the repo root `C:\Users\deand\Projects\rendering`, on branch `renderer/director`.
- Use `py`, never bare `python`.
- Fast loop: `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"`.
  Record the count in Task 34.
- **No live API calls.** There is no `ANTHROPIC_API_KEY` yet. Every director test uses `FakeProvider`
  or the refusing provider, which forces the fallback. A `live` test is written only where noted and
  stays skipped.
- **Render budget: TOTAL ≤ 3 frames per invocation, enforced in code** (`harness/variety.py`
  `MAX_FRAMES_TOTAL`, which raises before exceeding it). Rendering needs the owner's OK first (they game
  on this PC). Only Task 49 Step 6 renders anything: 3 runs × 1 frame.
- **Phase-3 names are moving (Chunk 4 fixes are in flight).** Before you reference `play_clip_ref`,
  `rest_animation` or a motion checker code (`motion_needs_profile` or its older name), run
  `py -c "import inspect, engine.director.capabilities as c; print(inspect.signature(c.play_clip_ref))"`
  and search the tree with the Grep tool. This plan never calls them directly: keep their existing call
  sites in `fallback.py` / `sanitize.py` untouched, and never assert a motion checker code name in a
  phase-4 test.
- **Verification commands are PowerShell-safe.** Use `py` scripts or pytest, never `grep`, `sed` or
  `head` pipelines.
- **Shared working tree.** Other agents commit here at the same time. Before every commit, run
  `git diff --cached --name-only` and stage **only** the files the task names, with
  `git commit -m "..." -- <paths>`. Never `git stash`, never `git add -A`, never rewrite a whole file
  another lane edits. **Re-read before you edit:** `job.py`, `pipeline.py`, `fallback.py`,
  `sanitize.py`, `request.py`, `rulebook.py`, `rulebook.txt`, `engine/__main__.py` and
  `harness/director_eval.py` are live in other lanes. The code blocks below say *what to add*,
  anchored on function and constant names, never on line numbers.
- Each commit message ends with the two attribution lines given in the session.
- Codex is unavailable until 2026-09-29. Delegate to Opus subagents (`model: "opus"`).
- Every number marked (eng) is an engineering guess. It goes in the calibration register (Task 50).

---

## File structure

| File | Status | Responsibility |
|---|---|---|
| `engine/director/baseline_phase3.py` + `engine/director/baseline/phase3_tiers.json` | create (Task 34, before any phase-4 code) | The FROZEN phase-3 baseline: fallback tier, direction, shot count per (eval subject, prompt, seed). The floor and the harness compare against it |
| `engine/director/dice.json` | create | Dice data: tone-by-mood, pace by family, openers (full-framing hook cameras), durations, weather/wind, pin phrases (world, mood, tone, pace, opener), detail params (layer 1), axis weights, (eng) thresholds |
| `engine/director/direction.py` | modify | `Direction` gains `world`, `opener`, `weather`, `wind`, `pinned`. `AXES`, `make_id`, `parse_id`, `direction_of`, `Direction.from_script`. `interim_direction` is unchanged |
| `engine/director/axes.py` | create | `axis_values(profile, catalog, fmt)` from catalog ∩ dice.json, `compatible`, `validate_axes`, `opener_of(script)` |
| `engine/director/pins.py` | create | `read_direction_pins(prompt)` for world, mood, tone, pace and opener (negation-aware) |
| `engine/director/distance.py` | create | `direction_distance`, `script_distance`, `near_duplicate` |
| `engine/director/dice.py` | create | `candidates`, `roll` (viable-pool rotation: unseen first, then LRU; pins; avoid; near-dup penalty), `roll_duration` |
| `engine/director/fallback.py` | modify | honours `direction.opener` and `direction.world` (existing `_plan(..., n_markers)` / `_script(..., skip)` arguments kept); applies layer-1 details |
| `engine/director/details.py` | create | `vary_details(script, seed, catalog)`: layer 1, seeded in-range look params the script left unset |
| `engine/director/floor.py` | create | `script_tier`, `cadence_range`, `cadence_ok`, `floor_tier` (frozen baseline), `make_viable` |
| `engine/director/memory.py` | create | `VarietyMemory`: issued random user tokens, catalog-validated ids only, per user+subject lock, atomic writes, caps, `forget` |
| `engine/director/variety.py` | create | `subject_key`, `DirectionIncompatible`, `choose_direction` (like → dice → interim+pins), `replay_record`, `replay`, `reachable` |
| `engine/director/job.py` | modify | `make_job(..., like, avoid, history, duration)`: duration order pin > explicit > liked > rolled; direction from `choose_direction` |
| `engine/director/intent.py` | modify | `make_format(pins, seed, duration=None)` |
| `engine/director/adherence.py` | create | `drift`, `enforce_direction` (grade swap, pace + cadence, tone; world/opener/cadence → repair) |
| `engine/director/request.py`, `rulebook.py`, `rulebook/rulebook.txt` | modify | Direction card gains `world` + `opener`. Default text updated. Rulebook regenerated |
| `engine/director/pipeline.py` | modify | locked memory read–roll–record, `like`/`avoid`/`user`/`subject_id`/`duration`, adherence, details, final-script floor gate, `DirectorResult.direction` + `.replay` |
| `engine/__main__.py` | modify | `direct --user --new-user --subject-id --memory-dir --like --less-like --avoid --out-replay`, `replay`, `variety-report` |
| `harness/variety.py` | create | Variety score runner, paired tier regressions, `--hold-direction`, `frame_distance`, render budget |
| `harness/__main__.py` | modify | `py -m harness variety ...` |
| `.gitignore` | modify | `var/` (variety memory lives there locally) |
| Tests | create | `engine/tests/test_director_{baseline,direction_v2,axes,pins,distance,dice,fallback_opener,details,floor,memory,variety,adherence,replay,ownership}.py`, `engine/tests/test_cli_variety.py`, `harness/tests/test_variety.py` |
---

## What grew from the seed

The owner's seed was "dice, variety memory, 'more like this', variety score". This plan expands it to:

1. **More axes than mood/pace/tone:** world, camera language (opener), weather and wind (recorded now,
   rollable in phase 5), and duration (8/10/12 s, the phase-3 promise "phase 4 varies duration").
2. **The user's words beat the dice everywhere:** world, mood, tone, pace and opener pins,
   negation-aware, first mention wins. They survive exhaustion, the fallback and floor substitution.
3. **"Less like this":** per-roll excludes plus stored dislikes, validated against the catalog. They
   relax gracefully and never leave an empty set.
4. **Exact replay:** the saved checked script plus its metadata, re-checked, with no provider call.
5. **A quality floor on novelty, and on the final script:** it is measured against a FROZEN phase-3
   baseline, and the harness counts paired tier regressions per case (must be 0).
6. **Real direction enforcement on vague prompts:** the grade swap, pace checked by measured cut
   cadence, and world/opener drift sent back to the LLM through repair (spec §11 "safe look" risk).
7. **Layer 1 made real:** seeded in-range detail params reach the lighting and world builders, proven
   with the direction and duration held constant (`--hold-direction`).
8. **Near-duplicate detection:** script distance plus a near-duplicate flag and a soft penalty on
   close directions.
9. **Catalog-size honesty:** viable direction counts per subject with the prompt's own pins, plus
   single-valued axes. Spec §6's "honest limit" becomes a number.
10. **Full rotation before any repeat:** computed over the viable pool.
11. **Privacy- and race-safe memory:** random issued user tokens, catalog-validated ids only (no free
    text), a per user+subject lock around read–roll–record, bounded files, `forget(user)`, and a
    failed write never fails a job.
12. **Rare-but-good kept:** a weight floor keeps corpus-rare values rollable, and `noir` stays
    pin-only.
13. **Frame-level variety, opt-in:** a hard total of 3 frames per invocation.

---

## Chunk 0: Gate and baseline

### Task 34: Gate, test baseline, and the FROZEN phase-3 quality baseline

This task runs **before any phase-4 code lands**. The baseline fixture is what "never worse than phase
3" is measured against, so it must be made with phase-3 code.

**Files:**
- Modify: `.gitignore`
- Create: `engine/director/baseline_phase3.py`, `engine/director/baseline/phase3_tiers.json` (generated)
- Test: `engine/tests/test_director_baseline.py`

- [ ] **Step 1: Check the phase-3 contract is at HEAD.** Create
  `C:\Users\deand\AppData\Local\Temp\p4_gate.py` with:

```python
import inspect
from engine.director.direction import Direction, interim_direction   # noqa: F401
from engine.director.job import make_job                              # noqa: F401
from engine.director.pipeline import direct                           # noqa: F401
from engine.director.fallback import build_fallback, slot_camera, _plan, _script
print("_plan", inspect.signature(_plan))
print("_script", inspect.signature(_script))
print("ok")
```

Run: `py C:\Users\deand\AppData\Local\Temp\p4_gate.py`. Expected: two signatures, then `ok`.
Write both signatures down: Task 40 appends arguments **after** them. If the import fails, stop and
report that phase 3 has not landed.

- [ ] **Step 2: Record the test baseline.** Run
  `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"` and write the
  count into the Task 50 register. If something is already red, note it and leave it alone: it belongs
  to another lane.

- [ ] **Step 3: Write the failing baseline test** `engine/tests/test_director_baseline.py`:

```python
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
```

- [ ] **Step 4: Create `engine/director/baseline_phase3.py`:**

```python
"""Freeze the phase-3 quality baseline (run ONCE, before phase-4 code; plan Task 34). For every eval
subject x prompt x seed, the phase-3 pipeline with a refusing provider (so the fallback, no API call):
the script-level tier, the direction id, the duration and the shot count. The quality floor and the
harness compare against this file, so 'never worse than phase 3' does not drift as the code changes."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name("baseline") / "phase3_tiers.json"
MODELS = ("camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
          "sports_car", "toycar", "vintage_microscope")
PROMPTS = ("", "luxury")
SEEDS = (0, 1, 2, 3, 4)


def profile_key(profile):
    """Same formula as engine.director.variety.subject_key (Task 43 asserts they agree)."""
    return hashlib.sha256(json.dumps(profile.to_dict(), sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def build():
    from engine.catalog import Catalog
    from engine.director.llm import FakeProvider
    from engine.director.pipeline import direct
    from harness.director_eval import _profile, s_tier
    cat, cases = Catalog.load(), []
    for m in MODELS:
        p = _profile(m)
        for prompt in PROMPTS:
            for seed in SEEDS:
                r = direct(prompt, p, provider=FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3),
                           seed=seed, catalog=cat)
                cases.append({"model": m, "subjectKey": profile_key(p), "prompt": prompt, "seed": seed,
                              "tier": s_tier(r.script, p, cat), "directionId": r.script["direction"]["id"],
                              "durationS": r.script["format"]["durationS"], "shots": len(r.script["shots"])})
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    return {"schema": "valora.baseline/1", "frozenAt": sha, "cases": cases}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine.director.baseline_phase3")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if BASELINE.exists() and not a.force:
        raise SystemExit("the phase-3 baseline is frozen; regenerate only with --force and the owner's OK")
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(build(), indent=1), encoding="utf-8", newline="\n")
    print(f"wrote {BASELINE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Generate it once** (CPU only, 90 fallback builds, no render, no network):
  `py -m engine.director.baseline_phase3`. Then run
  `py -m pytest engine/tests/test_director_baseline.py -q` → PASS. Paste the tier counts per subject into
  the Task 50 register.

- [ ] **Step 6: Ignore local variety memory.** Append to `.gitignore`:

```
# Variety memory (phase 4): local per-user direction history, never committed
var/
```

- [ ] **Step 7: Commit**

```bash
git diff --cached --name-only
git commit -m "chore(director): freeze the phase-3 quality baseline; ignore local variety memory" -- .gitignore engine/director/baseline_phase3.py engine/director/baseline/phase3_tiers.json engine/tests/test_director_baseline.py
```

---

## Chunk 1: Direction v2, dice data, axes, prompt pins

### Task 35: `dice.json` and Direction v2 (seven axes, ids that round-trip)

**Files:**
- Create: `engine/director/dice.json`
- Modify: `engine/director/direction.py`
- Test: `engine/tests/test_director_direction_v2.py`

- [ ] **Step 1: Write the failing test** `engine/tests/test_director_direction_v2.py`:

```python
import pytest

from engine.director.direction import AXES, Direction, direction_of, make_id, parse_id

AX = {"world": "studio_cyc", "mood": "teal_night", "tone": "black", "pace": "calm",
      "opener": "arc_orbit", "weather": "dry", "wind": "calm"}


def test_axes_order_is_fixed():
    assert AXES == ("world", "mood", "tone", "pace", "opener", "weather", "wind")


def test_id_round_trips():
    assert make_id(AX) == "studio_cyc/teal_night/black/calm/arc_orbit/dry/calm"
    assert parse_id(make_id(AX)) == AX


def test_legacy_three_part_id_parses_with_defaults():
    ax = parse_id("premium_dark/medium/black")
    assert ax == {"world": "studio_cyc", "mood": "premium_dark", "tone": "black", "pace": "medium",
                  "opener": "low_hero_push", "weather": "dry", "wind": "calm"}


@pytest.mark.parametrize("bad", ["", "a/b", "a/b/c/d", "a/b/c/d/e/f/g/h", "a//b", 7, None])
def test_bad_ids_raise(bad):
    with pytest.raises(ValueError):
        parse_id(bad)


def test_direction_of_fills_every_field_and_sorts_pins():
    d = direction_of(AX, "dice", pinned={"pace": "calm", "mood": "teal_night"})
    assert d.id == make_id(AX) and d.source == "dice" and d.pinned == ("mood", "pace")
    assert d.axes() == AX and (d.mood, d.pace, d.tone, d.opener, d.world) == ("teal_night", "calm", "black",
                                                                              "arc_orbit", "studio_cyc")


def test_old_constructor_still_works():
    d = Direction("premium_dark/medium/black", "premium_dark", "medium", "black")
    assert d.source == "interim" and d.opener == "low_hero_push" and d.world == "studio_cyc"


def test_from_script_is_a_replay():
    d = Direction.from_script({"direction": {"id": make_id(AX), "source": "dice"}})
    assert d.axes() == AX and d.source == "replay"
```

- [ ] **Step 2: Run it to verify it fails.**

Run: `py -m pytest engine/tests/test_director_direction_v2.py -q`
Expected: FAIL with `ImportError: cannot import name 'AXES'`.

- [ ] **Step 3: Create `engine/director/dice.json`:**

```json
{
 "schema": "valora.dice/1",
 "note": "Phase 4 dice data. Values are intersected with the catalog at run time (axes.py), so a value here that the catalog lacks is never rolled. (eng) numbers are listed in the phase-4 plan's calibration register.",
 "rare": {"mood": ["noir"]},
 "toneByMood": {"clean": ["white", "grey"], "premium_dark": ["black"], "warm_golden": ["grey", "white"],
                "teal_night": ["black"], "noir": ["black", "grey"], "vivid": ["grey", "white", "black"]},
 "paceByFamily": {"vehicle": ["medium", "hype"], "product": ["calm", "medium", "hype"],
                  "furniture": ["calm"], "character": ["calm", "medium"]},
 "openers": ["low_hero_push", "arc_orbit"],
 "durationsS": [8, 10, 12],
 "weather": {"values": ["dry", "wet", "rain", "snow", "fog"], "rollable": ["dry"]},
 "wind": {"values": ["calm", "breeze", "windy"], "rollable": ["calm"]},
 "axisWeights": {"world": 3, "mood": 3, "tone": 1, "pace": 1, "opener": 2, "weather": 2, "wind": 1},
 "memoryN": 5,
 "minDistance": 0.25,
 "nearPenalty": 0.25,
 "weightFloor": 0.1,
 "nearDuplicateScript": 0.08,
 "pins": {
  "mood": {
   "premium_dark": ["luxury", "luxurious", "premium", "elegant", "high[- ]end", "moody"],
   "teal_night": ["night", "neon", "nocturnal", "after dark", "cyberpunk"],
   "warm_golden": ["warm", "golden", "sunset", "sunrise", "cozy", "cosy"],
   "clean": ["clean", "minimal", "minimalist", "simple", "catalog(?:ue)?", "e-?commerce"],
   "vivid": ["vivid", "colou?rful", "playful", "fun", "bright"],
   "noir": ["noir", "black and white", "black & white", "monochrome", "b&w"]
  },
  "pace": {
   "calm": ["slow", "calm", "gentle", "relaxed", "elegant"],
   "hype": ["fast", "quick cuts?", "energetic", "hype", "punchy", "high energy", "dynamic"]
  },
  "tone": {
   "white": ["white background", "on white", "white backdrop"],
   "black": ["black background", "on black", "black backdrop"]
  },
  "world": {
   "studio_cyc": ["studio", "cyclorama", "seamless backdrop"]
  },
  "opener": {
   "low_hero_push": ["low angle", "low[- ]hero", "push[- ]in"],
   "arc_orbit": ["orbit(?:s|ing)?", "circle around", "circling"]
  }
 }
}
```

Pin values the catalog lacks are dropped at run time (`variety.prompt_pins`), so a world phrase for a
world that does not exist yet is simply ignored. `macro_detail` is not an opener: the sequence checker
requires a full-framing hook (`seq_bad_hook`). `detailParams` is added in Task 40a.

- [ ] **Step 4: Extend `engine/director/direction.py`.** Keep `TONE`, `PACES`, `RARE` and
  `interim_direction` exactly as they are (the phase-3 test pins its 3-part id). Replace the
  docstring and the `Direction` class, and add the helpers:

```python
"""A direction: what the dice rolled for one job (spec §6 layer 2). Seven axes, in a fixed order, so a
direction id round-trips and any job can be replayed from its script. interim_direction (phase 3) is
kept as the last resort when the dice find nothing viable."""
import random
from dataclasses import dataclass

from engine.director.family import family

AXES = ("world", "mood", "tone", "pace", "opener", "weather", "wind")
AXIS_DEFAULTS = {"world": "studio_cyc", "opener": "low_hero_push", "weather": "dry", "wind": "calm"}

# ... TONE, PACES, RARE unchanged ...


@dataclass(frozen=True)
class Direction:
    id: str
    mood: str
    pace: str
    tone: str
    source: str = "interim"          # interim | dice | more_like_this | replay
    world: str = "studio_cyc"
    opener: str = "low_hero_push"
    weather: str = "dry"
    wind: str = "calm"
    pinned: tuple = ()               # axes the prompt pinned (sorted names)

    def axes(self):
        return {a: getattr(self, a) for a in AXES}

    @classmethod
    def from_script(cls, script):
        return direction_of(parse_id(script["direction"]["id"]), "replay")


def make_id(axes):
    return "/".join(axes[a] for a in AXES)


def parse_id(s):
    """7-part ids (phase 4) or legacy 3-part mood/pace/tone ids (phase 3). Anything else: ValueError."""
    if not isinstance(s, str):
        raise ValueError("direction id must be text")
    parts = s.split("/")
    if any(not p for p in parts):
        raise ValueError(f"bad direction id {s!r}")
    if len(parts) == len(AXES):
        return dict(zip(AXES, parts))
    if len(parts) == 3:
        mood, pace, tone = parts
        return {**AXIS_DEFAULTS, "mood": mood, "pace": pace, "tone": tone}
    raise ValueError(f"bad direction id {s!r}")


def direction_of(axes, source, pinned=()):
    return Direction(id=make_id(axes), mood=axes["mood"], pace=axes["pace"], tone=axes["tone"], source=source,
                     world=axes["world"], opener=axes["opener"], weather=axes["weather"], wind=axes["wind"],
                     pinned=tuple(sorted(pinned)))
```

`parse_id` returns a dict ordered in the natural key order, so the legacy dict equality in the test
holds (dict equality ignores order).

- [ ] **Step 5: Run the new test and the phase-3 intent test.**

Run: `py -m pytest engine/tests/test_director_direction_v2.py engine/tests/test_director_intent.py engine/tests/test_director_request.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(director): Direction v2 - seven axes, round-tripping ids, dice data" -- engine/director/dice.json engine/director/direction.py engine/tests/test_director_direction_v2.py
```

### Task 36: Axis values from the catalog

**Files:**
- Create: `engine/director/axes.py`
- Test: `engine/tests/test_director_axes.py`

- [ ] **Step 1: Write the failing test** `engine/tests/test_director_axes.py`:

```python
import pytest

from engine.catalog import Catalog
from engine.director.axes import DICE, axis_values, compatible, opener_of, validate_axes
from engine.director.direction import AXES
from engine.tests.test_director_package import _p

FMT = {"aspect": "9:16", "durationS": 10, "fps": 30}
NINE = ["camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
        "sports_car", "toycar", "vintage_microscope"]


@pytest.mark.parametrize("model", NINE)
def test_every_eval_subject_has_a_value_on_every_axis(model):
    v = axis_values(_p(model), Catalog.load(), FMT)
    assert tuple(v) == AXES and all(v[a] for a in AXES), v


def test_turntable_is_never_an_opener_negative_control():
    cat = Catalog.load()
    assert "turntable" in [b for (k, b) in cat._blocks if k == "camera"]  # the control exists ...
    for model in NINE:
        assert "turntable" not in axis_values(_p(model), cat, FMT)["opener"]  # ... and is never rolled


def test_rare_and_future_values_are_pin_only():
    cat, p = Catalog.load(), _p("pocket_watch")
    rolled, known = axis_values(p, cat, FMT), axis_values(p, cat, FMT, rollable=False)
    assert "noir" not in rolled["mood"] and "noir" in known["mood"]
    assert rolled["weather"] == ["dry"] and rolled["wind"] == ["calm"]
    assert "rain" in known["weather"] and "windy" in known["wind"]


def test_values_come_from_the_catalog():
    cat = Catalog.load()
    moods = cat.get("grade", "mood_grade")["params"]["preset"]["values"]
    v = axis_values(_p("pocket_watch"), cat, FMT, rollable=False)
    assert set(v["mood"]) == set(moods) and set(v["world"]) <= set(cat.selectable_ids("world"))
    assert set(v["opener"]) <= set(cat.selectable_ids("camera"))


def test_tone_compatibility():
    assert compatible({"mood": "premium_dark", "tone": "black"}) and not compatible({"mood": "premium_dark",
                                                                                        "tone": "white"})
    assert compatible({"mood": "unknown_mood", "tone": "white"})  # unknown moods combine freely


def test_openers_are_full_framing_hook_cameras():
    v = axis_values(_p("pocket_watch"), Catalog.load(), FMT)
    assert v["opener"] == ["low_hero_push", "arc_orbit"]   # macro_detail cannot open: seq_bad_hook


def test_opener_of_and_validate_axes():
    assert opener_of({"shots": [{"purpose": "hook", "camera": {"id": "arc_orbit"}}]}) == "arc_orbit"
    cat, p = Catalog.load(), _p("pocket_watch")
    ok = {"world": "studio_cyc", "mood": "clean", "tone": "white", "pace": "calm", "opener": "arc_orbit",
          "weather": "dry", "wind": "calm"}
    assert validate_axes(ok, p, cat, FMT) == []
    assert validate_axes({**ok, "mood": "<script>", "opener": "turntable"}, p, cat, FMT) == ["mood", "opener"]
    assert validate_axes("junk", p, cat, FMT) == list(AXES)


def test_dice_json_is_consistent():
    assert set(DICE["axisWeights"]) == set(AXES)
    assert set(DICE["weather"]["rollable"]) <= set(DICE["weather"]["values"])
    assert set(DICE["wind"]["rollable"]) <= set(DICE["wind"]["values"])
```

- [ ] **Step 2: Run to verify it fails.**
Run: `py -m pytest engine/tests/test_director_axes.py -q`
Expected: FAIL (`No module named engine.director.axes`).

- [ ] **Step 3: Create `engine/director/axes.py`:**

```python
"""Dice axes (spec §6 layer 2): which values this subject and format may roll. Values come from the
catalog (worlds, grade presets, selectable cameras) intersected with dice.json, so the dice can never
pick something the menu does not offer. Harness-only blocks (turntable) are not selectable and so are
never values."""
import json
from pathlib import Path

from engine.director.direction import AXES
from engine.director.family import family

DICE_FILE = Path(__file__).with_name("dice.json")


def load_dice(path=DICE_FILE):
    return json.loads(path.read_text(encoding="utf-8"))


DICE = load_dice()


def _world_ok(m, profile, fmt):
    lo, hi = m["subjectSizeM"]
    return lo <= profile.longest <= hi and fmt["aspect"] in m["aspects"]


def axis_values(profile, catalog, fmt, dice=None, rollable=True):
    """{axis: [values]}. rollable=False lists every value an axis knows: prompt pins and 'more like
    this' may use them, the dice may not (noir, rain, windy)."""
    dice = dice or DICE
    rare = set(dice["rare"].get("mood", [])) if rollable else set()
    cams = set(catalog.selectable_ids("camera"))
    pace = (dice["paceByFamily"][family(profile)] if rollable
            else catalog.get("edit", "sequence")["params"]["pace"]["values"])
    out = {
        "world": [w for w in catalog.selectable_ids("world") if _world_ok(catalog.get("world", w), profile, fmt)],
        "mood": [m for m in catalog.get("grade", "mood_grade")["params"]["preset"]["values"] if m not in rare],
        "tone": list(catalog.get("world", "studio_cyc")["params"]["tone"]["values"]),
        "pace": list(pace),
        "opener": [c for c in dice["openers"] if c in cams],
        "weather": list(dice["weather"]["rollable" if rollable else "values"]),
        "wind": list(dice["wind"]["rollable" if rollable else "values"]),
    }
    return {a: out[a] for a in AXES}


def compatible(axes, dice=None):
    """Tone must suit the mood (dice.json toneByMood). Everything else combines freely."""
    table = (dice or DICE)["toneByMood"]
    return axes["tone"] in table.get(axes["mood"], [axes["tone"]])


def opener_of(script):
    """The opener a script actually uses: the first shot's camera (openers are full-framing hooks)."""
    return script["shots"][0]["camera"]["id"]


def validate_axes(axes, profile, catalog, fmt):
    """Axes whose value this subject/format does not know (rollable=False values). [] means valid. Used
    for 'more like this' and for memory writes, so no unknown or free-text value is ever accepted."""
    if not isinstance(axes, dict):
        return list(AXES)
    known = axis_values(profile, catalog, fmt, rollable=False)
    return [a for a in AXES if axes.get(a) not in known[a]]
```

If the `sequence` pace param is not an enum, read it from the block and adapt: `rollable=False` needs
the full set.

- [ ] **Step 4: Run it.** `py -m pytest engine/tests/test_director_axes.py -q` → PASS. If a subject
  has an empty `world` list (its size is outside `studio_cyc.subjectSizeM`), **stop and report**. Do
  not widen the block's range in this plan. `choose_direction` falls back to the interim direction
  in that case (Task 43).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): dice axes from the catalog; full-framing openers; validate_axes" -- engine/director/axes.py engine/tests/test_director_axes.py
```

### Task 37: Prompt pins — an explicit request beats the dice

**Files:**
- Create: `engine/director/pins.py`
- Test: `engine/tests/test_director_pins.py`

- [ ] **Step 1: Write the failing test:**

```python
import pytest

from engine.director.pins import read_direction_pins


@pytest.mark.parametrize("prompt,pins", [
    ("", {}), ("make it look cool", {}), ("ad", {}),
    ("luxury", {"mood": "premium_dark"}),
    ("rainy night", {"mood": "teal_night"}),
    ("fun, bright and energetic social clip with quick cuts", {"mood": "vivid", "pace": "hype"}),
    ("moody cinematic 16:9 commercial", {"mood": "premium_dark"}),
    ("A premium launch ad for this: slow reveal from darkness, close-ups of the details, then a clean hero shot.",
     {"mood": "premium_dark", "pace": "calm"}),                       # first mention wins per axis
    ("sunset on the beach with music", {"mood": "warm_golden"}),
    ("black and white, on black", {"mood": "noir", "tone": "black"}),
    ("not dark, no neon, bright", {"mood": "vivid"}),                 # negated mentions are not pins
    ("without quick cuts", {}),
    ("studio shot, orbiting the product", {"world": "studio_cyc", "opener": "arc_orbit"}),
    ("low angle push in, black background", {"opener": "low_hero_push", "tone": "black"}),
    ("no orbit, just calm", {"pace": "calm"}),                        # a negated opener is not a pin
    ("funky", {}), ("nightstand", {}),                                # whole words only
])
def test_pins(prompt, pins):
    assert read_direction_pins(prompt) == pins
```

- [ ] **Step 2: Run to verify it fails.** Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `engine/director/pins.py`:**

```python
"""Direction pins read from the prompt (spec §6: an explicit request beats the dice). The phrases are
data (dice.json "pins"). Per axis, the first mention in reading order wins. A negated mention ('no
neon', 'without quick cuts') is not a pin; the negation rule is the same one capability detection uses.
Deterministic: what the prompt pinned is never left to the LLM."""
import re

from engine.director.axes import DICE
from engine.director.capabilities import _negated


def compile_pins(dice=None):
    table = (dice or DICE)["pins"]
    return {axis: [(value, re.compile(r"\b(?:" + "|".join(ph) + r")\b", re.I)) for value, ph in vals.items()]
            for axis, vals in table.items()}


_PINS = compile_pins()


def read_direction_pins(prompt, pins=None):
    text, out = prompt or "", {}
    for axis, table in (pins or _PINS).items():
        best = None
        for value, rx in table:
            for m in rx.finditer(text):
                if _negated(text, m):
                    continue
                if best is None or m.start() < best[0]:
                    best = (m.start(), value)
                break
        if best:
            out[axis] = best[1]
    return out
```

- [ ] **Step 4: Run.** `py -m pytest engine/tests/test_director_pins.py -q` → PASS. If a case fails
  because `_negated` treats a clause differently, fix the **phrase data** or the test expectation
  with a one-line reason in the test. Do not fork the negation rule.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): prompt pins for world/mood/tone/pace/opener (negation-aware)" -- engine/director/pins.py engine/tests/test_director_pins.py
```

---

## Chunk 2: Distance, the dice, directions the fallback honours, the quality floor

### Task 38: Direction distance, script distance, near-duplicates

**Files:**
- Create: `engine/director/distance.py`
- Test: `engine/tests/test_director_distance.py`

- [ ] **Step 1: Write the failing test:**

```python
import copy
import json

from engine.catalog import Catalog
from engine.director.distance import direction_distance, near_duplicate, script_distance
from engine.director.rulebook import EXAMPLES_DIR, example_script

A = {"world": "studio_cyc", "mood": "teal_night", "tone": "black", "pace": "calm", "opener": "arc_orbit",
     "weather": "dry", "wind": "calm"}


def _ex(name):
    return example_script(json.loads((EXAMPLES_DIR / f"{name}.json").read_text(encoding="utf-8")))


def test_direction_distance_is_a_weighted_hamming_in_0_1():
    assert direction_distance(A, A) == 0.0
    b = {**A, "mood": "clean"}
    assert direction_distance(A, b) == direction_distance(b, A) == 3 / 13
    far = {k: v + "_x" for k, v in A.items()}
    assert direction_distance(A, far) == 1.0


def test_script_distance_zero_for_identical_and_symmetric():
    cat, s = Catalog.load(), _ex("watch_luxury")
    assert script_distance(s, copy.deepcopy(s), cat) == 0.0
    t = _ex("chair_warm")
    d = script_distance(s, t, cat)
    assert 0.0 < d <= 1.0 and abs(d - script_distance(t, s, cat)) < 1e-12


def test_small_param_change_is_small_and_near_duplicate():
    cat, s = Catalog.load(), _ex("watch_luxury")
    t = copy.deepcopy(s)
    t["shots"][0]["camera"]["params"]["lensMm"] = t["shots"][0]["camera"]["params"].get("lensMm", 50) + 2
    d = script_distance(s, t, cat)
    assert 0.0 < d < 0.08 and near_duplicate(s, t, cat)


def test_different_grade_preset_is_not_a_near_duplicate():
    cat, s = Catalog.load(), _ex("watch_luxury")
    t = copy.deepcopy(s)
    t["grade"] = {"id": "mood_grade", "params": {"preset": "vivid"}}
    assert not near_duplicate(s, t, cat)
```

(If `chair_warm` is not in `EXAMPLES_DIR`, use any other checked example name listed there.)

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/distance.py`:**

```python
"""How different two directions / two scripts are, in [0, 1]. Direction distance is a weighted Hamming
distance over the dice axes (dice.json axisWeights). Script distance compares what a viewer would see:
world, light, grade, effects, the cut pattern and each camera's parameters normalised by the catalog
range. Used by the dice (near-duplicate penalty) and the harness variety score (spec §9)."""
from engine.director.axes import DICE
from engine.director.direction import AXES


def direction_distance(a, b, dice=None):
    w = (dice or DICE)["axisWeights"]
    return sum(w[x] for x in AXES if a.get(x) != b.get(x)) / sum(w[x] for x in AXES)


def _params_d(ra, rb, kind, catalog):
    ra, rb = ra or {}, rb or {}
    if ra.get("id") != rb.get("id"):
        return 1.0
    m = catalog.get(kind, ra.get("id")) if ra.get("id") else None
    if not m or not m["params"]:
        return 0.0
    pa, pb, ds = ra.get("params") or {}, rb.get("params") or {}, []
    for name, spec in m["params"].items():
        va, vb = pa.get(name, spec["default"]), pb.get(name, spec["default"])
        if spec["type"] == "number":
            span = (spec["max"] - spec["min"]) or 1.0
            try:
                ds.append(min(1.0, abs(float(va) - float(vb)) / span))
            except (TypeError, ValueError):
                ds.append(1.0)
        else:
            ds.append(0.0 if va == vb else 1.0)
    return sum(ds) / len(ds)


def _grade_key(s):
    g = s.get("grade") or {}
    return (g.get("id"), (g.get("params") or {}).get("preset"))


def _bounds(s):
    return [sh["endS"] for sh in s["shots"][:-1]]


def script_distance(a, b, catalog):
    sa, sb = a["shots"], b["shots"]
    dur = max(a["format"]["durationS"], b["format"]["durationS"], 1e-9)
    n = max(len(sa), len(sb))
    cam_seq = sum(1 for i in range(n) if i >= len(sa) or i >= len(sb)
                  or sa[i]["camera"]["id"] != sb[i]["camera"]["id"]) / n
    aligned = [(x["camera"], y["camera"]) for x, y in zip(sa, sb) if x["camera"]["id"] == y["camera"]["id"]]
    cam_params = sum(_params_d(x, y, "camera", catalog) for x, y in aligned) / len(aligned) if aligned else 1.0
    ba, bb = _bounds(a), _bounds(b)
    cuts = (sum(min(1.0, abs(x - y) / dur * 4) for x, y in zip(ba, bb)) / max(len(ba), len(bb))
            if ba and bb and len(ba) == len(bb) else (0.0 if ba == bb else 1.0))
    ea, eb = {e["id"] for e in a.get("effects", [])}, {e["id"] for e in b.get("effects", [])}
    parts = [  # (distance, weight)
        (0.0 if a["world"]["id"] == b["world"]["id"] else 1.0, 2), (_params_d(a["world"], b["world"], "world", catalog), 1),
        (0.0 if a["lighting"]["id"] == b["lighting"]["id"] else 1.0, 2),
        (_params_d(a["lighting"], b["lighting"], "lighting", catalog), 1),
        (0.0 if _grade_key(a) == _grade_key(b) else 1.0, 2), (_params_d(a.get("grade"), b.get("grade"), "grade", catalog), 1),
        (1.0 - len(ea & eb) / len(ea | eb) if ea | eb else 0.0, 1),
        (min(1.0, abs(len(sa) - len(sb)) / 3), 1), (cam_seq, 2), (cam_params, 1), (cuts, 1),
        (0.0 if a["format"]["durationS"] == b["format"]["durationS"] else 1.0, 1),
    ]
    return sum(d * w for d, w in parts) / sum(w for _, w in parts)


def near_duplicate(a, b, catalog, dice=None):
    return script_distance(a, b, catalog) < (dice or DICE)["nearDuplicateScript"]
```

- [ ] **Step 4: Run.** PASS. If `test_small_param_change...` lands at ≥ 0.08, do not tune the
  weights to the test. Print the parts, check which one is wrong, fix it, and write the reason in the
  commit message.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): direction and script distance, near-duplicate flag" -- engine/director/distance.py engine/tests/test_director_distance.py
```

### Task 39: The dice — viable-pool rotation, pins, avoid, near-dup penalty

**Rotation contract (revision 2).** History is the user+subject's direction ids, oldest first. The
preference order is:
1. viable candidates never used in history (weighted random);
2. viable used candidates, least-recently-used first.

So the whole **viable** pool is used before any repeat. There is no try cap: viability is cached, and
the pool is small (≤ ~60 combinations today).

**Files:**
- Create: `engine/director/dice.py`
- Test: `engine/tests/test_director_dice.py`

- [ ] **Step 1: Write the failing test:**

```python
from engine.director.dice import candidates, roll, roll_duration
from engine.director.direction import make_id

V = {"world": ["studio_cyc"], "mood": ["clean", "premium_dark", "teal_night"], "tone": ["white", "grey", "black"],
     "pace": ["calm", "medium"], "opener": ["low_hero_push", "arc_orbit"], "weather": ["dry"], "wind": ["calm"]}


def test_candidates_respect_tone_compatibility_unless_tone_is_pinned():
    c = candidates(V)
    assert all(x["tone"] == "black" for x in c if x["mood"] in ("premium_dark", "teal_night"))
    assert any(x["tone"] == "white" for x in candidates(V, pins={"mood": "premium_dark", "tone": "white"}))


def test_same_inputs_same_direction_replayable():
    assert roll(7, V).axes == roll(7, V).axes
    assert len({make_id(roll(s, V).axes) for s in range(40)}) >= 8


def test_pins_are_never_overridden():
    for s in range(20):
        a = roll(s, V, pins={"mood": "noir", "pace": "calm"}).axes
        assert a["mood"] == "noir" and a["pace"] == "calm"


def test_whole_viable_pool_before_any_repeat():
    viable = lambda a: a["opener"] == "arc_orbit" and a["mood"] != "clean"   # noqa: E731
    pool = [c for c in candidates(V) if viable(c)]
    hist = []
    for s in range(len(pool)):
        r = roll(s, V, history=hist, viable=viable)
        assert make_id(r.axes) not in hist and "repeat_after_rotation" not in r.flags
        hist.append(make_id(r.axes))
    assert {make_id(c) for c in pool} == set(hist)
    r = roll(99, V, history=hist, viable=viable)                        # pool exhausted -> LRU repeat
    assert make_id(r.axes) == hist[0] and "repeat_after_rotation" in r.flags


def test_non_viable_never_chosen_even_when_unseen():
    for s in range(20):
        assert roll(s, V, viable=lambda a: a["opener"] == "arc_orbit").axes["opener"] == "arc_orbit"
    r = roll(3, V, viable=lambda a: False)
    assert r.axes is None and "nothing_viable" in r.flags


def test_avoid_excludes_and_relaxes_instead_of_emptying():
    for s in range(20):
        assert roll(s, V, avoid={"mood": ["teal_night"]}).axes["mood"] != "teal_night"
    r = roll(1, V, avoid={"mood": ["clean", "premium_dark", "teal_night"]})
    assert r.axes is not None and "avoid_relaxed" in r.flags


def test_pins_beat_avoid():
    assert roll(1, V, pins={"mood": "clean"}, avoid={"mood": ["clean"]}).axes["mood"] == "clean"


def test_duration_is_seeded_and_in_range():
    assert roll_duration(5) == roll_duration(5) and {roll_duration(s) for s in range(40)} == {8, 10, 12}
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/dice.py`:**

```python
"""The creative dice (spec §3 stage 2, §6 layers 2-3). Pure and deterministic: the same seed, pins,
history, avoid list and viability always give the same direction. Rotation runs over the VIABLE pool:
never-used viable directions first (weighted random), then used ones least-recently-used first, so a
subject gets every eligible direction before any repeat. Variety comes from here, not the LLM (§11)."""
import itertools
import random
from dataclasses import dataclass

from engine.director.axes import DICE, compatible
from engine.director.direction import AXES, make_id, parse_id
from engine.director.distance import direction_distance
from engine.director.taste import MIN_STAT_N

AVOID_RELAX_ORDER = ("wind", "weather", "pace", "tone", "opener", "world", "mood")  # least salient first


@dataclass(frozen=True)
class Roll:
    axes: dict | None
    flags: tuple = ()
    tried: int = 0


def candidates(values, pins=None, dice=None):
    pins = pins or {}
    pools = [[pins[a]] if a in pins else values[a] for a in AXES]
    out = []
    for combo in itertools.product(*pools):
        axes = dict(zip(AXES, combo))
        if "tone" in pins or compatible(axes, dice):
            out.append(axes)
    return out


def _apply_avoid(cands, avoid, pins):
    avoid = {a: set(v) for a, v in (avoid or {}).items() if a in AXES and a not in pins and v}
    relaxed = False
    for drop in (None,) + AVOID_RELAX_ORDER:
        if drop is not None and drop in avoid:
            avoid.pop(drop)
            relaxed = True
        kept = [c for c in cands if not any(c[a] in vals for a, vals in avoid.items())]
        if kept:
            return kept, relaxed
    return cands, True


def pace_weights(fam, stats, dice=None):
    """Corpus energy shares for this family when trusted (n >= MIN_STAT_N), plus a floor so a
    rare-but-good pace stays rollable (spec §9a use 3). Untrusted: {} (uniform)."""
    s = ((stats or {}).get("families", {}).get(fam) or {}).get("energy") or {}
    if s.get("trusted") is True and s.get("n", 0) >= MIN_STAT_N:
        return {k: v + (dice or DICE)["weightFloor"] for k, v in s["shares"].items()}
    return {}


def _weight(axes, pw, recent_axes, dice):
    w = pw.get(axes["pace"], dice["weightFloor"]) if pw else 1.0
    if any(direction_distance(axes, r, dice) < dice["minDistance"] for r in recent_axes):
        w *= dice["nearPenalty"]
    return w


def _parsed(ids):
    out = []
    for i in ids:
        try:
            out.append(parse_id(i))
        except ValueError:
            continue
    return out


def roll(seed, values, *, pins=None, history=(), avoid=None, viable=None, family_name=None, stats=None, dice=None):
    dice, pins, flags = dice or DICE, pins or {}, []
    cands = candidates(values, pins, dice)
    if not cands:
        return Roll(None, ("no_candidates",))
    cands, relaxed = _apply_avoid(cands, avoid, pins)
    if relaxed:
        flags.append("avoid_relaxed")
    history = list(history)
    last_use = {h: i for i, h in enumerate(history)}          # later index wins = most recent use
    unseen = [c for c in cands if make_id(c) not in last_use]
    seen = sorted((c for c in cands if make_id(c) in last_use), key=lambda c: last_use[make_id(c)])
    recent_axes = _parsed(history[-dice["memoryN"]:])
    pw = pace_weights(family_name, stats, dice) if family_name else {}
    rng = random.Random(f"dice:{seed}")
    keys = [rng.random() ** (1.0 / _weight(c, pw, recent_axes, dice)) for c in unseen]  # weighted, no replacement
    order = [c for _, c in sorted(zip(keys, unseen), key=lambda kc: (-kc[0], make_id(kc[1])))] + seen
    for i, c in enumerate(order):
        if viable is None or viable(c):
            if make_id(c) in last_use:
                flags.append("repeat_after_rotation")
            return Roll(c, tuple(flags), i + 1)
    return Roll(None, tuple(flags + ["nothing_viable"]), len(order))


def roll_duration(seed, dice=None):
    return random.Random(f"duration:{seed}").choice((dice or DICE)["durationsS"])
```

- [ ] **Step 4: Run.** `py -m pytest engine/tests/test_director_dice.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): deterministic dice - viable-pool rotation, pins, avoid, near-dup penalty" -- engine/director/dice.py engine/tests/test_director_dice.py
```

### Task 40: The fallback honours the direction's opener and world

The floor (Task 41) judges a direction by its safe fallback, so the fallback must use the rolled
opener. Re-read `engine/director/fallback.py` at HEAD first. Another lane edits it: the marker fix
`a9cbdde` added `_plan(..., n_markers=0)`, and `_script(..., skip=frozenset())` exists. **Keep every
existing argument and append new ones after them**, using the Task 34 Step 1 signatures. `_plan` does
not change: both openers are full-framing hook cameras, so the `hook` purpose stays (`seq_bad_hook`).

**Files:**
- Modify: `engine/director/fallback.py` (`slot_camera`, `_script`, `build_fallback`)
- Test: `engine/tests/test_director_fallback_opener.py` (new file; the phase-3 test file stays untouched)

- [ ] **Step 1: Write the failing test:**

```python
import dataclasses

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.director.axes import opener_of
from engine.director.direction import direction_of
from engine.director.fallback import build_fallback
from engine.director.job import make_job
from engine.tests.test_director_package import _p

NINE = ["camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
        "sports_car", "toycar", "vintage_microscope"]
AX = {"world": "studio_cyc", "mood": "clean", "tone": "white", "pace": "medium", "opener": "low_hero_push",
      "weather": "dry", "wind": "calm"}


def _job(p, cat, seed, opener):
    return dataclasses.replace(make_job("a 10 second clip", p, cat, seed=seed),
                               direction=direction_of({**AX, "opener": opener}, "dice"))


@pytest.mark.parametrize("opener", ["low_hero_push", "arc_orbit"])
def test_fallback_uses_the_opener_on_the_watch(opener):
    cat, p = Catalog.load(), _p("pocket_watch")
    s = build_fallback(_job(p, cat, 3, opener), p, cat)
    assert check(s, p, cat).ok and opener_of(s) == opener


@pytest.mark.parametrize("model", NINE)
def test_every_subject_still_gets_a_valid_fallback_for_every_opener(model):
    """The fallback may swap to the safe opener, but it must never fail (spec §4.6)."""
    cat, p = Catalog.load(), _p(model)
    for opener in ("low_hero_push", "arc_orbit"):
        assert check(build_fallback(_job(p, cat, 4, opener), p, cat), p, cat).ok


def test_markers_still_get_detail_shots_with_the_new_opener():
    """Regression guard for the n_markers argument (a9cbdde)."""
    from engine.tests.test_director_fallback import _markers  # if the helper moved, build 2 markers inline
    cat, p = Catalog.load(), _p("pocket_watch")
    job = dataclasses.replace(make_job("a 10 second clip", p, cat, seed=2, markers=_markers(p, 2)),
                              direction=direction_of({**AX, "opener": "arc_orbit"}, "dice"))
    s = build_fallback(job, p, cat)
    assert {(sh.get("target") or {}).get("marker") for sh in s["shots"]} >= {m["id"] for m in job.markers}
```

The prompt pins 10 s, so these tests do not depend on Task 44's duration roll. If
`test_director_fallback` has no `_markers` helper, build two `placed` markers on `detailPoints[0..1]`
inline, the same way `harness.director_eval.markers_for` does.

- [ ] **Step 2: Run to verify it fails** (the `arc_orbit` case fails on `opener_of`).

- [ ] **Step 3: Implement.** In `fallback.py`:

```python
OPENER_HOOK = {  # hook cameras for non-default openers (values follow slot_camera's proven ranges) (eng)
    "arc_orbit": {"id": "arc_orbit", "params": {"startAzimuthDeg": 20.0, "sweepDeg": 25.0, "lensMm": 50.0,
                                                "elevationDeg": 6.0}},
}
```

- `slot_camera(purpose, k, fam, jitter=0.0, detail_jitter=0.0, opener="low_hero_push")`: in the
  `purpose in ("hook", "establish")` branch, when `opener in OPENER_HOOK`, use a deep copy of it with
  `startAzimuthDeg += jitter`. Otherwise keep the existing `low_hero_push` camera. The vehicle f/8 line
  after the branch applies to both.
- `_script(<existing args>, skip=frozenset(), opener="low_hero_push")`: pass `opener` to
  `slot_camera` and keep the `_plan(...)` call exactly as HEAD has it (with `n_markers`). The world
  becomes `{"id": job.direction.world, "params": {"tone": job.direction.tone, "floorGloss": 0.4}}` when
  the world is `studio_cyc`, else `{"id": job.direction.world, "params": {}}`.
- `build_fallback`: the attempts become `(pace, jitter, seq, opener)` tuples. Try the direction's
  opener first, then fall back to the safe `low_hero_push`. Pins stay intact: the attempts never change
  `job.direction`, so mood, tone and world always come from it.

```python
    o = getattr(job.direction, "opener", "low_hero_push")
    attempts = ((job.direction.pace, jitter, True, o), (job.direction.pace, 0.0, True, o),
                (job.direction.pace, 0.0, True, "low_hero_push"), ("medium", 0.0, True, "low_hero_push"),
                ("medium", 0.0, False, "low_hero_push"))
```

  Forward `opener` into `_script(..., frozenset(skip), opener=o_attempt)` inside the existing skip loop.

- [ ] **Step 4: Run** `py -m pytest engine/tests/test_director_fallback_opener.py engine/tests/test_director_fallback.py -q` → PASS.
  If `arc_orbit` fails the checker on a subject, that is acceptable: the safety attempts cover it, and
  Task 41's floor marks that opener non-viable there. Record the subject in the Task 50 register.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): fallback honours the direction's opener and world; marker/skip args kept" -- engine/director/fallback.py engine/tests/test_director_fallback_opener.py
```

### Task 40a: Layer 1 — seeded detail variation

Spec §6 layer 1: "Details always differ." Today the fallback jitter has 201 rounded values, the safety
attempts reset it to 0, and the lighting builders never read the seed. The fix is in the script,
not the builders. A whitelist of look params (dice.json `detailParams`) that the script left unset gets
a seeded, in-range offset. Builders receive the variation through their params, and the script fully
describes the render (replay, farm consistency). Values the LLM set are kept.

**Files:**
- Modify: `engine/director/dice.json` (add `detailParams`)
- Create: `engine/director/details.py`
- Modify: `engine/director/fallback.py` (`_script` calls `vary_details` before returning)
- Test: `engine/tests/test_director_details.py`

- [ ] **Step 1: Add to `dice.json`** (fractions of each param's catalog range, all (eng)):

```json
 "detailParams": {
  "lighting/softbox_three_point": {"keyAzimuthDeg": 0.06, "keyElevationDeg": 0.06, "colorTempK": 0.04},
  "lighting/reflection_rig": {"rimElevationDeg": 0.06, "colorTempK": 0.04, "stripDistR": 0.04},
  "world/studio_cyc": {"floorGloss": 0.06},
  "effect/haze_volume": {"density": 0.06, "anisotropy": 0.06}
 },
```

- [ ] **Step 2: Write the failing test** `engine/tests/test_director_details.py`:

```python
import copy
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.director.axes import DICE
from engine.director.details import vary_details
from engine.director.rulebook import EXAMPLES_DIR, example_script

S = example_script(json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8")))


def test_every_detail_param_exists_and_its_builder_reads_it():
    cat = Catalog.load()
    for ref, params in DICE["detailParams"].items():
        kind, bid = ref.split("/")
        m = cat.get(kind, bid)
        assert m is not None, ref
        src = (Path("engine/blocks") / kind / bid / "build.py").read_text(encoding="utf-8")
        for name in params:
            assert name in m["params"] and m["params"][name]["type"] == "number", (ref, name)
            assert name in src, f"{ref}: build.py never reads {name}, so varying it changes nothing"


def test_seeded_in_range_and_deterministic():
    cat = Catalog.load()
    a, b = vary_details(copy.deepcopy(S), 1, cat), vary_details(copy.deepcopy(S), 1, cat)
    c = vary_details(copy.deepcopy(S), 2, cat)
    assert a == b and a != c
    for key in ("world", "lighting"):
        spec = cat.get(key, a[key]["id"])["params"]
        for n, v in a[key]["params"].items():
            if spec[n]["type"] == "number":
                assert spec[n]["min"] <= v <= spec[n]["max"]


def test_values_the_script_set_are_kept():
    cat, s = Catalog.load(), copy.deepcopy(S)
    s["world"]["params"]["floorGloss"] = 0.4
    assert vary_details(s, 9, cat)["world"]["params"]["floorGloss"] == 0.4
```

The builder-reads-it test is the guard that the builders really vary with the seed. If a builder does
not read a whitelisted param, drop that param from `detailParams`. Do not edit the builder in this plan.

- [ ] **Step 3: Create `engine/director/details.py`:**

```python
"""Spec §6 layer 1: details always differ. Seeded, small, in-range offsets to a whitelist of look params
(dice.json detailParams) that the script left unset. Values the script set are kept. Deterministic by
seed and pipeline-owned: applied to LLM and fallback scripts alike before the checker, so builders get
seed-driven variation through their params and the script still fully describes the render."""
import random

from engine.director.axes import DICE


def _vary(ref, kind, path, seed, catalog, table):
    if not isinstance(ref, dict) or not isinstance(ref.get("id"), str):
        return
    fracs, m = table.get(f"{kind}/{ref['id']}"), catalog.get(kind, ref["id"])
    if not fracs or m is None:
        return
    params = ref.setdefault("params", {})
    if not isinstance(params, dict):
        return
    rng = random.Random(f"detail:{seed}:{path}")
    for name, frac in sorted(fracs.items()):
        spec = m["params"].get(name)
        if name in params or not spec or spec["type"] != "number":
            continue
        v = spec["default"] + rng.uniform(-frac, frac) * (spec["max"] - spec["min"])
        params[name] = round(min(spec["max"], max(spec["min"], v)), 4)


def vary_details(script, seed, catalog, dice=None):
    table = (dice or DICE)["detailParams"]
    _vary(script.get("world"), "world", "world", seed, catalog, table)
    _vary(script.get("lighting"), "lighting", "lighting", seed, catalog, table)
    for i, e in enumerate(script.get("effects") if isinstance(script.get("effects"), list) else []):
        _vary(e, "effect", f"effects[{i}]", seed, catalog, table)
    return script
```

- [ ] **Step 4: Wire it into the fallback.** In `fallback._script`, call
  `vary_details(s, job.seed, catalog)` on the finished dict just before `return s`. The fallback's
  `check()` then judges the varied script, so viability includes the variation.

- [ ] **Step 5: Run** the details, fallback and fallback-opener tests → PASS.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(director): layer 1 - seeded in-range detail params the builders read" -- engine/director/dice.json engine/director/details.py engine/director/fallback.py engine/tests/test_director_details.py
```

### Task 41: The quality floor (frozen baseline, measured cadence)

**Files:**
- Create: `engine/director/floor.py`
- Test: `engine/tests/test_director_floor.py`

- [ ] **Step 1: Write the failing test:**

```python
import dataclasses

from engine.catalog import Catalog
from engine.director.axes import axis_values
from engine.director.baseline_phase3 import BASELINE
from engine.director.dice import candidates
from engine.director.direction import direction_of
from engine.director.fallback import build_fallback
from engine.director.floor import _RANK, cadence_ok, cadence_range, floor_tier, make_viable, script_tier
from engine.director.job import make_job
from engine.tests.test_director_package import _p


def _job(model, seed=2):
    cat, p = Catalog.load(), _p(model)
    return make_job("a 10 second clip", p, cat, seed=seed), p, cat


def test_floor_comes_from_the_frozen_baseline():
    import json
    doc = json.loads(BASELINE.read_text(encoding="utf-8"))
    job, p, cat = _job("sports_car")
    best = max((c["tier"] for c in doc["cases"] if c["model"] == "sports_car"), key=_RANK.get)
    assert floor_tier(job, p, cat) == min(("T3", best), key=_RANK.get)


def test_unknown_subject_uses_the_live_interim_tier(monkeypatch):
    import engine.director.floor as fl
    monkeypatch.setattr(fl, "_baseline_best", lambda key: None)
    job, p, cat = _job("pocket_watch")
    assert floor_tier(job, p, cat) in ("T1", "T2", "T3")


def test_cadence_is_measured_from_the_shots():
    cat = Catalog.load()
    lo, hi = cadence_range("calm", 10, cat)
    s = {"format": {"durationS": 10}, "shots": [{}] * lo}
    assert cadence_ok(s, "calm", cat) and not cadence_ok({**s, "shots": [{}] * (hi + 1)}, "calm", cat)
    assert cadence_ok({"format": {"durationS": 5}, "shots": [{}] * 2}, "hype", cat)  # short plan: exempt


def test_viable_is_cached_boolean_and_checks_cadence_not_the_param(monkeypatch):
    job, p, cat = _job("pocket_watch")
    v = make_viable(job, p, cat)
    c = candidates(axis_values(p, cat, job.fmt))[0]
    assert v(c) in (True, False) and v(c) == v(c) and len(v.cache) == 1
    import engine.director.floor as fl
    monkeypatch.setattr(fl, "cadence_ok", lambda s, pace, catalog: False)
    assert make_viable(job, p, cat)(c) is False


def test_non_honoured_opener_is_not_viable(monkeypatch):
    import engine.director.floor as fl
    monkeypatch.setattr(fl, "opener_of", lambda s: "something_else")
    job, p, cat = _job("pocket_watch")
    assert make_viable(job, p, cat)(candidates(axis_values(p, cat, job.fmt))[0]) is False


def test_script_tier_matches_the_harness_definition():
    from harness.director_eval import s_tier
    job, p, cat = _job("pocket_watch")
    s = build_fallback(job, p, cat)
    assert script_tier(s, p, cat) == s_tier(s, p, cat)
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/floor.py`:**

```python
"""The quality floor: novelty never buys a worse clip. floor_tier = min(T3, the BEST tier the frozen
phase-3 baseline (baseline/phase3_tiers.json, Task 34) reached for this subject). For a subject not in
the baseline, it is the tier of the interim direction's fallback, computed live. A direction is viable
when its safe fallback passes the checker, keeps the opener, has a MEASURED cut cadence inside its
pace's shotsPer10s range, and reaches the floor. pipeline.direct also gates the final script (Task 46)."""
import dataclasses
import functools
import json
import math

from engine.craft_rules import score_script
from engine.director.axes import opener_of
from engine.director.baseline_phase3 import BASELINE, profile_key
from engine.director.direction import direction_of, interim_direction, make_id
from engine.director.fallback import MIN_SEQ_S, FallbackError, build_fallback

FLOOR_TIER = "T3"
_RANK = {"T1": 1, "T2": 2, "T3": 3}


def script_tier(script, profile, catalog):
    """Same definition as harness.director_eval.s_tier: script level only, not a quality grade."""
    items = score_script(script, profile, catalog)
    fail = lambda *pre: any(r.status == "fail" and r.id.startswith(pre) for r in items)  # noqa: E731
    if fail("T1-") or fail("T2-"):
        return "T1"
    return "T2" if fail("T3-", "V-") else "T3"


def cadence_range(pace, duration, catalog):
    lo, hi = catalog.get("edit", "sequence")["shotsPer10s"][pace]
    return math.floor(lo * duration / 10.0), math.ceil(hi * duration / 10.0)


def cadence_ok(script, pace, catalog):
    """The pace as CUT, not as declared: shot count inside the pace's shotsPer10s range. Clips shorter
    than the sequence minimum (MIN_SEQ_S) use the 2-shot short plan and are exempt."""
    dur = script["format"]["durationS"]
    if dur < MIN_SEQ_S:
        return True
    lo, hi = cadence_range(pace, dur, catalog)
    return lo <= len(script["shots"]) <= hi


@functools.lru_cache(maxsize=1)
def _baseline():
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))["cases"]
    except (OSError, ValueError, KeyError):
        return []


def _baseline_best(key):
    tiers = [c["tier"] for c in _baseline() if c.get("subjectKey") == key]
    return max(tiers, key=_RANK.get) if tiers else None


def _tier_of(job, profile, catalog):
    try:
        return script_tier(build_fallback(job, profile, catalog), profile, catalog)
    except FallbackError:
        return "T1"


def floor_tier(job, profile, catalog):
    best = _baseline_best(profile_key(profile))
    if best is None:
        best = _tier_of(dataclasses.replace(job, direction=interim_direction(job.seed, profile, catalog)),
                        profile, catalog)
    return min((FLOOR_TIER, best), key=_RANK.get)


def make_viable(job, profile, catalog):
    need = floor_tier(job, profile, catalog)
    cache = {}

    def viable(axes):
        key = make_id(axes)
        if key not in cache:
            try:
                s = build_fallback(dataclasses.replace(job, direction=direction_of(axes, "dice")), profile, catalog)
                cache[key] = (opener_of(s) == axes["opener"] and cadence_ok(s, axes["pace"], catalog)
                              and _RANK[script_tier(s, profile, catalog)] >= _RANK[need])
            except FallbackError:
                cache[key] = False
        return cache[key]

    viable.cache, viable.floor = cache, need
    return viable
```

If `MIN_SEQ_S` has moved out of `fallback.py`, import it from where HEAD defines it.

- [ ] **Step 4: Run.** `py -m pytest engine/tests/test_director_floor.py -q` → PASS.

- [ ] **Step 5: Measure (CPU only, no render).** Create
  `C:\Users\deand\AppData\Local\Temp\p4_viable.py`:

```python
from engine.catalog import Catalog
from engine.director.axes import axis_values
from engine.director.baseline_phase3 import MODELS
from engine.director.dice import candidates
from engine.director.floor import make_viable
from engine.director.job import make_job
from engine.tests.test_director_package import _p

cat = Catalog.load()
for m in MODELS:
    p = _p(m)
    j = make_job("a 10 second clip", p, cat, seed=0)
    v = make_viable(j, p, cat)
    c = candidates(axis_values(p, cat, j.fmt))
    print(m, v.floor, sum(v(x) for x in c), "/", len(c))
```

Run: `py C:\Users\deand\AppData\Local\Temp\p4_viable.py`. Paste the table (population: nine eval
profiles, seed 0, 10 s, date) into the Task 50 register. A subject with **0 viable** directions is not
an error: `choose_direction` then uses the interim direction with pins, which is phase-3 behaviour.
But report it, because that subject gets no variety.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(director): quality floor from the frozen phase-3 baseline; pace judged by measured cadence" -- engine/director/floor.py engine/tests/test_director_floor.py
```

## Chunk 3: Memory, choosing the direction, wiring into the job and pipeline

### Task 42: Variety memory (issued tokens, validated ids, per user+subject lock)

**Files:**
- Create: `engine/director/memory.py`
- Test: `engine/tests/test_director_memory.py`

- [ ] **Step 1: Write the failing test:**

```python
import json
import threading

import pytest

from engine.director.direction import AXES, direction_of
from engine.director.memory import MAX_ENTRIES, MemoryBusy, VarietyMemory, issue_user_token

AX = {"world": "studio_cyc", "mood": "clean", "tone": "white", "pace": "calm", "opener": "arc_orbit",
      "weather": "dry", "wind": "calm"}
KNOWN = {"world": ["studio_cyc"], "mood": ["clean", "vivid", "noir", "teal_night", "warm_golden", "premium_dark"],
         "tone": ["white", "grey", "black"], "pace": ["calm", "medium", "hype"], "opener": ["low_hero_push", "arc_orbit"],
         "weather": ["dry", "rain"], "wind": ["calm", "windy"]}
S = "0123456789abcdef"


def _d(mood="clean"):
    return direction_of({**AX, "mood": mood}, "dice")


@pytest.fixture
def u():
    return issue_user_token()


def test_tokens_are_random_and_well_formed():
    a, b = issue_user_token(), issue_user_token()
    assert a != b and a.startswith("u_") and len(a) == 34


def test_record_and_recent_in_order(tmp_path, u):
    m = VarietyMemory(tmp_path)
    m.record(u, S, _d("clean"), seed=1, duration_s=10, known=KNOWN)
    m.record(u, S, _d("vivid"), seed=2, duration_s=8, known=KNOWN)
    assert m.recent(u, S) == [_d("clean").id, _d("vivid").id] and m.recent(issue_user_token(), S) == []


def test_only_catalog_validated_values_are_stored(tmp_path, u):
    m = VarietyMemory(tmp_path)
    with pytest.raises(ValueError):
        m.record(u, S, direction_of({**AX, "mood": "call_me_555_1234"}, "dice"), seed=1, duration_s=10, known=KNOWN)
    with pytest.raises(ValueError):
        m.dislike(u, S, {"mood": ["my name is alice"]}, known=KNOWN)
    assert not list(tmp_path.rglob("*.json"))


def test_files_hold_no_raw_ids_and_only_known_fields(tmp_path, u):
    m = VarietyMemory(tmp_path)
    m.record(u, S, _d(), seed=1, duration_s=10, known=KNOWN)
    assert not any(u in p.name or S in p.name for p in tmp_path.rglob("*"))
    doc = json.loads(next(tmp_path.rglob("*.json")).read_text(encoding="utf-8"))
    assert set(doc["entries"][0]) == {"id", "seed", "durationS", "source", "day"}


@pytest.mark.parametrize("bad", ["", "alice@example.com", "u_short", "../x", "u_" + "é" * 32, None, 5])
def test_only_issued_user_tokens_are_accepted(tmp_path, bad):
    with pytest.raises(ValueError):
        VarietyMemory(tmp_path).recent(bad, S)


def test_entries_capped_and_corrupt_file_reads_empty(tmp_path, u):
    m = VarietyMemory(tmp_path)
    for i in range(MAX_ENTRIES + 3):
        m.record(u, S, _d(), seed=i, duration_s=10, known=KNOWN)
    assert len(m.recent(u, S)) == MAX_ENTRIES
    next(tmp_path.rglob("*.json")).write_text("{not json", encoding="utf-8")
    assert m.recent(u, S) == []


def test_dislikes_merge_and_cap(tmp_path, u):
    m = VarietyMemory(tmp_path)
    m.dislike(u, S, {"mood": ["noir"], "opener": ["arc_orbit"]}, known=KNOWN)
    m.dislike(u, S, {"mood": ["vivid", "clean", "teal_night", "warm_golden"]}, known=KNOWN)
    av = m.avoided(u, S)
    assert set(av) == {"mood", "opener"} and len(av["mood"]) == 3 and "noir" not in av["mood"]


def test_lock_serializes_read_modify_write(tmp_path, u):
    m, errors = VarietyMemory(tmp_path), []

    def worker(i):
        try:
            with m.locked(u, S):
                n = len(m.recent(u, S))
                m.record(u, S, _d(), seed=n, duration_s=10, known=KNOWN)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and len(m.recent(u, S)) == 12
    seeds = [e["seed"] for e in json.loads(next(tmp_path.rglob("*.json")).read_text(encoding="utf-8"))["entries"]]
    assert seeds == list(range(12))                          # no lost update, no interleaving


def test_busy_lock_times_out(tmp_path, u, monkeypatch):
    import engine.director.memory as mm
    monkeypatch.setattr(mm, "LOCK_TIMEOUT_S", 0.05)
    m = VarietyMemory(tmp_path)
    with m.locked(u, S):
        with pytest.raises(MemoryBusy):
            with m.locked(u, S):
                pass


def test_forget_deletes_one_user(tmp_path, u):
    m, v = VarietyMemory(tmp_path), issue_user_token()
    m.record(u, S, _d(), seed=1, duration_s=10, known=KNOWN)
    m.record(v, S, _d(), seed=1, duration_s=10, known=KNOWN)
    m.forget(u)
    assert m.recent(u, S) == [] and m.recent(v, S) != []


def test_env_var_sets_the_root(tmp_path, monkeypatch):
    monkeypatch.setenv("VALORA_VARIETY_DIR", str(tmp_path / "mem"))
    assert VarietyMemory().root == tmp_path / "mem"
    assert set(AXES) == set(KNOWN)
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/memory.py`:**

```python
"""Variety memory (spec §6 layer 3): per user and per subject, the directions used and the values the
user disliked. Local files only. Privacy by construction:
- users are identified only by RANDOM tokens we issue (issue_user_token); an email or a guessable id is
  rejected, and the token is hashed again before it touches a path;
- only catalog-validated values are stored (every axis value must be in `known`), so no free text
  (prompts, names) can reach a file;
- files are bounded, writes atomic, a corrupt file reads as empty, and forget(user) serves deletion.
Concurrency: locked(user, subject) is an exclusive lock file around read -> roll -> record, so two
simultaneous jobs for the same user+subject never pick the same direction or lose history."""
import contextlib
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from engine.director.direction import AXES, parse_id

MEMORY_ENV = "VALORA_VARIETY_DIR"
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "var" / "variety"
MAX_ENTRIES = 50           # (eng) far above any viable pool today; bounds the file
MAX_DISLIKES_PER_AXIS = 3  # (eng)
MAX_FILE_BYTES = 256_000
LOCK_TIMEOUT_S = 10.0      # (eng)
STALE_LOCK_S = 60.0        # (eng) a crashed holder's lock is broken after this
_USER = re.compile(r"^u_[A-Za-z0-9_-]{32}$")
_SUBJECT = re.compile(r"^(?:[0-9a-f]{16}|s_[A-Za-z0-9_-]{16,64})$")


class MemoryBusy(RuntimeError):
    pass


def issue_user_token():
    return "u_" + secrets.token_urlsafe(24)       # 24 random bytes -> 32 url-safe characters


def _key(value, rx, what):
    if not isinstance(value, str) or not rx.match(value):
        raise ValueError(f"variety memory: bad {what} (use an issued token / subject key)")
    return hashlib.sha256(f"valora-variety:{value}".encode()).hexdigest()[:24]


def _check_axes(axes, known):
    bad = [a for a in AXES if axes.get(a) not in known.get(a, ())]
    if bad:
        raise ValueError(f"variety memory: values not in the catalog for {bad}")


class VarietyMemory:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get(MEMORY_ENV) or DEFAULT_DIR)

    def _dir(self, user):
        return self.root / _key(user, _USER, "user token")

    def _path(self, user, subject):
        return self._dir(user) / f"{_key(subject, _SUBJECT, 'subject key')}.json"

    @contextlib.contextmanager
    def locked(self, user, subject):
        p = self._path(user, subject).with_suffix(".lock")
        p.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while True:
            try:
                fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    if time.time() - p.stat().st_mtime > STALE_LOCK_S:
                        os.remove(p)
                        continue
                except OSError:
                    continue
                if time.monotonic() > deadline:
                    raise MemoryBusy("variety memory is busy for this user and subject")
                time.sleep(0.01)
        try:
            yield
        finally:
            os.close(fd)
            with contextlib.suppress(OSError):
                os.remove(p)

    def _load(self, user, subject):
        p = self._path(user, subject)
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                return {"entries": [], "dislikes": {}}
            doc = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(doc.get("entries"), list) or not isinstance(doc.get("dislikes", {}), dict):
                raise ValueError
            return {"entries": doc["entries"], "dislikes": doc.get("dislikes", {})}
        except (OSError, ValueError, AttributeError):
            return {"entries": [], "dislikes": {}}

    def _save(self, user, subject, doc):
        p = self._path(user, subject)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            os.replace(tmp, p)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def recent(self, user, subject):
        out = []
        for e in self._load(user, subject)["entries"]:
            try:
                parse_id(e["id"])
                out.append(e["id"])
            except (TypeError, KeyError, ValueError):
                continue
        return out

    def record(self, user, subject, direction, *, seed, duration_s, known):
        _check_axes(direction.axes(), known)
        if isinstance(seed, bool) or not isinstance(seed, int) or not isinstance(duration_s, (int, float)):
            raise ValueError("variety memory: seed must be an int and duration a number")
        doc = self._load(user, subject)
        doc["entries"] = (doc["entries"] + [{"id": direction.id, "seed": seed, "durationS": duration_s,
                                             "source": direction.source,
                                             "day": datetime.date.today().isoformat()}])[-MAX_ENTRIES:]
        self._save(user, subject, doc)

    def avoided(self, user, subject):
        return {a: list(v) for a, v in self._load(user, subject)["dislikes"].items() if a in AXES and v}

    def dislike(self, user, subject, avoid, *, known):
        bad = [f"{a}={v}" for a, vals in (avoid or {}).items() for v in vals
               if a not in AXES or v not in known.get(a, ())]
        if bad:
            raise ValueError(f"variety memory: unknown dislike values {bad}")
        doc = self._load(user, subject)
        for axis, vals in avoid.items():
            merged = [v for v in doc["dislikes"].get(axis, []) if v not in vals] + list(vals)
            doc["dislikes"][axis] = merged[-MAX_DISLIKES_PER_AXIS:]
        self._save(user, subject, doc)

    def forget(self, user):
        shutil.rmtree(self._dir(user), ignore_errors=True)
```

- [ ] **Step 4: Run.** PASS. Then run the lock test 20 times to shake out flakes:
  `py -m pytest engine/tests/test_director_memory.py::test_lock_serializes_read_modify_write -q --count 20`
  (if `pytest-repeat` is missing, loop it 20 times from a small `py` script instead).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): variety memory - issued tokens, catalog-validated ids, per user+subject lock" -- engine/director/memory.py engine/tests/test_director_memory.py
```

### Task 43: Choosing the direction — more like this, dice, interim+pins; replay; honesty

**Files:**
- Create: `engine/director/variety.py`
- Test: `engine/tests/test_director_variety.py`

- [ ] **Step 1: Write the failing test:**

```python
import pytest

from engine.catalog import Catalog
from engine.director.baseline_phase3 import profile_key
from engine.director.direction import make_id
from engine.director.job import make_job
from engine.director.variety import DirectionIncompatible, choose_direction, reachable, subject_key
from engine.tests.test_director_package import _p

FMT = {"aspect": "9:16", "durationS": 10, "fps": 30}


def _choose(prompt="", seed=1, model="pocket_watch", **kw):
    cat, p = Catalog.load(), _p(model)
    return choose_direction(prompt, p, cat, seed, FMT, job=make_job("a 10 second clip", p, cat, seed=seed), **kw)


def test_empty_prompt_rolls_dice_with_one_assumption_line():
    c = _choose()
    assert c.direction.source == "dice" and "dice" in c.notes[0]


def test_prompt_pins_beat_the_dice_including_world_and_opener():
    for s in range(6):
        d = _choose("luxury, slow, studio, orbiting", seed=s).direction
        assert (d.mood, d.pace, d.world, d.opener) == ("premium_dark", "calm", "studio_cyc", "arc_orbit")
        assert d.pinned == ("mood", "opener", "pace", "world")


def test_pins_survive_the_interim_fallback(monkeypatch):
    import engine.director.variety as v
    monkeypatch.setattr(v, "make_viable", lambda *a, **k: (lambda axes: False))
    d = _choose("neon, slow", seed=3).direction
    assert d.source == "interim" and (d.mood, d.pace) == ("teal_night", "calm") and "mood" in d.pinned


def test_more_like_this_keeps_the_direction_and_pins_still_win():
    first = _choose(seed=1).direction
    assert _choose(seed=99, like=first).direction.axes() == first.axes()
    d = _choose("neon", seed=5, like={"direction": {"id": first.id}}).direction
    assert d.mood == "teal_night" and d.opener == first.opener and d.source == "more_like_this"


@pytest.mark.parametrize("like", ["nonsense", "studio_cyc/<b>/black/calm/arc_orbit/dry/calm",
                                  "moon_world/clean/white/calm/arc_orbit/dry/calm"])
def test_like_unknown_or_foreign_values_is_an_explicit_error(like):
    with pytest.raises(DirectionIncompatible) as e:
        _choose(like=like)
    assert "can't be used for this model" in str(e.value)


def test_like_below_the_floor_is_an_explicit_error(monkeypatch):
    import engine.director.variety as v
    monkeypatch.setattr(v, "make_viable", lambda *a, **k: (lambda axes: False))
    with pytest.raises(DirectionIncompatible, match="quality"):
        _choose(like=_choose(seed=1).direction)


def test_avoid_with_unknown_values_is_an_explicit_error():
    with pytest.raises(DirectionIncompatible):
        _choose(avoid={"mood": ["purple_rain"]})


def test_history_is_rotated():
    hist = [_choose(seed=s).direction.id for s in range(3)]
    for s in range(10, 14):
        assert _choose(seed=s, history=hist).direction.id not in hist


def test_subject_key_matches_the_frozen_baseline_key():
    p = _p("pocket_watch")
    assert subject_key(p) == profile_key(p) and subject_key(p) != subject_key(_p("sneaker"))


def test_reachable_uses_pins_format_and_viability():
    cat, p = Catalog.load(), _p("pocket_watch")
    job = make_job("a 10 second clip", p, cat, seed=0)
    free, pinned = reachable(p, cat, FMT, job=job), reachable(p, cat, FMT, job=job, prompt="luxury, slow")
    assert pinned["combinations"] < free["combinations"] and "viable" in free and free["viable"] <= free["combinations"]
    assert "world" in free["singleValued"] and "note" in free
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/variety.py`:**

```python
"""Stage 2 of spec §3: the job's direction. Order:
1. 'more like this': keep a validated direction with a new seed, so only layer 1 changes;
2. the dice: pins from the prompt, history rotated over the viable pool, dislikes avoided, the floor
   enforced;
3. the interim direction with the prompt's pins applied (pins are never dropped).
Pure: the caller holds the memory lock and reads/writes memory (pipeline.py).
Replay never comes here: replay() returns the saved checked script (no provider call)."""
from dataclasses import dataclass

from engine.catalog import Catalog  # noqa: F401  (type context)
from engine.director.axes import DICE, axis_values, validate_axes
from engine.director.baseline_phase3 import profile_key
from engine.director.dice import candidates, roll
from engine.director.direction import AXES, Direction, direction_of, interim_direction, parse_id
from engine.director.family import family
from engine.director.floor import make_viable
from engine.director.pins import read_direction_pins
from engine.director.taste import STATS

REPLAY_SCHEMA = "valora.replay/1"
FLAG_NOTES = {"avoid_relaxed": "every option was on your 'less like this' list; relaxed it to find one",
              "repeat_after_rotation": "every direction for this model has been used once; starting a new round"}


class DirectionIncompatible(ValueError):
    """A 'more like this' / 'less like this' request this model or catalog cannot honour (plain words)."""


@dataclass(frozen=True)
class Choice:
    direction: Direction
    notes: tuple = ()
    flags: tuple = ()


def subject_key(profile):
    return profile_key(profile)


def _load_stats():
    import json
    try:
        return json.loads(STATS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def prompt_pins(prompt, profile, catalog, fmt):
    known = axis_values(profile, catalog, fmt, rollable=False)
    return {a: v for a, v in read_direction_pins(prompt).items() if v in known[a]}


def like_axes(like, profile, catalog, fmt):
    try:
        if isinstance(like, Direction):
            axes = like.axes()
        elif isinstance(like, dict):
            axes = parse_id((like.get("direction") or like)["id"])
        else:
            axes = parse_id(str(like))
    except (KeyError, TypeError, ValueError):
        raise DirectionIncompatible("that 'more like this' reference can't be used for this model: "
                                    "it is not a saved direction") from None
    bad = validate_axes(axes, profile, catalog, fmt)
    if bad:
        raise DirectionIncompatible(f"that direction can't be used for this model: {', '.join(bad)} "
                                    "is not available here")
    return axes


def check_avoid(avoid, profile, catalog, fmt):
    known = axis_values(profile, catalog, fmt, rollable=False)
    bad = [f"{a}={v}" for a, vals in (avoid or {}).items() for v in vals if a not in AXES or v not in known[a]]
    if bad:
        raise DirectionIncompatible(f"'less like this' names things this model doesn't have: {', '.join(bad)}")
    return avoid


def _line(d):
    words = f"{d.mood}, {d.pace} pace, {d.tone} backdrop, opens with {d.opener}"
    kept = f"; kept from the prompt: {', '.join(d.pinned)}" if d.pinned else ""
    return f"dice direction: {words}{kept}"


def choose_direction(prompt, profile, catalog, seed, fmt, *, job=None, like=None, avoid=None, history=(),
                     stats=None):
    pins = prompt_pins(prompt, profile, catalog, fmt)
    avoid = check_avoid(avoid, profile, catalog, fmt)
    viable = make_viable(job, profile, catalog) if job is not None else None
    if like is not None:
        axes = {**like_axes(like, profile, catalog, fmt), **pins}
        if viable is not None and not viable(axes):
            raise DirectionIncompatible("that direction doesn't meet the quality bar for this model; "
                                        "try 'new direction' instead")
        d = direction_of(axes, "more_like_this", pinned=pins)
        return Choice(d, (f"more like this: kept the direction ({d.mood}, {d.pace} pace); only details change",))
    r = roll(seed, axis_values(profile, catalog, fmt), pins=pins, history=history, avoid=avoid, viable=viable,
             family_name=family(profile), stats=_load_stats() if stats is None else stats)
    if r.axes is None:
        base = parse_id(interim_direction(seed, profile, catalog).id)
        d = direction_of({**base, **pins}, "interim", pinned=pins)
        return Choice(d, ("no rolled direction met the quality floor; used the default direction",), r.flags)
    d = direction_of(r.axes, "dice", pinned=pins)
    return Choice(d, (_line(d),) + tuple(FLAG_NOTES[f] for f in r.flags if f in FLAG_NOTES), r.flags)


def reachable(profile, catalog, fmt, job=None, prompt=""):
    """Catalog-size honesty (spec §6 'honest limit') for THIS prompt: the same pins, format and
    viability rules the dice use."""
    pins = prompt_pins(prompt, profile, catalog, fmt)
    vals = axis_values(profile, catalog, fmt)
    cands = candidates(vals, pins)
    out = {"pins": pins, "perAxis": vals, "combinations": len(cands),
           "singleValued": [a for a in AXES if a not in pins and len(vals[a]) == 1]}
    if job is not None:
        v = make_viable(job, profile, catalog)
        out["viable"], out["floor"] = sum(1 for c in cands if v(c)), v.floor
    n = out.get("viable", out["combinations"])
    out["distinctBeforeRepeat"] = n
    out["note"] = (f"{n} distinct directions for this model and prompt; axes with one value: "
                   f"{', '.join(out['singleValued']) or 'none'}. Perceived variety is capped by the catalog.")
    return out
```

`validate_axes` is from Task 36. Replay (`replay_record`, `replay`) arrives in Task 46, next to the
pipeline that fills it.

- [ ] **Step 4: Run.** PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): choose_direction (validated more-like-this, dice, interim with pins); honesty per prompt" -- engine/director/variety.py engine/tests/test_director_variety.py
```

### Task 44: Wire the dice into the job (duration order fixed)

Re-read `engine/director/job.py`, `intent.py` and `pipeline.py` at HEAD.

**Duration order:** a prompt pin beats an explicit `duration`, which beats a liked script's duration,
which beats the rolled one. The duration is decided after the seed is validated (the roll needs the
final seed) and before the format is built.

**Files:**
- Modify: `engine/director/intent.py` (`make_format`)
- Modify: `engine/director/job.py` (`Job`, `make_job`)
- Modify: `engine/director/pipeline.py` (`direct` gains `duration=None`, forwarded to `make_job`. Forwarding only; Task 46 adds the rest)
- Test: add to `engine/tests/test_director_variety.py`

- [ ] **Step 1: Write the failing tests** (append):

```python
def test_make_job_uses_the_dice_and_rolls_duration():
    cat, p = Catalog.load(), _p("pocket_watch")
    jobs = [make_job("", p, cat, seed=s) for s in range(12)]
    assert all(j.direction.source == "dice" for j in jobs)
    assert {j.fmt["durationS"] for j in jobs} <= {8, 10, 12} and len({j.fmt["durationS"] for j in jobs}) > 1
    assert any("dice direction" in n for n in jobs[0].notes)


def test_duration_order_pin_explicit_liked_rolled():
    cat, p = Catalog.load(), _p("pocket_watch")
    liked = {"direction": {"id": make_job("", p, cat, seed=1).direction.id}, "format": {"durationS": 12}}
    assert make_job("a 15 second clip", p, cat, seed=1, duration=8, like=liked).fmt["durationS"] == 15
    assert make_job("", p, cat, seed=1, duration=8, like=liked).fmt["durationS"] == 8
    assert make_job("", p, cat, seed=5, like=liked).fmt["durationS"] == 12


def test_given_direction_is_used_verbatim():
    cat, p = Catalog.load(), _p("pocket_watch")
    d = make_job("", p, cat, seed=1).direction
    assert make_job("", p, cat, seed=77, direction=d, duration=10).direction == d


def test_incompatible_like_is_director_input_error():
    from engine.director.job import DirectorInputError
    cat, p = Catalog.load(), _p("pocket_watch")
    with pytest.raises(DirectorInputError):
        make_job("", p, cat, seed=1, like="moon/clean/white/calm/arc_orbit/dry/calm")


def test_direct_forwards_duration():
    from engine.director.llm import FakeProvider
    from engine.director.pipeline import direct
    r = direct("", _p("pocket_watch"), provider=FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3),
               seed=3, duration=10)
    assert r.script["format"]["durationS"] == 10
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement.**

`intent.make_format(pins, seed=None, duration=None)`: change the duration line to
`d = pins.get("durationS", DEFAULT_DURATION_S if duration is None else duration)`.

`job.py`: add `varietyFlags: list = field(default_factory=list)` to `Job`. Then change `make_job`:

```python
def make_job(prompt, profile, catalog, seed=None, markers=None, direction=None, *, like=None, avoid=None,
             history=(), duration=None, stats=None):
    ...                                   # prompt checks unchanged
    seed = secrets.randbelow(SEED_LIMIT) if seed is None else seed
    ...                                   # seed validation unchanged: it must finish before the roll
    pins = read_pins(prompt)
    if "durationS" not in pins and duration is None:
        liked = like.get("format", {}).get("durationS") if isinstance(like, dict) else None
        duration = liked if liked is not None else (None if direction is not None else roll_duration(seed))
    fmt = make_format(pins, seed, duration=duration)
    ...                                   # markers unchanged
    job = Job(prompt=prompt, seed=seed, fmt=fmt, direction=direction or interim_direction(seed, profile, catalog),
              family=family(profile), pins=pins, markers=markers, detected=unsupported(asks, catalog, profile),
              asks=asks, notes=format_notes(pins, fmt))
    if direction is None:
        try:
            c = choose_direction(prompt, profile, catalog, seed, fmt, job=job, like=like, avoid=avoid,
                                 history=history, stats=stats)
        except DirectionIncompatible as e:
            raise DirectorInputError(str(e)) from e
        job = dataclasses.replace(job, direction=c.direction, notes=job.notes + list(c.notes),
                                  varietyFlags=list(c.flags))
    return job
```

Import `dataclasses`, `roll_duration`, `choose_direction` and `DirectionIncompatible`. If importing
`engine.director.variety` at module level creates a cycle (`variety → floor → fallback`; and
`fallback` must never import `job`), import it inside `make_job`.

`pipeline.direct`: add `duration=None` to the signature and pass `duration=duration` to `make_job`.
Nothing else changes in this task.

- [ ] **Step 4: Run** the new tests, then the whole fast loop.

- [ ] **Step 5: Fix the expected breakages. Only these kinds are allowed:**
  - Tests that feed a 10 s `FakeProvider` reply (e.g. `test_director_pipeline.py`,
    `test_director_recorded.py`, `test_cli.py::test_direct_with_a_fake_provider`) now get a rolled
    8/10/12 s job, so the reply breaks shot contiguity and falls back. Fix: pass `duration=10` to that
    `direct(...)` call (it exists from this task), or add "10 seconds" to the prompt for CLI tests. Never
    weaken an assertion.
  - Tests asserting exact `assumptions` lists now see one extra `dice direction: ...` line. Update the
    expected list and say so in the commit.
  - Anything else red: **stop and investigate** (@superpowers:systematic-debugging).

  Those test files belong to phase 3: re-read each one and edit only the failing call sites.

- [ ] **Step 6: Commit** (name every touched test file):

```bash
git commit -m "feat(director): the job rolls its direction and duration from the dice; direct(duration=)" -- engine/director/intent.py engine/director/job.py engine/director/pipeline.py engine/tests/test_director_variety.py <each phase-3 test file you edited>
```

### Task 45: Direction adherence (grade swap, measured cadence, repair on drift); the director sees world + opener

**Rules:**
- **Enforce** means the prompt is vague, or the axis is pinned.
- **mood:** a `mood_grade` preset is set in place (a missing preset counts as the catalog default). Any
  other grade (e.g. `neutral_film`) is **replaced** with `{"id": "mood_grade", "params": {"preset": mood}}`.
- **tone:** the `studio_cyc` tone is set in place (missing = default).
- **pace:** the `sequence` pace is set in place. Then the **measured** cut count must fit the pace
  (`floor.cadence_ok`), otherwise the error `direction_cadence` goes back to the LLM through the repair
  loop, with the shot range it needs.
- **world / opener:** a mismatch is the error `direction_world` / `direction_opener` (repair loop).
- When not enforcing, every mismatch is `direction_drift` (`info`, measured only).

Errors go through the existing repair loop. After 2 repairs the fallback, which honours the direction
by construction, takes over.

**Files:**
- Create: `engine/director/adherence.py`
- Modify: `engine/director/pipeline.py` (`_evaluate_reply`), `engine/director/request.py` (`first_message`),
  `engine/director/repair.py` (hints for the three new codes, if it keeps a hint table), `engine/director/rulebook.py`
  (`DEFAULT`), `engine/director/rulebook/rulebook.txt` (regenerated)
- Test: `engine/tests/test_director_adherence.py`

- [ ] **Step 1: Write the failing test:**

```python
import copy
import json

from engine.catalog import Catalog
from engine.director.adherence import drift, enforce_direction
from engine.director.direction import direction_of
from engine.director.floor import cadence_range
from engine.director.rulebook import EXAMPLES_DIR, example_script

AX = {"world": "studio_cyc", "mood": "teal_night", "tone": "black", "pace": "calm", "opener": "low_hero_push",
      "weather": "dry", "wind": "calm"}
S = example_script(json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8")))
CAT = Catalog.load()


def _drifted():
    s = copy.deepcopy(S)
    s["grade"] = {"id": "neutral_film", "params": {}}
    s.setdefault("edit", {"id": "sequence", "params": {}})["params"]["pace"] = "hype"
    s["world"] = {"id": "studio_cyc", "params": {}}          # tone omitted -> catalog default (grey)
    return s


def test_drift_resolves_defaults_and_sees_neutral_film():
    assert set(drift(_drifted(), direction_of(AX, "dice"), CAT)) >= {"mood", "pace", "tone"}


def test_vague_prompt_swaps_the_grade_and_sets_tone_and_pace():
    s, issues = enforce_direction(_drifted(), direction_of(AX, "dice"), CAT, enforce=True)
    assert s["grade"] == {"id": "mood_grade", "params": {"preset": "teal_night"}}
    assert s["world"]["params"]["tone"] == "black" and s["edit"]["params"]["pace"] == "calm"
    assert "direction_enforced" in {i.code for i in issues}


def test_cadence_is_measured_not_assumed():
    s = _drifted()
    lo, hi = cadence_range("calm", s["format"]["durationS"], CAT)
    if not lo <= len(s["shots"]) <= hi:
        _, issues = enforce_direction(s, direction_of(AX, "dice"), CAT, enforce=True)
        assert any(i.code == "direction_cadence" and i.severity == "error" for i in issues)
    s2 = copy.deepcopy(s)
    s2["shots"] = s2["shots"][:1] * (hi + 2)
    _, issues = enforce_direction(s2, direction_of(AX, "dice"), CAT, enforce=True)
    assert any(i.code == "direction_cadence" and i.severity == "error" for i in issues)


def test_opener_and_world_drift_go_to_repair_when_enforced():
    s = copy.deepcopy(S)
    _, issues = enforce_direction(s, direction_of({**AX, "opener": "arc_orbit"}, "dice"), CAT, enforce=True)
    if s["shots"][0]["camera"]["id"] != "arc_orbit":
        assert any(i.code == "direction_opener" and i.severity == "error" for i in issues)


def test_long_prompt_only_enforces_pins():
    d = direction_of(AX, "dice", pinned={"mood": "teal_night"})
    s, issues = enforce_direction(_drifted(), d, CAT, enforce=False)
    assert s["grade"]["params"]["preset"] == "teal_night" and s["edit"]["params"]["pace"] == "hype"
    assert any(i.code == "direction_drift" and i.severity == "info" for i in issues)
    assert not any(i.severity == "error" for i in issues)


def test_first_message_carries_world_and_opener_never_wind():
    from engine.director.request import first_message
    from engine.tests.test_director_package import _p
    msg = first_message(fmt={"aspect": "9:16", "durationS": 10, "fps": 30}, direction=direction_of(AX, "dice"),
                        profile=_p("pocket_watch"), prompt="", markers=[], detected=[])
    job = json.loads(msg.split("<job>")[1].split("</job>")[0])
    assert job["direction"]["opener"] == "low_hero_push" and job["direction"]["world"] == "studio_cyc"
    assert "weather" not in job["direction"] and "wind" not in job["direction"]
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/adherence.py`:**

```python
"""Keep the LLM on the rolled direction (spec §3: variety comes from the dice; §11: the LLM converges on
one safe look). Values resolve catalog defaults. Enforced on vague prompts and for pinned axes:
- mood swaps any grade for mood_grade(preset); tone and pace are set in place;
- the pace is then checked as CUT (measured shot count, floor.cadence_ok);
- a cadence, world or opener mismatch is an error, which goes back to the LLM through the repair loop.
Otherwise every mismatch is info-level drift (measured, not changed)."""
from engine.director.axes import opener_of
from engine.director.floor import cadence_ok, cadence_range
from engine.issues import Issue

_PATHS = {"mood": ("grade", "preset", "mood_grade"), "pace": ("edit", "pace", "sequence"),
          "tone": ("world", "tone", "studio_cyc")}


def _value(script, axis, catalog):
    key, param, bid = _PATHS[axis]
    ref = script.get(key)
    if not isinstance(ref, dict):
        return None
    if ref.get("id") != bid:
        return "clean" if axis == "mood" and ref.get("id") == "neutral_film" else f"<{ref.get('id')}>"
    params = ref.get("params") if isinstance(ref.get("params"), dict) else {}
    return params.get(param, catalog.get(key, bid)["params"][param]["default"])


def drift(script, d, catalog):
    out = [a for a in _PATHS if _value(script, a, catalog) not in (None, getattr(d, a))]
    if isinstance(script.get("world"), dict) and script["world"].get("id") != d.world:
        out.append("world")
    try:
        if opener_of(script) != d.opener:
            out.append("opener")
        if not cadence_ok(script, d.pace, catalog):
            out.append("cadence")
    except (KeyError, IndexError, TypeError):
        pass
    return out


def enforce_direction(script, d, catalog, enforce):
    issues = []
    for axis in drift(script, d, catalog):
        on = enforce or axis in d.pinned or (axis == "cadence" and "pace" in d.pinned)
        if not on:
            issues.append(Issue("direction_drift", axis, f"script differs from the direction on {axis}", "info"))
            continue
        if axis == "mood":
            if (script.get("grade") or {}).get("id") != "mood_grade":
                script["grade"] = {"id": "mood_grade", "params": {"preset": d.mood}}
            else:
                script["grade"].setdefault("params", {})["preset"] = d.mood
            issues.append(Issue("direction_enforced", "grade", f"mood -> {d.mood}", "repaired"))
        elif axis in ("pace", "tone"):
            key, param, _ = _PATHS[axis]
            if isinstance(script.get(key), dict) and script[key].get("id") == _PATHS[axis][2]:
                script[key].setdefault("params", {})[param] = getattr(d, axis)
                issues.append(Issue("direction_enforced", f"{key}.params.{param}", f"-> {getattr(d, axis)}",
                                    "repaired"))
            elif axis == "tone":
                issues.append(Issue("direction_drift", axis, "world has no tone to set", "info"))
        elif axis == "cadence":
            continue                              # judged after pace is set, below
        else:
            issues.append(Issue(f"direction_{axis}", axis,
                                f"use {axis} '{getattr(d, axis)}' as the job's direction asks", "error"))
    try:
        if (enforce or "pace" in d.pinned) and not cadence_ok(script, d.pace, catalog):
            lo, hi = cadence_range(d.pace, script["format"]["durationS"], catalog)
            issues.append(Issue("direction_cadence", "shots",
                                f"a {d.pace} pace needs {lo}-{hi} shots in this duration", "error"))
    except (KeyError, TypeError):
        pass
    return script, issues
```

- [ ] **Step 4: Wire it in.** Make three changes:
  - `pipeline._evaluate_reply`: after `script, sissues = sanitize(...)`, when `script` is a dict with a
    `shots` list, add these lines:
    `script, dissues = enforce_direction(script, job.direction, catalog, enforce=is_vague(job.prompt))`,
    then `script = vary_details(script, job.seed, catalog)` (Task 40a), then
    `sissues = sissues + dissues`. The checker runs after that, as before. `direction_*` errors join
    the issue list and flow through the existing `problems(...)` / repair message. If `repair.py`
    keeps a hint table keyed by code, add one plain hint each for `direction_cadence`,
    `direction_opener` and `direction_world`.
  - `request.first_message`: the `"direction"` dict adds `"world"` and `"opener"` (via `getattr` with
    defaults). Never weather or wind.
  - `rulebook.DEFAULT` item 1 becomes: "The job's direction is the brief: its mood is the mood_grade
    preset, its pace the sequence pace (and the number of shots that pace allows), its tone the
    studio_cyc tone, its world the world block and its opener the first shot's camera. When the prompt
    is short the system enforces all of them."

- [ ] **Step 5: Regenerate the rulebook.** Run `py -m engine.director.rulebook --write`, then
  `git diff --stat -- engine/director/rulebook/rulebook.txt`. If the diff holds another lane's
  uncommitted edits (changes outside part 4), **do not commit rulebook.txt**. Say so in the
  handoff; the rulebook equality test tells that lane to regenerate.

- [ ] **Step 6: Run** the adherence, request, rulebook and pipeline tests, then the fast loop. The pipeline
  fixtures built on the 10 s examples must still pass on the first call. If one now fails only on
  `direction_*`, the example contradicts the rolled direction: pass `direction=` matching the
  example's grade/pace/tone in that test (this is a test-setup fix, not a weakening), and note it.

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(director): enforce the rolled direction (grade swap, measured cadence, repair on drift)" -- engine/director/adherence.py engine/director/pipeline.py engine/director/request.py engine/director/repair.py engine/director/rulebook.py engine/director/rulebook/rulebook.txt engine/tests/test_director_adherence.py
```

### Task 46: Pipeline — locked memory, final-script floor gate, like/avoid, replay without the provider

Re-read `engine/director/pipeline.py` at HEAD.

**Files:**
- Modify: `engine/director/pipeline.py` (`DirectorResult`, `direct`)
- Modify: `engine/director/variety.py` (add `replay_record`, `replay`, `ReplayStale`)
- Test: `engine/tests/test_director_replay.py`

- [ ] **Step 1: Write the failing test:**

```python
import threading

import pytest

from engine.catalog import Catalog
from engine.director.distance import script_distance
from engine.director.floor import _RANK, floor_tier, script_tier
from engine.director.llm import FakeProvider
from engine.director.memory import VarietyMemory, issue_user_token
from engine.director.pipeline import direct
from engine.director.variety import ReplayStale, replay, subject_key
from engine.tests.test_director_package import _p

REFUSE = [{"stop_reason": "refusal", "text": ""}]


class NoCalls:
    def generate(self, **kw):
        raise AssertionError("replay must never call the provider")


def _run(seed, **kw):
    return direct(kw.pop("prompt", ""), _p("pocket_watch"), provider=FakeProvider(REFUSE * 3), seed=seed, **kw)


def test_replay_returns_the_saved_script_without_calling_the_provider():
    a = _run(5)
    b = replay(a.replay, _p("pocket_watch"), Catalog.load(), provider=NoCalls())
    assert b.script == a.script and b.source == "replay" and b.direction["id"] == a.direction["id"]
    assert b.script["assumptions"] == a.script["assumptions"]


def test_replay_of_a_tampered_or_stale_record_is_refused():
    a = _run(5)
    bad = {**a.replay, "script": {**a.replay["script"], "world": {"id": "moon", "params": {}}}}
    with pytest.raises(ReplayStale):
        replay(bad, _p("pocket_watch"), Catalog.load())
    with pytest.raises(ReplayStale):
        replay({**a.replay, "seed": a.replay["seed"] + 1}, _p("pocket_watch"), Catalog.load())


def test_layer_one_same_direction_and_duration_still_differs():
    a = _run(1)
    b = _run(2, like=a.script)
    assert b.direction["id"] == a.direction["id"]
    assert b.script["format"]["durationS"] == a.script["format"]["durationS"]
    assert b.script["lighting"]["params"] != a.script["lighting"]["params"]         # seeded details
    assert script_distance(a.script, b.script, Catalog.load()) > 0


def test_final_script_never_below_the_floor(monkeypatch):
    import json
    from engine.director.rulebook import EXAMPLES_DIR
    watch = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]
    import engine.director.pipeline as pl
    monkeypatch.setattr(pl, "script_tier", lambda s, p, c: "T1" if s.get("assumptions", [""])[-1] != pl.FALLBACK_NOTE else "T3")
    r = direct("luxury", _p("pocket_watch"), provider=FakeProvider([watch]), seed=11, duration=10)
    assert r.source.endswith("+floor")


def test_memory_rotates_under_the_lock(tmp_path):
    mem, u = VarietyMemory(tmp_path), issue_user_token()
    ids = [_run(s, memory=mem, user=u).direction["id"] for s in range(5)]
    assert len(set(ids)) == 5 and mem.recent(u, subject_key(_p("pocket_watch"))) == ids


def test_concurrent_jobs_same_user_and_subject_get_distinct_directions(tmp_path):
    mem, u, out = VarietyMemory(tmp_path), issue_user_token(), []
    ts = [threading.Thread(target=lambda s=s: out.append(_run(s, memory=mem, user=u).direction["id"]))
          for s in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(out) == 6 and len(set(out)) == 6
    assert len(mem.recent(u, subject_key(_p("pocket_watch")))) == 6


def test_less_like_this_is_remembered(tmp_path):
    mem, u = VarietyMemory(tmp_path), issue_user_token()
    mood = _run(1, memory=mem, user=u).direction["axes"]["mood"]
    _run(2, memory=mem, user=u, avoid={"mood": [mood]})
    for s in range(3, 8):
        assert _run(s, memory=mem, user=u).direction["axes"]["mood"] != mood


def test_bad_user_is_input_error_and_memory_failure_never_fails_the_job(tmp_path, monkeypatch):
    from engine.director.job import DirectorInputError
    mem = VarietyMemory(tmp_path)
    with pytest.raises(DirectorInputError):
        _run(1, memory=mem, user="alice@example.com")
    u = issue_user_token()
    monkeypatch.setattr(mem, "record", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    r = _run(1, memory=mem, user=u)
    assert r.script and "memory_write_failed" in r.direction["flags"]


def test_result_reports_the_direction_and_replay_record():
    r = _run(1)
    assert set(r.direction) == {"id", "source", "axes", "pinned", "flags"}
    assert r.replay["schema"] == "valora.replay/1" and r.replay["script"] == r.script
```

`FALLBACK_NOTE` names the fallback's assumption line. Export `from engine.director.fallback import NOTE
as FALLBACK_NOTE` in `pipeline.py`. If the test's detection trick is brittle against HEAD, detect the
substitution via `r.source` alone and monkeypatch `script_tier` by call order. The assertion that
matters is: a below-floor LLM script is never delivered.

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement in `variety.py`:**

```python
class ReplayStale(ValueError):
    """The saved script no longer checks against today's catalog, or the record was altered."""


def replay_record(result, job):
    return {"schema": REPLAY_SCHEMA, "script": result.script, "seed": job.seed, "prompt": job.prompt,
            "direction": dict(result.direction), "format": dict(job.fmt), "pins": dict(job.pins),
            "assumptions": list(result.script.get("assumptions", [])), "markers": list(job.markers),
            "rulebookVersion": result.rulebookVersion}


def replay(record, profile, catalog, provider=None):
    """Return the saved checked script as a DirectorResult. Never calls `provider` (kept in the
    signature only so callers can pass one and a test can prove it is unused)."""
    from engine.checker import check
    from engine.director.pipeline import DirectorResult
    s = record.get("script") if isinstance(record, dict) else None
    if (not isinstance(s, dict) or record.get("schema") != REPLAY_SCHEMA or s.get("seed") != record.get("seed")
            or s.get("format") != record.get("format") or s.get("assumptions") != record.get("assumptions")
            or (s.get("direction") or {}).get("id") != (record.get("direction") or {}).get("id")):
        raise ReplayStale("this replay record does not match its script")
    r = check(s, profile, catalog)
    if not r.ok:
        raise ReplayStale("the saved script no longer passes today's checker: "
                          + ", ".join(sorted({i.code for i in r.issues if i.severity == "error"})))
    if r.script != s:
        raise ReplayStale("today's checker would change the saved script, so it cannot replay exactly")
    return DirectorResult(script=s, source="replay", firstPassOk=True, firstPassClean=True,
                          rulebookVersion=record.get("rulebookVersion", ""),
                          direction={**record["direction"], "source": "replay"}, replay=record)
```

- [ ] **Step 4: Implement in `pipeline.py`:**

```python
@dataclass
class DirectorResult:
    ...                                             # existing fields unchanged
    direction: dict = field(default_factory=dict)   # {id, source, axes, pinned, flags}
    replay: dict = field(default_factory=dict)      # valora.replay/1 (variety.replay_record)


def direct(prompt, profile, *, provider, catalog=None, seed=None, markers=None, direction=None, rulebook=None,
           like=None, avoid=None, user=None, subject_id=None, memory=None, duration=None):
    t0 = time.perf_counter()
    catalog = catalog or Catalog.load()
    subject = subject_id or subject_key(profile)
    flags = []
    kw = dict(seed=seed, markers=markers, direction=direction, like=like, avoid=avoid, duration=duration)
    if memory is not None and user is not None:
        try:
            with memory.locked(user, subject):               # read -> roll -> record, atomically
                stored = memory.avoided(user, subject)
                merged = {a: sorted(set(stored.get(a, [])) | set((avoid or {}).get(a, [])))
                          for a in set(stored) | set(avoid or {})}
                job = make_job(prompt, profile, catalog, history=memory.recent(user, subject),
                               **{**kw, "avoid": merged or None})
                known = axis_values(profile, catalog, job.fmt, rollable=False)
                try:
                    memory.record(user, subject, job.direction, seed=job.seed, duration_s=job.fmt["durationS"],
                                  known=known)
                    if avoid:
                        memory.dislike(user, subject, avoid, known=known)
                except OSError:
                    flags.append("memory_write_failed")
        except ValueError as e:                              # a bad user token / subject key
            if isinstance(e, DirectorInputError):
                raise
            raise DirectorInputError(str(e)) from e
        except MemoryBusy:
            flags.append("memory_busy")
            job = make_job(prompt, profile, catalog, **kw)
    else:
        job = make_job(prompt, profile, catalog, **kw)
    ...                                                      # the existing loop, unchanged
    # after `script, craft, source` are chosen (best LLM script or fallback):
    need = floor_tier(job, profile, catalog)
    if _RANK[script_tier(script, profile, catalog)] < _RANK[need]:
        fb = build_fallback(job, profile, catalog)
        if _RANK[script_tier(fb, profile, catalog)] >= _RANK[script_tier(script, profile, catalog)]:
            script, source = fb, source + "+floor"
            craft = [f.id for f in craft_failures(script, profile, catalog)]
    d = job.direction
    res = DirectorResult(..., direction={"id": d.id, "source": d.source, "axes": d.axes(),
                                         "pinned": list(d.pinned), "flags": flags + list(job.varietyFlags)})
    res.replay = replay_record(res, job)
    return res
```

Imports: `subject_key`, `replay_record` from `variety`; `MemoryBusy` from `memory`; `axis_values` from
`axes`; `_RANK`, `floor_tier`, `script_tier` from `floor`; `DirectorInputError` from `job`. Memory is
recorded before the LLM call on purpose: the lock is held for milliseconds, never across a provider
call. A job that later falls back still "used" its direction, which is what the user sees.

- [ ] **Step 5: Run** the replay test (the concurrency test runs 6 threads, CPU only) and the fast loop → PASS.
  If `test_layer_one...` fails, the LLM or fallback path is not calling `vary_details`: fix the
  wiring, not the test.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(director): locked memory read-roll-record, final-script floor gate, replay without the provider" -- engine/director/pipeline.py engine/director/variety.py engine/tests/test_director_replay.py
```

## Chunk 4: CLI, harness variety score, finish

### Task 47: CLI — variety flags, `replay`, `variety-report`

Re-read `engine/__main__.py` at HEAD.

**Files:**
- Modify: `engine/__main__.py` (docstring, `main`, `_run`, `_direct`, new `_replay`, `_variety_report`)
- Test: `engine/tests/test_cli_variety.py`

- [ ] **Step 1: Write the failing test:**

```python
import json

from engine.__main__ import EXIT_BAD_INPUT, EXIT_CHECK_FAILED, EXIT_OK, main
from engine.director.memory import issue_user_token

PROFILE = "engine/tests/fixtures/profiles/pocket_watch.json"


def _refuse(tmp_path):
    p = tmp_path / "refuse.json"
    p.write_text(json.dumps({"replies": [{"stop_reason": "refusal", "text": ""}] * 3}), encoding="utf-8")
    return f"fake:{p}"


def _direct(tmp_path, capsys, *extra):
    rc = main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path), *extra])
    return rc, json.loads(capsys.readouterr().out)


def test_new_user_prints_a_token(capsys):
    assert main(["new-user"]) == EXIT_OK
    tok = capsys.readouterr().out.strip()
    assert tok.startswith("u_") and len(tok) == 34


def test_memory_flags_rotate_directions(tmp_path, capsys):
    u, ids = issue_user_token(), []
    for s in range(3):
        rc, out = _direct(tmp_path, capsys, "--seed", str(s), "--user", u, "--memory-dir", str(tmp_path / "m"))
        assert rc == EXIT_OK
        ids.append(out["direction"]["id"])
    assert len(set(ids)) == 3


def test_like_and_replay_from_the_saved_record(tmp_path, capsys):
    rec = tmp_path / "a.replay.json"
    _direct(tmp_path, capsys, "--seed", "4", "--out-replay", str(rec))
    a = json.loads(rec.read_text(encoding="utf-8"))
    _, like = _direct(tmp_path, capsys, "--seed", "9", "--like", str(rec))
    assert like["direction"]["id"] == a["direction"]["id"]
    assert main(["replay", str(rec), "--profile", PROFILE]) == EXIT_OK        # no provider flag at all
    assert json.loads(capsys.readouterr().out)["script"] == a["script"]


def test_stale_replay_exits_3(tmp_path, capsys):
    rec = tmp_path / "a.replay.json"
    _direct(tmp_path, capsys, "--seed", "4", "--out-replay", str(rec))
    doc = json.loads(rec.read_text(encoding="utf-8"))
    doc["script"]["world"] = {"id": "moon", "params": {}}
    rec.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["replay", str(rec), "--profile", PROFILE]) == EXIT_CHECK_FAILED


def test_bad_inputs_exit_5(tmp_path, capsys):
    assert main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path), "--user", "alice@example.com",
                 "--memory-dir", str(tmp_path)]) == EXIT_BAD_INPUT
    assert main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path),
                 "--avoid", "mood=purple_rain"]) == EXIT_BAD_INPUT
    assert main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path),
                 "--like", "moon/clean/white/calm/arc_orbit/dry/calm"]) == EXIT_BAD_INPUT


def test_avoid_parses_axis_value(tmp_path, capsys):
    for s in range(4):
        _, out = _direct(tmp_path, capsys, "--seed", str(s), "--avoid", "mood=clean", "--avoid", "mood=vivid")
        assert out["direction"]["axes"]["mood"] not in ("clean", "vivid")


def test_variety_report_with_prompt(capsys):
    assert main(["variety-report", "--profile", PROFILE, "--prompt", "luxury", "--viable"]) == EXIT_OK
    r = json.loads(capsys.readouterr().out)
    assert r["pins"] == {"mood": "premium_dark"} and "viable" in r
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement.**
  - `new-user`: prints `issue_user_token()`. The site stores it per account; the engine never sees an
    email.
  - `direct` gains `--user`, `--subject-id`, `--memory-dir` (memory is on when `--user` is set and
    `--memory-dir` or `VALORA_VARIETY_DIR` gives a root), `--like FILE_OR_ID`, `--less-like FILE`,
    `--avoid AXIS=VALUE` (`action="append"`) and `--out-replay FILE` (writes `res.replay`).
    - `--like` takes a replay record, a script file or a direction id.
    - `--less-like` turns a replay/script file's direction into
      `{"mood": [m], "opener": [o]}`, plus `world` when the subject has more than one.
    - `--avoid` splits on the first `=`.
    - `DirectorInputError` (which includes `DirectionIncompatible` and bad tokens) → `EXIT_BAD_INPUT`,
      with its plain message.
  - `replay FILE --profile P` → `variety.replay(record, profile, catalog)`. It takes no `--provider` at
    all. `ReplayStale` → `EXIT_CHECK_FAILED`, with its message.
  - `variety-report --profile P [--prompt TEXT] [--aspect 9:16] [--viable]` prints `reachable(...)`
    with `prompt=` and, when `--viable` is set, `job=make_job("a 10 second clip" if not prompt else prompt, ...)`.
  - Update the module docstring's usage and exit-code lines.

- [ ] **Step 4: Run** the new test plus `engine/tests/test_cli.py` → PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(cli): variety flags, new-user tokens, replay without a provider, variety-report per prompt" -- engine/__main__.py engine/tests/test_cli_variety.py
```

### Task 48: Harness variety score (offline, paired regressions, per-group honesty)

**Files:**
- Create: `harness/variety.py`
- Test: `harness/tests/test_variety.py`

- [ ] **Step 1: Write the failing test:**

```python
from engine.director.llm import FakeProvider
from harness.variety import run_variety

REFUSE = lambda cid: FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3)  # noqa: E731


def test_variety_report_offline(tmp_path):
    s = run_variety(models=["pocket_watch", "sports_car"], prompt_ids=["empty", "luxury"], runs=5,
                    provider_factory=REFUSE, out_root=tmp_path, run_id="t")
    m = s["metrics"]
    assert m["groups"] == 4 and m["exactRepeats"]["value"] == 0
    assert m["meanDirectionDistance"]["value"] > 0 and m["meanScriptDistance"]["value"] > 0
    assert all(g["tierRegressions"] == 0 for g in s["groups"])            # paired, per case, per group
    assert m["frameDistance"]["n"] == 0 and (tmp_path / "t" / "summary.md").exists()
    g = next(c for c in s["groups"] if c["prompt"] == "luxury" and c["model"] == "pocket_watch")
    assert all(d["axes"]["mood"] == "premium_dark" for d in g["directions"])
    assert g["honesty"]["pins"] == {"mood": "premium_dark"} and "viable" in g["honesty"]


def test_hold_direction_proves_layer_one(tmp_path):
    s = run_variety(models=["pocket_watch"], prompt_ids=["empty"], runs=3, hold_direction=True,
                    provider_factory=REFUSE, out_root=tmp_path, run_id="h")
    g = s["groups"][0]
    assert len({d["id"] for d in g["directions"]}) == 1 and g["meanScriptDistance"] > 0


def test_single_run_reports_without_crashing(tmp_path):
    s = run_variety(models=["pocket_watch"], prompt_ids=["empty"], runs=1, provider_factory=REFUSE,
                    out_root=tmp_path, run_id="one")
    assert s["groups"][0]["meanDirectionDistance"] is None
    assert "n/a" in (tmp_path / "one" / "summary.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `harness/variety.py`:**

```python
"""Variety score (spec §9): N runs of the same model + prompt. Report-only, except that paired tier
regressions must be 0. Per group:
- direction distance (mean and min pairwise) and script distance; near-duplicates; exact repeats;
- tierRegressions: runs whose [S] tier is below the SAME case (seed, duration) run with the phase-3
  interim direction and no dice. Paired per case, so a loss is never offset by a gain elsewhere;
- honesty: reachable() with this group's own pins, format and viability;
- frameDistance: only with a renderer (a hard total of 3 frames per invocation, Task 49).
Each group gets a fresh temporary memory with one issued user token, so layer 3 runs as in production.
hold_direction=True keeps the first run's direction (more like this), so only layer 1 varies."""
import itertools
import json
import tempfile
import time
from pathlib import Path

from engine.catalog import Catalog
from engine.director.direction import interim_direction, parse_id
from engine.director.distance import direction_distance, near_duplicate, script_distance
from engine.director.floor import _RANK, script_tier
from engine.director.job import make_job
from engine.director.llm import FakeProvider
from engine.director.memory import VarietyMemory, issue_user_token
from engine.director.pipeline import direct
from engine.director.variety import reachable
from harness.director_eval import MODELS, _profile, _rate, load_prompt_set, markers_for


def _refuse(cid):
    return FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3)


def _pairs(xs, f):
    return [f(a, b) for a, b in itertools.combinations(xs, 2)]


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def run_group(model, case, sets, *, runs, memory, seed_base, factory, catalog, render=None, hold_direction=False):
    profile = _profile(model)
    spec = sets.get(case.get("markers")) if case.get("markers") else None
    markers = markers_for(spec, profile) if spec else None
    res = []
    with tempfile.TemporaryDirectory() as tmp:
        mem, user = (VarietyMemory(tmp), issue_user_token()) if memory else (None, None)
        for k in range(runs):
            like = res[0].script if hold_direction and res else None
            res.append(direct(case["prompt"], profile, provider=factory(f"{model}__{case['id']}__{k}"),
                              seed=seed_base + k, markers=markers, catalog=catalog, memory=mem, user=user, like=like))
    base = [direct(case["prompt"], profile, provider=factory(f"{model}__{case['id']}__base{k}"), seed=seed_base + k,
                   markers=markers, catalog=catalog, direction=interim_direction(seed_base + k, profile, catalog),
                   duration=r.script["format"]["durationS"]) for k, r in enumerate(res)]
    scripts = [r.script for r in res]
    tiers = [script_tier(s, profile, catalog) for s in scripts]
    btiers = [script_tier(b.script, profile, catalog) for b in base]
    dd = _pairs([parse_id(s["direction"]["id"]) for s in scripts], direction_distance)
    sd = _pairs(scripts, lambda a, b: script_distance(a, b, catalog))
    fmt = scripts[0]["format"]
    job = make_job(case["prompt"], profile, catalog, seed=seed_base, duration=fmt["durationS"])
    row = {"model": model, "prompt": case["id"], "runs": runs, "memory": memory, "holdDirection": hold_direction,
           "directions": [r.direction for r in res],
           "meanDirectionDistance": _mean(dd), "minDirectionDistance": min(dd) if dd else None,
           "meanScriptDistance": _mean(sd),
           "nearDuplicates": sum(near_duplicate(a, b, catalog) for a, b in itertools.combinations(scripts, 2)),
           "exactRepeats": runs - len({s["direction"]["id"] for s in scripts}),
           "tiers": tiers, "baselineTiers": btiers,
           "tierRegressions": sum(_RANK[t] < _RANK[b] for t, b in zip(tiers, btiers)),
           "honesty": reachable(profile, catalog, fmt, job=job, prompt=case["prompt"]), "frameDistance": None}
    if render is not None:
        row["frameDistance"] = render(model, profile, scripts)
    return row


def run_variety(prompt_set="v1", models=None, prompt_ids=None, runs=5, memory=True, provider_factory=None,
                out_root="harness/out/variety", run_id=None, seed_base=5000, render=None, hold_direction=False):
    prompts, sets = load_prompt_set(prompt_set)
    prompts = [p for p in prompts if not prompt_ids or p["id"] in prompt_ids]
    catalog, factory = Catalog.load(), provider_factory or _refuse
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    groups = []
    for model in models or MODELS:
        for case in prompts:
            try:
                groups.append(run_group(model, case, sets, runs=runs, memory=memory, seed_base=seed_base,
                                        factory=factory, catalog=catalog, render=render,
                                        hold_direction=hold_direction))
            except Exception as e:  # noqa: BLE001 - recorded, never skipped
                groups.append({"model": model, "prompt": case["id"], "error": f"{type(e).__name__}: {e}"})
    ok = [g for g in groups if "error" not in g]
    metrics = {"groups": len(ok), "errors": len(groups) - len(ok),
               "tierRegressions": sum(g["tierRegressions"] for g in ok),
               "meanDirectionDistance": _rate([g["meanDirectionDistance"] for g in ok]),
               "minDirectionDistance": _rate([g["minDirectionDistance"] for g in ok]),
               "meanScriptDistance": _rate([g["meanScriptDistance"] for g in ok]),
               "nearDuplicates": _rate([g["nearDuplicates"] for g in ok]),
               "exactRepeats": _rate([g["exactRepeats"] for g in ok]),
               "frameDistance": _rate([g["frameDistance"] for g in ok]),
               "singleValuedAxes": sorted({a for g in ok for a in g["honesty"]["singleValued"]})}
    summary = {"promptSet": prompt_set, "runId": run_id, "runs": runs, "memory": memory,
               "holdDirection": hold_direction, "metrics": metrics, "groups": groups}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    (run_dir / "summary.md").write_text(_md(summary), encoding="utf-8")
    return summary


def _f(v, spec=".3f"):
    return "n/a" if v is None else format(v, spec)


def _md(s):
    m = s["metrics"]
    rate = lambda r: f"{_f(r['value'])} (n={r['n']})"  # noqa: E731
    lines = [f"# Variety score {s['runId']} ({s['promptSet']}, {s['runs']} runs, memory {'on' if s['memory'] else 'off'}"
             f"{', direction held' if s['holdDirection'] else ''})", "",
             "Report-only. Distances 0..1. Tier regressions are paired per case against the no-dice run and must be 0.", "",
             f"- **Tier regressions: {m['tierRegressions']}**",
             f"- Direction distance mean {rate(m['meanDirectionDistance'])}, min {rate(m['minDirectionDistance'])}",
             f"- Script distance mean {rate(m['meanScriptDistance'])}; near-duplicate pairs {rate(m['nearDuplicates'])}",
             f"- Exact repeats {rate(m['exactRepeats'])}; frame distance {rate(m['frameDistance'])} (render only)",
             f"- Axes with one value somewhere (catalog honesty): {', '.join(m['singleValuedAxes']) or 'none'}",
             "", "| model | prompt | dir dist | script dist | repeats | near dups | tier regressions | viable |",
             "|---|---|---|---|---|---|---|---|"]
    for g in s["groups"]:
        if "error" in g:
            lines.append(f"| {g['model']} | {g['prompt']} | ERROR {g['error'][:80]} | | | | | |")
        else:
            lines.append(f"| {g['model']} | {g['prompt']} | {_f(g['meanDirectionDistance'])} | "
                         f"{_f(g['meanScriptDistance'])} | {g['exactRepeats']} | {g['nearDuplicates']} | "
                         f"{g['tierRegressions']} | {g['honesty'].get('viable', 'n/a')} |")
    return "\n".join(lines) + "\n"
```

If `_rate` / `_profile` / `markers_for` / `MODELS` have moved in `harness/director_eval.py`, import
them from where they are now. Do not copy them.

- [ ] **Step 4: Run.** PASS. **A tier regression is a finding, not a test to loosen.** It means the
  floor or the final-script gate let a worse script through. Debug `floor_tier` / the Task 46 gate
  (@superpowers:systematic-debugging).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(harness): variety score - paired tier regressions, per-group honesty, hold-direction layer-1 check" -- harness/variety.py harness/tests/test_variety.py
```

### Task 49: Frame distance under a hard 3-frame budget, and `py -m harness variety`

**Files:**
- Modify: `harness/variety.py` (add `MAX_FRAMES_TOTAL`, `frame_distance`, `make_renderer`)
- Modify: `harness/__main__.py` (subcommand `variety`)
- Test: add to `harness/tests/test_variety.py`

- [ ] **Step 1: Write the failing tests** (append):

```python
import numpy as np
import pytest
from PIL import Image

from harness.variety import MAX_FRAMES_TOTAL, frame_distance, make_renderer


def _png(path, rgb):
    Image.fromarray(np.full((64, 36, 3), rgb, dtype=np.uint8)).save(path)
    return path


def test_frame_distance(tmp_path):
    a, b = _png(tmp_path / "a.png", (10, 10, 10)), _png(tmp_path / "b.png", (240, 240, 240))
    assert frame_distance(a, a) == 0.0 and 0.5 < frame_distance(a, b) <= 1.0


def test_budget_cannot_exceed_three():
    assert MAX_FRAMES_TOTAL == 3
    with pytest.raises(ValueError):
        make_renderer("x", budget=4)


def test_total_frames_per_invocation_never_exceed_three(tmp_path, monkeypatch):
    calls = []

    def fake_compile(script, profile, glb, out_dir, **kw):
        assert kw["tier"] == "keyframes" and len(kw["frames"]) == 1
        calls.append(kw["frames"][0])
        (out_dir / "beauty").mkdir(parents=True, exist_ok=True)
        _png(out_dir / "beauty" / f"{kw['frames'][0]:04d}.png", (script["seed"] % 255, 0, 0))
        return {}

    import harness.variety as hv
    monkeypatch.setattr(hv, "compile_scene", fake_compile)
    s = run_variety(models=["pocket_watch", "sneaker"], prompt_ids=["empty"], runs=5, provider_factory=REFUSE,
                    out_root=tmp_path, run_id="r", render=make_renderer(tmp_path / "frames"))
    assert len(calls) <= MAX_FRAMES_TOTAL                      # 2 groups x 5 runs asked; 3 frames rendered
    rendered = [g["frameDistance"] for g in s["groups"] if g["frameDistance"] is not None]
    assert len(rendered) == 1 and rendered[0] > 0              # one group got 3 runs x 1 frame
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** in `harness/variety.py`:

```python
import numpy as np
from PIL import Image

from engine.compiler.run import compile_scene

ROOT = Path(__file__).resolve().parents[1]
SUITE = json.loads((ROOT / "harness" / "suites" / "v0" / "suite.json").read_text(encoding="utf-8"))
MAX_FRAMES_TOTAL = 3     # owner rule: at most 3 rendered frames per invocation, on this PC
TIER = "keyframes"


def _img(path, size=(36, 64)):
    return np.asarray(Image.open(path).convert("RGB").resize(size, Image.BILINEAR), dtype=np.float64) / 255.0


def frame_distance(a, b):
    """0..1: half mean luminance difference of thumbnails, half colour-histogram distance."""
    A, B = _img(a), _img(b)
    lum = lambda x: x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722  # noqa: E731
    hist = lambda x: np.histogramdd(x.reshape(-1, 3), bins=(8, 8, 8), range=((0, 1),) * 3)[0].ravel() / (x.size / 3)  # noqa: E731
    return round(0.5 * float(np.abs(lum(A) - lum(B)).mean()) + 0.25 * float(np.abs(hist(A) - hist(B)).sum()), 4)


def make_renderer(out_root, budget=MAX_FRAMES_TOTAL):
    """One mid-clip frame per run until the invocation's total budget is spent. Groups after that get
    None (reported as n/a). The budget can never be raised above MAX_FRAMES_TOTAL."""
    if not 0 < budget <= MAX_FRAMES_TOTAL:
        raise ValueError(f"render budget must be 1..{MAX_FRAMES_TOTAL} frames per invocation")
    left = [budget]

    def render(model, profile, scripts):
        if left[0] < 2:                       # a distance needs at least two frames
            return None
        glb, frames = ROOT / SUITE["glb"].format(m=model), []
        for k, s in enumerate(scripts[:left[0]]):
            f = max(1, round(s["format"]["durationS"] * s["format"]["fps"] / 2))
            out = Path(out_root) / f"{model}__{k}"
            compile_scene(s, profile, glb, out, tier=TIER, frames=[f])
            left[0] -= 1
            frames.append(out / "beauty" / f"{f:04d}.png")
        ds = [frame_distance(a, b) for a, b in itertools.combinations(frames, 2)]
        return sum(ds) / len(ds) if ds else None
    return render
```

Check where `compile_scene` writes beauty frames (`harness/run.py::_encode` reads
`case_dir / "beauty" / "%04d.png"`). If it differs, use the real path.

In `harness/__main__.py`, add a `variety` subparser with `--prompts` (v1), `--models`,
`--prompt-ids`, `--runs` (5, minimum 1), `--no-memory`, `--hold-direction`, `--render`, `--run-id`
and `--out-root` (`harness/out/variety`).
- `--render` builds `make_renderer(...)` with the fixed 3-frame budget and prints "rendering at most 3
  frames in total (keyframes tier)" before starting. There is no flag to raise the budget.
- It uses the refusing provider (no live flag until a key exists), prints the metrics JSON, and exits 1
  on `errors` or `tierRegressions > 0`.
- Add the usage line to the module docstring.

- [ ] **Step 4: Run** `py -m pytest harness/tests/test_variety.py -q` → PASS. Then the offline smoke,
  with no render (CPU, a few minutes):
  `py -m harness variety --models pocket_watch,sports_car,cesium_man --prompt-ids empty,cool,luxury,rainy_night --runs 5 --run-id phase4-smoke`
  and `py -m harness variety --models pocket_watch --prompt-ids empty --runs 3 --hold-direction --run-id phase4-layer1`.
  Paste the headline metrics (population, fallback-only, date) into the Task 50 register.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(harness): py -m harness variety; frame distance under a hard 3-frame budget" -- harness/variety.py harness/__main__.py harness/tests/test_variety.py
```

- [ ] **Step 6 (owner-gated): a tiny visible-difference check.** Ask the owner first. If OK, run:
  `py -m harness variety --models pocket_watch --prompt-ids empty --runs 3 --hold-direction --render --run-id phase4-frames`
  That is 3 runs × 1 frame = **3 frames in total**, with direction and duration held, so it proves layer
  1 is visible. Record the frame distance. If the owner says no, record "frame distance unmeasured
  (owner-gated)".

### Task 50: Finish — ownership test, register, full loop, handoff

**Files:**
- Create: `engine/tests/test_director_ownership.py`
- Modify: this plan (register rows filled in)

- [ ] **Step 1: Write the ownership test.** It is PowerShell-safe: pytest, not grep. It distinguishes
  pipeline-owned writes from LLM output.

```python
import json

from engine.catalog import Catalog
from engine.director.axes import axis_values
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from engine.director.rulebook import EXAMPLES_DIR
from engine.realism import realism_defaults
from engine.tests.test_director_package import _p

WATCH = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]


def test_llm_cannot_write_realism_wind_or_fields_pipeline_still_owns_realism():
    p, cat = _p("pocket_watch"), Catalog.load()
    hostile = {**WATCH, "realism": [{"id": "tyre_contact", "params": {}}],
               "wind": {"id": "wind", "params": {"speedMs": 14}}, "field": {"id": "wind"}}
    r = direct("luxury", p, provider=FakeProvider([hostile]), seed=11, duration=10)
    assert "wind" not in r.script and "field" not in r.script                     # LLM output dropped
    want = realism_defaults(p, cat)
    assert r.script.get("realism", []) == (want or [])                            # pipeline-owned, expected


def test_turntable_never_rolled_negative_control():
    p, cat = _p("pocket_watch"), Catalog.load()
    fmt = {"aspect": "9:16", "durationS": 10, "fps": 30}
    assert "turntable" not in axis_values(p, cat, fmt)["opener"]
    assert "turntable" not in axis_values(p, cat, fmt, rollable=False)["opener"]
```

If HEAD's sanitize makes `realism` absent when the defaults are empty, the `or []` covers it. If the
pipeline has since started writing a `wind` field by design (the phase-3½ hand-off H3), assert instead
that its value equals the pipeline's own resolution and not the LLM's 14 m/s.

- [ ] **Step 2: Full fast loop.** Run `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"`
  and compare with the Task 34 baseline. New failures must be zero. Other lanes' pre-existing reds are
  listed, not fixed.
- [ ] **Step 3: Fill in the calibration register below** (numbers with population and date).
- [ ] **Step 4: Commit the ownership test and the register**, then write the handoff
  `.handoffs/YYYY-MM-DD-HHMM-renderer-director-phase4-variety-done.md` (`track: renderer-director`) and
  commit it with `git commit -- <that path>`.

```bash
git commit -m "test(director): LLM never writes realism/wind/fields; register filled" -- engine/tests/test_director_ownership.py docs/superpowers/plans/2026-09-25-director-phase4-variety.md
```

---

## Calibration register — every (eng) number this plan introduces

None of these may be quoted as a quality fact until measured.

| Number(s) | Where | Calibrated through |
|---|---|---|
| Baseline fast-loop count | Task 34 | (fill in) |
| Frozen phase-3 tiers per subject (9 × 2 prompts × 5 seeds) | `baseline/phase3_tiers.json` | (fill in counts); never regenerated without the owner's OK |
| Viable directions per subject (seed 0, 10 s) | Task 41 Step 5 | (fill in table) |
| `memoryN` 5 (near-dup window only; rotation now covers the whole viable pool) | `dice.json` | Harness exact repeats, owner repetition reports |
| `minDistance` 0.25, `nearPenalty` 0.25 | `dice.json` | Harness min direction distance; owner "these look the same" reports |
| `axisWeights` world 3 / mood 3 / opener 2 / weather 2 / tone, pace, wind 1 | `dice.json` | Owner pairwise "how different" judgments on renders (after phase 5 worlds) |
| `weightFloor` 0.1 | `dice.json` | Corpus energy shares once n ≥ 30 per family |
| `toneByMood`, `paceByFamily` (carried over from the interim direction) | `dice.json` | Corpus co-occurrence (spec §9a use 3) |
| `durationsS` 8/10/12 | `dice.json` | Owner preference; corpus shot length × count |
| `detailParams` fractions (0.04–0.06 of range) | `dice.json` | Task 49 Step 6 frame distance with the direction held; owner "same clip?" check |
| `nearDuplicateScript` 0.08 | `dice.json` | Frame distance vs script distance (Task 49) |
| `FLOOR_TIER` T3, best-baseline rule | `floor.py` | Harness tier regressions (must stay 0); viable counts |
| `OPENER_HOOK` arc_orbit params | `fallback.py` | Subjects where arc_orbit is non-viable (fill in) |
| Pin phrase lists (world, mood, tone, pace, opener) | `dice.json` | Pin precision/recall on the harness prompts and live prompts once a key exists |
| `MAX_ENTRIES` 50, `MAX_DISLIKES_PER_AXIS` 3, `LOCK_TIMEOUT_S` 10, `STALE_LOCK_S` 60 | `memory.py` | Product decision; the lock test under load |
| Script-distance part weights; frame-distance mix | `distance.py`, `harness/variety.py` | Correlation with owner judgments on Task 49 frames |

## Deferred (and why)

- **Rollable weather, wind and season dressing:** phase 5 blocks (PHASING §2). Only `dry`/`calm` roll.
  When wind becomes rollable, the **pipeline** maps the rolled value to `field/wind` (phase-3½ hand-off
  H3). The LLM never does.
- **`macro_detail` as an opener:** the sequence rule needs a full-framing hook. It could become a
  "detail-first cold open" only if the owner wants that rule relaxed for some pace.
- **Tone as a per-world backdrop axis:** needed when phase 5 adds `night_street` / `golden_field`.
- **Lighting and effect axes:** lighting stays with the taste guide (TG-08) until a third rig exists.
- **Builder-internal seeded noise:** layer 1 goes through params for now (the script stays the full
  description). Procedural noise inside builders is a phase 5/7 item, tied to farm-consistency tests.
- **Live variety score** with the real LLM: needs `ANTHROPIC_API_KEY` (phase-3 O1).
- **Owner "do these feel different?" grading:** at the all-phases grading session.
- **Web wiring** (the site issues and stores the `new-user` token; "more like this" / "less like this"
  buttons): `apps/web` stays `not_connected`.
- **Budget-aware dice** (spec §11, costWeight): phase 7 farm.

## Owner-only items

- **OK before Task 49 Step 6** (3 frames in total). Everything else in this plan is CPU-only and
  renders nothing. The baseline freeze (Task 34 Step 5) is 90 fallback builds on the CPU, with no
  render and no network.

## Done when

- The fast loop has no new failures against the Task 34 baseline.
- The frozen phase-3 baseline is committed.
- `py -m harness variety` (offline) reports **0 tier regressions**, 0 exact repeats with memory on, and
  a per-prompt honesty line. `--hold-direction` shows script distance > 0 with one direction id.
- `py -m engine direct ... --user <new-user token> --memory-dir var/variety` rotates through every
  viable direction before any repeat.
- `py -m engine replay <record> --profile P` reproduces the saved script exactly, with no provider.
- An incompatible `--like` / `--avoid` exits 5 with a plain reason.
- The LLM never writes realism, wind or a field (the Task 50 ownership test), and `turntable` is never
  a dice value.
