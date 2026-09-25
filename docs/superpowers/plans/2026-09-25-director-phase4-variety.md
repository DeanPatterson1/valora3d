# Director Layer Phase 4 — Variety: Dice, Variety Memory, "More Like This", Variety Score

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The same model and prompt, run twice, give two clearly different videos (spec §1 success
criterion 2). No run may be worse than today's default. Every run can be replayed exactly from its
seed and direction. The harness measures all of this.

**Architecture:**

- **The dice are deterministic code (spec §3 stage 2), not the LLM.** `engine/director/dice.py` rolls a
  direction over seven axes: world, mood, tone, pace, opener, weather, wind. The allowed values come
  from the catalog (worlds, grade presets, selectable cameras) intersected with `engine/director/dice.json`,
  so the dice cannot pick a block the menu does not offer. A roll is a pure function of (seed, pins,
  memory snapshot, avoid list). Same inputs give the same direction, so any job can be replayed.
- **Spec §6 has three layers.** Layer 1 is details: the seed drives jitter, particles and camera
  micro-paths, which already exist. Layer 2 is the direction: the dice. Layer 3 is variety memory: a
  file-based store keyed per (opaque user, subject). It keeps the last directions and the values the
  user disliked. `dice.json memoryN` (5) sets how many recent directions are excluded, reduced to
  n − 1 for a subject with only n viable directions. So a small catalog rotates through everything
  before it repeats.
- **An explicit request beats the dice.** `engine/director/pins.py` reads mood, pace and tone phrases
  from the prompt deterministically and is negation-aware. The dice fill only the axes the prompt
  left open. On vague prompts, `adherence.py` enforces the rolled mood, pace and tone in place, so an
  LLM that falls back to one "safe" look cannot erase the variety. On long prompts it only measures
  drift.
- **Quality floor (novelty never costs quality).** A direction is *viable* for a subject only when its
  safe fallback script passes the checker, honours the direction's opener and pace, and reaches the
  floor tier on the script-level [S] items. The floor is `min(T3, what the phase-3 default direction
  reaches)`, so variety never pushes a subject below today's quality. The dice skip non-viable rolls,
  and the harness reports the quality cost against a no-dice baseline.
- **"More like this" / "less like this" / replay.** `like` keeps the direction (and duration) with a
  new seed, so only layer 1 changes. `avoid` / `--less-like` excludes values and is stored as a
  per-user dislike. `replay` rebuilds a job from a script's seed, direction id, duration, prompt and
  markers.
- **Harness variety score (spec §9).** `py -m harness variety` runs N (default 5) runs per model ×
  prompt and reports: direction distance, script distance, exact repeats, near-duplicates,
  catalog-size honesty (reachable and viable directions, single-valued axes), quality cost against the
  no-dice baseline, and, opt-in only, frame difference on ≤ 3 rendered key frames per run.

**What the director never does.** It never writes `realism`, `wind` or any `field` (pipeline-owned,
`sanitize.OWNED`). The weather and wind axes exist only so memory records them from day one
(`research/physics/PHASING.md` §2 Phase 4). Only `dry` and `calm` are rollable until phase 5 blocks
exist, and neither value is ever written into a script. `turntable` is a harness negative control:
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

**Task numbering** continues after phase 3's highest task (Task 33): this plan uses **Tasks 34–50**.

**Conventions (same as phases 1–3½):**

- Run every command from the repo root `C:\Users\deand\Projects\rendering`, on branch `renderer/director`.
- Use `py`, never bare `python`.
- Fast loop: `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"`.
  Record the count in Task 34.
- **No live API calls.** There is no `ANTHROPIC_API_KEY` yet. Every director test uses `FakeProvider`
  or the refusing provider, which forces the fallback. A `live` test is written only where noted and
  stays skipped.
- **Renders ≤ 3 frames and only after the owner says OK** (the owner games on this PC). Only Task 49
  Step 6 renders anything.
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
| `engine/director/dice.json` | create | Dice data: tone-by-mood compatibility, pace by family, openers, durations, weather/wind (values + rollable), prompt pin phrases, axis weights, memory N, (eng) thresholds |
| `engine/director/direction.py` | modify | `Direction` gains `world`, `opener`, `weather`, `wind`, `pinned`. `AXES`, `make_id`, `parse_id`, `direction_of`, `Direction.from_script`. `interim_direction` is kept unchanged as the last resort |
| `engine/director/axes.py` | create | `axis_values(profile, catalog, fmt)` from catalog ∩ dice.json, `compatible`, `opener_of(script)` |
| `engine/director/pins.py` | create | `read_direction_pins(prompt)`: mood, pace and tone the prompt pinned (negation-aware) |
| `engine/director/distance.py` | create | `direction_distance`, `script_distance`, `near_duplicate` |
| `engine/director/dice.py` | create | `candidates`, `roll` (weights, pins, memory exclusion, avoid, near-dup penalty, floor callback), `roll_duration` |
| `engine/director/fallback.py` | modify | honours `direction.opener` and `direction.world` |
| `engine/director/floor.py` | create | `script_tier`, `make_viable` (the quality floor) |
| `engine/director/memory.py` | create | `VarietyMemory`: file store, hashed opaque ids, atomic writes, caps, corrupt-file tolerance, `forget` |
| `engine/director/variety.py` | create | `subject_key`, `choose_direction` (replay → like → dice), `replay_kwargs`, `reachable` (catalog honesty) |
| `engine/director/job.py` | modify | `make_job(..., like, avoid, recent, duration)`. Rolled duration; direction from `choose_direction` |
| `engine/director/intent.py` | modify | `make_format(pins, seed, duration=None)` |
| `engine/director/adherence.py` | create | `drift`, `enforce_direction` |
| `engine/director/request.py`, `rulebook.py`, `rulebook/rulebook.txt` | modify | Direction card gains `world` + `opener`. Default text updated. Rulebook regenerated |
| `engine/director/pipeline.py` | modify | memory read/write, `like`/`avoid`/`user`/`subject_id`/`duration`, adherence, `DirectorResult.direction` |
| `engine/__main__.py` | modify | `direct --user --subject-id --memory-dir --like --less-like --avoid --replay`; `variety-report` |
| `harness/variety.py` | create | Variety score runner, `frame_distance`, optional ≤ 3-frame renders |
| `harness/__main__.py` | modify | `py -m harness variety ...` |
| `.gitignore` | modify | `var/` (variety memory lives there locally) |
| Tests | create | `engine/tests/test_director_{direction_v2,axes,pins,distance,dice,floor,memory,variety,adherence,replay}.py`, `harness/tests/test_variety.py` |

---

## What grew from the seed

The owner's seed was "dice, variety memory, 'more like this', variety score". This plan expands it to:

1. **More axes than mood/pace/tone:** world, camera language (opener), weather and wind (recorded now,
   rollable in phase 5), and duration (8/10/12 s, which pays off the phase-3 promise "phase 4 varies
   duration").
2. **An explicit request beats the dice, deterministically:** prompt pins with negation ("not dark"
   is not a pin), first mention wins.
3. **"Less like this" / avoid:** per-roll excludes plus stored per-user dislikes. They relax
   gracefully and never leave an empty set.
4. **Deterministic replay by seed:** a script alone reproduces its job (`--replay`).
5. **A quality floor on novelty:** a direction must be viable (its safe fallback passes the checker
   and reaches the floor tier) before the dice may pick it. The harness measures the quality cost
   against a no-dice baseline.
6. **Direction enforcement on vague prompts:** stops the LLM converging on one safe look (spec §11
   risk). Drift is measured on long prompts.
7. **Near-duplicate detection:** script distance plus a near-duplicate flag, and a soft penalty on
   directions close to recent ones, not only exact repeats.
8. **Catalog-size honesty:** reachable and viable direction counts per subject, single-valued axes, and
   "guaranteed distinct in a row". Spec §6's "honest limit" becomes a number instead of a promise.
9. **Memory rotation guarantee:** for a small catalog, exclude the last min(N, n−1) directions, so a
   subject rotates through everything before it repeats.
10. **Privacy-safe memory:** hashed opaque ids only, no prompt text, bounded files, `forget(user)`
    for deletion requests, and a failed write never fails a job.
11. **Rare-but-good kept:** a weight floor keeps corpus-rare values rollable, and `noir` stays
    pin-only.
12. **Frame-level variety, opt-in:** ≤ 3 key frames per run, owner-gated.

---

## Chunk 0: Gate and baseline

### Task 34: Gate — phase 3's director exists and the interim direction is still in place

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Check the phase-3 contract is at HEAD.**

Run: `py -c "from engine.director.direction import Direction, interim_direction; from engine.director.job import make_job; from engine.director.pipeline import direct; from engine.director.fallback import build_fallback, slot_camera; print('ok')"`
Expected: `ok`. If this fails, stop and report: phase 3 has not landed.

- [ ] **Step 2: Record the baseline.**

Run: `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"`
Expected: all pass. Write the count (for example `NNN passed, MM deselected`) into this plan's Task
50 register under "Baseline". If something is already red, note it and leave it alone: it belongs to
another lane.

- [ ] **Step 3: Ignore local variety memory.** Append to `.gitignore`:

```
# Variety memory (phase 4): local per-user direction history, never committed
var/
```

- [ ] **Step 4: Commit**

```bash
git diff --cached --name-only
git commit -m "chore: ignore local variety memory (var/)" -- .gitignore
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
 "openers": ["low_hero_push", "arc_orbit", "macro_detail"],
 "durationsS": [8, 10, 12],
 "weather": {"values": ["dry", "wet", "rain", "snow", "fog"], "rollable": ["dry"]},
 "wind": {"values": ["calm", "breeze", "windy"], "rollable": ["calm"]},
 "axisWeights": {"world": 3, "mood": 3, "tone": 1, "pace": 1, "opener": 2, "weather": 2, "wind": 1},
 "memoryN": 5,
 "minDistance": 0.25,
 "nearPenalty": 0.25,
 "weightFloor": 0.1,
 "maxFloorTries": 24,
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
  }
 }
}
```

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
from engine.director.axes import DICE, axis_values, compatible, opener_of
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


def test_opener_of():
    assert opener_of({"shots": [{"purpose": "detail", "camera": {"id": "macro_detail"}}]}) == "macro_detail"
    assert opener_of({"shots": [{"purpose": "hook", "camera": {"id": "arc_orbit"}}]}) == "arc_orbit"


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
    """The opener a script actually uses: a first detail shot is macro_detail, else the first camera."""
    first = script["shots"][0]
    return "macro_detail" if first.get("purpose") == "detail" else first["camera"]["id"]
```

If the `sequence` pace param is not an enum, read it from the block and adapt: `rollable=False` needs
the full set.

- [ ] **Step 4: Run it.** `py -m pytest engine/tests/test_director_axes.py -q` → PASS. If a subject
  has an empty `world` list (its size is outside `studio_cyc.subjectSizeM`), **stop and report**. Do
  not widen the block's range in this plan. `choose_direction` falls back to the interim direction
  in that case (Task 43).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): dice axes from the catalog; turntable never an opener" -- engine/director/axes.py engine/tests/test_director_axes.py
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
git commit -m "feat(director): prompt pins for mood/pace/tone (negation-aware, data-driven)" -- engine/director/pins.py engine/tests/test_director_pins.py
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

### Task 39: The dice — deterministic roll with pins, memory, avoid and a floor hook

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


def test_recent_directions_are_excluded():
    recent = [make_id(roll(s, V).axes) for s in range(5)]
    for s in range(30):
        assert make_id(roll(100 + s, V, recent=recent).axes) not in recent


def test_small_catalog_rotates_through_everything_before_repeating():
    small = {**V, "mood": ["clean"], "tone": ["white", "grey"], "pace": ["calm"], "opener": ["low_hero_push", "arc_orbit"]}
    n, seen = len(candidates(small)), []
    for s in range(n):
        seen.append(make_id(roll(s, small, recent=seen, dice={**_d(), "memoryN": 10}).axes))
    assert len(set(seen)) == n


def test_avoid_excludes_and_relaxes_instead_of_emptying():
    for s in range(20):
        assert roll(s, V, avoid={"mood": ["teal_night"]}).axes["mood"] != "teal_night"
    r = roll(1, V, avoid={"mood": ["clean", "premium_dark", "teal_night"]})
    assert r.axes is not None and "avoid_relaxed" in r.flags


def test_floor_callback_skips_non_viable_and_reports():
    r = roll(3, V, viable=lambda a: a["opener"] == "arc_orbit")
    assert r.axes["opener"] == "arc_orbit"
    r = roll(3, V, viable=lambda a: False)
    assert r.axes is None and "nothing_viable" in r.flags


def test_duration_is_seeded_and_in_range():
    assert roll_duration(5) == roll_duration(5) and {roll_duration(s) for s in range(40)} == {8, 10, 12}


def _d():
    from engine.director.axes import DICE
    return DICE
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/dice.py`:**

```python
"""The creative dice (spec §3 stage 2, §6 layer 2). Pure and deterministic: the same seed, pins, memory
snapshot and avoid list always give the same direction, so any job replays. Variety comes from here,
not from the LLM (spec §11)."""
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


def roll(seed, values, *, pins=None, recent=(), avoid=None, viable=None, family_name=None, stats=None, dice=None):
    dice, pins, flags = dice or DICE, pins or {}, []
    cands = candidates(values, pins, dice)
    if not cands:
        return Roll(None, ("no_candidates",))
    cands, relaxed = _apply_avoid(cands, avoid, pins)
    if relaxed:
        flags.append("avoid_relaxed")
    recent = list(recent)
    k = min(dice["memoryN"], len(cands) - 1)
    excluded = set(recent[-k:]) if k > 0 else set()
    fresh = [c for c in cands if make_id(c) not in excluded] or cands
    recent_axes = _parsed(recent[-dice["memoryN"]:])
    pw = pace_weights(family_name, stats, dice) if family_name else {}
    rng = random.Random(f"dice:{seed}")
    keys = [rng.random() ** (1.0 / _weight(c, pw, recent_axes, dice)) for c in fresh]  # weighted, no replacement
    order = [c for _, c in sorted(zip(keys, fresh), key=lambda kc: (-kc[0], make_id(kc[1])))]
    for i, c in enumerate(order[:dice["maxFloorTries"]]):
        if viable is None or viable(c):
            return Roll(c, tuple(flags + ([f"floor_skipped:{i}"] if i else [])), i + 1)
    return Roll(None, tuple(flags + ["nothing_viable"]), min(len(order), dice["maxFloorTries"]))


def roll_duration(seed, dice=None):
    return random.Random(f"duration:{seed}").choice((dice or DICE)["durationsS"])
```

- [ ] **Step 4: Run.** `py -m pytest engine/tests/test_director_dice.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): deterministic dice - pins, memory rotation, avoid, near-dup penalty, floor hook" -- engine/director/dice.py engine/tests/test_director_dice.py
```

### Task 40: The fallback honours the direction's opener and world

The quality floor (Task 41) judges a direction by its safe fallback. So the fallback must actually
*use* the rolled opener. Re-read `engine/director/fallback.py` at HEAD first: another lane edits it.

**Files:**
- Modify: `engine/director/fallback.py` (`_plan`, `slot_camera`, `_script`, `build_fallback`)
- Test: `engine/tests/test_director_fallback_opener.py` (new file, so the phase-3 test file stays untouched)

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


@pytest.mark.parametrize("opener", ["low_hero_push", "arc_orbit", "macro_detail"])
def test_fallback_uses_the_opener_on_the_watch(opener):
    cat, p = Catalog.load(), _p("pocket_watch")
    job = dataclasses.replace(make_job("", p, cat, seed=3, duration=10),
                              direction=direction_of({**AX, "opener": opener}, "dice"))
    s = build_fallback(job, p, cat)
    assert check(s, p, cat).ok and opener_of(s) == opener


@pytest.mark.parametrize("model", NINE)
def test_every_subject_still_gets_a_valid_fallback_for_every_opener(model):
    """The fallback may swap to a safe opener, but it must never fail (spec §4.6)."""
    cat, p = Catalog.load(), _p(model)
    for opener in ("low_hero_push", "arc_orbit", "macro_detail"):
        job = dataclasses.replace(make_job("", p, cat, seed=4, duration=10),
                                  direction=direction_of({**AX, "opener": opener}, "dice"))
        assert check(build_fallback(job, p, cat), p, cat).ok
```

`make_job(..., duration=10)` arrives in Task 44. Until then, write `make_job("", p, cat, seed=3)`
here and add `duration=10` in Task 44 Step 5.

- [ ] **Step 2: Run to verify it fails** (the arc_orbit / macro_detail cases fail on `opener_of`).

- [ ] **Step 3: Implement.** In `fallback.py`:

```python
OPENER_HOOK = {  # hook cameras for non-default openers (values follow slot_camera's proven ranges)
    "arc_orbit": {"id": "arc_orbit", "params": {"startAzimuthDeg": 20.0, "sweepDeg": 25.0, "lensMm": 50.0,
                                                "elevationDeg": 6.0}},
}
```

- `slot_camera(purpose, k, fam, jitter=0.0, detail_jitter=0.0, opener="low_hero_push")`: in the
  `purpose in ("hook", "establish")` branch, if `opener in OPENER_HOOK`, use a deep copy of it with
  `startAzimuthDeg += jitter`. Otherwise keep the existing `low_hero_push` camera. Everything after
  the branch (vehicle f/8) is unchanged.
- `_plan(duration, pace, template, seq, opener="low_hero_push")`: in the full-sequence branch, if
  `opener == "macro_detail"`, replace the first purpose `"hook"` with `"detail"` (lengths unchanged).
  The short plan already opens on a detail.
- `_script(...)` passes `opener` through to `_plan` and to `slot_camera`, and writes
  `"world": {"id": job.direction.world, "params": {"tone": job.direction.tone, "floorGloss": 0.4}}`
  when the world is `studio_cyc`, else `{"id": job.direction.world, "params": {}}`.
- `build_fallback`: the attempts become `(pace, jitter, seq, opener)` tuples. Try the direction's
  opener first, then fall back to the safe `low_hero_push`:

```python
    o = getattr(job.direction, "opener", "low_hero_push")
    attempts = ((job.direction.pace, jitter, True, o), (job.direction.pace, 0.0, True, o),
                (job.direction.pace, 0.0, True, "low_hero_push"), ("medium", 0.0, True, "low_hero_push"),
                ("medium", 0.0, False, "low_hero_push"))
```

- [ ] **Step 4: Run** the new test, then the phase-3 fallback tests:
  `py -m pytest engine/tests/test_director_fallback_opener.py engine/tests/test_director_fallback.py -q` → PASS.
  If an opener fails the checker on some subject, that is acceptable: the safety attempts cover it,
  and Task 41's floor will mark that opener non-viable for that subject. Record which subject and
  opener in the Task 50 register.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): fallback honours the direction's opener and world, safe opener last" -- engine/director/fallback.py engine/tests/test_director_fallback_opener.py
```

### Task 41: The quality floor

**Files:**
- Create: `engine/director/floor.py`
- Test: `engine/tests/test_director_floor.py`

- [ ] **Step 1: Write the failing test:**

```python
import dataclasses

from engine.catalog import Catalog
from engine.director.axes import axis_values
from engine.director.dice import candidates
from engine.director.floor import _RANK, make_viable, script_tier
from engine.director.job import make_job
from engine.tests.test_director_package import _p


def _job(model):
    cat, p = Catalog.load(), _p(model)
    return make_job("", p, cat, seed=2), p, cat


def test_viable_is_cached_and_boolean():
    job, p, cat = _job("pocket_watch")
    v = make_viable(job, p, cat)
    c = candidates(axis_values(p, cat, job.fmt))[0]
    assert v(c) in (True, False) and v(c) == v(c) and len(v.cache) == 1


def test_floor_never_below_the_phase3_default():
    job, p, cat = _job("sports_car")
    v = make_viable(job, p, cat)
    assert _RANK[v.floor] <= _RANK["T3"] and v.floor == min(("T3", v.baseline), key=_RANK.get)


def test_non_honoured_opener_is_not_viable(monkeypatch):
    job, p, cat = _job("pocket_watch")
    import engine.director.floor as fl
    monkeypatch.setattr(fl, "opener_of", lambda s: "something_else")
    c = candidates(axis_values(p, cat, job.fmt))[0]
    assert make_viable(job, p, cat)(c) is False


def test_script_tier_matches_the_harness_definition():
    from harness.director_eval import s_tier
    job, p, cat = _job("pocket_watch")
    from engine.director.fallback import build_fallback
    s = build_fallback(job, p, cat)
    assert script_tier(s, p, cat) == s_tier(s, p, cat)
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/floor.py`:**

```python
"""The quality floor on variety: novelty never buys a worse clip. A direction is viable for a subject
when its safe fallback script passes the checker, honours the direction's opener and pace, and reaches
the floor tier on the script-level [S] items. The floor is min(T3, the tier the phase-3 default
direction reaches here), so the dice can never take a subject below today's quality. The LLM's own
script may differ; this proves that a good script exists for the direction before the dice may pick it."""
import dataclasses

from engine.craft_rules import score_script
from engine.director.axes import opener_of
from engine.director.direction import direction_of, interim_direction, make_id
from engine.director.fallback import FallbackError, build_fallback

FLOOR_TIER = "T3"
_RANK = {"T1": 1, "T2": 2, "T3": 3}


def script_tier(script, profile, catalog):
    """Same definition as harness.director_eval.s_tier: script level only, not a quality grade."""
    items = score_script(script, profile, catalog)
    fail = lambda *pre: any(r.status == "fail" and r.id.startswith(pre) for r in items)  # noqa: E731
    if fail("T1-") or fail("T2-"):
        return "T1"
    return "T2" if fail("T3-", "V-") else "T3"


def _tier_of(job, profile, catalog):
    try:
        return script_tier(build_fallback(job, profile, catalog), profile, catalog)
    except FallbackError:
        return "T1"


def make_viable(job, profile, catalog, floor=FLOOR_TIER):
    baseline = _tier_of(dataclasses.replace(job, direction=interim_direction(job.seed, profile, catalog)),
                        profile, catalog)
    need = min(_RANK[floor], _RANK[baseline])
    cache = {}

    def viable(axes):
        key = make_id(axes)
        if key not in cache:
            try:
                s = build_fallback(dataclasses.replace(job, direction=direction_of(axes, "dice")), profile, catalog)
                pace = ((s.get("edit") or {}).get("params") or {}).get("pace", axes["pace"])
                cache[key] = (opener_of(s) == axes["opener"] and pace == axes["pace"]
                              and _RANK[script_tier(s, profile, catalog)] >= need)
            except FallbackError:
                cache[key] = False
        return cache[key]

    viable.cache, viable.baseline = cache, baseline
    viable.floor = next(t for t, r in _RANK.items() if r == need)
    return viable
```

- [ ] **Step 4: Run.** `py -m pytest engine/tests/test_director_floor.py -q` → PASS.

- [ ] **Step 5: Measure (no render, CPU only, about a minute).** Count viable directions per eval
  subject:

```bash
py -c "from engine.catalog import Catalog; from engine.director.axes import axis_values; from engine.director.dice import candidates; from engine.director.floor import make_viable; from engine.director.job import make_job; from engine.tests.test_director_package import _p
cat=Catalog.load()
for m in ['camera_01','cesium_man','flighthelmet','mid_century_lounge_chair','pocket_watch','sneaker','sports_car','toycar','vintage_microscope']:
    p=_p(m); j=make_job('',p,cat,seed=0); v=make_viable(j,p,cat); c=candidates(axis_values(p,cat,j.fmt)); n=sum(v(x) for x in c); print(m, v.floor, n, '/', len(c))"
```

Paste the table into the Task 50 register (population: nine eval profiles, seed 0, 10 s, date). If a
subject has **0 viable**, stop and report. That means the floor rejects everything; do not loosen
`FLOOR_TIER` silently.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(director): quality floor - a direction is viable only if its fallback reaches today's tier" -- engine/director/floor.py engine/tests/test_director_floor.py
```

---

## Chunk 3: Memory, choosing the direction, wiring into the job and pipeline

### Task 42: Variety memory (file-based, opaque ids only)

**Files:**
- Create: `engine/director/memory.py`
- Test: `engine/tests/test_director_memory.py`

- [ ] **Step 1: Write the failing test:**

```python
import json

import pytest

from engine.director.direction import direction_of
from engine.director.memory import MAX_ENTRIES, VarietyMemory

AX = {"world": "studio_cyc", "mood": "clean", "tone": "white", "pace": "calm", "opener": "arc_orbit",
      "weather": "dry", "wind": "calm"}


def _d(mood="clean"):
    return direction_of({**AX, "mood": mood}, "dice")


def test_record_and_recent_in_order(tmp_path):
    m = VarietyMemory(tmp_path)
    m.record("u1", "s1", _d("clean"), seed=1, duration_s=10)
    m.record("u1", "s1", _d("vivid"), seed=2, duration_s=8)
    assert m.recent("u1", "s1") == [_d("clean").id, _d("vivid").id]
    assert m.recent("u1", "other") == [] and m.recent("u2", "s1") == []


def test_files_never_contain_raw_ids_or_prompt_text(tmp_path):
    m = VarietyMemory(tmp_path)
    m.record("alice_123", "subj", _d(), seed=1, duration_s=10)
    names = [p.name for p in tmp_path.rglob("*")]
    assert not any("alice" in n or "subj" in n for n in names)
    doc = json.loads(next(tmp_path.rglob("*.json")).read_text(encoding="utf-8"))
    assert set(doc["entries"][0]) == {"id", "seed", "durationS", "source", "day"}


@pytest.mark.parametrize("bad", ["", "../x", "a/b", "x" * 65, "é", None, 5])
def test_bad_opaque_ids_are_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        VarietyMemory(tmp_path).recent(bad, "s")


def test_entries_are_capped(tmp_path):
    m = VarietyMemory(tmp_path)
    for i in range(MAX_ENTRIES + 7):
        m.record("u", "s", _d(), seed=i, duration_s=10)
    assert len(m.recent("u", "s")) == MAX_ENTRIES


def test_corrupt_file_reads_as_empty_and_is_overwritten(tmp_path):
    m = VarietyMemory(tmp_path)
    m.record("u", "s", _d(), seed=1, duration_s=10)
    f = next(tmp_path.rglob("*.json"))
    f.write_text("{not json", encoding="utf-8")
    assert m.recent("u", "s") == []
    m.record("u", "s", _d(), seed=2, duration_s=10)
    assert len(m.recent("u", "s")) == 1


def test_dislikes_merge_and_cap(tmp_path):
    m = VarietyMemory(tmp_path)
    m.dislike("u", "s", {"mood": ["noir"], "opener": ["arc_orbit"], "bogus": ["x"]})
    m.dislike("u", "s", {"mood": ["vivid", "clean", "teal_night", "warm_golden"]})
    av = m.avoided("u", "s")
    assert set(av) == {"mood", "opener"} and len(av["mood"]) == 3 and "noir" not in av["mood"]  # newest 3 kept


def test_forget_deletes_everything_for_one_user(tmp_path):
    m = VarietyMemory(tmp_path)
    m.record("u", "s", _d(), seed=1, duration_s=10)
    m.record("v", "s", _d(), seed=1, duration_s=10)
    m.forget("u")
    assert m.recent("u", "s") == [] and m.recent("v", "s") != []


def test_env_var_sets_the_root(tmp_path, monkeypatch):
    monkeypatch.setenv("VALORA_VARIETY_DIR", str(tmp_path / "mem"))
    assert VarietyMemory().root == tmp_path / "mem"
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/memory.py`:**

```python
"""Variety memory (spec §6 layer 3): per user and per subject, the last directions and the values the
user disliked. Local files only. Privacy by construction: the caller passes OPAQUE ids (never an
email or a name), which are hashed again before they touch a path. No prompt text is stored.
Files are bounded, writes are atomic, and a corrupt file reads as empty. forget(user) serves a
deletion request."""
import datetime
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from engine.director.direction import AXES

MEMORY_ENV = "VALORA_VARIETY_DIR"
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "var" / "variety"
MAX_ENTRIES = 50           # (eng) far above memoryN; bounds the file
MAX_DISLIKES_PER_AXIS = 3  # (eng)
MAX_FILE_BYTES = 256_000
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _key(opaque):
    if not isinstance(opaque, str) or not _ID.match(opaque):
        raise ValueError("variety memory ids must be opaque tokens of 1-64 letters, digits, _ or -")
    return hashlib.sha256(f"valora-variety:{opaque}".encode()).hexdigest()[:24]


class VarietyMemory:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get(MEMORY_ENV) or DEFAULT_DIR)

    def _path(self, user, subject):
        return self.root / _key(user) / f"{_key(subject)}.json"

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
        return [e["id"] for e in self._load(user, subject)["entries"] if isinstance(e, dict) and "id" in e]

    def record(self, user, subject, direction, *, seed, duration_s):
        doc = self._load(user, subject)
        doc["entries"] = (doc["entries"] + [{"id": direction.id, "seed": seed, "durationS": duration_s,
                                             "source": direction.source,
                                             "day": datetime.date.today().isoformat()}])[-MAX_ENTRIES:]
        self._save(user, subject, doc)

    def avoided(self, user, subject):
        return {a: list(v) for a, v in self._load(user, subject)["dislikes"].items() if a in AXES and v}

    def dislike(self, user, subject, avoid):
        doc = self._load(user, subject)
        for axis, vals in (avoid or {}).items():
            if axis not in AXES:
                continue
            merged = [v for v in doc["dislikes"].get(axis, []) if v not in vals] + [str(v)[:40] for v in vals]
            doc["dislikes"][axis] = merged[-MAX_DISLIKES_PER_AXIS:]
        self._save(user, subject, doc)

    def forget(self, user):
        shutil.rmtree(self.root / _key(user), ignore_errors=True)
```

- [ ] **Step 4: Run.** PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): variety memory - local, hashed opaque ids, bounded, atomic, forget()" -- engine/director/memory.py engine/tests/test_director_memory.py
```

### Task 43: Choosing the direction — replay, more like this, dice; catalog honesty

**Files:**
- Create: `engine/director/variety.py`
- Test: `engine/tests/test_director_variety.py`

- [ ] **Step 1: Write the failing test:**

```python
from engine.catalog import Catalog
from engine.director.direction import direction_of, make_id
from engine.director.job import make_job
from engine.director.variety import choose_direction, reachable, subject_key
from engine.tests.test_director_package import _p

FMT = {"aspect": "9:16", "durationS": 10, "fps": 30}


def _choose(prompt="", seed=1, model="pocket_watch", **kw):
    cat, p = Catalog.load(), _p(model)
    return choose_direction(prompt, p, cat, seed, FMT, job=make_job(prompt, p, cat, seed=seed), **kw)


def test_empty_prompt_rolls_dice_with_one_assumption_line():
    c = _choose()
    assert c.direction.source == "dice" and len(c.notes) >= 1 and "dice" in c.notes[0]


def test_prompt_pins_beat_the_dice():
    for s in range(8):
        d = _choose("luxury, slow", seed=s).direction
        assert (d.mood, d.pace) == ("premium_dark", "calm") and d.pinned == ("mood", "pace")


def test_more_like_this_keeps_the_direction():
    first = _choose(seed=1).direction
    again = _choose(seed=99, like=first).direction
    assert again.axes() == first.axes() and again.source == "more_like_this"


def test_more_like_this_from_a_script_and_pins_still_win():
    first = _choose(seed=1).direction
    d = _choose("neon", seed=5, like={"direction": {"id": first.id}}).direction
    assert d.mood == "teal_night" and d.opener == first.opener


def test_memory_snapshot_is_excluded():
    recent = [_choose(seed=s).direction.id for s in range(4)]
    for s in range(10, 20):
        assert _choose(seed=s, recent=recent).direction.id not in recent


def test_unknown_pinned_value_is_ignored_not_crashing():
    c = _choose("black and white")          # noir exists in the catalog -> pinned
    assert c.direction.mood == "noir"


def test_subject_key_is_stable_opaque_and_distinct():
    a, b = subject_key(_p("pocket_watch")), subject_key(_p("sneaker"))
    assert a == subject_key(_p("pocket_watch")) and a != b and len(a) == 16 and a.isalnum()


def test_reachable_reports_catalog_honesty():
    cat, p = Catalog.load(), _p("pocket_watch")
    r = reachable(p, cat, FMT)
    assert r["combinations"] > 1 and "world" in r["singleValued"] and r["guaranteedDistinctInARow"] >= 2
    assert "note" in r
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/variety.py`:**

```python
"""Stage 2 of spec §3: the job's direction. Order: 'more like this' (keep the direction with a new seed,
so only layer 1 changes), else the dice (layers 2-3: pins from the prompt, this user's recent
directions excluded, disliked values avoided, the quality floor enforced), else the phase-3 interim
direction. Pure: the caller reads and writes variety memory (pipeline.py). A replayed direction is
passed straight to make_job(direction=...) and never reaches here."""
import hashlib
import json
from dataclasses import dataclass

from engine.director.axes import DICE, axis_values
from engine.director.dice import candidates, roll
from engine.director.direction import AXES, Direction, direction_of, interim_direction, parse_id
from engine.director.family import family
from engine.director.floor import make_viable
from engine.director.pins import read_direction_pins
from engine.director.taste import STATS

FLAG_NOTES = {"avoid_relaxed": "every option was on your 'less like this' list; relaxed it to find one"}


@dataclass(frozen=True)
class Choice:
    direction: Direction
    notes: tuple = ()
    flags: tuple = ()


def subject_key(profile):
    blob = json.dumps(profile.to_dict(), sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _load_stats():
    try:
        return json.loads(STATS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def like_axes(like):
    """'more like this' from a Direction, a script (or its direction dict) or a direction id."""
    if isinstance(like, Direction):
        return like.axes()
    if isinstance(like, dict):
        return parse_id((like.get("direction") or like)["id"])
    return parse_id(str(like))


def _line(d):
    words = f"{d.mood}, {d.pace} pace, {d.tone} backdrop, opens with {d.opener}"
    kept = f"; kept from the prompt: {', '.join(d.pinned)}" if d.pinned else ""
    return f"dice direction: {words}{kept}"


def choose_direction(prompt, profile, catalog, seed, fmt, *, job=None, like=None, avoid=None, recent=(),
                     stats=None):
    known = axis_values(profile, catalog, fmt, rollable=False)
    pins = {a: v for a, v in read_direction_pins(prompt).items() if v in known[a]}
    if like is not None:
        d = direction_of({**like_axes(like), **pins}, "more_like_this", pinned=pins)
        return Choice(d, (f"more like this: kept the direction ({d.mood}, {d.pace} pace); only details change",))
    viable = make_viable(job, profile, catalog) if job is not None else None
    r = roll(seed, axis_values(profile, catalog, fmt), pins=pins, recent=recent, avoid=avoid, viable=viable,
             family_name=family(profile), stats=_load_stats() if stats is None else stats)
    if r.axes is None:
        return Choice(interim_direction(seed, profile, catalog),
                      ("no rolled direction met the quality floor; used the default direction",), r.flags)
    d = direction_of(r.axes, "dice", pinned=pins)
    return Choice(d, (_line(d),) + tuple(FLAG_NOTES[f] for f in r.flags if f in FLAG_NOTES), r.flags)


def replay_kwargs(script):
    """Everything direct() needs to rebuild this job exactly (same seed, direction, duration)."""
    kw = {"seed": script["seed"], "direction": Direction.from_script(script),
          "duration": script["format"]["durationS"]}
    if script.get("markers"):
        kw["markers"] = script["markers"]
    return script.get("prompt", ""), kw


def reachable(profile, catalog, fmt, job=None):
    """Catalog-size honesty (spec §6 'honest limit'): how many directions this subject can really get."""
    vals = axis_values(profile, catalog, fmt)
    cands = candidates(vals)
    out = {"perAxis": vals, "singleValued": [a for a in AXES if len(vals[a]) == 1], "combinations": len(cands)}
    if job is not None:
        v = make_viable(job, profile, catalog)
        out["viable"], out["floor"] = sum(1 for c in cands if v(c)), v.floor
    n = out.get("viable", out["combinations"])
    out["guaranteedDistinctInARow"] = min(n, DICE["memoryN"] + 1)
    out["note"] = (f"{n} distinct directions for this subject; axes with one value: "
                   f"{', '.join(out['singleValued']) or 'none'}. Perceived variety is capped by the catalog.")
    return out
```

`make_job` does not take `like`/`recent` until Task 44. The tests call `make_job(prompt, p, cat,
seed=...)` only to get a job for the floor, and that call works today.

- [ ] **Step 4: Run.** PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): choose_direction (more-like-this, dice, interim), replay kwargs, catalog honesty" -- engine/director/variety.py engine/tests/test_director_variety.py
```

### Task 44: Wire the dice into the job (duration included)

Re-read `engine/director/job.py` and `intent.py` at HEAD.

**Files:**
- Modify: `engine/director/intent.py` (`make_format`)
- Modify: `engine/director/job.py` (`Job`, `make_job`)
- Test: add to `engine/tests/test_director_variety.py`

- [ ] **Step 1: Write the failing tests** (append):

```python
def test_make_job_uses_the_dice_and_rolls_duration():
    cat, p = Catalog.load(), _p("pocket_watch")
    jobs = [make_job("", p, cat, seed=s) for s in range(12)]
    assert all(j.direction.source == "dice" for j in jobs)
    assert {j.fmt["durationS"] for j in jobs} <= {8, 10, 12} and len({j.fmt["durationS"] for j in jobs}) > 1
    assert any("dice direction" in n for n in jobs[0].notes)


def test_pinned_or_given_duration_wins():
    cat, p = Catalog.load(), _p("pocket_watch")
    assert make_job("a 15 second clip", p, cat, seed=1).fmt["durationS"] == 15
    assert make_job("", p, cat, seed=1, duration=10).fmt["durationS"] == 10


def test_given_direction_is_used_verbatim():
    cat, p = Catalog.load(), _p("pocket_watch")
    d = make_job("", p, cat, seed=1).direction
    j = make_job("", p, cat, seed=77, direction=d)
    assert j.direction == d


def test_like_keeps_the_liked_duration():
    cat, p = Catalog.load(), _p("pocket_watch")
    script = {"direction": {"id": make_job("", p, cat, seed=1).direction.id}, "format": {"durationS": 12}}
    assert make_job("", p, cat, seed=5, like=script).fmt["durationS"] == 12
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement.**

`intent.make_format(pins, seed=None, duration=None)`: change `d = pins.get("durationS", DEFAULT_DURATION_S)`
to `d = pins.get("durationS", DEFAULT_DURATION_S if duration is None else duration)`. Update the
docstring: "duration is the dice's roll (phase 4); a prompt pin beats it". `DEFAULT_DURATION_S`
stays 10 for callers that roll nothing.

`job.py`: add a `varietyFlags: list = field(default_factory=list)` field to `Job`. Change `make_job`:

```python
def make_job(prompt, profile, catalog, seed=None, markers=None, direction=None, *, like=None, avoid=None,
             recent=(), duration=None, stats=None):
    ...  # prompt / seed validation unchanged
    pins = read_pins(prompt)
    if duration is None and "durationS" not in pins and direction is None:
        duration = (like.get("format", {}).get("durationS") if isinstance(like, dict) else None) or roll_duration(seed)
    fmt = make_format(pins, seed, duration=duration)
    ...  # markers unchanged
    job = Job(prompt=prompt, seed=seed, fmt=fmt, direction=direction or interim_direction(seed, profile, catalog),
              family=family(profile), pins=pins, markers=markers, detected=unsupported(asks, catalog, profile),
              asks=asks, notes=format_notes(pins, fmt))
    if direction is None:
        c = choose_direction(prompt, profile, catalog, seed, fmt, job=job, like=like, avoid=avoid, recent=recent,
                             stats=stats)
        job = dataclasses.replace(job, direction=c.direction, notes=job.notes + list(c.notes),
                                  varietyFlags=list(c.flags))
    return job
```

Imports: `import dataclasses`, `from engine.director.dice import roll_duration`, and
`from engine.director.variety import choose_direction`. Check for an import cycle:
`variety → floor → fallback`, and `fallback` must not import `job`. If it does, import
`choose_direction` inside `make_job`.

- [ ] **Step 4: Run the new tests**, then the whole fast loop:
  `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"`.

- [ ] **Step 5: Fix the expected breakages. Only these kinds are allowed:**
  - Tests that feed a 10 s `FakeProvider` reply (for example `test_director_pipeline.py`,
    `test_director_recorded.py`, `test_cli.py::test_direct_with_a_fake_provider`, the Task 40 test)
    now get a rolled 8/10/12 s job, so the reply fails `shots` contiguity and falls back. Fix: pass
    `duration=10` to the `direct(...)` / `make_job(...)` call (the kwarg reaches `direct` in Task 46;
    until then pass it through `make_job` only), or pin it in the prompt. **Never** weaken an
    assertion.
  - Tests asserting exact `assumptions` lists now see one extra `dice direction: ...` line. Update
    the expected list and say so in the commit.
  - Anything else that goes red: **stop and investigate** (@superpowers:systematic-debugging). Do not
    patch around it.
  Those test files belong to phase 3. Edit only the failing call sites, and re-read each file first.

- [ ] **Step 6: Commit** (list every touched test file explicitly):

```bash
git diff --name-only
git commit -m "feat(director): the job rolls its direction and duration from the dice (phase-4 swap for the interim direction)" -- engine/director/intent.py engine/director/job.py engine/tests/test_director_variety.py <each phase-3 test file you edited>
```

### Task 45: Direction adherence, and the director sees world + opener

The LLM tends to pick one safe look (spec §11). On vague prompts, the rolled mood, pace and tone are
**enforced in place**. On long prompts, only the pinned axes are enforced, and drift is recorded as
`info`.

**Files:**
- Create: `engine/director/adherence.py`
- Modify: `engine/director/pipeline.py` (`_evaluate_reply`), `engine/director/request.py` (`first_message`),
  `engine/director/rulebook.py` (`DEFAULT`), `engine/director/rulebook/rulebook.txt` (regenerated)
- Test: `engine/tests/test_director_adherence.py`

- [ ] **Step 1: Write the failing test:**

```python
import copy
import json

from engine.director.adherence import drift, enforce_direction
from engine.director.direction import direction_of
from engine.director.rulebook import EXAMPLES_DIR, example_script

AX = {"world": "studio_cyc", "mood": "teal_night", "tone": "black", "pace": "calm", "opener": "low_hero_push",
      "weather": "dry", "wind": "calm"}
S = example_script(json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8")))


def _drifted():
    s = copy.deepcopy(S)
    s["grade"] = {"id": "mood_grade", "params": {"preset": "clean"}}
    s.setdefault("edit", {"id": "sequence", "params": {}})["params"]["pace"] = "hype"
    s["world"] = {"id": "studio_cyc", "params": {"tone": "white"}}
    return s


def test_drift_lists_the_axes():
    assert set(drift(_drifted(), direction_of(AX, "dice"))) >= {"mood", "pace", "tone"}


def test_vague_prompt_enforces_in_place():
    s, issues = enforce_direction(_drifted(), direction_of(AX, "dice"), enforce=True)
    assert s["grade"]["params"]["preset"] == "teal_night" and s["edit"]["params"]["pace"] == "calm"
    assert s["world"]["params"]["tone"] == "black"
    assert {i.code for i in issues} == {"direction_enforced"} and all(i.severity == "repaired" for i in issues)


def test_long_prompt_only_enforces_pins():
    d = direction_of(AX, "dice", pinned={"mood": "teal_night"})
    s, issues = enforce_direction(_drifted(), d, enforce=False)
    assert s["grade"]["params"]["preset"] == "teal_night" and s["edit"]["params"]["pace"] == "hype"
    assert any(i.code == "direction_drift" and i.severity == "info" for i in issues)


def test_first_message_carries_world_and_opener():
    from engine.director.request import first_message
    from engine.tests.test_director_package import _p
    msg = first_message(fmt={"aspect": "9:16", "durationS": 10, "fps": 30}, direction=direction_of(AX, "dice"),
                        profile=_p("pocket_watch"), prompt="", markers=[], detected=[])
    job = json.loads(msg.split("<job>")[1].split("</job>")[0])
    assert job["direction"]["opener"] == "low_hero_push" and job["direction"]["world"] == "studio_cyc"
    assert "weather" not in job["direction"] and "wind" not in job["direction"]  # director never gets wind
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `engine/director/adherence.py`:**

```python
"""Keep the LLM on the rolled direction (spec §3: variety comes from the dice, §11: the LLM converges on
one safe look). mood -> mood_grade preset, pace -> sequence pace, tone -> studio_cyc tone are fixed in
place when enforced; world and opener are only measured (changing them would rebuild shots)."""
from engine.director.axes import opener_of
from engine.issues import Issue

_PATHS = {"mood": ("grade", "preset", "mood_grade"), "pace": ("edit", "pace", "sequence"),
          "tone": ("world", "tone", "studio_cyc")}


def _get(script, axis):
    key, param, bid = _PATHS[axis]
    ref = script.get(key) if isinstance(script.get(key), dict) else None
    if not ref or ref.get("id") != bid:
        return None, False
    return (ref.get("params") or {}).get(param), True


def drift(script, d):
    out = []
    for axis in _PATHS:
        v, fixable = _get(script, axis)
        if fixable and v is not None and v != getattr(d, axis):
            out.append(axis)
        elif axis == "mood" and not fixable and d.mood != "clean":  # neutral_film reads as clean
            out.append(axis)
    if isinstance(script.get("world"), dict) and script["world"].get("id") != d.world:
        out.append("world")
    try:
        if opener_of(script) != d.opener:
            out.append("opener")
    except (KeyError, IndexError, TypeError):
        pass
    return out


def enforce_direction(script, d, enforce):
    issues = []
    for axis in drift(script, d):
        want = getattr(d, axis)
        v, fixable = _get(script, axis) if axis in _PATHS else (None, False)
        if fixable and (enforce or axis in d.pinned):
            key, param, _ = _PATHS[axis]
            script[key].setdefault("params", {})[param] = want
            issues.append(Issue("direction_enforced", f"{key}.params.{param}", f"{v} -> {want} (the job's direction)",
                                "repaired"))
        else:
            issues.append(Issue("direction_drift", axis, f"script differs from the direction ({want})", "info"))
    return script, issues
```

- [ ] **Step 4: Wire it in.** Make three changes:
  - `pipeline._evaluate_reply`: after `script, sissues = sanitize(...)`, add
    `script, dissues = enforce_direction(script, job.direction, enforce=is_vague(job.prompt))` and
    `sissues = sissues + dissues`. Imports: `from engine.director.adherence import enforce_direction`
    and `from engine.director.intent import is_vague`. Guard it: if `script` is not a dict, or has no
    `shots` list, skip enforcement (the checker reports that shape error itself).
  - `request.first_message`: the `"direction"` dict adds `"world": direction.world` and
    `"opener": direction.opener`, using `getattr(..., default)` so older `Direction` objects still
    work. Never add weather or wind.
  - `rulebook.DEFAULT` item 1 becomes: "The job's direction is the brief: its mood is the mood_grade
    preset, its pace the sequence pace, its tone the studio_cyc tone, its world the world block, and
    its opener the first shot's camera (macro_detail means open on a detail shot). When the prompt
    is short the system enforces mood, pace and tone."

- [ ] **Step 5: Regenerate the rulebook.** Run `py -m engine.director.rulebook --write`, then
  `git diff --stat engine/director/rulebook/rulebook.txt`. The file may already carry another lane's
  uncommitted edits (it was dirty on 2026-09-24). If `git diff` shows changes that are not yours
  (anything outside part 4 "When the prompt says little"), **do not commit rulebook.txt**. Commit the
  code, and write "rulebook.txt regenerated but held: mixed with <lane>'s edits" in the handoff. The
  rulebook equality test then tells that lane to regenerate.

- [ ] **Step 6: Run** the adherence, request, rulebook and pipeline tests, then the fast loop → PASS.

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(director): enforce the rolled direction on vague prompts; the director sees world and opener" -- engine/director/adherence.py engine/director/pipeline.py engine/director/request.py engine/director/rulebook.py engine/director/rulebook/rulebook.txt engine/tests/test_director_adherence.py
```

### Task 46: Pipeline — memory, like, avoid, replay

Re-read `engine/director/pipeline.py` at HEAD.

**Files:**
- Modify: `engine/director/pipeline.py` (`DirectorResult`, `direct`)
- Test: `engine/tests/test_director_replay.py`

- [ ] **Step 1: Write the failing test:**

```python
from engine.catalog import Catalog
from engine.director.distance import script_distance
from engine.director.llm import FakeProvider
from engine.director.memory import VarietyMemory
from engine.director.pipeline import direct
from engine.director.variety import replay_kwargs, subject_key
from engine.tests.test_director_package import _p

REFUSE = [{"stop_reason": "refusal", "text": ""}]


def _run(seed, **kw):
    return direct(kw.pop("prompt", ""), _p("pocket_watch"), provider=FakeProvider(REFUSE * 3), seed=seed, **kw)


def test_two_runs_differ_in_direction_or_details():
    a, b = _run(1), _run(2)
    assert a.script != b.script and script_distance(a.script, b.script, Catalog.load()) > 0


def test_replay_reproduces_the_script_exactly():
    a = _run(5)
    prompt, kw = replay_kwargs(a.script)
    b = direct(prompt, _p("pocket_watch"), provider=FakeProvider(REFUSE * 3), **kw)
    assert b.script == {**a.script, "direction": {**a.script["direction"], "source": "replay"}}


def test_memory_is_read_and_written(tmp_path):
    mem = VarietyMemory(tmp_path)
    ids = [_run(s, memory=mem, user="u1").script["direction"]["id"] for s in range(6)]
    assert len(set(ids)) == 6                                    # last 5 excluded -> 6 distinct in a row
    assert mem.recent("u1", subject_key(_p("pocket_watch"))) == ids


def test_more_like_this_changes_only_details(tmp_path):
    a = _run(1)
    b = _run(2, like=a.script)
    assert b.script["direction"]["id"] == a.script["direction"]["id"] and b.script != a.script
    assert b.script["format"]["durationS"] == a.script["format"]["durationS"]


def test_less_like_this_is_remembered(tmp_path):
    mem = VarietyMemory(tmp_path)
    a = _run(1, memory=mem, user="u1")
    mood = a.script["direction"]["id"].split("/")[1]
    _run(2, memory=mem, user="u1", avoid={"mood": [mood]})
    for s in range(3, 9):
        assert _run(s, memory=mem, user="u1").script["direction"]["id"].split("/")[1] != mood


def test_memory_write_failure_never_fails_the_job(tmp_path, monkeypatch):
    mem = VarietyMemory(tmp_path)
    monkeypatch.setattr(mem, "record", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    r = _run(1, memory=mem, user="u1")
    assert r.script and "memory_write_failed" in r.direction["flags"]


def test_result_reports_the_direction():
    r = _run(1)
    assert set(r.direction) == {"id", "source", "axes", "pinned", "flags"}
```

`test_replay_reproduces_the_script_exactly` compares everything except `direction.source`. If the
script records the source (it does, via sanitize/fallback), the replay says `replay` and nothing
else may differ.

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** in `pipeline.py`:

```python
@dataclass
class DirectorResult:
    ...                              # existing fields unchanged
    direction: dict = field(default_factory=dict)   # {id, source, axes, pinned, flags} (phase 4)


def direct(prompt, profile, *, provider, catalog=None, seed=None, markers=None, direction=None, rulebook=None,
           like=None, avoid=None, user=None, subject_id=None, memory=None, duration=None):
    t0 = time.perf_counter()
    catalog = catalog or Catalog.load()
    remember = memory is not None and user is not None
    subject = subject_id or subject_key(profile)
    recent, stored = (memory.recent(user, subject), memory.avoided(user, subject)) if remember else ((), {})
    merged = {a: sorted(set(stored.get(a, [])) | set((avoid or {}).get(a, []))) for a in set(stored) | set(avoid or {})}
    job = make_job(prompt, profile, catalog, seed=seed, markers=markers, direction=direction, like=like,
                   avoid=merged or None, recent=recent, duration=duration)
    ...                              # the existing loop, unchanged
    flags = list(job.varietyFlags)
    if remember:
        try:
            if avoid:
                memory.dislike(user, subject, avoid)
            memory.record(user, subject, job.direction, seed=job.seed, duration_s=job.fmt["durationS"])
        except OSError:
            flags.append("memory_write_failed")
    d = job.direction
    return DirectorResult(..., direction={"id": d.id, "source": d.source, "axes": d.axes(),
                                          "pinned": list(d.pinned), "flags": flags})
```

Import `subject_key` from `engine.director.variety`. `user` / `subject_id` are validated by
`VarietyMemory` (a `ValueError` becomes `DirectorInputError`: catch `ValueError` around the
`memory.recent` call and re-raise as `DirectorInputError("user id ...")`). Memory writes happen only
after a script exists, so a rejected input records nothing.

- [ ] **Step 4: Run** the replay test and the fast loop → PASS. If `test_replay...` fails on a
  difference other than `direction.source`, find what is not seeded (@superpowers:systematic-debugging).
  Every random draw in the director must come from `random.Random(f"...:{seed}...")`. That is the fix
  to make; do not relax the test.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(director): direct() reads/writes variety memory; more-like-this, less-like-this, exact replay" -- engine/director/pipeline.py engine/tests/test_director_replay.py
```

---

## Chunk 4: CLI, harness variety score, finish

### Task 47: CLI — `direct` variety flags and `variety-report`

Re-read `engine/__main__.py` at HEAD.

**Files:**
- Modify: `engine/__main__.py` (docstring, `main`, `_run`, `_direct`, new `_variety_report`)
- Test: `engine/tests/test_cli_variety.py`

- [ ] **Step 1: Write the failing test:**

```python
import json

from engine.__main__ import EXIT_BAD_INPUT, EXIT_OK, main

PROFILE = "engine/tests/fixtures/profiles/pocket_watch.json"
REFUSE = "engine/tests/fixtures/director/refuse.json"


def _fixture(tmp_path):
    p = tmp_path / "refuse.json"
    p.write_text(json.dumps({"replies": [{"stop_reason": "refusal", "text": ""}] * 3}), encoding="utf-8")
    return f"fake:{p}"


def _direct(tmp_path, capsys, *extra):
    rc = main(["direct", "--profile", PROFILE, "--provider", _fixture(tmp_path), *extra])
    return rc, json.loads(capsys.readouterr().out)


def test_memory_flags_rotate_directions(tmp_path, capsys):
    ids = []
    for s in range(3):
        rc, out = _direct(tmp_path, capsys, "--seed", str(s), "--user", "u1", "--memory-dir", str(tmp_path / "m"))
        assert rc == EXIT_OK
        ids.append(out["direction"]["id"])
    assert len(set(ids)) == 3


def test_like_and_replay(tmp_path, capsys):
    out_file = tmp_path / "a.json"
    _direct(tmp_path, capsys, "--seed", "4", "--out", str(out_file))
    a = json.loads(out_file.read_text(encoding="utf-8"))
    _, like = _direct(tmp_path, capsys, "--seed", "9", "--like", str(out_file))
    assert like["direction"]["id"] == a["direction"]["id"]
    _, rep = _direct(tmp_path, capsys, "--replay", str(out_file))
    assert rep["script"]["shots"] == a["shots"]


def test_bad_user_id_is_bad_input(tmp_path, capsys):
    rc = main(["direct", "--profile", PROFILE, "--provider", _fixture(tmp_path), "--user", "../x",
               "--memory-dir", str(tmp_path)])
    assert rc == EXIT_BAD_INPUT


def test_avoid_parses_axis_value(tmp_path, capsys):
    for s in range(4):
        _, out = _direct(tmp_path, capsys, "--seed", str(s), "--avoid", "mood=clean", "--avoid", "mood=vivid")
        assert out["direction"]["axes"]["mood"] not in ("clean", "vivid")


def test_variety_report(capsys):
    assert main(["variety-report", "--profile", PROFILE]) == EXIT_OK
    r = json.loads(capsys.readouterr().out)
    assert r["combinations"] > 1 and "singleValued" in r
```

Remove the unused `REFUSE` constant if your linter complains.

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement.** Add these flags to the `direct` subparser: `--user`, `--subject-id`,
  `--memory-dir` (memory is on only when both `--user` and `--memory-dir` are given; the env var
  `VALORA_VARIETY_DIR` also enables it when `--user` is set), `--like SCRIPT`, `--less-like SCRIPT`,
  `--avoid AXIS=VALUE` (`action="append"`) and `--replay SCRIPT` (conflicts with `--seed`/`--prompt`).
  Add a new `variety-report` subparser: `--profile` (required), `--aspect` (default `9:16`),
  `--viable` (also runs the floor, which is slower).

  In `_direct`:
  - `--replay` → `prompt, kw = replay_kwargs(script)`.
  - `--less-like` → `avoid` gets `{mood: [m], opener: [o]}` from that script's direction id (plus
    `world` when the subject has more than one world).
  - `--avoid` entries split on the first `=`. An axis not in `AXES` is bad input (exit 5).
  - Pass `memory=VarietyMemory(a.memory_dir)`, `user`, `subject_id`, `like`, `avoid` to `direct`.
  - A `ValueError` / `DirectorInputError` exits `EXIT_BAD_INPUT`.

  `_variety_report` prints
  `json.dumps(reachable(prof, cat, {"aspect": a.aspect, "durationS": 10, "fps": 30}, job=make_job("", prof, cat, seed=0) if a.viable else None), indent=2)`.
  Update the module docstring's usage lines.

- [ ] **Step 4: Run** the new test plus `engine/tests/test_cli.py` → PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(cli): direct --user/--memory-dir/--like/--less-like/--avoid/--replay; variety-report" -- engine/__main__.py engine/tests/test_cli_variety.py
```

### Task 48: Harness variety score (offline, no render)

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
    assert m["groups"] == 4 and m["exactRepeats"]["value"] == 0          # memory on: 5 distinct in a row
    assert m["meanDirectionDistance"]["value"] > 0 and m["meanScriptDistance"]["value"] > 0
    assert m["qualityCost"]["value"] <= 0                                # dice never below the no-dice baseline
    assert m["frameDistance"]["n"] == 0                                  # no render unless asked
    assert (tmp_path / "t" / "summary.md").exists()
    g = next(c for c in s["groups"] if c["prompt"] == "luxury")
    assert all(d["axes"]["mood"] == "premium_dark" for d in g["directions"])   # the pin held in every run


def test_memory_off_measures_layers_1_2_only(tmp_path):
    s = run_variety(models=["pocket_watch"], prompt_ids=["empty"], runs=5, memory=False,
                    provider_factory=REFUSE, out_root=tmp_path, run_id="t2")
    assert s["metrics"]["groups"] == 1


def test_honesty_block_present(tmp_path):
    s = run_variety(models=["pocket_watch"], prompt_ids=["empty"], runs=2, provider_factory=REFUSE,
                    out_root=tmp_path, run_id="t3")
    h = s["groups"][0]["honesty"]
    assert h["combinations"] >= 1 and "singleValued" in h and "note" in h
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Create `harness/variety.py`:**

```python
"""Variety score (spec §9): N runs of the same model + prompt. Report-only. Per group:
- direction distance (mean and min pairwise, weighted Hamming over the dice axes)
- script distance (what a viewer would see) and near-duplicates
- exact direction repeats (0 expected with memory on and N <= memoryN + 1)
- quality cost: share of dice runs below T3 ([S] tier) minus the same share for the no-dice baseline
  (interim direction, same seeds). > 0 means variety cost quality.
- catalog honesty: reachable directions, single-valued axes
- frame distance: only with render=True (<= 3 key frames per run, owner OK first)
Each group gets a fresh temporary memory for one synthetic user, so layer 3 runs as in production."""
import itertools
import json
import tempfile
import time
from pathlib import Path

from engine.catalog import Catalog
from engine.director.direction import interim_direction, parse_id
from engine.director.distance import direction_distance, near_duplicate, script_distance
from engine.director.floor import script_tier
from engine.director.llm import FakeProvider
from engine.director.memory import VarietyMemory
from engine.director.pipeline import direct
from engine.director.variety import reachable
from harness.director_eval import MODELS, _profile, _rate, load_prompt_set, markers_for

USER = "harness-variety"


def _refuse(cid):
    return FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3)


def _pairs(xs, f):
    return [f(a, b) for a, b in itertools.combinations(xs, 2)]


def run_group(model, case, sets, *, runs, memory, seed_base, factory, catalog, render=None):
    profile = _profile(model)
    spec = sets.get(case.get("markers")) if case.get("markers") else None
    markers = markers_for(spec, profile) if spec else None
    with tempfile.TemporaryDirectory() as tmp:
        mem = VarietyMemory(tmp) if memory else None
        res = [direct(case["prompt"], profile, provider=factory(f"{model}__{case['id']}__{k}"), seed=seed_base + k,
                      markers=markers, catalog=catalog, memory=mem, user=USER if memory else None)
               for k in range(runs)]
    base = [direct(case["prompt"], profile, provider=factory(f"{model}__{case['id']}__base{k}"), seed=seed_base + k,
                   markers=markers, catalog=catalog, direction=interim_direction(seed_base + k, profile, catalog),
                   duration=r.script["format"]["durationS"]) for k, r in enumerate(res)]
    scripts = [r.script for r in res]
    dirs = [parse_id(s["direction"]["id"]) for s in scripts]
    dd, sd = _pairs(dirs, direction_distance), _pairs(scripts, lambda a, b: script_distance(a, b, catalog))
    low = lambda ss: sum(script_tier(s, profile, catalog) != "T3" for s in ss) / len(ss)  # noqa: E731
    row = {"model": model, "prompt": case["id"], "runs": runs, "memory": memory,
           "directions": [r.direction for r in res],
           "meanDirectionDistance": sum(dd) / len(dd) if dd else None, "minDirectionDistance": min(dd) if dd else None,
           "meanScriptDistance": sum(sd) / len(sd) if sd else None,
           "nearDuplicates": sum(near_duplicate(a, b, catalog) for a, b in itertools.combinations(scripts, 2)),
           "exactRepeats": runs - len({s["direction"]["id"] for s in scripts}),
           "qualityCost": low(scripts) - low([b.script for b in base]),
           "honesty": reachable(profile, catalog, scripts[0]["format"]), "frameDistance": None}
    if render is not None:
        row["frameDistance"] = render(model, profile, scripts)
    return row


def run_variety(prompt_set="v1", models=None, prompt_ids=None, runs=5, memory=True, provider_factory=None,
                out_root="harness/out/variety", run_id=None, seed_base=5000, render=None):
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
                                        factory=factory, catalog=catalog, render=render))
            except Exception as e:  # noqa: BLE001 - recorded, never skipped
                groups.append({"model": model, "prompt": case["id"], "error": f"{type(e).__name__}: {e}"})
    ok = [g for g in groups if "error" not in g]
    metrics = {"groups": len(ok), "errors": len(groups) - len(ok),
               "meanDirectionDistance": _rate([g["meanDirectionDistance"] for g in ok]),
               "minDirectionDistance": _rate([g["minDirectionDistance"] for g in ok]),
               "meanScriptDistance": _rate([g["meanScriptDistance"] for g in ok]),
               "nearDuplicates": _rate([g["nearDuplicates"] for g in ok]),
               "exactRepeats": _rate([g["exactRepeats"] for g in ok]),
               "qualityCost": _rate([g["qualityCost"] for g in ok]),
               "frameDistance": _rate([g["frameDistance"] for g in ok]),
               "singleValuedAxes": sorted({a for g in ok for a in g["honesty"]["singleValued"]})}
    summary = {"promptSet": prompt_set, "runId": run_id, "runs": runs, "memory": memory, "metrics": metrics,
               "groups": groups}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    (run_dir / "summary.md").write_text(_md(summary), encoding="utf-8")
    return summary


def _md(s):
    m = s["metrics"]
    f = lambda r: f"{r['value']} (n={r['n']})"  # noqa: E731
    lines = [f"# Variety score {s['runId']} ({s['promptSet']}, {s['runs']} runs, memory {'on' if s['memory'] else 'off'})",
             "", "Report-only. Distances are 0..1. Quality cost > 0 means the dice cost [S]-tier quality.", "",
             f"- Direction distance mean {f(m['meanDirectionDistance'])}, min {f(m['minDirectionDistance'])}",
             f"- Script distance mean {f(m['meanScriptDistance'])}; near-duplicate pairs {f(m['nearDuplicates'])}",
             f"- Exact repeats {f(m['exactRepeats'])}; quality cost {f(m['qualityCost'])}",
             f"- Frame distance {f(m['frameDistance'])} (only with --render)",
             f"- Axes with one value somewhere (catalog honesty): {', '.join(m['singleValuedAxes']) or 'none'}",
             "", "| model | prompt | dir dist | script dist | repeats | near dups | quality cost | reachable |",
             "|---|---|---|---|---|---|---|---|"]
    for g in s["groups"]:
        if "error" in g:
            lines.append(f"| {g['model']} | {g['prompt']} | ERROR {g['error'][:80]} | | | | | |")
        else:
            lines.append(f"| {g['model']} | {g['prompt']} | {g['meanDirectionDistance']:.3f} | "
                         f"{g['meanScriptDistance']:.3f} | {g['exactRepeats']} | {g['nearDuplicates']} | "
                         f"{g['qualityCost']:+.2f} | {g['honesty']['combinations']} |")
    return "\n".join(lines) + "\n"
```

If `_rate` / `_profile` / `markers_for` / `MODELS` have moved in `harness/director_eval.py`, import
them from where they are now. Do not copy them.

- [ ] **Step 4: Run.** PASS. If `qualityCost > 0` on some group, **that is a finding, not a test to
  loosen**. It means the floor let a worse direction through. Debug `make_viable` for that subject
  (@superpowers:systematic-debugging).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(harness): variety score - direction/script distance, repeats, near-dups, quality cost, honesty" -- harness/variety.py harness/tests/test_variety.py
```

### Task 49: Frame distance (≤ 3 frames, opt-in) and `py -m harness variety`

**Files:**
- Modify: `harness/variety.py` (add `frame_distance`, `make_renderer`)
- Modify: `harness/__main__.py` (subcommand `variety`)
- Test: add to `harness/tests/test_variety.py`

- [ ] **Step 1: Write the failing tests** (append):

```python
import numpy as np
from PIL import Image

from harness.variety import frame_distance, make_renderer


def _png(path, rgb):
    Image.fromarray(np.full((64, 36, 3), rgb, dtype=np.uint8)).save(path)
    return path


def test_frame_distance(tmp_path):
    a, b = _png(tmp_path / "a.png", (10, 10, 10)), _png(tmp_path / "b.png", (240, 240, 240))
    assert frame_distance(a, a) == 0.0 and 0.5 < frame_distance(a, b) <= 1.0


def test_renderer_asks_for_at_most_three_frames(tmp_path, monkeypatch):
    calls = []

    def fake_compile(script, profile, glb, out_dir, **kw):
        calls.append(kw["frames"])
        (out_dir / "beauty").mkdir(parents=True, exist_ok=True)
        for f in kw["frames"]:
            _png(out_dir / "beauty" / f"{f:04d}.png", (script["seed"] % 255, 0, 0))
        return {}

    import harness.variety as hv
    monkeypatch.setattr(hv, "compile_scene", fake_compile)
    s = run_variety(models=["pocket_watch"], prompt_ids=["empty"], runs=3, provider_factory=REFUSE,
                    out_root=tmp_path, run_id="r", render=make_renderer(tmp_path / "frames"))
    assert all(len(f) <= 3 and all(x >= 1 for x in f) for f in calls) and len(calls) == 3
    assert s["metrics"]["frameDistance"]["n"] == 1 and s["metrics"]["frameDistance"]["value"] > 0
    assert all(kw_tier == "keyframes" for kw_tier in hv.LAST_TIERS)
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** in `harness/variety.py`:

```python
import numpy as np
from PIL import Image

from engine.compiler.run import compile_scene

ROOT = Path(__file__).resolve().parents[1]
SUITE = json.loads((ROOT / "harness" / "suites" / "v0" / "suite.json").read_text(encoding="utf-8"))
MAX_FRAMES = 3           # owner rule: renders on this PC are <= 3 frames
TIER = "keyframes"
LAST_TIERS = []          # test hook: the tiers actually requested


def _img(path, size=(36, 64)):
    return np.asarray(Image.open(path).convert("RGB").resize(size, Image.BILINEAR), dtype=np.float64) / 255.0


def frame_distance(a, b):
    """0..1: half mean luminance difference of thumbnails, half colour-histogram distance."""
    A, B = _img(a), _img(b)
    lum = lambda x: x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722  # noqa: E731
    thumb = float(np.abs(lum(A) - lum(B)).mean())
    hist = lambda x: np.histogramdd(x.reshape(-1, 3), bins=(8, 8, 8), range=((0, 1),) * 3)[0].ravel() / (x.size / 3)  # noqa: E731
    return round(0.5 * thumb + 0.5 * 0.5 * float(np.abs(hist(A) - hist(B)).sum()), 4)


def _frames(script):
    n = round(script["format"]["durationS"] * script["format"]["fps"])
    return sorted({1, max(1, n // 2), max(1, n)})[:MAX_FRAMES]


def make_renderer(out_root):
    """render(model, profile, scripts) -> mean pairwise frame distance over the shared frame slots."""
    def render(model, profile, scripts):
        glb = ROOT / SUITE["glb"].format(m=model)
        per_run = []
        for k, s in enumerate(scripts):
            out = Path(out_root) / f"{model}__{k}"
            frames = _frames(s)
            LAST_TIERS.append(TIER)
            compile_scene(s, profile, glb, out, tier=TIER, frames=frames)
            per_run.append([out / "beauty" / f"{f:04d}.png" for f in frames])
        ds = [frame_distance(x, y) for a, b in itertools.combinations(per_run, 2) for x, y in zip(a, b)]
        return sum(ds) / len(ds) if ds else None
    return render
```

Check where `compile_scene` writes beauty frames (`harness/run.py::_encode` reads
`case_dir / "beauty" / "%04d.png"`). If the path differs, use the real one.

In `harness/__main__.py`, add a `variety` subparser with `--prompts` (v1), `--models`,
`--prompt-ids`, `--runs` (5), `--no-memory`, `--render` (off by default; prints
"rendering <= 3 key frames per run at the keyframes tier" before starting), `--run-id` and
`--out-root` (`harness/out/variety`). It calls `run_variety(...)` with the refusing provider (there
is no live provider flag until a key exists), prints the metrics JSON, and exits 1 on `errors`. Add
the usage line to the module docstring.

- [ ] **Step 4: Run** `py -m pytest harness/tests/test_variety.py -q` → PASS. Then the offline smoke,
  with no render (CPU, about a minute):
  `py -m harness variety --models pocket_watch,sports_car,cesium_man --prompt-ids empty,cool,luxury,rainy_night --runs 5 --run-id phase4-smoke`
  Paste the headline metrics (population: 3 models × 4 prompts × 5 runs, fallback-only, date) into
  the Task 50 register.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(harness): py -m harness variety; frame distance on <= 3 key frames (opt-in)" -- harness/variety.py harness/__main__.py harness/tests/test_variety.py
```

- [ ] **Step 6 (owner-gated, optional in this phase): tiny frame-difference check.** Ask the owner
  first (they game on this PC). If OK:
  `py -m harness variety --models pocket_watch --prompt-ids empty --runs 3 --render --run-id phase4-frames`
  That is 3 runs × ≤ 3 key frames at the keyframes tier. Record the frame distance. If the owner says
  no, write "frame distance unmeasured (owner-gated)" in the register.

### Task 50: Finish — register, docs, full loop, handoff

**Files:**
- Modify: this plan (register rows filled in)
- Modify: `engine/director/direction.py` docstring if anything still says "interim"

- [ ] **Step 1: Full fast loop.** Run `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"`
  and compare with the Task 34 baseline. New failures must be zero. Pre-existing reds from other
  lanes are listed, not fixed.
- [ ] **Step 2: Negative controls hold.** Run `py -m pytest engine/tests/test_director_axes.py::test_turntable_is_never_an_opener_negative_control -q`,
  and grep: `git grep -n '"wind"\|"field"' -- engine/director/ | grep -v "dice.json\|axes.py\|direction.py\|memory.py\|catalog"`.
  No director code may write wind or a field into a script.
- [ ] **Step 3: Fill in the calibration register below** (numbers with population and date).
- [ ] **Step 4: Write the handoff** `.handoffs/YYYY-MM-DD-HHMM-renderer-director-phase4-variety-done.md`
  (`track: renderer-director`). Commit it with `git commit -- <that path>`.

---

## Calibration register — every (eng) number this plan introduces

None of these may be quoted as a quality fact until measured.

| Number(s) | Where | Calibrated through |
|---|---|---|
| Baseline fast-loop count | Task 34 | (fill in) |
| `memoryN` 5 (spec §5 says "last 5") | `dice.json` | Owner feel for repetition; harness exact repeats with memory on/off |
| `minDistance` 0.25, `nearPenalty` 0.25 | `dice.json` | Harness min direction distance distribution; owner "these two look the same" reports |
| `axisWeights` world 3 / mood 3 / opener 2 / weather 2 / tone, pace, wind 1 | `dice.json` | Owner pairwise "how different" judgments on rendered pairs (after phase 5 adds worlds) |
| `weightFloor` 0.1 | `dice.json` | Corpus energy shares once n ≥ 30 per family |
| `toneByMood`, `paceByFamily` (interim carried over) | `dice.json` | Corpus co-occurrence (spec §9a use 3) when grade/palette fields are trusted |
| `durationsS` 8/10/12 | `dice.json` | Owner preference; corpus `shotLenS` × shot count |
| `maxFloorTries` 24 | `dice.json` | Task 41 viable counts: tries needed at p95 |
| `nearDuplicateScript` 0.08 | `dice.json` | Frame distance vs script distance on Task 49 renders |
| `FLOOR_TIER` T3 and relative-floor rule | `floor.py` | Task 41 viable table (fill in: subject → floor, viable / combinations) |
| `OPENER_HOOK` arc_orbit hook params | `fallback.py` | Task 40/41: which subjects fail this opener (fill in) |
| `MAX_ENTRIES` 50, `MAX_DISLIKES_PER_AXIS` 3, 256 kB cap | `memory.py` | Product decision; no quality impact |
| Script-distance part weights | `distance.py` | Correlation with frame distance (Task 49) and owner judgments |
| Frame-distance mix 0.5/0.5, 36×64 thumbs, 8³ bins | `harness/variety.py` | Task 49 Step 6 renders |
| Pin phrase lists | `dice.json` | Pin precision/recall on harness prompts + live prompts once a key exists |

## Deferred (and why)

- **Rollable weather, wind and season dressing** — phase 5 blocks (PHASING §2). The axes exist; only
  `dry`/`calm` roll. The director still never writes wind: when wind becomes rollable, the
  **pipeline** maps the rolled value to the `field/wind` block (phase-3½ hand-off H3). The LLM never
  does.
- **Tone as a per-world backdrop axis** — `tone` is `studio_cyc`-specific today. When phase 5 adds
  `night_street` / `golden_field`, turn `tone` into "backdrop" values declared per world.
- **Lighting and effect axes** — the lighting choice stays with the taste guide (TG-08 gloss rule). A
  lighting axis waits for a third rig.
- **Live variety score** (the real LLM instead of the fallback) — needs `ANTHROPIC_API_KEY` (phase-3
  O1). Then `py -m harness variety` gains `--provider anthropic`.
- **Owner-graded "do these feel different?" pass** — with the all-phases owner grading session.
- **Web wiring** — the site passes an opaque user id and a "more like this" / "less like this"
  button. `apps/web` stays `not_connected` (engine spec §10.2).
- **Budget-aware dice** (spec §11: costWeight lets the dice prefer cheaper combinations) — phase 7
  farm, once cost per block is measured.

## Owner-only items

- **OK before Task 49 Step 6** (3 runs × ≤ 3 key frames). Everything else in this plan is CPU-only
  and renders nothing.

## Done when

- `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"` has no new
  failures against the Task 34 baseline.
- `py -m engine direct --profile engine/tests/fixtures/profiles/pocket_watch.json --prompt "" --provider fake:<refusing fixture> --user u1 --memory-dir var/variety --seed N`
  run 6 times with different seeds prints 6 distinct direction ids. `--replay` reproduces a saved
  script exactly. `--like` keeps the direction.
- `py -m harness variety` (offline) reports exact repeats 0 with memory on, quality cost ≤ 0 on every
  group, and a catalog-honesty line per subject.
- No director code writes `realism`, `wind` or a `field`. `turntable` is never a dice value.
