# Director Layer Phase 5: Catalog Growth, Subject Motion and Weather

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The director can place any upload in four worlds (the studio plus `rain_courtyard`,
`night_street` and `golden_field`), move the subject with intent (drive, roll, topple, toss, float,
drop, slide, plinth spin), shoot it with the rest of the v1 camera programmes (plus a tracking camera
for driving), and dress it in real weather (drizzle to downpour, wet ground after rain, puddles, snow,
fog and mist, and wind). Every new block reaches T3 at script level, passes its checker gates and meets
the quality floor. Every block has taste rules and eval prompts, including asks it cannot do. The dice
can now roll weather and wind, and no run is worse than the frozen phase-3 baseline (90/90).

**Architecture:**

- **Growth under a contract, not by hand.** `engine/catalog_growth.json` lists every block that phase 5
  adds. For each one it names:
  - its taste rules;
  - its checker gate codes;
  - its eval prompts: a delivered ask, plus an unsupported ask where one exists;
  - its floor test;
  - its golden-render status (null until the owner grades it).

  `engine/tests/test_catalog_growth.py` fails if a director-selectable block is missing from that
  list, or if any link in its entry is broken. So nothing ships half-done. This turns the owner's
  "every new world, camera, motion or weather has rules, gates, a floor and prompts" into a mechanical
  guard (memory: gates retire into guards).
- **Subject motion is pure maths first.** Each new `motion` block ships a pure `path.py`,
  `sample(params, profile, t, duration) -> SubjectPose`, like camera `path.py` today.
  - `engine/motion_path.py` is the ONE place that turns a script's motion into subject poses.
  - The checker frames the moving subject with it: camera clearance, coverage and in-frame at 12
    samples per shot. It also runs the new `path_through_world` / `path_through_subject` gates.
  - The compiler keyframes the `valora_motion` empty from the same function.
  - A Blender test proves the keyframes equal the pure samples.
  - Cameras declare `follows: "anchor" | "subject"`. An anchor camera is solved against the subject's
    pose at the shot's midpoint (a pass-by stays centred); `rolling_track` follows the subject.
  - `static` and `play_clip` return the identity pose, so every existing script checks and compiles
    byte-for-byte as before (tested against the frozen baseline).
- **Weather is a package, stateless, wind-driven.** `rain`, `wet_surface`, `droplets`, `snow`,
  `ground_fog` and `lens_drops` are `effect` blocks. Their manifests declare:
  - `physics.couplings`: rain adds wet_surface and droplets;
  - `excludes`: rain and snow;
  - `requiresWorld`: an outdoor world with a ground;
  - `maxPerClip`.

  The checker (`engine/weather_rules.py`) adds coupled blocks as `coupled_added` repairs and rejects
  impossible combinations. Everything is METHODS R1 stateless: analytic streaks, flakes and impact
  events in a camera-following box, shader wetness, and Geometry Nodes driven only by scene time and
  the seed. So preview equals final, and a frame range renders anywhere. No bake, no VDB, no sims
  (phase 6).
- **Ports are adapted to the block contract, never copy-pasted.** render-studio
  (`C:\Users\deand\Projects\ModVision\tools\render-studio\`) holds the rain courtyard, the falling rain
  with its car shadow, the drips, the wet asphalt with its puddles and ripples, the distance fog and the
  operator camera. Each port removes the car gates and the mesh-name keys (`MANTHEY_992`, `drl-*`),
  sizes itself from the SubjectProfile (true metres), takes the block seed, reads the one wind field,
  and gets its numbers from the block's params. ModVision's render-studio is **read, never edited**
  (spec §2).
- **Wind reaches the director only through H3's schema path.** The `field/wind` manifest becomes
  director-selectable. The output schema gains one `wind` object (`SINGLE_FIELDS`). Sanitize keeps a
  schema-valid `wind` and still drops `field` and any per-effect wind param (`wind_param_on_effect`).
  The dice's wind axis (`calm | breeze | windy`) is mapped to `speedMs` by the **pipeline**, and a pinned
  or rolled value overrides the LLM. The LLM still never writes `realism` (ownership test updated,
  Task 58).
- **One wind, calibrated per consumer (H4).** The compiler builds one `valora_wind` Geometry Nodes group
  and one Blender WIND force field from the same params. Each consumer (rain slant, snow drift, fog/haze
  drift, foliage sway) records a `physics.windCalibration` mapping from m/s to its own units. A compile
  probe, `wind_coherent`, measures it without rendering.
- **The dice unlock weather and wind through the floor.** `dice.json` weather rollable becomes
  `dry | wet | rain | snow | fog`, and wind becomes `calm | breeze | windy`. Two filters decide what can
  roll:
  - each world lists the `weathers` it supports;
  - `compatible()` removes implausible pairs.

  A rolled weather maps to a package (`dice.json weatherPackages`), which `adherence.py` inserts on
  vague prompts. A direction is viable only if its fallback with the package passes the checker and
  reaches the floor. **No new dice axis is added.** A new axis would change every direction id and break
  the frozen baseline (Task 51 guards this). Time of day is a world param with pins and layer-1 detail
  instead.
- **Corpus drives priority.** `py -m corpus backlog` clusters the §9a records (world type, camera move,
  subject motion, weather, effect) and ranks them by frequency × fit. It writes
  `research/corpus/backlog.json`. Each chunk starts with a re-rank checkpoint that reorders the chunk's
  remaining optional blocks by that ranking. Clip sourcing stays owner-only (no automated downloads,
  §9a).

**Tech Stack:** Python 3.12 dev; Blender 5.0.1 (bundled 3.11). `engine/` stays stdlib-only at import
time. Geometry Nodes, Cycles volumes and the compositor (all 5.0 features, METHODS §0.2). pytest 8. The
harness keeps numpy + Pillow. No new dependencies, no network at render time.

**Spec and research:**
- `docs/superpowers/specs/2026-09-24-director-layer-design.md`:
  - §2a (tiers; `tierMax`; catalog order by T2→T3)
  - §4.3 (v1 block set)
  - §4.5 (compile order)
  - §4.6 (checker)
  - §6 (uniqueness)
  - §9 (eval), §9a (corpus uses 1–5)
  - §10 step 5 plus the physics re-phasing
  - §11 (risk: new worlds look CG)
- `research/physics/PHASING.md` §2 Phase 5 (5a, 5b) and §3 (unsupported contract).
- `research/physics/BLOCKS.md`: §2.3–2.4 (blocks), §2.6 (world params), §3 (dependencies), §4 (tags and
  phrase collisions), §5 (checker and compile probes), §6 (PH items).
- `research/physics/METHODS.md`: R1–R10, §2.2, §2.3, §2.6, §2.8, §2.9, §2.10.
- `research/physics/ASSETS.md` (licences), `research/physics/TAXONOMY.md` (ids).
- `research/craft/CATALOG-GAPS.md` ranks 5, 6, 7, 9, 12, 13.
- Hand-offs H3–H6 in `docs/superpowers/plans/2026-09-25-phase3-5-realism-defaults.md`.
- Phase 4 plan `docs/superpowers/plans/2026-09-25-director-phase4-variety.md` (dice, floor, frozen
  baseline, Deferred list).

**Task numbering** continues after phase 4's last task (Task 50). This plan uses **Tasks 51–92**.

**Review amendments.** An independent review against HEAD (2026-09-25) found 36 problems. Blockers
and code-block bugs are fixed inline. The rest are in **"Review amendments (binding)"** at the end of
this plan: before starting any task, read that table's rows for the task and apply them; they override
the task text where they differ.

**Conventions (same as phases 1–4):**

- Run every command from the repo root `C:\Users\deand\Projects\rendering`, on branch
  `renderer/director`. Use `py`, never bare `python`.
- **Fast loop:** `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"`.
- **Full suite (the chunk gate):** `py -m pytest engine/tests harness/tests corpus/tests -q -m "not live"`.
  This includes the Blender tests, which compile headless and render nothing unless a task says so.
  Never run `live` tests.
- **Frozen baseline gate (every chunk end):**
  `py -m pytest engine/tests/test_director_floor.py engine/tests/test_director_baseline.py harness/tests/test_baseline_regressions.py -q`.
  It must show all 90 `test_phase3_default_still_reproduces_the_frozen_baseline[...]` cases passing and
  the regression gate green. The fixture is never regenerated (that needs the owner's OK).
- **No live API.** Director tests use `FakeProvider` or the refusing provider.
- **Render budget: at most 3 rendered frames per invocation, reserved before rendering and never
  refunded.** Use `harness/budget.py` (Task 51 extracts it from `harness/variety.py`, which keeps
  importing it). Only the look-check steps marked `[render ≤ 3]` render. Anything larger than 3 frames is owner-gated.
- **Licence-clean assets only:** CC0 or owned. CC-BY is allowed only with a row in
  `engine/assets/CREDITS.md`. Every asset is pinned by sha256 in `engine/assets/manifest.json`
  (Task 62). A block never downloads at build time, and it always has a procedural fallback, so tests
  and farm workers never need a file to exist. Downloads that need an owner click are listed under
  Owner-only and are never scripted.
- **Shared working tree.** Other lanes commit here too.
  - Before every commit, run `git diff --cached --name-only`, then commit only the task's files with
    `git commit -m "..." -- <paths>`.
  - Never `git stash`, `git add -A`, or rewrite a whole file another lane edits.
  - **Re-read before you edit** `job.py`, `pipeline.py`, `fallback.py`, `sanitize.py`, `adherence.py`,
    `dice.py`, `rulebook.py`, `rulebook.txt`, `engine/__main__.py`, `harness/director_eval.py` and
    `engine/checker.py`. The code blocks below are anchored on function and constant names, never on
    line numbers.
- **Verification commands are PowerShell-safe:** `py` scripts or pytest, never `grep`/`sed`/`head`
  pipelines.
- Each commit message ends with the two attribution lines given in the session.
- Every number marked **(eng)** is an engineering guess and goes in the calibration register (Task 92).
- **Blender builders:** `build.py` imports `bpy` only inside `build(ctx)`
  (`test_blocks_complete.py`). Every size is a fraction of `profile.longest` or real-world metres
  (METHODS R5); scale cues such as drops, flakes and leaves stay at real size. Seeds come from
  `ctx.seed` / `ctx.rng` only. Node lookups use node **type**, never localized names.

---

## File structure

| File | Status | Responsibility |
|---|---|---|
| `engine/catalog_growth.json` | create (T52) | The phase-5 growth contract: per block its taste rules, gate codes, prompts, floor test, golden status; `baselineBlocks` = the selectable set at T51 |
| `engine/gates.py` | create (T52) | Registry `CODES = {code: severity}` of every checker Issue code; a test scans the engine for `Issue("...")` literals and requires each to be registered |
| `harness/budget.py` | create (T51) | `RenderBudget` (reserve-before-render, never refund, total ≤ `MAX_FRAMES_TOTAL` = 3), moved out of `harness/variety.py` |
| `corpus/backlog.py` + `research/corpus/backlog.json` | create (T53) | Cluster §9a records into block candidates, rank frequency × fit, mark which exist; `py -m corpus backlog` |
| `engine/catalog.py` | modify (T54) | Validators: `couplings`, `excludes`, `requiresWorld`, `maxPerClip`, `timeScaleParam`, `windCalibration`, world `outdoor`/`weathers`/`temperature`/`timeOfDay`/`toneParam`/`driveLaneM`, camera `follows`; `load_motion_path` |
| `engine/physics/shape.py` | create (T55) | Pure shape facts from `surfaceSamples`: `principal_axes`, `roll_axis`, `support_polygon`, `up_facing`, `low_edges`, `nose_sign`; no re-ingest |
| `engine/physics/applies.py` | modify (T55, T79) | `facts()` gains `rollAxis`, `supportPolygon`, `principalAxes`; `motion_flags(s, catalog)` (dynamic flags from `path.flags(params)`) |
| `engine/motion_path.py` | create (T56) | `SubjectPose`, `subject_pose(script, profile, catalog, t)`, `posed_profile`, `camera_profile(shot, ...)`, `swept_bounds` |
| `engine/checker.py`, `engine/compiler/timeline.py` | modify (T56) | Frame the moving subject; anchor/follow cameras; motion gates |
| `engine/weather_rules.py` | create (T57) | `coupled_added`, `coupling_removed`, `exclusive_effects`, `effect_needs_world`, `effect_needs_profile`, `effect_max_per_clip`, `time_scale_weather`, `spawn_in_subject`, `effect_off_screen`, `surface_state_continuity`, `wind_implausible` |
| `engine/blocks/field/wind/block.json`, `engine/director/output_schema.py`, `engine/director/sanitize.py`, `engine/physics/applies.py` | modify (T58) | H3: wind is director-selectable via the schema path only |
| `engine/blender/wind_field.py` + `engine/blocks/field/wind/build.py` | create/modify (T59) | H4: `valora_wind` GN group + WIND force field from one param set; `wind_coherent` probe |
| `engine/blocks/effect/ground_fog/` | create (T60) | Port of `rain_look.distance_fog`, generalised; `mode` fog/mist |
| `engine/grade_plan.py`, `engine/blender/grade.py`, `engine/blocks/grade/mood_grade/block.json` | modify (T61) | Finish the compositor port: halation, lens distortion + dispersion, filter width, seeded grain; neutral defaults, **no new presets** |
| `engine/assets.py`, `engine/assets/manifest.json`, `engine/assets/CREDITS.md` | create (T62) | Pinned, licence-checked assets with procedural fallbacks |
| `engine/blocks/world/rain_courtyard/` | create (T63) | Generalised courtyard (no car gates), foliage contract, `valora_ground` |
| `engine/blocks/effect/{rain,wet_surface,droplets,snow,lens_drops}/` | create (T64–T68) | The weather package |
| `engine/blender/weather_nodes.py` | create (T64) | Shared stateless GN: camera-following particle box, impact events, wind slant |
| `engine/blocks/world/{night_street,golden_field}/` | create (T70–T71) | The two new worlds |
| `engine/blocks/lighting/{hard_sun,rim_neon,hdri_only}/` | create (T72) | Lights the new worlds need (spec v1 list) |
| `engine/blocks/motion/{drop_settle,float_drift,plinth_spin,slide_in,roll,topple,toss_tumble,drive}/` | create (T74–T79) | Subject motion, each `block.json` + `path.py` + `build.py` |
| `engine/physics/wheel_spin.py`, `engine/physics/suspension.py`, `engine/blocks/realism/{wheel_roll,suspension}/` | modify (T79) | H5: curvature-aware slip, `rollDegPerG`, strobe guard |
| `engine/blocks/camera/{reveal_rise,dutch_hero,handheld_operator,profile_slide,rolling_track}/` | create (T80–T84) | The remaining v1 cameras plus the tracking camera |
| `engine/director/{vocabulary.json,dice.json,axes.py,pins.py,adherence.py,fallback.py,details.py,rulebook/rulebook.txt}`, `engine/director/taste/rules.json` | modify (T85–T89) | Tags, taste, dice unlock, packages, fallback, layer 1 |
| `harness/prompts/v1.json`, `harness/director_eval.py`, `harness/score.py`, `harness/physics.py`, `harness/look.py` | modify/create (T90–T91) | Eval prompts (delivered + unsupported), delivered recall, [S] items, PH items, `py -m harness look` |

---

## What grew from the seed

The seed named: port rain courtyard, haze, fog and grade; `night_street` and `golden_field`; the
remaining v1 cameras; drive/roll/topple/toss/float; rain package and snow. This plan grows it into:

1. **More motion verbs.** On top of the named five: `drop_settle` with 0–3 **bounces** (spec
   `drop_in`); `slide_in` (glide in on the ground and stop with friction); `plinth_spin` (a bounded
   eased turn on a visible plinth, never a turntable); and `float_drift` generalised from `hover_bob`
   with slow yaw. Roll and topple get shape facts computed from existing surface samples, so there is
   no re-ingest.
2. **Weather variants, not one rain.** Rain `intensity` is `drizzle | steady | downpour`, which maps to
   mm/h, drop size and impact rate. The package also covers:
   - **wet ground after the rain** (`wet_surface` alone, calm puddles);
   - **puddles that reflect** (a mirror-flat film in low areas, rippled only while it rains);
   - **drips and droplets** on the subject's up-facing surfaces;
   - **mist**, as a mode of `ground_fog`;
   - **snow accumulation** on upward faces;
   - **lens drops**, allowed in at most 1 shot and only with rain, as a taste guard.
3. **Time of day** is a world param: dawn, golden, dusk and overcast on the field; dusk and night on
   the street. It has pins ("sunset", "blue hour") and layer-1 variation, and adds **no new dice axis**,
   so direction ids stay stable.
4. **Wind that everyone agrees on.** One field, one GN group, a calibration per consumer, a
   `wind_coherent` probe, and a wind that is director-selectable only through the schema.
5. **A tracking camera** (`rolling_track`, CATALOG-GAPS rank 5) and a **profile slide** (rank 13)
   join the named `reveal_rise`, `dutch_hero` and `handheld_operator`. `macro_slide` is already covered
   by `macro_detail` (vocabulary alias, no duplicate block).
6. **World-matched lighting**: `hard_sun`, `rim_neon` and `hdri_only`, from the spec v1 list. A
   `lighting_world_mismatch` repair keeps the studio rigs out of the street at night.
7. **Tone per world** (phase-4 deferred item). Each world names its `toneParam`, so the tone axis
   means something outside the studio.
8. **A growth contract and a gate registry.** Rules, gates, prompts and the floor are enforced by
   tests, not by memory.
9. **Honest partial support.** A profile-blocked motion ("roll" on a chair) becomes `unsupported` with
   a reason. So does world-blocked weather (rain pinned to the studio). Weather asks on the studio say
   what the video does instead.
10. **Corpus-ranked backlog.** Candidates the corpus surfaces but this plan does not build are ranked
    in `backlog.json` for the next pass: steam, heat haze, exhaust, falling leaves, tumbleweed, dust
    motes, `interior_daylight`, transitions.
11. **The drive contract made safe.** Heading comes from the path. A nose-sign estimate falls back to a
    side pass-by when confidence is low. Slip is curvature-aware per wheel. Body roll leans out of the
    turn. The strobe guard is a checker repair.

---

## Chunk 0: Gate, guards, growth contract, corpus backlog

### Task 51: Gate, test baseline, the render-budget helper, and "growth cannot move the baseline"

**Files:**
- Create: `harness/budget.py`, `engine/tests/test_growth_baseline_guard.py`
- Modify: `harness/variety.py` (import the budget from `harness/budget.py`)
- Test: `harness/tests/test_budget.py`

- [ ] **Step 1: Check the phase-4 contract is at HEAD.** Create
  `C:\Users\deand\AppData\Local\Temp\p5_gate.py`:

```python
import inspect
from engine.director.axes import axis_values, compatible
from engine.director.dice import candidates, roll
from engine.director.floor import floor_tier, phase3_default, make_viable
from engine.director.adherence import enforce_direction
from engine.director.details import vary_details
from engine.director.output_schema import SINGLE_FIELDS, LIST_FIELDS
from engine.physics.applies import match, resolve_wind, resolve_realism
from engine.clips import swept_profile
from engine.compiler.timeline import camera_keys, _pose_at
for f in (axis_values, candidates, roll, make_viable, enforce_direction, vary_details, match, camera_keys, _pose_at):
    print(f.__name__, inspect.signature(f))
print("SINGLE_FIELDS", SINGLE_FIELDS, "LIST_FIELDS", LIST_FIELDS)
print("ok")
```

  Run `py C:\Users\deand\AppData\Local\Temp\p5_gate.py`. Expected: the signatures, then `ok`. Write
  them into the Task 92 register; later tasks append arguments **after** them. If an import fails,
  stop and report that phase 4 has not landed.

- [ ] **Step 2: Record the counts.** Run the fast loop and then the full suite (Conventions). Write
  both counts, and any pre-existing reds, into the Task 92 register. Other lanes' reds are listed,
  not fixed. Then run the frozen baseline gate and record `90 passed` for the parametrized case.

- [ ] **Step 3: Write the failing guard test.** Growing the catalog must never move the phase-3
  default. Create `engine/tests/test_growth_baseline_guard.py`:

```python
"""Phase 5 grows worlds, grade params, cameras and motions. The frozen phase-3 default must not notice:
it rolls moods from a FROZEN tuple, keeps studio_cyc, and fills no new param differently."""
import copy
import json

from engine.catalog import Catalog
from engine.director.baseline_phase3 import BASELINE
from engine.director.direction import AXES, PHASE3_MOODS, interim_direction
from engine.director.floor import phase3_default, script_tier
from engine.director.job import make_job
from engine.tests.test_director_package import _p

CASES = json.loads(BASELINE.read_text(encoding="utf-8"))["cases"]


def _grown(cat):
    """A catalog with an extra world and an extra mood preset, as phase 5 might add."""
    g = copy.copy(cat)
    g._blocks = copy.deepcopy(cat._blocks)
    grade = g._blocks[("grade", "mood_grade")]
    grade["params"]["preset"]["values"] = list(grade["params"]["preset"]["values"]) + ["zz_new_mood"]
    w = copy.deepcopy(g._blocks[("world", "studio_cyc")])
    w["id"] = "zz_new_world"
    g._blocks[("world", "zz_new_world")] = w
    return g


def test_axes_are_frozen_at_seven():
    assert AXES == ("world", "mood", "tone", "pace", "opener", "weather", "wind")   # a new axis changes every id


def test_interim_moods_are_frozen():
    cat = Catalog.load()
    assert set(PHASE3_MOODS) <= set(cat.get("grade", "mood_grade")["params"]["preset"]["values"])


def test_phase3_default_ignores_catalog_growth():
    cat = Catalog.load()
    grown = _grown(cat)
    for case in CASES[::9]:                          # 10 spread cases; the full 90 run in test_director_floor
        p = _p(case["model"])
        d0 = interim_direction(case["seed"], p, cat)
        d1 = interim_direction(case["seed"], p, grown)
        assert d0 == d1 and d0.world == "studio_cyc"
        job = make_job(case["prompt"], p, cat, seed=case["seed"], direction=d0)
        s0, s1 = phase3_default(job, p, cat), phase3_default(job, p, grown)
        assert (script_tier(s0, p, cat), len(s0["shots"]), s0["direction"]["id"]) == \
               (case["tier"], case["shots"], case["directionId"]) == \
               (script_tier(s1, p, grown), len(s1["shots"]), s1["direction"]["id"])
```

  Before writing `_grown`, check how `Catalog` stores blocks (`py -c "from engine.catalog import Catalog; print(vars(Catalog.load()).keys())"`).
  Adapt the copy to the real attribute name; the assertion logic stays as written.

- [ ] **Step 4: Run it and see it fail** with
  `py -m pytest engine/tests/test_growth_baseline_guard.py -q`. Expected: FAIL with
  `ImportError: cannot import name 'PHASE3_MOODS'`.

- [ ] **Step 5: Freeze the interim mood list** in `engine/director/direction.py`. Next to `RARE`, add:

```python
# Frozen phase-3 inputs (phase 5 Task 51): the interim direction must not change when the catalog grows.
# These are the mood_grade presets at the frozen revision, in catalog order, minus RARE.
PHASE3_MOODS = (...)   # fill from: [v for v in catalog.get("grade","mood_grade")["params"]["preset"]["values"] if v not in RARE]
```

  Fill the tuple by running that expression at HEAD and pasting the result literally. Then change
  `interim_direction` to use the tuple:

```python
def interim_direction(seed, profile, catalog):
    known = set(catalog.get("grade", "mood_grade")["params"]["preset"]["values"])
    moods = [v for v in PHASE3_MOODS if v in known]   # frozen order; a dropped preset still drops out
    rng = random.Random(f"direction:{seed}")
    ...  # unchanged from here
```

- [ ] **Step 6: Extract the render budget.** Create `harness/budget.py`:

```python
"""Owner rule: at most 3 rendered frames per invocation on this PC. Frames are RESERVED before a render
starts and never refunded, so a crash mid-render cannot free budget for a retry loop."""
MAX_FRAMES_TOTAL = 3


class BudgetExceeded(RuntimeError):
    pass


class RenderBudget:
    def __init__(self, total=MAX_FRAMES_TOTAL):
        if not 0 < total <= MAX_FRAMES_TOTAL:
            raise ValueError(f"render budget must be 1..{MAX_FRAMES_TOTAL} frames per invocation")
        self.total, self.used = total, 0

    def reserve(self, n=1):
        if n < 1 or self.used + n > self.total:
            raise BudgetExceeded(f"{self.used}+{n} > {self.total} frames")
        self.used += n
        return n

    @property
    def left(self):
        return self.total - self.used
```

  In `harness/variety.py`, replace the local constant with
  `from harness.budget import MAX_FRAMES_TOTAL, RenderBudget  # noqa: F401`. Keep `make_renderer`'s
  behaviour; if it has its own counter, route that counter through `RenderBudget.reserve`. Write
  `harness/tests/test_budget.py`:

```python
import pytest

from harness.budget import MAX_FRAMES_TOTAL, BudgetExceeded, RenderBudget


def test_budget_reserves_and_never_refunds():
    b = RenderBudget()
    assert MAX_FRAMES_TOTAL == 3 and b.reserve(2) == 2 and b.left == 1
    with pytest.raises(BudgetExceeded):
        b.reserve(2)
    assert b.used == 2                       # a refused reservation takes nothing


@pytest.mark.parametrize("n", [0, 4, -1])
def test_budget_total_is_capped(n):
    with pytest.raises(ValueError):
        RenderBudget(n)
```

- [ ] **Step 7: Run** `py -m pytest engine/tests/test_growth_baseline_guard.py harness/tests/test_budget.py harness/tests/test_variety.py -q`
  and the frozen baseline gate. Expected: PASS, 90/90.

- [ ] **Step 8: Commit**

```bash
git diff --cached --name-only
git commit -m "chore(director): phase-5 gate; frozen interim moods; render budget helper" -- engine/director/direction.py engine/tests/test_growth_baseline_guard.py harness/budget.py harness/variety.py harness/tests/test_budget.py
```

---

### Task 52: The growth contract and the gate registry

**Files:**
- Create: `engine/gates.py`, `engine/catalog_growth.json`, `engine/tests/test_catalog_growth.py`,
  `engine/tests/test_gates_registry.py`

- [ ] **Step 1: Write the failing registry test** `engine/tests/test_gates_registry.py`:

```python
"""Every Issue code the engine can emit is registered with its severity, so the growth contract can say
'this block is guarded by gate X' and a typo in a code name fails a test instead of shipping silently."""
import ast
from pathlib import Path

from engine.gates import CODES, SEVERITIES

ROOT = Path(__file__).resolve().parents[1]


def _emitted():
    found = {}
    for f in ROOT.rglob("*.py"):
        if "tests" in f.parts or "__pycache__" in f.parts:
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "Issue"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.setdefault(node.args[0].value, set()).add(str(f.relative_to(ROOT)))
    return found


def test_every_emitted_code_is_registered():
    missing = sorted(set(_emitted()) - set(CODES))
    assert not missing, f"register these in engine/gates.py: {missing}"


def test_registry_has_no_dead_codes_and_valid_severities():
    dead = sorted(set(CODES) - set(_emitted()))
    assert not dead, f"registered but never emitted: {dead}"
    assert all(sev in SEVERITIES for sev in CODES.values())
```

- [ ] **Step 2: Run it:** `py -m pytest engine/tests/test_gates_registry.py -q`. Expected: FAIL
  (`No module named engine.gates`).

- [ ] **Step 3: Create `engine/gates.py`.** Generate the initial dict from `_emitted()`, not by hand.
  Put the scan in `C:\Users\deand\AppData\Local\Temp\p5_codes.py` (import `_emitted` from the test
  module) and run it with `py`. Paste each code with the severity it is emitted with. Where a code is
  emitted with two severities, record the stricter one and add a comment.

```python
"""Registry of checker/repair codes (phase 5 Task 52). The growth contract names gates by these codes."""
SEVERITIES = ("info", "repaired", "warning", "error")
CODES = {
    # --- phases 1-4 (generated from the tree at Task 52; keep sorted) ---
    "aspect_unsupported": "error",
    # ...
}
```

  Code whose first `Issue` argument is not a string literal (for example a variable) is invisible to
  the scan. Where one exists, register its possible values by hand and note the file in a comment.

- [ ] **Step 4: Write the failing growth-contract test** `engine/tests/test_catalog_growth.py`:

```python
"""Phase-5 growth contract: a director-selectable block outside the phase-1..4 set ships only with taste
rules that reference it, registered gate codes, eval prompts that exercise it (and an unsupported ask
where the block has a profile or world requirement), and a floor test. golden stays null until the
owner grades a render (spec §4.3); the harness reports ungraded blocks."""
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.director.taste import load_rules
from engine.gates import CODES

ROOT = Path(__file__).resolve().parents[2]
GROWTH = json.loads((ROOT / "engine" / "catalog_growth.json").read_text(encoding="utf-8"))
PROMPTS = {p["id"]: p for p in json.loads((ROOT / "harness" / "prompts" / "v1.json").read_text(encoding="utf-8"))["prompts"]}
KINDS = ("world", "lighting", "camera", "motion", "effect", "grade", "field")


def _selectable(cat):
    return {f"{k}/{b}" for k in KINDS for b in cat.selectable_ids(k)}


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
    needs = m.get("requiresProfile") or (m.get("physics") or {}).get("requiresWorld")
    if needs:
        assert entry.get("unsupportedPrompt") in PROMPTS, f"{ref}: needs an unsupported-ask prompt"
    assert entry["floor"].startswith("engine/tests/") and "::" in entry["floor"]
    assert entry.get("golden") in (None,) or isinstance(entry["golden"], str)


def test_turntable_is_never_under_growth_or_selectable():
    cat = Catalog.load()
    assert "camera/turntable" not in GROWTH["blocks"] and "turntable" not in cat.selectable_ids("camera")
```

- [ ] **Step 5: Create `engine/catalog_growth.json`.** `baselineBlocks` is the output of `_selectable`
  at HEAD; paste it literally, sorted.

```json
{
  "schema": "valora.growth/1",
  "note": "Phase-5 growth contract (plan Task 52). Each block: taste rule ids, gate codes (engine/gates.py), eval prompt ids (harness/prompts/v1.json, one must list the block in 'exercises'), unsupportedPrompt when the block has requiresProfile/requiresWorld, floor = pytest node id proving a script using it reaches the floor, golden = null until the owner grades a render.",
  "baselineBlocks": ["..."],
  "blocks": {}
}
```

- [ ] **Step 6: Run** `py -m pytest engine/tests/test_gates_registry.py engine/tests/test_catalog_growth.py -q`.
  Expected: PASS (no new blocks yet).
- [ ] **Step 7: Commit**

```bash
git diff --cached --name-only
git commit -m "test(catalog): growth contract and gate registry for phase-5 blocks" -- engine/gates.py engine/catalog_growth.json engine/tests/test_catalog_growth.py engine/tests/test_gates_registry.py
```

**From here on, every task that emits a new Issue code adds it to `engine/gates.py` in the same commit,
and every task that adds a selectable block adds its entry to `engine/catalog_growth.json`.** The floor
node id may point at a test that the same task creates.

---

### Task 53: Corpus backlog, so corpus findings pick what gets built

The spec (§9a use 1, §10) says the full 300–500 corpus lands during step 5 and drives which blocks get
built. Sourcing clips is owner-only (hand-picked, no scraping). This task builds the **consumer**, so
every record that lands updates the ranking without a code change.

**Files:**
- Create: `corpus/backlog.py`, `corpus/tests/test_backlog.py`, `research/corpus/backlog.json` (generated)
- Modify: `corpus/__main__.py` (subcommand `backlog`)

- [ ] **Step 1: Check the record schema** in `corpus/schema.py`. Find the field paths for world type,
  per-shot camera move, subject motion, weather/atmosphere and effects. Write them into `FIELDS` below.
  If a path differs from the guess, fix the guess and not the schema.

- [ ] **Step 2: Write the failing test** `corpus/tests/test_backlog.py`:

```python
from corpus.backlog import BLOCK_MAP, rank


def _rec(world, moves, motion=None, weather=None, effects=(), fam="vehicle"):
    return {"subject": {"category": fam}, "world": {"type": world, "weather": weather},
            "shots": [{"cameraMove": m, "subjectMotion": motion} for m in moves], "effects": list(effects)}


def test_rank_orders_by_frequency_times_fit_and_marks_existing():
    recs = [_rec("street", ["push", "tracking"], "drive", "rain")] * 6 + [_rec("nature", ["slide"], weather="snow")] * 2
    out = rank(recs, catalog_ids={"camera/low_hero_push", "effect/rain"})
    top = out["candidates"][0]
    assert top["key"] in ("world:street", "camera:tracking", "motion:drive", "weather:rain")
    assert all(c["count"] >= 1 and 0 < c["fit"] <= 1 for c in out["candidates"])
    rain = next(c for c in out["candidates"] if c["key"] == "weather:rain")
    assert rain["block"] == "effect/rain" and rain["exists"] is True
    assert out["n"] == 8 and out["trusted"] is False            # < 30 records: ranking is advisory


def test_unknown_values_become_never_thought_of_candidates():
    out = rank([_rec("underwater", ["fpv"])] * 3, catalog_ids=set())
    keys = {c["key"]: c for c in out["candidates"]}
    assert keys["world:underwater"]["block"] is None and keys["world:underwater"]["novel"] is True


def test_block_map_targets_are_catalog_style_refs():
    assert all(v is None or v.count("/") == 1 for v in BLOCK_MAP.values())
```

- [ ] **Step 3: Run it** with `py -m pytest corpus/tests/test_backlog.py -q`. Expected: FAIL (no module).
- [ ] **Step 4: Write `corpus/backlog.py`:**

```python
"""Spec §9a use 1: cluster corpus records into block candidates and rank them by frequency x fit.
Advisory until >= TRUST_N records (the ranking then reorders a plan chunk's optional tasks)."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "corpus" / "backlog.json"
TRUST_N = 30  # (eng) same bar as the dice weight floor in the phase-4 register
FIELDS = {"world": ("world", "type"), "weather": ("world", "weather")}   # confirm in Step 1
BLOCK_MAP = {  # corpus value -> catalog ref (None = no block yet)
    "world:cyclorama": "world/studio_cyc", "world:studio": "world/studio_cyc",
    "world:street": "world/night_street", "world:courtyard": "world/rain_courtyard",
    "world:nature": "world/golden_field", "world:field": "world/golden_field",
    "world:interior": None, "world:abstract": None, "world:water": None,
    "camera:push": "camera/low_hero_push", "camera:orbit": "camera/arc_orbit", "camera:slide": "camera/profile_slide",
    "camera:rise": "camera/reveal_rise", "camera:handheld": "camera/handheld_operator",
    "camera:tracking": "camera/rolling_track", "camera:macro": "camera/macro_detail", "camera:fpv": None,
    "camera:locked": None, "camera:dutch": "camera/dutch_hero",
    "motion:drive": "motion/drive", "motion:roll": "motion/roll", "motion:drop": "motion/drop_settle",
    "motion:float": "motion/float_drift", "motion:spin": "motion/plinth_spin", "motion:toss": "motion/toss_tumble",
    "motion:topple": "motion/topple", "motion:slide": "motion/slide_in",
    "weather:rain": "effect/rain", "weather:snow": "effect/snow", "weather:fog": "effect/ground_fog",
    "weather:wet": "effect/wet_surface",
    "effect:steam": None, "effect:smoke": None, "effect:leaves": None, "effect:dust": None,
}
FIT = {"world": 1.0, "camera": 1.0, "motion": 0.9, "weather": 0.9, "effect": 0.7}   # (eng) Valora3D fit by area


def _get(d, path):
    for k in path:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def _keys(rec):
    out = set()
    for area, path in FIELDS.items():
        v = _get(rec, path)
        if isinstance(v, str) and v and v not in ("none", "dry", "clear"):
            out.add(f"{area}:{v.lower()}")
    for sh in rec.get("shots", []):
        if sh.get("cameraMove"):
            out.add(f"camera:{sh['cameraMove'].lower()}")
        if sh.get("subjectMotion"):
            out.add(f"motion:{sh['subjectMotion'].lower()}")
    out |= {f"effect:{e.lower()}" for e in rec.get("effects", []) if isinstance(e, str)}
    return out


def rank(records, catalog_ids):
    counts = Counter(k for r in records for k in _keys(r))
    cands = []
    for key, n in counts.items():
        area = key.split(":")[0]
        block = BLOCK_MAP.get(key)
        fit = FIT.get(area, 0.5)
        cands.append({"key": key, "count": n, "share": round(n / len(records), 3), "fit": fit,
                      "score": round(n / len(records) * fit, 4), "block": block,
                      "exists": bool(block and block in catalog_ids), "novel": key not in BLOCK_MAP})
    cands.sort(key=lambda c: (-c["score"], c["key"]))
    return {"schema": "valora.backlog/1", "n": len(records), "trusted": len(records) >= TRUST_N, "candidates": cands}


def main(argv=None):
    from corpus.stats import eligible          # the same record filter the stats use
    from engine.catalog import Catalog
    cat = Catalog.load()
    ids = {f"{k}/{b}" for k in ("world", "camera", "motion", "effect") for b in cat.ids(k)}
    recs = eligible([json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "research" / "corpus" / "refs").glob("*.json"))])
    doc = rank(recs, ids)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8", newline="\n")
    print(f"{doc['n']} records, trusted={doc['trusted']}; top: " + ", ".join(c["key"] for c in doc["candidates"][:8]))
    return 0
```

  Check `corpus.stats.eligible`'s signature before you call it, and adapt the call if it differs. Add
  the `backlog` subcommand in `corpus/__main__.py`, following that file's existing subcommand pattern.

- [ ] **Step 5: Run** the test (PASS), then `py -m corpus backlog`. Paste the one-line summary into the
  Task 92 register. With 11 records it prints `trusted=False`. That is expected: the plan's order holds
  until the corpus reaches 30 records.
- [ ] **Step 6: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(corpus): backlog ranking so corpus findings order catalog growth" -- corpus/backlog.py corpus/__main__.py corpus/tests/test_backlog.py research/corpus/backlog.json
```

**Re-rank checkpoint (the first step of every later chunk).** Run `py -m corpus backlog`.
- If `trusted` is true and a candidate the chunk treats as *optional* ranks below a `novel` or missing
  candidate by more than 2× score, record it in the Task 92 register and tell the coordinator.
- The coordinator may swap the optional task for the higher-ranked one. The owner sees the swap in the
  handoff.
- Mandatory tasks (the spec §10 step 5 list plus the named motions and weather) are never dropped by a
  re-rank.

**Chunk 0 gate:** full suite green (no new reds against Task 51), frozen baseline 90/90.

---

## Chunk 1: Shared foundations (manifest keys, shape facts, moving-subject checker, weather rules, wind)

Start with the re-rank checkpoint (Task 53).

### Task 54: Manifest keys for worlds, effects, motions and cameras

**Files:**
- Modify: `engine/catalog.py`, `engine/blocks/world/studio_cyc/block.json`
- Test: `engine/tests/test_catalog_phase5.py`

- [ ] **Step 1: Write the failing test** `engine/tests/test_catalog_phase5.py`:

```python
import copy

import pytest

from engine.catalog import Catalog, CatalogError, _check_manifest

WORLD = {"id": "w", "kind": "world", "description": "d", "params": {}, "subjectSizeM": [0.02, 8.0],
         "aspects": ["9:16"], "costWeight": 1.0, "tags": {"mood": [], "energy": [], "palette": []}, "tierMax": "T3",
         "hasGround": True, "groundType": "asphalt", "hasFoliage": False, "windDefault": 0.8,
         "outdoor": True, "weathers": ["dry", "wet", "rain", "fog"], "temperature": "mild",
         "timeOfDay": {"param": "timeOfDay", "values": ["dusk", "night"]}, "toneParam": None, "driveLaneM": 24.0}
FX = {"id": "rain", "kind": "effect", "description": "d", "params": {"rateMmH": {"type": "number", "min": 0.5, "max": 50, "default": 4}},
      "subjectSizeM": [0.02, 30.0], "aspects": ["9:16"], "costWeight": 1.6, "tags": {"mood": [], "energy": [], "palette": []},
      "tierMax": "T3", "maxPerClip": 1,
      "physics": {"taxonomy": ["FL-01"], "state": "stateless", "windDriven": True, "couplings": ["wet_surface"],
                  "excludes": ["snow"], "requiresWorld": {"outdoor": True, "hasGround": True},
                  "timeScaleParam": None, "windCalibration": {"unit": "slant", "perMs": 1.0}}}


def test_valid_phase5_world_and_effect_manifests_load():
    _check_manifest("world", "w", copy.deepcopy(WORLD))
    _check_manifest("effect", "rain", copy.deepcopy(FX))


@pytest.mark.parametrize("key,bad", [("weathers", ["dry", "hail"]), ("temperature", "warmish"), ("outdoor", "yes"),
                                     ("driveLaneM", -1), ("timeOfDay", {"param": "x"})])
def test_bad_world_keys_are_rejected(key, bad):
    with pytest.raises(CatalogError):
        _check_manifest("world", "w", {**copy.deepcopy(WORLD), key: bad})


@pytest.mark.parametrize("key,bad", [("couplings", "wet_surface"), ("excludes", [3]), ("requiresWorld", {"colour": 1}),
                                     ("windCalibration", {"unit": "slant"})])
def test_bad_effect_physics_keys_are_rejected(key, bad):
    m = copy.deepcopy(FX)
    m["physics"][key] = bad
    with pytest.raises(CatalogError):
        _check_manifest("effect", "rain", m)


def test_max_per_clip_and_camera_follows():
    with pytest.raises(CatalogError):
        _check_manifest("effect", "rain", {**copy.deepcopy(FX), "maxPerClip": 0})


def test_catalog_couplings_resolve_to_real_blocks():
    cat = Catalog.load()
    for bid in cat.ids("effect"):
        for c in (cat.get("effect", bid).get("physics") or {}).get("couplings", []):
            assert cat.get("effect", c) is not None, (bid, c)


def test_studio_is_indoor_and_dry_only():
    m = Catalog.load().get("world", "studio_cyc")
    assert m["outdoor"] is False and m["weathers"] == ["dry"] and m["toneParam"] == "tone"
```

- [ ] **Step 2: Run** `py -m pytest engine/tests/test_catalog_phase5.py -q`. Expected: FAIL. The bad
  keys are not rejected yet, and studio lacks `outdoor`.
- [ ] **Step 3: Implement the validators** in `engine/catalog.py`, inside `_check_physics`, after its
  existing world block:

```python
WEATHERS = ("dry", "wet", "rain", "snow", "fog")          # dice.json weather values (phase 4)
TEMPERATURES = ("cold", "mild", "hot")
FOLLOWS = ("anchor", "subject")
WORLD_REQ_KEYS = {"outdoor": bool, "hasGround": bool, "hasFoliage": bool, "groundType": list, "temperature": list}

# inside _check_physics, kind == "world":
        if not isinstance(m.get("outdoor", False), bool):
            raise CatalogError(f"{where}: outdoor must be true or false")
        ws = m.get("weathers", ["dry"])
        if not isinstance(ws, list) or not ws or "dry" not in ws or set(ws) - set(WEATHERS):
            raise CatalogError(f"{where}: weathers must list values of {list(WEATHERS)} including 'dry'")
        if m.get("temperature", "mild") not in TEMPERATURES:
            raise CatalogError(f"{where}: temperature must be one of {list(TEMPERATURES)}")
        tod = m.get("timeOfDay")
        if tod is not None and not (isinstance(tod, dict) and tod.get("param") in m["params"]
                                    and set(tod.get("values", [])) <= set(m["params"][tod["param"]].get("values", []))
                                    and tod.get("values")):
            raise CatalogError(f"{where}: timeOfDay names an enum param and a subset of its values")
        tp = m.get("toneParam")
        if tp is not None and tp not in m["params"]:
            raise CatalogError(f"{where}: toneParam must name one of its params or be null")
        lane = m.get("driveLaneM", 0.0)
        if not _is_num(lane) or lane < 0:
            raise CatalogError(f"{where}: driveLaneM must be a length in metres >= 0")
# kind == "effect" (and "motion", "camera") shared:
    mpc = m.get("maxPerClip")          # absent = unlimited; the phase-3 default uses several orbit/macro shots
    if mpc is not None and (not isinstance(mpc, int) or isinstance(mpc, bool) or mpc < 1):
        raise CatalogError(f"{where}: maxPerClip must be an integer >= 1")
    if kind == "camera" and m.get("follows", "anchor") not in FOLLOWS:
        raise CatalogError(f"{where}: follows must be one of {list(FOLLOWS)}")
```

  In `_check_physics_meta`, validate the new physics keys:

```python
    for k in ("couplings", "excludes"):
        v = p.get(k, [])
        if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
            raise CatalogError(f"{where}: physics.{k} must be a list of block ids")
    rw = p.get("requiresWorld", {})
    if not isinstance(rw, dict) or set(rw) - set(WORLD_REQ_KEYS):
        raise CatalogError(f"{where}: physics.requiresWorld keys are {sorted(WORLD_REQ_KEYS)}")
    for k, typ in WORLD_REQ_KEYS.items():
        if k in rw and not isinstance(rw[k], typ):
            raise CatalogError(f"{where}: physics.requiresWorld.{k} must be {typ.__name__}")
    tsp = p.get("timeScaleParam")
    if tsp is not None and not isinstance(tsp, str):
        raise CatalogError(f"{where}: physics.timeScaleParam names a param or is null")
    wc = p.get("windCalibration")
    if wc is not None and not (isinstance(wc, dict) and isinstance(wc.get("unit"), str) and _is_num(wc.get("perMs"))):
        raise CatalogError(f"{where}: physics.windCalibration is {{unit, perMs}}")
```

  `Catalog.load` must also check, once all blocks are loaded:
  - every coupling and every exclude names an existing effect;
  - `timeScaleParam` names one of the block's own params.

  Add that to the post-load pass (or create one) and raise `CatalogError` if either fails.
- [ ] **Step 4: Tag the studio.** Add these keys to `engine/blocks/world/studio_cyc/block.json`:
  `"outdoor": false`, `"weathers": ["dry"]`, `"temperature": "mild"`, `"toneParam": "tone"`,
  `"driveLaneM": 0.0`.
- [ ] **Step 5: Add the motion loader.** Add `has_motion_path(bid)` (true only when the block folder
  has a `path.py`; `_load_module` raises `CatalogError` otherwise, so callers must ask first) and
  `load_motion_path(bid)` next to `load_camera_path`. It returns the module's `sample` and loads
  `path.py` the same way. Also add `load_motion_flags(bid)`,
  which returns the module's `flags` or `None`. Test both against a temp block in the same test file,
  using the helper that `test_catalog.py` uses for temporary block folders.
- [ ] **Step 6: Run** the new test plus `engine/tests/test_catalog.py engine/tests/test_catalog_physics.py`.
  Expected: PASS. Run the frozen baseline gate: 90/90.
- [ ] **Step 7: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(catalog): phase-5 manifest keys (weathers, couplings, requiresWorld, follows, motion paths)" -- engine/catalog.py engine/blocks/world/studio_cyc/block.json engine/tests/test_catalog_phase5.py
```

---

### Task 55: Shape facts from existing surface samples (no re-ingest)

Roll, topple, toss and droplets need the principal axes, a roll axis and radius, a support polygon, the
up-facing samples and the low edges (METHODS §3). All of them are computed in pure Python from
`profile.surfaceSamples` (points plus normals, ≤ 2000), so the eval profiles are **not** regenerated.

**Files:**
- Create: `engine/physics/shape.py`, `engine/tests/test_physics_shape.py`
- Modify: `engine/physics/applies.py` (`facts()`)

- [ ] **Step 1: Samples carry no normals at HEAD.** `profile.surfaceSamples` is a list of bare
  `[x, y, z]` points (reviewed 2026-09-25); `profile.parts` holds only
  `{index, boundsMin, boundsMax, polyShare}` (no material class). So the module adds
  `estimate_normals(points, k=12)`: per point, PCA of its k nearest neighbours (brute force is fine at
  ≤ 2000 points; cache per profile), normal = the smallest-eigenvalue vector, oriented away from the
  centroid. `samples(profile)` returns `[{"p": p, "n": n}]` built this way, and every function below
  takes that list. Add tests: on the synthetic box and cylinder (fed as bare points) the estimated
  normals agree with the true ones (mean |dot| ≥ 0.95). **No per-sample material class exists**, so
  any "glass zone" logic (Task 66) is dropped; do not re-ingest in phase 5.
- [ ] **Step 2: Write the failing tests** `engine/tests/test_physics_shape.py`, using synthetic
  point clouds so the expected values are exact:

```python
import math
import random

from engine.physics import shape


def _cylinder(r=0.05, h=0.2, axis="x", n=800, seed=1):
    rng, out = random.Random(seed), []
    for _ in range(n):
        a, t = rng.uniform(0, 2 * math.pi), rng.uniform(-h / 2, h / 2)
        c, s = math.cos(a), math.sin(a)
        p = {"x": (t, r * c, r + r * s), "y": (r * c, t, r + r * s)}[axis]
        nrm = {"x": (0, c, s), "y": (c, 0, s)}[axis]
        out.append({"p": list(p), "n": list(nrm)})
    return out


def _box(sx=0.3, sy=0.2, sz=0.1, n=900, seed=2):
    rng, out = random.Random(seed), []
    for _ in range(n):
        f = rng.randrange(6)
        u, v = rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5)
        p = [[sx/2, u*sy, (v+0.5)*sz], [-sx/2, u*sy, (v+0.5)*sz], [u*sx, sy/2, (v+0.5)*sz],
             [u*sx, -sy/2, (v+0.5)*sz], [u*sx, v*sy, sz], [u*sx, v*sy, 0.0]][f]
        nrm = [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]][f]
        out.append({"p": p, "n": nrm})
    return out


def test_principal_axes_orders_long_to_short():
    ax = shape.principal_axes(_box())
    assert abs(abs(ax[0][0]) - 1) < 0.05 and abs(abs(ax[2][2]) - 1) < 0.05


def test_roll_axis_found_on_a_lying_cylinder_not_on_a_box():
    r = shape.roll_axis(_cylinder(axis="x"))
    assert r["confidence"] == "high" and abs(abs(r["axis"][0]) - 1) < 0.05 and abs(r["radius"] - 0.05) < 0.004
    assert shape.roll_axis(_box())["confidence"] == "low"


def test_support_polygon_is_the_footprint_hull():
    poly = shape.support_polygon(_box())
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    assert abs(max(xs) - 0.15) < 0.02 and abs(min(ys) + 0.1) < 0.02 and len(poly) >= 4


def test_up_facing_and_low_edges():
    up = shape.up_facing(_box())
    assert up and all(s["n"][2] > 0.7 for s in up)
    low = shape.low_edges(_cylinder(axis="x"))
    assert low and all(s["n"][2] < -0.3 for s in low)


def test_empty_samples_degrade_to_low_confidence():
    assert shape.roll_axis([])["confidence"] == "low" and shape.support_polygon([]) == []
```

- [ ] **Step 3: Run it.** Expected: FAIL (no module).
- [ ] **Step 4: Write `engine/physics/shape.py`** (stdlib only; a 3×3 symmetric eigen-solve by Jacobi
  rotations):

```python
"""Shape facts from SubjectProfile.surfaceSamples (METHODS §3), pure and stdlib-only, so no re-ingest.
principal_axes: PCA of the sample points (long -> short). roll_axis: the principal axis whose samples sit
at a near-constant distance from it (cylinder/sphere fit) with its radius and a confidence. support_polygon:
convex hull (XY) of samples within SUPPORT_Z of the ground. up_facing / low_edges: normal filters."""
import math

ROUND_CV = 0.08        # (eng) coefficient of variation of the radial distance for a 'round' section
SUPPORT_Z = 0.01       # (eng) share of height counted as touching the ground
UP_DOT, DOWN_DOT = 0.7, -0.3   # METHODS PT-04 (n.up > 0.7), FL-20 (n.up < -0.3)


def _pts(samples):
    return [tuple(s["p"]) for s in samples]


def _jacobi(a, sweeps=50):
    a = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(sweeps):
        off = max(abs(a[0][1]), abs(a[0][2]), abs(a[1][2]))
        if off < 1e-15:
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if abs(a[p][q]) < 1e-18:
                continue
            th = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
            c, s = math.cos(th), math.sin(th)
            for k in range(3):
                akp, akq = a[k][p], a[k][q]
                a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
            for k in range(3):
                apk, aqk = a[p][k], a[q][k]
                a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
            for k in range(3):
                vkp, vkq = v[k][p], v[k][q]
                v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    vals = [a[i][i] for i in range(3)]
    vecs = [[v[k][i] for k in range(3)] for i in range(3)]
    order = sorted(range(3), key=lambda i: -vals[i])
    return [vals[i] for i in order], [vecs[i] for i in order]


def _centroid(pts):
    n = len(pts)
    return tuple(sum(p[i] for p in pts) / n for i in range(3))


def principal_axes(samples):
    pts = _pts(samples)
    if len(pts) < 4:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    c = _centroid(pts)
    cov = [[sum((p[i] - c[i]) * (p[j] - c[j]) for p in pts) / len(pts) for j in range(3)] for i in range(3)]
    return _jacobi(cov)[1]


def _radial(pts, c, axis):
    out = []
    for p in pts:
        d = [p[i] - c[i] for i in range(3)]
        t = sum(d[i] * axis[i] for i in range(3))
        out.append(math.sqrt(max(0.0, sum(x * x for x in d) - t * t)))
    return out


def roll_axis(samples):
    """{'axis', 'radius', 'confidence'}: a horizontal principal axis with a round cross-section."""
    pts = _pts(samples)
    if len(pts) < 16:
        return {"axis": [1.0, 0.0, 0.0], "radius": 0.0, "confidence": "low"}
    c = _centroid(pts)
    best = None
    for ax in principal_axes(samples):
        if abs(ax[2]) > 0.3:             # must lie roughly flat to roll on the ground
            continue
        r = _radial(pts, c, ax)
        mean = sum(r) / len(r)
        cv = math.sqrt(sum((x - mean) ** 2 for x in r) / len(r)) / mean if mean else 1.0
        if best is None or cv < best[0]:
            best = (cv, ax, mean)
    if best is None:
        return {"axis": [1.0, 0.0, 0.0], "radius": 0.0, "confidence": "low"}
    cv, ax, mean = best
    return {"axis": [round(x, 6) for x in ax], "radius": round(mean, 6), "confidence": "high" if cv <= ROUND_CV else "low"}


def _hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return [list(p) for p in pts]
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])  # noqa: E731
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return [list(p) for p in lo[:-1] + hi[:-1]]


def support_polygon(samples):
    pts = _pts(samples)
    if not pts:
        return []
    h = max(p[2] for p in pts) or 1.0
    return _hull([(round(p[0], 5), round(p[1], 5)) for p in pts if p[2] <= SUPPORT_Z * h + 1e-9])


def up_facing(samples):
    return [s for s in samples if s["n"][2] > UP_DOT]


def low_edges(samples):
    return [s for s in samples if s["n"][2] < DOWN_DOT and s["p"][2] > 0.0]


def nose_sign(profile):
    """(+1 | -1, confidence) along vehicle.forward: glass (windscreen) sits forward of the body centre on
    most cars. Low confidence when no glass part or the offset is < 3% of length (hand-off H5)."""
    veh = getattr(profile, "vehicle", None) or {}
    ax = veh.get("forwardAxis")
    glass = [p for p in (profile.parts or []) if p.get("class") == "glass"]
    if not ax or not glass:
        return 1, "low"
    i = {"x": 0, "y": 1}.get(str(ax).lstrip("+-").lower(), 0)
    mid = sum((p["boundsMin"][i] + p["boundsMax"][i]) / 2 for p in glass) / len(glass)
    off = mid - profile.center[i]
    return (1 if off >= 0 else -1), ("high" if abs(off) >= 0.03 * profile.longest else "low")
```

  **At HEAD parts carry no class and `vehicle.forwardAxis` is a vector** (e.g. `[0.0, 1.0, 0.0]`).
  So: parse the axis as the argmax of absolute components, and since there is no glass class,
  `nose_sign` returns `(sign of forwardAxis component, "low")` for every profile in phase 5. Nose
  detection needs an ingest fact (a `noseSign` field); record that as a phase-6 ingest item in the
  register. Add `test_nose_sign_parses_vector_axis` and `test_nose_sign_low_without_glass`.
- [ ] **Step 5: Expose the facts** to `appliesWhen` and `requiresProfile`. In
  `engine/physics/applies.py` `facts(profile)`, add
  `"rollAxis": (roll_axis(...)["confidence"] == "high", False)`, `"supportPolygon": (len(...) >= 3, False)`
  and `"upFacing": (len(up_facing(...)) >= 8, False)`. Cache the results per profile with a small
  cache keyed on `baseline_phase3.profile_key(profile)` (never `id(profile)`, which is reused after
  garbage collection). Extend `catalog._has(profile, fact)` the same way, **add `rollAxis`,
  `supportPolygon` and `upFacing` to `REQUIRES_PROFILE` and `PROFILE_FACTS`** (otherwise manifest
  validation rejects them), and **route the checker's `_compat` through `_has`** (it reads
  `getattr(profile, r)` today, so a computed fact would always read as missing). Test all three.
- [ ] **Step 6: Run** `py -m pytest engine/tests/test_physics_shape.py engine/tests/test_physics_applies.py -q`,
  then the frozen baseline gate. Record in the Task 92 register which eval subjects get
  `rollAxis high`. Expected: none of the nine is certain; a toy car's wheels are not the whole body.
- [ ] **Step 7: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(physics): shape facts (axes, roll axis, support polygon, up-facing) from surface samples" -- engine/physics/shape.py engine/physics/applies.py engine/catalog.py engine/tests/test_physics_shape.py
```

---

### Task 56: Moving subjects: one pose function for checker and compiler

**Files:**
- Create: `engine/motion_path.py`, `engine/tests/test_motion_path.py`
- Modify: `engine/checker.py` (`_shot_verdict`, `_fix_shot`, `check`), `engine/compiler/timeline.py`
  (`_pose_at`), `engine/compiler/blender_main.py` (motion keys), `engine/blocks/motion/static/block.json`
  (no change of behaviour; `path.py` added)
- Create: `engine/blocks/motion/static/path.py`
- Test: `engine/tests/test_checker_motion.py`, `engine/tests/test_compile_blender.py` (one new
  `blender` test)

- [ ] **Step 1: Write the failing pure tests** `engine/tests/test_motion_path.py`:

```python
import math

from engine.catalog import Catalog
from engine.motion_path import IDENTITY, SubjectPose, camera_profile, posed_profile, subject_pose, swept_bounds
from engine.tests.test_director_package import _p


def _script(motion, dur=10.0, shots=((0, 5), (5, 10))):
    return {"format": {"durationS": dur, "fps": 30, "aspect": "9:16"}, "subject": {"placement": "ground", "motion": motion},
            "shots": [{"startS": a, "endS": b, "camera": {"id": "low_hero_push", "params": {}}} for a, b in shots]}


def test_static_and_play_clip_are_identity():
    cat, p = Catalog.load(), _p("pocket_watch")
    for m in ({"id": "static", "params": {}}, {"id": "play_clip", "params": {}}):
        for t in (0.0, 3.3, 10.0):
            assert subject_pose(_script(m), p, cat, t) == IDENTITY


def test_posed_profile_moves_bounds_and_centre():
    p = _p("sports_car")
    q = posed_profile(p, SubjectPose(offset=(2.0, 0.0, 0.0), yaw=0.0))
    assert math.isclose(q.center[0], p.center[0] + 2.0) and math.isclose(q.boundsMax[0], p.boundsMax[0] + 2.0)
    r = posed_profile(p, SubjectPose(offset=(0.0, 0.0, 0.0), yaw=math.pi / 2))
    assert math.isclose(r.boundsMax[0] - r.boundsMin[0], p.boundsMax[1] - p.boundsMin[1], rel_tol=1e-6)


def test_anchor_camera_uses_mid_shot_pose_subject_camera_uses_live_pose():
    p = _p("sports_car")
    pose = lambda t: SubjectPose(offset=(t, 0.0, 0.0), yaw=0.0)  # noqa: E731
    shot = {"startS": 2.0, "endS": 6.0}
    assert math.isclose(camera_profile(shot, p, pose, follows="anchor", u=0.0).center[0], p.center[0] + 4.0)
    assert math.isclose(camera_profile(shot, p, pose, follows="subject", u=0.25).center[0], p.center[0] + 3.0)


def test_swept_bounds_cover_every_pose():
    p = _p("pocket_watch")
    lo, hi = swept_bounds(p, lambda t: SubjectPose(offset=(0.1 * t, 0.0, 0.0), yaw=0.0), 0.0, 10.0)
    assert math.isclose(hi[0], p.boundsMax[0] + 1.0, rel_tol=1e-6) and math.isclose(lo[0], p.boundsMin[0])
```

- [ ] **Step 2: Run it.** Expected: FAIL (no module).
- [ ] **Step 3: Write `engine/motion_path.py`:**

```python
"""The ONE place a script's subject motion becomes subject poses (phase 5 Task 56). The checker frames the
moving subject with it and the compiler keyframes valora_motion from it, so they can never disagree.
A pose is an offset (placed metres) + yaw/pitch/roll (radians) applied about the subject's ground-centre
(profile.center[0], profile.center[1], 0). static/play_clip (and any motion without a path.py) = IDENTITY."""
import math
from dataclasses import dataclass, replace

SWEEP_SAMPLES = 24  # (eng) poses sampled per clip to build swept bounds


@dataclass(frozen=True)
class SubjectPose:
    offset: tuple = (0.0, 0.0, 0.0)
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0


IDENTITY = SubjectPose()


def subject_pose(script, profile, catalog, t):
    motion = (script.get("subject") or {}).get("motion") or {}
    bid = motion.get("id", "static")
    if not catalog.has_motion_path(bid):          # play_clip and fixture motions have no path.py
        return IDENTITY
    sample = catalog.load_motion_path(bid)
    return sample(motion.get("params") or {}, profile, float(t), float(script["format"]["durationS"]))


def pose_fn(script, profile, catalog):
    return lambda t: subject_pose(script, profile, catalog, t)


def _rot(p, pose, pivot):
    x, y, z = p[0] - pivot[0], p[1] - pivot[1], p[2]
    cr, sr = math.cos(pose.roll), math.sin(pose.roll)          # about the subject's local X
    y, z = cr * y - sr * z, sr * y + cr * z
    cp, sp = math.cos(pose.pitch), math.sin(pose.pitch)        # about local Y
    x, z = cp * x + sp * z, -sp * x + cp * z
    cy, sy = math.cos(pose.yaw), math.sin(pose.yaw)            # about world Z
    x, y = cy * x - sy * y, sy * x + cy * y
    return (x + pivot[0] + pose.offset[0], y + pivot[1] + pose.offset[1], z + pose.offset[2])


def _corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def posed_bounds(profile, pose):
    if pose == IDENTITY:
        return list(profile.boundsMin), list(profile.boundsMax)
    pivot = (profile.center[0], profile.center[1], 0.0)
    pts = [_rot(c, pose, pivot) for c in _corners(profile.boundsMin, profile.boundsMax)]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def posed_profile(profile, pose):
    """A shallow copy whose centre and bounds are the posed AABB. Sizes stay the measured ones (the
    subject's own size never changes; only where it is). Marker/detail points are moved the same way."""
    if pose == IDENTITY:
        return profile
    lo, hi = posed_bounds(profile, pose)
    pivot = (profile.center[0], profile.center[1], 0.0)
    moved = lambda pt: list(_rot(pt, pose, pivot))  # noqa: E731
    extra = {}
    if getattr(profile, "detailPoints", None):
        extra["detailPoints"] = [{**d, "point": moved(d["point"])} if "point" in d else d for d in profile.detailPoints]
    return replace(profile, boundsMin=lo, boundsMax=hi, **extra)


def camera_profile(shot, profile, pose_at, follows="anchor", u=0.5):
    """anchor: the pose at the shot's midpoint (a pass-by stays centred); subject: the live pose at u."""
    a, b = shot["startS"], shot["endS"]
    t = (a + b) / 2 if follows == "anchor" else a + u * (b - a)
    return posed_profile(profile, pose_at(t))


def swept_bounds(profile, pose_at, t0, t1, n=SWEEP_SAMPLES):
    los, his = zip(*(posed_bounds(profile, pose_at(t0 + (t1 - t0) * k / (n - 1))) for k in range(n)))
    return [min(v[i] for v in los) for i in range(3)], [max(v[i] for v in his) for i in range(3)]
```

  `profile.center` must be derived from the bounds. If `SubjectProfile.center` is a stored field
  instead of a property, add `center=[(lo[i]+hi[i])/2 for i in range(3)]` to the `replace` call. Check
  whether `detailPoints` entries use `point` or `p` before writing the move.
- [ ] **Step 4: Add `engine/blocks/motion/static/path.py`:**

```python
from engine.motion_path import IDENTITY


def sample(params, profile, t, duration):
    return IDENTITY


def flags(params):
    return {}
```

- [ ] **Step 5: Write the failing checker tests** in `engine/tests/test_checker_motion.py`. Use a test
  motion block, `engine/tests/fixtures/blocks/motion/test_glide`, with a `path.py` that moves the
  subject 3 m along +X over the clip. Put the fixture in the test catalog dir, the same way the
  existing fixture blocks are wired:

```python
from engine.checker import check
# fixture catalog helper: reuse the one existing checker tests use for fixture blocks (see test_checker.py)


def test_static_scripts_check_exactly_as_before(frozen_scripts):
    """Every example script in engine/director/examples + the golden fixtures: identical CheckResult."""
    for s, p, cat in frozen_scripts:
        a = check(s, p, cat)
        assert a.ok and all(i.code != "subject_left_frame" for i in a.issues)


def test_moving_subject_leaving_an_anchor_frame_is_repaired_or_rejected(glide_catalog, watch):
    s = glide_script(camera="low_hero_push", distance=1.3)   # tight, so a 3 m glide leaves frame
    r = check(s, watch, glide_catalog)
    codes = {i.code for i in r.issues}
    assert "camera_distance_adjusted" in codes or "subject_left_frame" in codes


def test_camera_inside_a_moving_subject_is_caught(glide_catalog, watch):
    s = glide_script(camera="low_hero_push", distance=1.2, azimuth=0.0)  # the glide drives through the camera
    r = check(s, watch, glide_catalog)
    assert not r.ok or any(i.code == "camera_distance_adjusted" for i in r.issues)


def test_path_leaving_the_world_is_an_error(glide_catalog, watch):
    s = glide_script(world="studio_cyc", metres=40.0)   # studio driveLaneM 0 -> no travel allowed
    assert "path_through_world" in {i.code for i in check(s, watch, glide_catalog).issues}
```

  Write the fixtures (`frozen_scripts`, `glide_catalog`, `watch`, `glide_script`) in the same file or
  in `conftest.py`, reusing the example scripts in `engine/director/examples/*.json` and
  `_p("pocket_watch")`.
- [ ] **Step 6: Wire it into `engine/checker.py`.** Changes:

  - `_shot_verdict(sample, params, profile, framing, aspect, target=None, profile_at=None)`: when
    `profile_at` is given, use `prof_k = profile_at(k / (SAMPLES_PER_SHOT - 1))` for the camera sample
    and for the corners/containment at each k. Without it, behaviour is byte-identical.
  - `_fix_shot(...)`: build `pose_at = pose_fn(s, profile, catalog)`. Read
    `follows = m.get("follows", "anchor")`. Pass
    `profile_at=lambda u: camera_profile(shot, profile, pose_at, follows, u)` for the camera, and check
    coverage and containment against `posed_profile(profile, pose_at(shot_t(u)))`. The subject is
    judged where it really is; the camera is placed where its programme puts it. When the motion is
    identity, pass `None` so the static path is untouched.
  - New error `subject_left_frame`: the subject is out of frame at any sample and no distance fixes
    it. Reuse the `framing_unfixable` message pattern, but keep the new code. Register it in
    `engine/gates.py`.
  - New error `path_through_world`: the swept bounds (`swept_bounds(profile, pose_at, 0, dur)`) extend
    beyond the subject's own bounds by more than the world's `driveLaneM` along the travel direction.
    A world with `driveLaneM` 0 allows no travel. Motions that only rotate or bob pass, because their
    swept bounds are bounded by `profile.longest * 0.2` (eng).
  - `check()`: when the motion is not identity, run the size and world compatibility test (`_compat`)
    with the swept bounds.

  Import from `engine.motion_path` inside `checker.py` only; `motion_path` must not import the checker.

- [ ] **Step 7: Wire it into the compiler.** In `engine/compiler/timeline.py` `_pose_at`, pass
  `camera_profile(shot, profile, pose_fn(s, profile, catalog), m.get("follows","anchor"), u)` instead of
  `profile` when the motion is not identity. In `engine/compiler/blender_main.py`, add
  `key_subject_motion(scene, script, profile, catalog, motion_empty)`. At every frame it inserts
  location and rotation keys on `valora_motion` from `subject_pose` (offset → location; yaw/pitch/roll
  → rotation_euler 'XYZ', with the pivot handled by the empty's origin at (cx, cy, 0)). Call it before
  the motion block's `build(ctx)`, and **only when `catalog.has_motion_path(id)`**: motions without a
  `path.py` (play_clip, the fixture motions `test_drop` / `test_slide_stop`) key the empty themselves,
  and mixing identity keys into their fcurves breaks `test_realism_blender`. Motion `build.py` files add only what the path cannot express
  (plinth prop, spin guard), never their own keys for the empty.
- [ ] **Step 8: Blender proof** (`@pytest.mark.blender` in `test_compile_blender.py`). Compile the glide
  fixture on `pocket_watch` with the compile-only run (no render). Read `valora_motion`'s evaluated
  matrix at frames 1, mid and last, and assert it equals `subject_pose` within 1e-5 m and 1e-5 rad.
- [ ] **Step 9: Run** the pure tests, `py -m pytest engine/tests/test_checker.py engine/tests/test_timeline.py engine/tests/test_checker_motion.py engine/tests/test_motion_path.py -q`,
  the full suite, and the frozen baseline gate (90/90; static scripts must be unchanged).
- [ ] **Step 10: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(checker): frame moving subjects from one pose function shared with the compiler" -- engine/motion_path.py engine/checker.py engine/compiler/timeline.py engine/compiler/blender_main.py engine/blocks/motion/static/path.py engine/gates.py engine/tests/test_motion_path.py engine/tests/test_checker_motion.py engine/tests/test_compile_blender.py engine/tests/fixtures/blocks/motion/test_glide
```

---

### Task 57: Weather and coupling rules in the checker (pure)

**Files:**
- Create: `engine/weather_rules.py`, `engine/tests/test_weather_rules.py`
- Modify: `engine/checker.py` (`check` calls `apply_weather_rules` after `resolve_wind`, before
  `resolve_realism`), `engine/gates.py`

- [ ] **Step 1: Write the failing tests** `engine/tests/test_weather_rules.py`. They use fixture
  effect manifests with `rain`, `wet_surface`, `droplets` and `snow`, built as in-memory dicts through
  the fixture-catalog helper, so this task does not depend on the real blocks of Tasks 64–67:

```python
from engine.weather_rules import apply_weather_rules


def test_rain_couples_wet_surface_and_droplets(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "rain", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert [e["id"] for e in s["effects"]][:3] == ["rain", "wet_surface", "droplets"]
    assert [i.code for i in issues].count("coupled_added") == 2


def test_rain_and_snow_exclude(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "rain", "params": {}}, {"id": "snow", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "exclusive_effects" and i.severity == "error" for i in issues)


def test_rain_in_the_studio_needs_an_outdoor_world(fx_catalog, studio_script):
    s, issues = studio_script(effects=[{"id": "rain", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "effect_needs_world" and i.severity == "error" for i in issues)


def test_max_per_clip(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "rain", "params": {}}, {"id": "rain", "params": {}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "effect_max_per_clip" for i in issues)


def test_coupled_block_cannot_be_removed_while_parent_present(fx_catalog, outdoor_script):
    s = outdoor_script(effects=[{"id": "rain", "params": {}}], removed=["wet_surface"])
    issues = []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "coupling_removed" for i in issues)


def test_weather_time_scale_must_be_one(fx_catalog, outdoor_script):
    s, issues = outdoor_script(effects=[{"id": "rain", "params": {"timeScale": 0.5}}]), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert any(i.code == "time_scale_weather" for i in issues)


def test_dry_scripts_are_untouched(fx_catalog, studio_script):
    s = studio_script(effects=[{"id": "haze_volume", "params": {}}])
    before, issues = repr(s), []
    apply_weather_rules(s, fx_catalog, profile_car(), issues)
    assert repr(s) == before and issues == []
```

  `removed` models the LLM's attempt to drop a coupled block. The script carries
  `"effectsRemoved": [...]` only through the sanitize path, so in the unit test set it directly. Also
  add a test that sanitize maps an LLM reply that omits a coupled child to the `coupled_added` repair,
  **not** to an error. An omitted child is simply re-added; only an explicit `"remove": true` entry is
  `coupling_removed`. Decide this in the test and document it in the module docstring.
- [ ] **Step 2: Run it.** Expected: FAIL (no module).
- [ ] **Step 3: Write `engine/weather_rules.py`:**

```python
"""Weather, coupling and effect-world rules (BLOCKS.md §3, §5). Pure; milliseconds; runs after
resolve_wind and before resolve_realism, so realism sees the final effect list (e.g. wet_surface).
A coupled child omitted by the author is re-added (coupled_added, repaired). An explicit
{"id": child, "remove": true} while its parent is present is coupling_removed (error). A requested
effect whose profile requirement fails is an error the pipeline moves to `unsupported` with the block's
note (PHASING §3.6); it is never silently dropped."""
from engine.issues import Issue

WEATHER_IDS = ("rain", "snow", "ground_fog", "wet_surface")   # ambient: time scale must stay 1.0 (METHODS R4)


def _world(s, catalog):
    return catalog.get("world", s["world"]["id"]) or {}


def _needs_world(req, world):
    bad = []
    for k in ("outdoor", "hasGround", "hasFoliage"):
        if k in req and bool(world.get(k, False)) != req[k]:
            bad.append(k)
    if "groundType" in req and world.get("groundType", "studio") not in req["groundType"]:
        bad.append("groundType")
    if "temperature" in req and world.get("temperature", "mild") not in req["temperature"]:
        bad.append("temperature")
    return bad


def apply_weather_rules(s, catalog, profile, issues):
    effects = s.setdefault("effects", [])
    if not effects:
        return
    world = _world(s, catalog)
    removed = {e["id"] for e in effects if isinstance(e, dict) and e.get("remove")}
    effects[:] = [e for e in effects if not e.get("remove")]
    present = [e["id"] for e in effects]
    # 1. couplings: children go right after their parent, in the parent's declared order
    #    (rain -> wet_surface, droplets). A running cursor per parent keeps that order; indices are
    #    recomputed after every insert so issue paths never go stale.
    for parent in [e["id"] for e in effects]:
        m = catalog.get("effect", parent) or {}
        cursor = [e["id"] for e in effects].index(parent)
        for child in (m.get("physics") or {}).get("couplings", []):
            if child in removed:
                issues.append(Issue("coupling_removed", f"effects[{cursor}]", f"{child} is coupled to {parent}", "error"))
                continue
            ids = [e["id"] for e in effects]
            if child in ids:
                cursor = max(cursor, ids.index(child))
                continue
            cm = catalog.get("effect", child)
            need = cm.get("requiresProfile")
            if need:                                      # a coupled child never fails the clip
                from engine.catalog import _has
                if not all(_has(profile, f) for f in ([need] if isinstance(need, str) else need)):
                    issues.append(Issue("coupled_skipped", f"effects[{cursor}]", f"{child} (coupled:{parent}) does not fit this subject", "info"))
                    continue
            cursor += 1
            effects.insert(cursor, {"id": child, "params": {k: sp["default"] for k, sp in cm["params"].items()}})
            issues.append(Issue("coupled_added", f"effects[{cursor}]", f"{child} (coupled:{parent})", "repaired"))
    present = [e["id"] for e in effects]
    # 2. per-effect rules
    counts = {}
    for i, e in enumerate(effects):
        m = catalog.get("effect", e["id"]) or {}
        ph = m.get("physics") or {}
        counts[e["id"]] = counts.get(e["id"], 0) + 1
        if m.get("maxPerClip") is not None and counts[e["id"]] > m["maxPerClip"]:
            issues.append(Issue("effect_max_per_clip", f"effects[{i}]", f"{e['id']} more than {m['maxPerClip']}x", "error"))
        bad = _needs_world(ph.get("requiresWorld", {}), world)
        if bad:
            issues.append(Issue("effect_needs_world", f"effects[{i}]", f"{e['id']} needs {', '.join(bad)} (world {s['world']['id']})", "error"))
        for x in ph.get("excludes", []):
            if x in present:
                issues.append(Issue("exclusive_effects", f"effects[{i}]", f"{e['id']} cannot share a clip with {x}", "error"))
        tsp = ph.get("timeScaleParam")
        if e["id"] in WEATHER_IDS and float((e.get("params") or {}).get(tsp or "timeScale", 1.0)) != 1.0:
            issues.append(Issue("time_scale_weather", f"effects[{i}]", "ambient weather runs at real time", "error"))
        need = m.get("requiresProfile")
        if need:
            from engine.catalog import _has
            miss = [f for f in ([need] if isinstance(need, str) else need) if not _has(profile, f)]
            if miss:
                issues.append(Issue("effect_needs_profile", f"effects[{i}]", f"{e['id']} needs {', '.join(miss)}", "error"))
    # 3. wind plausibility (warnings; BLOCKS §5)
    speed = ((s.get("wind") or {}).get("params") or {}).get("speedMs", 0.0)
    if "ground_fog" in present and speed > 6.0:
        issues.append(Issue("wind_implausible", "wind", f"fog does not hold in {speed} m/s wind", "warning"))
```

  `time_scale_weather` fires only when a weather effect exposes a time-scale param; today none does. So
  that the rule can never be silently dead, the Task 64 manifests add no `timeScale` param and a test
  asserts they have none. The rule stays as the guard against someone adding one. Check that
  `engine.catalog._has` accepts the fact names `requiresProfile` uses; Task 55 extended it.
- [ ] **Step 4: Surface-state continuity and off-screen effects.** Add two script-level functions:
  - `surface_state_continuity(s, issues)`: an error if any shot carries its own `surfaceState` that
    differs from the clip's. The schema has no per-shot weather in v1, so this guards the future key;
    `engine/script.py` rejects `shots[].surfaceState` until a transition block exists. Test that
    rejection.
  - `spawn_in_subject(s, profile, catalog, issues)`: an error if any effect param named `*Position` or
    `*Lane` lies inside the bounds + `BOX_MARGIN`. Test it with a fixture effect that has a
    `lanePosition` param.

  `effect_off_screen` needs frustum maths per effect. Implement it for `lens_drops` only (it must land
  in a shot, Task 68) and leave the rest to PH-07 in the harness. Say so in the docstring.
- [ ] **Step 5: Wire into `check()`** after `resolve_wind(...)`: call
  `apply_weather_rules(s, catalog, profile, issues)`, then return early on errors, the same way
  `_compat` does. Register every new code in `engine/gates.py`.
- [ ] **Step 6: Run** the new tests, `engine/tests/test_checker.py`, the frozen baseline gate, and the
  gate registry test.
- [ ] **Step 7: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(checker): weather couplings, exclusions, world/profile requirements (pure)" -- engine/weather_rules.py engine/checker.py engine/script.py engine/gates.py engine/tests/test_weather_rules.py
```

---

### Task 58: Wind becomes director-selectable via the schema path only (hand-off H3)

**Files:**
- Modify: `engine/blocks/field/wind/block.json`, `engine/director/output_schema.py` (`SINGLE_FIELDS`),
  `engine/director/sanitize.py` (`LLM_KEYS`, wind validation), `engine/director/rulebook/rulebook.txt`
  (regenerated), `engine/director/taste/rules.json` (TG-24),
  `engine/tests/test_director_ownership.py`, `engine/catalog_growth.json`,
  `harness/prompts/v1.json` (`windy`, `still_air`)
- Test: `engine/tests/test_director_wind.py`

- [ ] **Step 1: Write the failing tests** `engine/tests/test_director_wind.py`:

```python
import json

from engine.catalog import Catalog
from engine.checker import check
from engine.director.llm import FakeProvider
from engine.director.output_schema import build_output_schema
from engine.director.pipeline import direct
from engine.director.rulebook import EXAMPLES_DIR
from engine.tests.test_director_package import _p

WATCH = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]


def test_schema_has_one_wind_object_and_no_field_key():
    sch = build_output_schema(Catalog.load())
    props = sch["properties"]
    assert "wind" in props and "field" not in props
    assert set(props["wind"]["properties"]["params"]["properties"]) == {"directionDeg", "speedMs", "gustiness", "turbulence"}


def test_llm_wind_survives_sanitize_and_is_pinned():
    p = _p("pocket_watch")
    reply = {**WATCH, "wind": {"id": "wind", "params": {"speedMs": 4.0}}}
    r = direct("windy", p, provider=FakeProvider([reply]), seed=3, duration=10)
    assert r.script["wind"]["params"]["speedMs"] == 4.0 and "speedMs" in r.script["wind"]["pinned"]


def test_per_effect_wind_and_field_key_are_still_dropped():
    p = _p("pocket_watch")
    reply = {**WATCH, "field": {"id": "wind"}, "effects": [{"id": "haze_volume", "params": {"windSpeed": 9}}]}
    r = direct("", p, provider=FakeProvider([reply]), seed=3, duration=10)
    assert "field" not in r.script
    assert all("windSpeed" not in e["params"] for e in r.script.get("effects", []))


def test_llm_still_cannot_write_realism():
    p, cat = _p("pocket_watch"), Catalog.load()
    reply = {**WATCH, "realism": [{"id": "tyre_contact", "params": {}}]}
    r = direct("", p, provider=FakeProvider([reply]), seed=3, duration=10)
    from engine.realism import realism_defaults
    assert r.script.get("realism", []) == (realism_defaults(p, cat, r.script) or [])


def test_windy_is_now_delivered_not_unsupported():
    p = _p("pocket_watch")
    r = direct("windy", p, provider=FakeProvider([{**WATCH, "wind": {"id": "wind", "params": {"speedMs": 6}}}]), seed=1, duration=10)
    assert "wind.breeze" not in {u["capability"] for u in r.script.get("unsupported", [])}
```

  Check the real name of the schema builder in `output_schema.py` and of the `realism_defaults`
  signature at HEAD. Phase 4 Task 50 notes that this signature moves.
- [ ] **Step 2: Run it.** Expected: FAIL. Wind is not in the schema, and sanitize drops it.
- [ ] **Step 3: Edit the manifest.** `field/wind/block.json`: `"directorSelectable": true`,
  `"capabilities": ["wind.breeze", "wind.strong"]`. Rewrite the description for the AI: "Set only when
  the prompt asks for wind or weather that implies it (storm, blizzard). speedMs: 0–1 still, 2–5
  breeze, 6–10 windy, 11–14 storm."
- [ ] **Step 4: Schema.** `output_schema.py`: `SINGLE_FIELDS = {"wind": "field"}`. The existing
  `_variant`/`_param` helpers already produce the param object; confirm that `FORBIDDEN` keywords stay
  out.
- [ ] **Step 5: Sanitize.** Add `"wind"` to `LLM_KEYS`, keeping `realism` in `OWNED`. The existing
  menu validation must accept `wind` only as `{"id": "wind", "params": {...}}` with known params;
  anything else is dropped with the existing `menu_issues` path. Per-effect wind params are already a
  catalog error (`_WIND_PARAM`). Make sure the sanitize path drops them with an issue and does not
  crash. `resolve_wind(..., given=...)` then pins what the LLM set (review fix 7 behaviour).
- [ ] **Step 6: Update the ownership test.** In `engine/tests/test_director_ownership.py`
  (phase 4 Task 50), replace `assert "wind" not in r.script` with: the final wind equals
  `resolve_wind`'s resolution of the LLM's schema-valid wind (14 m/s → pinned 14, clamped to the block
  range), and `field` is absent. Keep the realism assertion unchanged.
- [ ] **Step 7: Taste rule.** Add to `taste/rules.json`:

```json
{"id": "TG-24", "family": "any", "text": "Wind is one field for the whole clip. Leave it still indoors. Outdoors, a light breeze (2-4 m/s) makes grass, fog and rain feel alive; set 6-10 m/s only when the prompt asks for wind or a storm. Never put wind on a single effect.", "fallbackText": null, "cites": ["spec§6", "BLOCKS§3"], "blocks": ["field/wind.speedMs"]}
```

  `validate_rules` checks cites against `known_cites()`. If `BLOCKS§3` is not a known cite, use the
  closest spec heading cite that the validator accepts, and add the research file to `SPEC_DOCS` only
  if the taste lane agrees. Otherwise cite `spec§6` alone.
- [ ] **Step 8: Prompts.** Add these to `harness/prompts/v1.json`:
  - `{"id": "windy", "prompt": "windy", "exercises": ["field/wind"], "expectDelivered": ["wind.breeze"]}`
  - `{"id": "still_air", "prompt": "no wind, perfectly still", "exercises": ["field/wind"]}`

  `expectDelivered` is new; Task 90 adds the metric, and until then the harness ignores unknown keys
  (confirm this). Add the entry to `catalog_growth.json`: `"field/wind": {"taste": ["TG-24"],
  "gates": ["wind_from_script", "wind_defaulted", "wind_implausible"], "prompts": ["windy", "still_air"],
  "floor": "engine/tests/test_director_wind.py::test_llm_wind_survives_sanitize_and_is_pinned", "golden": null}`.
- [ ] **Step 9: Regenerate the rulebook** with the command the rulebook module documents (see
  `engine/director/rulebook.py` `main`/`__main__`). Then run
  `py -m pytest engine/tests/test_director_wind.py engine/tests/test_director_ownership.py engine/tests/test_director_rulebook.py engine/tests/test_director_output_schema.py engine/tests/test_catalog_growth.py -q`
  and the frozen baseline gate.
- [ ] **Step 10: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(director): wind selectable through the schema path only (H3); LLM still never writes realism" -- engine/blocks/field/wind/block.json engine/director/output_schema.py engine/director/sanitize.py engine/director/rulebook/rulebook.txt engine/director/taste/rules.json engine/tests/test_director_wind.py engine/tests/test_director_ownership.py engine/catalog_growth.json harness/prompts/v1.json
```

---

### Task 59: The wind field in Blender, calibrated per consumer (hand-off H4)

**Files:**
- Create: `engine/blender/wind_field.py`, `engine/physics/wind_calibration.py`,
  `engine/tests/test_wind_calibration.py`
- Modify: `engine/blocks/field/wind/build.py`, `engine/blender/realism_probe.py` (`wind_coherent`),
  `engine/blocks/effect/haze_volume/block.json` + `build.py`, `engine/blocks/realism/foliage_sway/block.json`
- Test: `engine/tests/test_physics_wind.py` (a `blender` test added)

- [ ] **Step 1: Write the failing pure test** `engine/tests/test_wind_calibration.py`:

```python
import math

from engine.catalog import Catalog
from engine.physics.wind_calibration import consumer_value, force_field_strength, rain_slant_deg


def test_rain_slant_matches_wind_over_fall_speed():
    assert math.isclose(rain_slant_deg(0.0, 6.5), 0.0)
    assert math.isclose(rain_slant_deg(6.5, 6.5), 45.0, rel_tol=1e-6)


def test_every_wind_driven_block_declares_a_calibration():
    cat = Catalog.load()
    for kind in ("effect", "realism"):
        for bid in cat.ids(kind):
            ph = cat.get(kind, bid).get("physics") or {}
            if ph.get("windDriven"):
                assert ph.get("windCalibration"), f"{kind}/{bid} reads wind but declares no calibration"


def test_consumer_value_is_linear_in_speed_and_zero_when_calm():
    cal = {"unit": "m/s drift", "perMs": 0.6}
    assert consumer_value(cal, 0.0) == 0.0 and math.isclose(consumer_value(cal, 5.0), 3.0)


def test_force_field_strength_is_monotonic_and_seed_in_range():
    s = [force_field_strength(v) for v in (0, 2, 5, 10, 14)]
    assert s == sorted(s) and s[0] == 0.0
```

- [ ] **Step 2: Run it.** Expected: FAIL (no module).
- [ ] **Step 3: Write `engine/physics/wind_calibration.py`:**

```python
"""One wind, many consumers (METHODS §2.9, hand-off H4). Each wind-driven block declares
physics.windCalibration = {unit, perMs}: its own unit per m/s of field speed. Rain slant is analytic
(slant = atan(wind / fall speed)); force-field strength is not m/s and gets its own mapping, recorded
only for phase-6 consumers (legacy particles, cloth). Numbers are (eng) until the wind_coherent probe
and a <=3-frame look-check agree."""
import math

FF_STRENGTH_PER_MS = 0.8   # (eng) Blender WIND strength per m/s at 1 m scale; calibrated in phase 6 with cloth


def consumer_value(cal, speed_ms):
    return 0.0 if speed_ms <= 0 else cal["perMs"] * speed_ms


def rain_slant_deg(wind_ms, fall_ms):
    return math.degrees(math.atan2(wind_ms, fall_ms))


def force_field_strength(speed_ms):
    return max(0.0, FF_STRENGTH_PER_MS * speed_ms)


def ff_seed(block_seed):
    return 1 + block_seed % 128          # METHODS R3: force-field seed accepts 1-128 only
```

- [ ] **Step 4: Declare the calibrations.**
  - `haze_volume`: `"physics": {"windDriven": true, "windCalibration": {"unit": "drift m/s", "perMs": 0.6}}`.
    Keep its current `DRIFT_*` behaviour and read `perMs` from the manifest instead of any inline
    constant.
  - `foliage_sway`: `{"unit": "bend rad per m/s", "perMs": <the constant engine/physics/sway.py uses today>}`.
    Read the constant from the code and write it here; do not change the look.
- [ ] **Step 5: Build the Blender side.** Write `engine/blender/wind_field.py` with two functions:
  - `ensure_wind_group(params, seed)` builds (or returns) one node group, `valora_wind`, with inputs
    `Position` and `Time` and output `Wind` (vector). Its value is
    `mean · (1 + gustiness·noise(p − dir·t·speed))`, plus `turbulence·curl-noise`. It uses only
    `GeometryNodeInputSceneTime`, `ShaderNodeTexNoise` and vector math, and looks nodes up by type.
  - `ensure_force_field(params, seed)` adds one WIND force field empty (`valora_wind_field`). Its
    rotation points the field along `directionDeg`, `strength` is `force_field_strength(speedMs)`,
    `noise` is `gustiness`, and `seed` is `ff_seed`. Phase 5 has no legacy-particle consumer, so this
    exists so that phase 6 cannot build a second wind.

  `field/wind/build.py` calls both, after its existing behaviour. Consumers call `ensure_wind_group`,
  never their own noise.
- [ ] **Step 6: Blender test** (`@pytest.mark.blender`, compile only, no render). Build a scene with
  wind `{directionDeg: 90, speedMs: 5}`, sample `valora_wind` at 3 points × 3 frames with the probe
  helper `sample_wind` (it exists in `realism_probe.py`), and assert that the mean direction is within
  10° of +Y. Then add the `wind_coherent` probe entry: for each wind-driven consumer present, the mean
  displacement direction of its tagged points between two frames lies within 45° of the wind vector
  when speed ≥ 1.5 m/s (BLOCKS §5), recorded in `compile.json` → `realismProbe.windCoherent` as
  report-only.
- [ ] **Step 7: Run** the calibration test, `engine/tests/test_physics_wind.py` (the blender one
  included), the full suite and the frozen baseline gate.
- [ ] **Step 8: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(wind): one Blender wind (GN group + force field) with per-consumer calibration (H4)" -- engine/blender/wind_field.py engine/physics/wind_calibration.py engine/blocks/field/wind/build.py engine/blender/realism_probe.py engine/blocks/effect/haze_volume/block.json engine/blocks/effect/haze_volume/build.py engine/blocks/realism/foliage_sway/block.json engine/tests/test_wind_calibration.py engine/tests/test_physics_wind.py
```

**Chunk 1 gate:** full suite green, frozen baseline 90/90, gate registry and growth contract green.

---

## The block recipe (used by every block task from here on)

Every new block task follows these steps in this order. A task below gives only what is specific to it:
the manifest, the pure maths with its tests, the build notes, the gates, the taste rule, the prompts and
the look-check. It does not repeat the recipe.

1. **Manifest test first.** Add a case to `engine/tests/test_blocks_phase5.py`, which this recipe
   creates on first use. The case loads the block, asserts its params, ranges, `tierMax`,
   `capabilities`, `physics` and (worlds) `weathers` against the table in the task, and asserts
   `directorSelectable` is true for director blocks. Run it: FAIL.
2. **Pure maths test first**, if the block has any (paths, counts, envelopes). Put it in
   `engine/tests/test_<block>.py`, with exact expected numbers from the task. Run it: FAIL.
3. **Write `block.json`, the pure module, and `build.py`.**
   - `build.py` imports `bpy` inside `build(ctx)`.
   - Every size scales with `ctx.profile` (METHODS R5), except real-size scale cues.
   - Every random draw uses `ctx.rng`.
   - Tag every object with the custom property `valora_block = "<kind>/<id>"` so probes can find it.
   - The block must build with no asset files present (the procedural fallback, Task 62).
4. **Blender compile test** (`@pytest.mark.blender`, compile only, no render). Add it to
   `engine/tests/test_blocks_phase5_blender.py`: compile the block's fixture script on the eval subject
   the task names and assert the task's probe conditions from `compile.json`. The compile runner is
   `engine.compiler.run.compile_scene(..., frames="key")`. Check its keyword names at HEAD before
   using them.
5. **Gates:** every new Issue code goes into `engine/gates.py`.
6. **Taste rule** in `engine/director/taste/rules.json`, with the next free `TG-` id. It must cite a
   source `validate_rules` accepts and list the block in `blocks`.
7. **Prompts** in `harness/prompts/v1.json`:
   - one delivered ask with `"exercises": ["<kind>/<id>"]` and `"expectDelivered": [<capability>]`;
   - one unsupported ask when the block has `requiresProfile` or `physics.requiresWorld`, with
     `"expectUnsupported"` and the subject or world that blocks it (`"models": [...]` or
     `"pins": {"world": ...}`, whichever `director_eval` supports; check before writing).
8. **Floor test** in `engine/tests/test_growth_floor.py`, parametrized over the growth entries: build
   the refusing-provider fallback for a direction whose pins or package use the block (worlds: pin the
   world; weather: pin the weather; motion: the delivered prompt). Assert
   `script_tier == "T3"` and `check(...).ok` on the task's eval subject.
9. **Growth entry** in `engine/catalog_growth.json` (taste, gates, prompts, unsupportedPrompt, floor,
   `golden: null`).
10. **Regenerate the rulebook** and run: the block's tests,
    `engine/tests/test_catalog_growth.py engine/tests/test_gates_registry.py engine/tests/test_blocks_complete.py engine/tests/test_director_rulebook.py`,
    and the frozen baseline gate.
11. **Look-check `[render ≤ 3]`** (only where the task says so). Run
    `py -m harness look --script <fixture> --profile <subject> --frames 1` (Task 91 builds the
    command; until then use the existing preview-tier render entry point with a `RenderBudget(1)`).
    Save the PNG under `harness/out/look/` (gitignored) and write its path in the register. **Never
    more than 3 frames per invocation; owner grading comes later.**
12. **Commit** only the task's files with `git commit -m "..." -- <paths>`.

---

## Chunk 2: Ports from render-studio (fog, grade, assets, rain courtyard)

Start with the re-rank checkpoint. **Read-only source:** `C:\Users\deand\Projects\ModVision\tools\render-studio\`.
Never edit it (spec §2: render-studio is not touched). Read the named line ranges before you port;
line numbers are from 2026-09-25 and may have drifted, so anchor on the function names.

### Task 60: `ground_fog` (port of `rain_look.distance_fog`, generalised) with a `mist` mode

**Source:** `rain_look.py` `distance_fog()` (≈ :391–443). It builds a 260×260×15 m cube, cuts a
Boolean cylinder "clear pocket" of radius max(8 m, farthest camera) + clearance, and uses density
0.0040 and anisotropy 0.35.

**Port changes:**
- Every size comes from the subject. The domain is `FOG_EXTENT × max(profile.longest, farthest camera
  distance)` wide (eng 6×). The height is `heightM` (real metres; a low fog). The pocket radius is
  `POCKET × profile.radius`.
- The Boolean cylinder becomes a density falloff in the volume shader, as `haze_volume` already does,
  so there is no mesh Boolean (cheaper, stateless).
- Density falls off with height (`exp(-z/heightM)`) and drifts along the wind:
  `noise(p − wind·t·perMs)`, taken from `valora_wind`.
- `mode: "mist"` gives a whole-set low-contrast veil: height 3× the fog height and density × 0.4
  (eng).

**Manifest** `engine/blocks/effect/ground_fog/block.json`:

| key | value |
|---|---|
| params | `heightM` number 0.1–1.5 **0.4**; `density` 0–1 **0.4**; `mode` enum [**fog**, mist]; `tint` enum [**neutral**, warm, cool] |
| physics | `{"taxonomy": ["GS-04"], "state": "stateless", "windDriven": true, "windCalibration": {"unit": "drift m/s", "perMs": 0.5}, "requiresWorld": {"hasGround": true}}` |
| other | `atmosphere: true`, `maxPerClip: 1`, `costWeight: 2.0` (eng), `tierMax: "T3"`, `subjectSizeM: [0.05, 30.0]`, `capabilities: ["atmosphere.fog"]`, tags mood [moody, night, mysterious], energy [calm, medium] |

**Pure maths** `engine/physics/fog.py`: `fog_density(z, height_m, density)` and
`pocket_weight(dist, radius)` (0 inside 1 r, 1 from 2 r, smoothstep between). Tests: a monotone falloff,
the pocket zero inside, and mist parameters = 3× the height and 0.4× the density.

**Gates:** `effect_needs_world` (a world with no ground, `hasGround: false`), `wind_implausible`
(> 6 m/s, Task 57).

**Taste TG-25:** "Low fog sells scale and night: 0.3–0.6 m on streets and fields, kept out of a clear
pocket around the subject. Use mist (not fog) for dawn and overcast. Never fog plus heavy haze in one
clip." Blocks: `effect/ground_fog.heightM`, `effect/ground_fog.mode`.

**Prompts:** `foggy_street` "foggy night street" (exercises `effect/ground_fog`, `world/night_street`);
`misty_morning` "misty morning". The unsupported prompt `fog_in_space` (a world with no ground) is
added only if a groundless world exists; today none does, so the entry is omitted (no `requiresWorld`
beyond `hasGround`, which every world has).

**Blender compile test** on `sports_car` in `studio_cyc`: exactly one volume object, tagged
`effect/ground_fog`, and density 0 at the subject centre (sample the evaluated domain's shader-driven
attribute through the probe, or check the pocket's node parameter equals `POCKET × radius`).

**Look-check `[render ≤ 3]`:** 1 frame, sports_car, dark studio, fog 0.4 m.

Commit: `feat(effect): ground_fog/mist ported from render-studio, subject-scaled and wind-driven`.

---

### Task 61: Finish the grade compositor port (neutral defaults, no new presets)

`engine/blender/grade.py` already ports `rain_look.compositor` (exposure, lift/gamma/gain, fog glow
bloom). It still lacks warm **halation** (Glare, threshold 1.2, size 0.45, tint 1/.58/.38), **lens
distortion + dispersion** (distortion 0.006, dispersion 0.00035, fit), the **filter width** (1.95),
per-shot exposure metering, and the **film grain**. Grain is an ffmpeg filter in render-studio
(`pipeline.py` `GRAIN_FILTER`: vignette PI/14, noise alls=13, luma mask); here it becomes a compositor
noise so that the Blender render is the whole look (spec §2b).

**Frozen-baseline rule:** the `mood_grade` `preset` enum does **not** change, because
`PHASE3_MOODS` guards the interim roll. Every new param defaults to "off" (0), so every existing script
renders exactly as before, and presets opt in through `engine/grade_plan.py` only when the script sets
the param. Layer 1 may vary the new params later; they go into `detailParams` only after a look-check.

**Params added to `mood_grade` (and `neutral_film` where marked):**

| param | range | default | source |
|---|---|---|---|
| `halation` | 0–1 | **0** | rain_look halation glare (strength scales the glare mix) |
| `lensDistortion` | 0–0.02 | **0** | Lensdist distortion (dispersion = 0.058 × distortion, from 0.00035/0.006) |
| `grain` | 0–1 | **0** (both blocks) | pipeline GRAIN_FILTER noise alls=13 ≈ grain 0.5 (eng mapping) |
| `vignette` | exists in grade_plan | unchanged | – |

**Pure maths** in `engine/grade_plan.py`: `plan_for(...)` emits `halation`, `lens` and `grain` node
specs only when their value is > 0. Tests in `engine/tests/test_grade_plan.py`:
- a script without the params yields exactly today's plan (compare dicts);
- `grain > 0` yields a noise spec whose seed is `block_seed(seed, "grade", id)` plus the frame, so it
  varies per frame and is deterministic per frame (METHODS R1: frame N from time and seed alone);
- `lensDistortion` 0.006 → dispersion 0.00035 ± 1e-6.

**Build notes** (`engine/blender/grade.py`): add the Glare node (type `GLARE`, and read the enum
identifier for "fog glow" from the node's RNA, since enums change between versions), the Lens
Distortion node (`LENSDIST`), and grain as a noise texture into a luma-masked Mix
(`MIX_RGB`/`MIX` — probe which node type 5.0 exposes). Set `scene.render.filter_size` only when the
script sets `filterWidth`; this task does not add that param, so leave the filter at its default and
record it for phase 7 (farm consistency).

**Blender test:** compile `script_t3.json` twice. First without the params: the node count and types
equal today's. Then with `halation 0.5, lensDistortion 0.006, grain 0.5`: 3 extra nodes of the
expected types.

**Taste TG-26:** "Finish like film, lightly: halation 0.2–0.4 on night and neon moods, grain 0.2–0.4 on
everything except clean catalogue looks, lens distortion at most 0.006 and never on product close-ups."
Blocks: `grade/mood_grade.halation`, `grade/mood_grade.grain`, `grade/mood_grade.lensDistortion`.

**Growth:** `mood_grade` is not a new block, so there is no growth entry. The taste rule and the
tests above are the contract. Add a prompt `film_look` "shot on film, grainy" with `exercises:
["grade/mood_grade"]`.

**Look-check `[render ≤ 3]`:** 1 frame, `script_t3` with the three params set.

Commit: `feat(grade): halation, lens distortion and seeded grain (render-studio compositor port finished)`.

---

### Task 62: Asset manifest, licence gate and procedural fallbacks

**Files:**
- Create: `engine/assets.py`, `engine/assets/manifest.json`, `engine/assets/CREDITS.md`,
  `engine/tests/test_assets.py`, `tools/assets/import_local.py`
- Modify: `.gitignore` (`assets-in/library/`)

- [ ] **Step 1: Write the failing test** `engine/tests/test_assets.py`:

```python
import json

import pytest

from engine.assets import ALLOWED_LICENCES, AssetError, load_manifest, resolve


def test_manifest_entries_are_licence_clean_and_pinned():
    for aid, a in load_manifest()["assets"].items():
        assert a["licence"] in ALLOWED_LICENCES, aid
        assert len(a["sha256"]) == 64 and a["source"].startswith(("https://", "owned:")), aid
        if a["licence"] == "CC-BY-4.0":
            assert a.get("credit"), aid


def test_missing_file_falls_back_never_raises(tmp_path):
    got = resolve("asphalt_02_diff", root=tmp_path)          # nothing on disk
    assert got is None                                        # caller builds the procedural fallback


def test_hash_mismatch_is_refused(tmp_path):
    m = load_manifest()
    aid, a = next(iter(m["assets"].items()))
    p = tmp_path / a["path"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"not the asset")
    with pytest.raises(AssetError):
        resolve(aid, root=tmp_path)


def test_unknown_licence_rejected(tmp_path, monkeypatch):
    import engine.assets as A
    doc = {"schema": "valora.assets/1", "assets": {"x": {"path": "x.png", "sha256": "0" * 64, "licence": "CC-BY-NC-4.0", "source": "https://x"}}}
    f = tmp_path / "m.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(AssetError):
        A.load_manifest(f)
```

- [ ] **Step 2: Run it.** Expected: FAIL (no module).
- [ ] **Step 3: Write `engine/assets.py`:**

```python
"""Pinned, licence-clean assets (ASSETS.md shipping rule; spec §4.7 same asset hashes on every worker).
Files live under assets-in/library/ (gitignored); the manifest is committed. resolve() returns a path only
when the file exists AND its sha256 matches; a missing file returns None and the block builds its
procedural fallback, so tests and farm workers never need the file. Blocks never download."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("assets") / "manifest.json"
LIBRARY = ROOT / "assets-in" / "library"
ALLOWED_LICENCES = ("CC0-1.0", "owned", "CC-BY-4.0")


class AssetError(RuntimeError):
    pass


def load_manifest(path=MANIFEST):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    for aid, a in doc["assets"].items():
        if a.get("licence") not in ALLOWED_LICENCES:
            raise AssetError(f"{aid}: licence {a.get('licence')!r} is not shippable (allowed {ALLOWED_LICENCES})")
    return doc


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(aid, root=LIBRARY, manifest=None):
    a = (manifest or load_manifest())["assets"].get(aid)
    if a is None:
        raise AssetError(f"unknown asset {aid}")
    p = Path(root) / a["path"]
    if not p.exists():
        return None
    if _sha(p) != a["sha256"]:
        raise AssetError(f"{aid}: sha256 mismatch at {p}")
    return p
```

- [ ] **Step 4: Import the local CC0 assets** that render-studio already pinned. Write
  `tools/assets/import_local.py`. It reads
  `C:\Users\deand\Projects\ModVision\tools\render-studio\assets\manifest.json`, copies (never moves)
  each file into `assets-in/library/polyhaven/<name>`, computes sha256, and writes the manifest
  entries with `licence: "CC0-1.0"`, `source: "https://polyhaven.com/a/<slug>"` and `credit: null`.
  This is a **local copy of files already on disk; it downloads nothing.** Import only the 4k HDRI,
  not the 8k. It covers `cloudy_vondelpark` 4k, `asphalt_02` (diff, rough, nor_gl, disp 2k),
  `tree_small_02` and `grass_medium_01`. If the render-studio manifest records a licence other than
  CC0 for any file, skip that file and list it under Owner-only. Run the tool, commit only
  `engine/assets/manifest.json` and never the files, and add `assets-in/library/` to `.gitignore`.
- [ ] **Step 5: Write `engine/assets/CREDITS.md`** with its header ("CC-BY assets used in renders; one
  row each") and an empty table. Phase 5 imports none.
- [ ] **Step 6: Run** the test (PASS; the manifest now has entries). Then commit:

```bash
git diff --cached --name-only
git commit -m "feat(assets): pinned licence-clean asset manifest with procedural fallbacks" -- engine/assets.py engine/assets/manifest.json engine/assets/CREDITS.md engine/tests/test_assets.py tools/assets/import_local.py .gitignore
```

---

### Task 63: `rain_courtyard`, the generalised courtyard world

**Source:**
- `rain_scene.py` `build()` (≈ :384–489): a 14×32 m asphalt court, soil and park ground, curbs, tree
  beds with trees, grass, benches, drainage grates, and 620 litter leaves plus 90 loose ones.
- `environment()` (≈ :249–289): the HDRI world rotated 110° and a 90 m camera-only backdrop dome.
- `park_ground()` (≈ :292): the HDRI projected onto the ground.
- `rain_look.environment()` (≈ :260–322): world grade and foliage saturation.

**Remove:**
- the `MANTHEY_992` material gate (`rain_look.car_materials`);
- every `drl-*` / `tail-light-bar` lamp key (`lamps`, `switch_off_lamps`, `animate_lamps`);
- `wheel_reflector` and `cabin_fill` (car mesh names);
- the per-car leaf exclusion box. It becomes subject bounds + `BOX_MARGIN` from the profile.

Materials of the upload are never touched (spec §4.5).

**Generalise:**
- The court scales with the subject: court length = `max(14 m, COURT_K × profile.longest)`, eng
  `COURT_K` 6. A 0.3 m sneaker gets a small-scale set dressing multiplier so that benches and trees do
  not read as giant. Set dressing is kept at real size and moved **out of frame** when the subject is
  small (< 0.5 m); the camera then sees asphalt, puddles and the soft background dome.
- Trees and grass follow the foliage contract (H6, Task 20 of the realism plan): tag `valora_foliage`,
  one mesh island per blade/stem with root points at `valora_sway` 0, `valora_sway`, `valora_sway_len`.
  The Poly Haven `grass_medium_01` glTF has shared vertices, so split it by island at build time and
  test that. The floor is tagged `valora_ground`.
- Loose leaves stay static litter in phase 5 (falling leaves are backlog).
- Wetness is a world param that `wet_surface` reads when it is present. On its own the world is dry
  asphalt with a damp-sheen param.

**Manifest:**

| key | value |
|---|---|
| params | `wetness` 0–1 **0.0**; `timeOfDay` enum [**overcast_day**, dusk]; `dressing` enum [**full**, sparse] |
| world facts | `hasGround: true`, `groundType: "asphalt"`, `hasFoliage: true`, `outdoor: true`, `weathers: ["dry","wet","rain","fog"]`, `temperature: "mild"`, `windDefault: 0.8`, `timeOfDay: {"param": "timeOfDay", "values": ["overcast_day", "dusk"]}`, `toneParam: null`, `driveLaneM: 24.0` |
| other | `subjectSizeM: [0.1, 6.0]`, `costWeight: 3.0` (eng; the rain film measured ≈ 35 s/frame at final), `tierMax: "T3"`, `capabilities: ["world.street", "world.nature"]`, tags mood [moody, cinematic, rainy], energy [calm, medium], palette [cool] |

**Pure maths** `engine/worlds/courtyard_layout.py`: `layout(profile, seed, dressing)` returns the court
extents, a list of prop placements (id, xy, yaw) and the exclusion rect. Tests:
- no prop lies inside the bounds + margin, or inside the drive lane when `driveLaneM > 0`;
- the court is ≥ `max(14, 6·longest)` long;
- the same seed gives the same layout, and another seed gives a different one;
- a sneaker gets zero props within the widest camera's frustum at the default low-hero distance (use
  the checker's `frame_stats` with the fallback hero pose).

**Build notes:**
- HDRI via `engine.assets.resolve("cloudy_vondelpark_4k")`. **Fallback:** Nishita sky at overcast
  settings plus a grey backdrop.
- Asphalt uses Poly Haven maps; **fallback:** procedural noise asphalt.
- Trees and grass use glTF; **fallback:** GN-procedural grass blades (the realism plan's test lawn
  generator, if one is importable; otherwise a small GN scatter of tapered blades that meets the
  foliage contract) and no trees.
- Background dome: camera-only visibility.
- Lighting pairs with `hdri_only` (Task 72). Until Task 72 lands, the fixture script uses
  `softbox_three_point`.

**Gates:** `world_has_no_ground` (existing; it must pass), `path_through_world` (Task 56),
`subject_size_unsupported` (> 6 m).

**Taste TG-27:** "rain_courtyard is the cinematic outdoor default for vehicles and large objects: low
hero angles, wet asphalt, overcast or dusk. Small products look lost in it unless the camera stays low
and close (macro_detail, low_hero_push at 50 mm or longer)." Blocks: `world/rain_courtyard`.

**Prompts:** `courtyard` "cinematic courtyard, overcast" (exercises `world/rain_courtyard`);
`courtyard_huge` asks for the courtyard with a >6 m subject. Use the `sports_car` profile scaled in the
fixture, or state it as an `expectCheck: "subject_size_unsupported"` case if `director_eval` cannot
scale; check which is supported.

**Blender compile test** (`sports_car`, `pocket_watch`):
- `valora_ground` exists at z = 0;
- ≥ 1 `valora_foliage` object whose islands have `valora_sway` = 0 at their lowest vertex;
- `ground_conform` applies (the realism resolver lists it; `hasFoliage` is true);
- the subject is grounded (`realismProbe.grounded`);
- no prop object intersects the subject's bounds + margin.

Run it once with `LIBRARY` pointed at an empty temp dir to prove every fallback builds.

**Look-check `[render ≤ 3]`:** 2 frames (sports_car hero; pocket_watch hero) at preview tier, in one
invocation.

Commit: `feat(world): rain_courtyard ported from render-studio, car gates removed, subject-scaled`.

**Chunk 2 gate:** full suite green, frozen baseline 90/90.

---

## Chunk 3: The weather package (rain, wet ground, droplets, snow, lens drops)

Start with the re-rank checkpoint. **Build order inside this chunk:** Task 64 ships `rain` **without**
`couplings`/`excludes` (the catalog load rejects references to blocks that do not exist yet). Tasks 65,
66 and 67 build `wet_surface`, `droplets` and `snow`; Task 67's last step adds rain's
`couplings: ["wet_surface","droplets"]` and `excludes: ["snow"]` plus snow's `excludes: ["rain"]`, and
moves the Task 57 coupling tests from fixtures to the real blocks. All blocks here are **stateless** (METHODS R1). The value at frame
N is a function of (time, seed, params, subject pose), so preview equals final and any frame range
renders on any worker. There is no simulation zone, no bake and no VDB (phase 6).

### Task 64: Shared stateless weather nodes, then `rain` (drizzle / steady / downpour)

**Source:** `rain_atmosphere.py` `build()` (≈ :10–119): about 850 × reach² columns of drops falling
at 6.5 m/s, a BVH ray-cast against the car so the car shelters the rain, no temporal wrap, and a
rain-only backlight lamp. `rain_look.LOOK` rain size, reach, backlight and glow (≈ :18–138).

**Pure maths** `engine/physics/rain.py`:

```python
"""Rain as analytic streams (METHODS FL-01, PT-04 pattern): each drop i has a seeded spawn (x, y) in a
camera-following box and phase; position(t) = spawn + v*(t + phase) wrapped in the box height, so frame N
needs no frame N-1. Fall speed by drop size (Gunn-Kinzer, eng fit), slant from the one wind field,
streak length = speed x shutter time (180 deg at 30 fps -> 1/60 s)."""
import math

INTENSITY = {  # (eng) mm/h and drop size by preset; render counts come from rate x box volume
    "drizzle": {"rateMmH": 1.0, "dropSizeMm": 0.8},
    "steady": {"rateMmH": 4.0, "dropSizeMm": 2.0},
    "downpour": {"rateMmH": 25.0, "dropSizeMm": 3.0},
}
MAX_DROPS = 60000     # (eng) instance cap per clip, by cost
DROPS_PER_MM_H_M3 = 90.0   # (eng) visible streak density per (mm/h x m^3); calibrated by the look-check


def fall_speed(d_mm):
    """Terminal velocity (m/s) for a drop of diameter d (mm): 9.65 - 10.3 exp(-0.6 d) (Atlas et al.)."""
    return max(0.5, 9.65 - 10.3 * math.exp(-0.6 * d_mm))


def streak_len(speed, fps=30, shutter=0.5):
    return speed * shutter / fps


def drop_count(rate_mm_h, box_m3):
    return min(MAX_DROPS, int(DROPS_PER_MM_H_M3 * rate_mm_h * box_m3))


def slant_vector(wind_vec, speed):
    """Unit fall direction including wind drift (wind_vec in m/s, world XY)."""
    x, y, z = wind_vec[0], wind_vec[1], -speed
    n = math.sqrt(x * x + y * y + z * z)
    return (x / n, y / n, z / n)


def drop_position(spawn, phase, t, fall_dir, speed, box_h):
    """Wrapped analytic position; spawn is the top of the column."""
    s = ((t + phase) * speed) % box_h
    return (spawn[0] + fall_dir[0] * s, spawn[1] + fall_dir[1] * s, spawn[2] + fall_dir[2] * s)


def sheltered(xy, bounds_lo, bounds_hi, margin=0.0):
    """A drop whose column passes over the posed subject's footprint dies at its roof (no rain under a car)."""
    return (bounds_lo[0] - margin <= xy[0] <= bounds_hi[0] + margin) and (bounds_lo[1] - margin <= xy[1] <= bounds_hi[1] + margin)
```

Tests `engine/tests/test_rain.py`:
- `fall_speed(2.0)` ≈ 6.49 ± 0.05 (render-studio's 6.5 m/s);
- `streak_len(6.5)` ≈ 0.108 m (the METHODS 11 cm example);
- `drop_position` is periodic in `box_h / speed`;
- the drizzle count < steady count < downpour count for the same box;
- `slant_vector` with zero wind is straight down, and 6.5 m/s wind gives 45°
  (`rain_slant_deg`, Task 59);
- `sheltered` is true over the footprint and false one margin outside it.

**Shared builder** `engine/blender/weather_nodes.py`:
- `particle_box_group(name)` is a GN group. It distributes N seeded points in a box that follows the
  active camera (the camera position is read through an Object Info node on the scene camera; cameras
  are keyframed, so the result is stateless). It advances each point analytically with
  `Scene Time` × speed along the fall direction, wraps it (`Wrap` math node), deletes points inside
  the posed subject's footprint column (Object Info on `valora_motion`, so shelter follows a moving
  subject), instances a streak (a thin quad of length `streak_len`, oriented to the fall direction)
  and writes a `velocity` attribute (METHODS R7, so motion blur streaks correctly).
- `impact_events(name)` is a GN group that emits seeded (xy, t0) impact events on the ground plane and
  on up-facing subject samples. Each event is a 3–8-frame crown instance whose scale is a function of
  `(t − t0)`, which is stateless. The same events drive the ripple rings in `wet_surface`'s shader
  through a shared attribute or texture: a seeded Voronoi keyed on `floor(t/period)`, so both agree
  without state.

Both use node **types** only (probe the 5.0 idnames once with `bpy.types` and list them in the module
docstring, as the realism plan did).

**Manifest** `engine/blocks/effect/rain/block.json`:

| key | value |
|---|---|
| params | `intensity` enum [drizzle, **steady**, downpour]; `rateMmH` 0.5–50 (unset = from intensity); `dropSizeMm` 0.5–4 (unset = from intensity); `impacts` bool **true**; `backlight` 0–1 **0.6** |
| physics | `{"taxonomy": ["FL-01","FL-02","LM-05"], "state": "stateless", "windDriven": true, "windCalibration": {"unit": "slant: atan(wind/fall)", "perMs": 1.0}, "couplings": ["wet_surface","droplets"], "excludes": ["snow"], "requiresWorld": {"outdoor": true, "hasGround": true}}` |
| other | `maxPerClip: 1`, `costWeight: 1.8` (eng), `tierMax: "T3"`, `subjectSizeM: [0.05, 30.0]`, `capabilities: ["weather.rain"]`, tags mood [moody, rainy, night, cinematic], energy [calm, medium, hype], palette [cool] |

**Build notes:**
- The camera box is sized from the farthest camera distance and lens (eng: 1.5× the frustum depth
  at the subject, capped).
- Backlight: a rain-only area light behind the subject relative to the hero camera (LM-05: streaks
  read in back- or side-light), light-linked to the streaks only, so the subject is not relit.
  render-studio does this with a rain-only lamp; use Cycles light linking (5.0), probed.
- No time-scale param (Task 57: weather runs at real time).

**Gates:** `effect_needs_world` (studio), `exclusive_effects` (with snow), `coupled_added`,
`effect_max_per_clip`.

**Taste TG-28:** "Rain reads only against light: keep a light behind or beside the subject (rim or
practicals). Drizzle for products and calm moods, steady for most, downpour only for vehicles and hype.
Rain means wet: the ground and subject get wet automatically."
Blocks: `effect/rain.intensity`, `effect/rain.backlight`.

**Prompts:**
- `add_rain` stays; change it to `"expectDelivered": ["weather.rain"]` with `"exercises":
  ["effect/rain"]`.
- `rainy_night` gets the same change.
- `drizzle` "light drizzle, calm".
- `downpour_car` "car in a downpour".
- `studio_rain` "rain in a white studio" becomes the unsupported ask: `expectUnsupported:
  ["weather.rain"]` when the studio is pinned. Its note must say the studio is indoor (Task 85 notes).

**Blender compile test** (`sports_car` in `rain_courtyard`, rain steady):
- the streak points carry `velocity`;
- 0 points inside the posed subject bounds at key frames (the `no_particles_in_subject` probe, Task 69);
- the point count at frame 1 equals `drop_count(rate, box)` ± 1%;
- the frame-40 positions computed twice from a fresh load are identical (stateless proof).

**Look-check `[render ≤ 3]`:** 1 frame each of drizzle and downpour on the sports car (2 frames).

Commit: `feat(effect): stateless rain (drizzle/steady/downpour) with shelter, impacts and wind slant`.

---

### Task 65: `wet_surface` (wet ground, puddles that reflect, ripples only while it rains)

**Source:**
- `rain_scene.py` `wet_asphalt()` (≈ :72–232): a water film plus standing water, thresholded at
  `PUDDLE_LEVEL = .69`.
- `car_apron()` (≈ :235): a dip of water under the car.
- `wet_detail.py` `puddle_normal()` (≈ :5): impact rings; `configure_ripple_animation()` (≈ :69).

**Port changes:**
- The film and puddle mask are shader-only on the world's `valora_ground` material (M-SHD, FL-06/07).
  The block **wraps** the ground material in a mix group (albedo × 0.6–0.85, roughness × 0.1–0.4,
  puddle mask = noise > `1 − puddles`, puddle roughness 0.02 so it reflects like a mirror). It never
  replaces the world's own nodes.
- The apron becomes a puddle bias under the subject's posed footprint, so reflections of the subject
  appear. This is a mask term, not geometry.
- Ripples are driven by `impact_events` only when `rain` is present. On its own (after the rain), the
  puddles are calm mirrors with slow drips.
- The upload's materials are **left alone** (spec §4.5). Subject wetness is carried by `droplets`
  (geometry), never by editing the upload's shaders. This is a decision; record it in the register.

**Manifest:**

| key | value |
|---|---|
| params | `wetness` 0.3–1 **0.8**; `puddles` 0–1 **0.4**; `ripples` enum [**auto**, off] (auto = on when rain present); `drips` bool **true** |
| physics | `{"taxonomy": ["FL-06","FL-07","FL-20"], "state": "stateless", "requiresWorld": {"outdoor": true, "hasGround": true}}` |
| other | `maxPerClip: 1`, `costWeight: 1.1`, `tierMax: "T3"`, `capabilities: ["surface.wet"]`, tags mood [moody, rainy, night, fresh], energy [calm, medium, hype] |

**Pure maths** `engine/physics/wet.py`: `albedo_factor(wetness)` (1 → 0.6 linear, eng) and
`roughness_factor(wetness)` (1 → 0.1). Also `puddle_threshold(puddles)`: puddles 0.31 gives
threshold 0.69, render-studio's `PUDDLE_LEVEL`. Tests assert that mapping exactly.

**Gates:** `effect_needs_world`, `coupling_removed` (while rain is present).

**Taste TG-29:** "After the rain beats rain for products: wet ground and calm puddles that mirror the
subject, no falling drops. Streets at night: wetness 0.6–1.0 (vehicles.md)."
Blocks: `effect/wet_surface.wetness`, `effect/wet_surface.puddles`.

**Prompts:**
- `after_rain` "after the rain, wet street reflections" (exercises `effect/wet_surface`,
  `expectDelivered: ["surface.wet"]`).
- `puddles` "puddles reflecting the car".
- Unsupported: `wet_studio` "wet floor in the studio" (studio pinned) → `surface.wet`.

**Blender compile test:**
- the ground material has exactly one `valora_wet` group node;
- the upload's material node trees are **unchanged**. Hash every upload material tree before and
  after and assert they are equal. This is the spec §4.5 guard.
- with rain present, the ripple input is connected; alone, it is not.

**Look-check `[render ≤ 3]`:** 1 frame, `pocket_watch` "after the rain" in `rain_courtyard`, low hero
angle so the puddle reflection is visible.

Commit: `feat(effect): wet_surface (wet ground, reflecting puddles, rain-only ripples) ported`.

---

### Task 66: `droplets` and drips on the subject

**Source:** `rain_atmosphere.py` `drips()` (≈ :122–297). Droplets swell on the car's lower edges and
fall, and the emitters are found by ray-casting the car. It is car-dependent but not GT3-specific.

**Port changes:**
- Emitters come from `shape.low_edges(profile.surfaceSamples)` (Task 55), posed with the subject.
  There is no mesh-name lookup.
- Droplets (FL-03) are GN-distributed on the evaluated subject surface. They are weighted by n·up and
  a noise mask, snapped with `Sample Nearest Surface`, flattened hemispheres of 1–4 mm (real size), and
  use a water glass material.
- Drip lifecycle (FL-20) is analytic: swell for 0.5–3 s, detach, fall with gravity, die at z = 0,
  where it spawns an impact event. Period and phase are seeded per emitter.
- The droplet GN lives on a **separate object** that reads the upload through Object Info. The upload
  itself gets no modifier, so its evaluated mesh (and the checker's bounds) are untouched.

**Manifest:**

| key | value |
|---|---|
| params | `density` 0.1–1 **0.5**; `sizeMm` 0.5–4 **1.5**; `zone` enum [all, **up_facing**] (no glass/paint zones: samples carry no material class, Task 55); `drips` bool **true** |
| physics | `{"taxonomy": ["FL-03","FL-20","LM-04"], "state": "stateless"}` |
| other | `requiresProfile: ["upFacing"]`, `maxPerClip: 1`, `costWeight: 1.2`, `tierMax: "T3"`, `capabilities: ["liquid.droplets"]`, tags mood [fresh, rainy, premium], energy [calm, medium] |

`droplets` is standalone-selectable ("dew", "fresh", "ice-cold" asks) as well as coupled by rain. It
works in the studio too: droplets on a bottle in a studio are fine (no `requiresWorld`).

**Pure tests** `engine/tests/test_droplets.py`:
- `drip_state(t, period, phase)` cycles swell → fall → gone, with the fall ending at z = 0 at
  `sqrt(2h/g)`;
- zone `up_facing` selects only samples whose estimated normal has n·up > 0.7 (the `pocket_watch` profile);
- a subject with < 8 up-facing samples is `requiresProfile`-blocked, which the checker turns into
  `effect_needs_profile`.

**Gates:** `effect_needs_profile`, `coupled_added`.

**Taste TG-30:** "Droplets are a freshness cue: 1–2 mm on glass and glossy paint, sparse on matte.
With rain they come automatically; alone they say 'ice-cold' or 'morning dew'." Blocks:
`effect/droplets.sizeMm`, `effect/droplets.zone`.

**Prompts:**
- `dewy` "fresh dewy look" (`exercises: ["effect/droplets"]`, `expectDelivered: ["liquid.droplets"]`).
- The existing `liquid` prompt ("liquid running down the can") stays unsupported for
  `liquid.run_down` (runners are phase 6). Its note must say "the can has droplets but they don't
  move" when droplets were added (PHASING §3.3); Task 85 updates the note.

**Blender compile test** (`pocket_watch`, alone in the studio):
- the droplet object exists and every instance lies within 1 mm of the evaluated subject surface
  (BVH nearest);
- no instance has n·up < 0 when `zone` is up_facing;
- the upload has no new modifier.

Commit: `feat(effect): droplets and drips on up-facing surfaces (render-studio drips generalised)`.

---

### Task 67: `snow`, with accumulation

**Pure maths** `engine/physics/snow.py`:
- Flakes fall at 0.5–1.5 m/s (METHODS PT-04) with a lateral wobble:
  `(A sin(2π f t + φ), A cos(2π f' t + φ'))`, A 2–6 cm, f 0.3–0.8 Hz (eng). Wind drift comes from
  `windCalibration perMs = 0.9`, because snow follows the air.
- Accumulation thickness is `accumulationMm` at t = 0 and grows by `rate × t × GROW` (eng small, so it
  stays stateless). It applies only on faces with n·up > 0.7, with rounded edges.

Tests:
- the fall speed is inside the range;
- the wobble is bounded by A;
- the accumulation mask is zero for n·up ≤ 0.7;
- the flake count scales with `rate`;
- the same seed gives the same flake positions at frame 40.

**Build:**
- Reuse `particle_box_group` with a flake instance (a real-size 2–15 mm card, `flakeMm`) and no streak
  (drift carries velocity).
- Accumulation is a GN layer on a **separate object** reading the subject (as in Task 66), plus a snow
  material on the world's `valora_ground`, wrapped as `wet_surface` wraps it.
- `groundType` stays the world's; snow is a coat. The realism resolver's `ground_conform` does not
  switch to snow sink in phase 5; record that in the register as a deferred coupling.

**Manifest:**

| key | value |
|---|---|
| params | `rate` 0.1–1 **0.4**; `flakeMm` 2–15 **6**; `accumulationMm` 0–30 **5**; `onSubject` bool **true** |
| physics | `{"taxonomy": ["PT-04"], "state": "stateless", "windDriven": true, "windCalibration": {"unit": "drift m/s", "perMs": 0.9}, "excludes": ["rain"], "requiresWorld": {"outdoor": true, "hasGround": true}}` |
| other | `maxPerClip: 1`, `costWeight: 1.6`, `tierMax: "T3"`, `capabilities: ["weather.snow"]`, tags mood [calm, wintry, premium, nostalgic], energy [calm, medium], palette [cool, neutral] |

When snow is present, the checker sets the world param `temperature` view to cold for the realism
resolver (`effects: snow` counts as cold in `applies.match`). Add `"cold"` to the facts `match` reads,
and test that it does not change any existing realism resolution without snow.

**Gates:** `effect_needs_world`, `exclusive_effects`, `wind_implausible` (snow above 11 m/s → warning
"blizzard reads as noise").

**Taste TG-31:** "Snow is quiet: calm pace, cool or neutral grade, light wind. Accumulation 3–10 mm
reads real; more buries detail. Never snow and rain together."
Blocks: `effect/snow.rate`, `effect/snow.accumulationMm`.

**Prompts:** `snowy` "snowy winter scene" (delivered, `weather.snow`); `snow_studio` "snow in the
studio" (unsupported, studio pinned); `snow_and_rain` "snow and rain" (the checker keeps one; the
note says which).

**Blender compile test** (`sports_car`, `golden_field` or `rain_courtyard`, whichever exists first):
- flakes carry `velocity`;
- the accumulation object covers only up-facing faces (sample its normals: every face n·up > 0.7);
- 0 flakes inside the posed bounds.

**Look-check `[render ≤ 3]`:** 1 frame.

Commit: `feat(effect): stateless snow with drift and up-facing accumulation`.

---

### Task 68: `lens_drops` (at most one shot, only with rain)

**Pure/checker:**
- `lens_drops` requires `rain` in the clip; otherwise the error is `effect_needs_source`. Register it.
- It has `shot` (index) and `amount` 0–1 **0.3**. The checker clamps `shot` into range and then
  applies `effect_off_screen`. A lens-drops shot must not be a `detail` shot (the refraction hides the
  detail), so move it to the nearest non-detail shot (`repaired`) or raise an error when there is
  none. Enforce `maxPerClip: 1` (one shot per clip).

**Build (M-COMP):** a compositor Displace driven by a droplet normal texture (procedural Voronoi
bumps, seeded), plus a small blur inside the drops, enabled only in the chosen shot's frame range
through the compositor mix factor, keyed at the shot boundaries (cuts sit in the closed-shutter gap,
so there is no bleed).

**Manifest:** `capabilities: ["camera.lens_drops"]`,
`physics: {"taxonomy": ["LM-06"], "state": "stateless", "requiresWorld": {"outdoor": true}}`,
`costWeight: 1.0`, tags mood [cinematic, rainy], energy [medium, hype].

**Taste TG-32:** "Lens drops are a cliché used once: at most one non-detail shot, only in rain, amount
0.2–0.4." Blocks: `effect/lens_drops.amount`.

**Prompts:** `rain_on_lens` "rain on the lens" (delivered); `lens_drops_dry` "water drops on the lens,
sunny day" (unsupported: no rain source → the note says so).

**Tests:** `engine/tests/test_lens_drops.py` covers the source rule, the detail-shot move, the clamp
and the one-per-clip rule. A Blender test asserts that the compositor mix factor is 0 outside the
chosen shot's frames and > 0 inside.

Commit: `feat(effect): lens_drops in at most one shot, only with rain`.

---

### Task 69: Weather compile probes and script-level PH items

**Files:**
- Modify: `engine/blender/realism_probe.py` (or create `engine/blender/weather_probe.py` if the realism
  module is at its size limit), `harness/physics.py` (`PH_ITEMS`), `harness/score.py`
- Test: `engine/tests/test_weather_probe.py` (pure parts), Blender cases in
  `engine/tests/test_blocks_phase5_blender.py`

- [ ] **Step 1: Pure verdict functions first**, in `engine/physics/probes.py` next to the existing
  ones:
  - `no_particles_in_subject(points_by_frame, bounds_by_frame, tol=0.001)`: the share of points
    inside the posed bounds must be ≤ tol.
  - `velocity_present(has_attr_by_object)`.
  - `streak_ok(len_px, speed, shutter, fps, px_per_m)`: within ±40% (PH-05).

  Write the tests first with synthetic numbers, then the functions.
- [ ] **Step 2: Wire the probes** into the compile probe for every present `effect` whose
  `physics.state` is stateless and that emits points (rain, snow, droplets). Record the result in
  `compile.json` → `weatherProbe`, report-only (thresholds are calibrated before they gate, spec §4.8).
- [ ] **Step 3: Script-level harness items.** In `harness/score.py`, add `[S]` checks:
  - **PH-08s:** rain present ⇒ `wet_surface` and `droplets` present (the coupling kept).
  - **PH-07s:** every `expectDelivered` capability is provided by a block in the final script.
  - **W-01:** at most one weather family per clip.

  Add PH-05, PH-06 and PH-08 to `PH_ITEMS` with their methods (`C+M`, `M`, `V`). The frame parts stay
  `n/a` until frames exist.
- [ ] **Step 4: Run** the new tests, `harness/tests`, the full suite and the frozen baseline gate.
- [ ] **Step 5: Commit** `feat(harness): weather compile probes and script-level PH items`, naming
  exactly the files touched.

**Chunk 3 gate:** full suite green, frozen baseline 90/90, growth contract green for `effect/rain`,
`effect/wet_surface`, `effect/droplets`, `effect/snow`, `effect/lens_drops` and `effect/ground_fog`.

---

## Chunk 4: New worlds and the lights they need

Start with the re-rank checkpoint. The risk this chunk owns is spec §11: "new worlds look CG next to the
rain film". The mitigations are true metres, the reused compositor and volumetrics, a look-check per
world, and golden status null until the owner grades.

### Task 70: `night_street`

A wet city street at dusk or night: asphalt with lane markings, a kerb and pavement, a row of low
building facades with emissive windows and shopfront glow, street lamps (practicals), and optional neon
signage bars. The signage has **no text and no logos**; the bars are coloured emissive strips whose
hue comes from `neonHue`. Everything is procedural, CC0 by construction. Poly Haven asphalt maps are
used when present (Task 62), with a noise asphalt as the fallback.

**Pure layout** `engine/worlds/street_layout.py`: `layout(profile, seed, lane_m)` returns the road
extents (length = max(30 m, 8 × longest), eng), facade blocks along one or both sides (seeded widths
3–12 m and heights 4–15 m; window grid with a seeded lit share of 0.2–0.6), lamp posts every 12–20 m
(eng), neon bars (0–4, seeded placement on facades, never inside the camera clear zone), and the drive
lane (centre line, `driveLaneM`). Tests:
- lamps and props sit outside the bounds + margin and outside the drive lane;
- the same seed gives the same layout;
- the neon count is inside its range;
- a small subject (< 0.5 m) gets the facades pushed back to keep the scale plausible: at the fallback
  hero pose the camera sees at most one lamp post (use `frame_stats`).

**Manifest:**

| key | value |
|---|---|
| params | `timeOfDay` enum [dusk, **night**]; `neonHue` 0–360 **285**; `neonAmount` 0–1 **0.5**; `windowsLit` 0–1 **0.4**; `wetness` 0–1 **0.6** |
| world facts | `hasGround: true`, `groundType: "asphalt"`, `hasFoliage: false`, `outdoor: true`, `weathers: ["dry","wet","rain","fog"]`, `temperature: "mild"`, `windDefault: 0.8`, `timeOfDay: {"param":"timeOfDay","values":["dusk","night"]}`, `toneParam: null`, `driveLaneM: 30.0` |
| other | `subjectSizeM: [0.1, 8.0]`, `costWeight: 2.6` (eng), `tierMax: "T3"`, `capabilities: ["world.street"]`, tags mood [night, neon, cinematic, moody], energy [medium, hype], palette [cool, neon] |

`wetness` here is the world's own damp sheen. When `wet_surface` is present it takes over, and the
world param is ignored. Record this in the manifest description.

**Build notes:**
- Sky: dark gradient (night) or a Nishita sky with the sun 2° below the horizon (dusk). The lower
  hemisphere gain follows CATALOG-GAPS rank 7 (0.05–0.2).
- Practicals: point or spot lights in lamp heads at real wattage-equivalent (eng 800–1500 lm, warm
  2700–3500 K).
- Neon bars: emissive, strength by `neonAmount`, colour from `neonHue`.
- Facade windows: emissive quads with a seeded pattern.
- The ground is tagged `valora_ground`.
- The default lighting pair is `rim_neon` (Task 72).

**Gates:** `path_through_world`, `subject_size_unsupported`, `lighting_world_mismatch` (Task 72).

**Taste TG-33:** "night_street is the neon/night world: rim_neon or practicals only, never a studio
softbox. Wet ground (0.6–1.0) doubles every light in reflections. Low camera, 28–50 mm for vehicles,
50–85 mm for products." Blocks: `world/night_street.neonHue`, `world/night_street.wetness`.

**Prompts:** `night_street` "neon street at night" (delivered, `world.street`); `rainy_night` already
exercises it together with rain; `dusk_street` "city street at dusk". Unsupported: `street_giant`, a
>8 m subject, like `courtyard_huge` (Task 63).

**Blender compile test** (`sports_car`, `sneaker`):
- ≥ 2 lamp lights;
- every neon material is emissive;
- `valora_ground` exists at z = 0;
- no prop or light object intersects the posed bounds + margin, or the camera keyframe positions
  (camera clearance, `camera_clearance` in `blender_main`, passes);
- with the asset library empty, it still builds.

**Look-check `[render ≤ 3]`:** 2 frames (sports_car night hero, sneaker dusk low hero).

Commit: `feat(world): night_street (procedural, neon without text or logos, practicals)`.

---

### Task 71: `golden_field`

An open field of grass or wheat under a low sun. It follows the outdoor-world foliage contract (H6)
from the start.

**Pure layout** `engine/worlds/field_layout.py`:
- The field extent is max(40 m, 10 × longest).
- A clearing around the subject: grass height tapers to 20% within 1.2 × the footprint (eng), so the
  subject is not buried.
- Seeded blade clusters.
- Optional path: a flattened dirt track along the drive lane when `driveLaneM > 0` and the motion
  translates. The world exposes `track` as a param.
- The horizon treeline or hills are a far card silhouette.
- Tests: no blade root inside the posed footprint; the clearing radius scales with the subject; the
  track is clear of blades; the same seed gives the same result.

**Foliage contract (H6):**
- Every blade or stem is its own mesh island, tagged `valora_foliage`.
- `valora_sway` is 0 at the root and rises to 1 at the tip; `valora_sway_len` is the blade length.
- The ground is `valora_ground`, `groundType: "grass"`, `hasFoliage: true`, `windDefault: 0.8`.
- `ground_conform` and `foliage_sway` then apply automatically (realism, with no director
  involvement).
- Blades are generated GN-procedurally and **realised** to mesh islands at compile time (the probe
  counts islands). Cap the count by cost (eng 60k blades in view); farther blades are a displaced
  ground texture.

**Sun:** a `SUN` light at `sunElevationDeg` 2–15° (CATALOG-GAPS rank 7), with CCT by time of day:
dawn 3500 K, golden 3200 K, dusk 2800 K, overcast 6000 K plus a soft angle. It pairs with `hard_sun`
(Task 72). The world owns the sky (Nishita) and `hard_sun` owns the key, and the two agree on the
azimuth through a shared `sunAzimuthDeg` world param that `hard_sun` reads (no duplicate sun). Test
that the combined scene has exactly one `SUN` light.

**Manifest:**

| key | value |
|---|---|
| params | `timeOfDay` enum [dawn, **golden**, dusk, overcast]; `sunAzimuthDeg` −180–180 **seeded**; `grassHeightM` 0.1–1.2 **0.45**; `crop` enum [**grass**, wheat, wildflowers]; `track` bool **false** |
| world facts | `hasGround: true`, `groundType: "grass"`, `hasFoliage: true`, `outdoor: true`, `weathers: ["dry","wet","fog","snow"]`, `temperature: "mild"`, `windDefault: 0.8`, `timeOfDay: {"param":"timeOfDay","values":["dawn","golden","dusk","overcast"]}`, `toneParam: null`, `driveLaneM: 40.0` |
| other | `subjectSizeM: [0.05, 8.0]`, `costWeight: 3.2` (eng; blades and volumes), `tierMax: "T3"`, `capabilities: ["world.nature"]`, tags mood [warm, nostalgic, calm, premium], energy [calm, medium], palette [warm, golden] |

The field does not list rain in `weathers` (eng: rain on a field reads grey and flat; the wet field
after rain is kept). The corpus may overturn this; record it in the register.

**Gates:** `path_through_world`, `effect_needs_world` (tumbleweed-style asks stay unsupported),
`lighting_world_mismatch`.

**Taste TG-34:** "golden_field is warm and quiet: sun 2–15° behind or beside the subject for a rim,
calm or medium pace, warm_golden grade. A breeze (2–4 m/s) keeps the grass alive; still air looks like a
photo." Blocks: `world/golden_field.timeOfDay`, `world/golden_field.sunAzimuthDeg`.

**Prompts:** `golden_hour` "golden hour in a field" (delivered, `world.nature`); `wheat_car` "car in a
wheat field at sunset"; `field_snow` "snowy field" (delivered with `effect/snow`). Unsupported:
`field_tumbleweed` "tumbleweeds rolling across the field" (`rigid.tumbleweed`, backlog).

**Blender compile test** (`sports_car`, `mid_century_lounge_chair`):
- the `valora_foliage` islands have `valora_sway` 0 at the root;
- the realism resolver lists `foliage_sway` and `ground_conform`;
- `realismProbe.foliageInSubject` is 0;
- there is one `SUN`;
- `windCoherent` holds with a 3 m/s breeze.

**Look-check `[render ≤ 3]`:** 2 frames (sports_car golden, chair overcast).

Commit: `feat(world): golden_field (foliage contract, low sun, clearing and track)`.

---

### Task 72: `hard_sun`, `rim_neon`, `hdri_only`, and the `lighting_world_mismatch` repair

The spec v1 lighting list names five rigs. Two exist today (`softbox_three_point`, `reflection_rig`).
The new worlds need three more; `moody_top` stays in the backlog (the corpus decides).

| block | what | key params (range, **default**) | pairs with |
|---|---|---|---|
| `hard_sun` | the key is the world's sun (reads `sunAzimuthDeg`/`timeOfDay` from the world when present, else its own), a bounce fill card, an optional rim | `elevationDeg` 2–60 **10**; `fillRatio` 0.1–0.6 **0.3**; `rim` 0–1 **0.4** | golden_field, rain_courtyard (dusk) |
| `rim_neon` | two coloured rims (hue pair from the world's `neonHue` ± `hueSplit`) + a low cool fill; practicals come from the world | `rimStrength` 0.5–3 **1.4**; `hueSplit` 0–180 **150**; `keyAzimuthDeg` 90–180 **140** | night_street |
| `hdri_only` | world HDRI (or sky) is the only light + a subtle negative fill | `exposure` −2–2 **0**; `negFill` 0–1 **0.3** | rain_courtyard (overcast) |

**Pure:**
- `engine/lighting/pairing.py` `allowed_lighting(world_manifest)` reads the world manifest's
  `lightingPairs` list. Add `lightingPairs` to all four worlds: studio lists `softbox_three_point`
  and `reflection_rig`; the new worlds list theirs plus `reflection_rig` for glossy subjects.
- The checker repair `lighting_world_mismatch`: when the script's lighting is not in the world's pairs,
  swap it for the first pair (keeping the params that share a name), as a `repaired` issue. TG-08
  gloss logic stays; for a glossy subject in a new world, `reflection_rig` is allowed.
- Tests: the studio is unchanged; `night_street` with a softbox becomes `rim_neon`; `golden_field` with
  `reflection_rig` stays (glossy allowed).

**Frozen-baseline check:** the studio pairs must include every lighting the phase-3 default uses.
Assert that in the test by building the phase-3 default for the 9 eval subjects.

**Build notes:**
- `hard_sun` never adds a second `SUN` when the world has one (Task 71 test). It sets the world sun's
  strength and angle instead.
- `rim_neon` rims are area lights with a colour from the hue; the world's practicals are untouched.
- `hdri_only` sets the world strength and adds a negative-fill black card.

**Gates:** `lighting_world_mismatch`. **Taste:** extend TG-33 and TG-34 to name the pairs, and add
TG-35: "Overcast courtyards light from the sky alone (hdri_only); add a rim only for gloss."

**Prompts:** each world prompt above exercises its lighting too (`"exercises": ["world/…",
"lighting/…"]`).

Growth entries for all three blocks. Blender compile tests: one light setup each, with the expected
light counts and colours.

Commit: `feat(lighting): hard_sun, rim_neon, hdri_only with world pairing repair`.

---

### Task 73: Tone per world (phase-4 deferred item)

Today the tone axis is `studio_cyc.tone` (white/grey/black). Each world now names its `toneParam`.
- The studio keeps `tone`.
- `night_street` gets `null`: tone does not apply at night.
- `golden_field` gets `null`.
- `rain_courtyard` gets `null`.

The dice's tone axis is then:
- the studio's values when the rolled world is `studio_cyc`;
- **the single value `"n/a"`** for worlds with `toneParam: null`.

**No new axis and no new id format:** tone stays the third axis. "n/a" is a value the direction id
already supports as a string; check `make_id` and `parse_id` round-trip "n/a", and use `na` if a slash
or space is a problem.

**Files:** `engine/director/axes.py` (`axis_values`: tone per rolled world means `candidates` must pair
world with tone; move the tone list into a `tone_values(world_manifest)` helper), `dice.json`
(`toneByMood` unchanged for the studio; add `"toneNA": "na"`), `engine/director/fallback.py`
(`_world` passes tone only when the world has a `toneParam`), tests in
`engine/tests/test_director_axes.py`.

**Tests:**
- a studio direction is unchanged (the frozen baseline gate proves it);
- a `night_street` direction has tone `na`, and the fallback's world params contain no `tone`;
- `validate_axes` accepts `na` only with a tone-less world;
- memory records with `na` round-trip.

Commit: `feat(director): tone axis per world (na for worlds without a tone param)`.

**Chunk 4 gate:** full suite green, frozen baseline 90/90, growth contract green for the three worlds and
three lights.

---

## Chunk 5: Subject motion (5a)

Start with the re-rank checkpoint. Every motion is **M-KIN** (keyframes from an analytic path, METHODS
§1), so it is stateless and bakes nothing.
- `path.py` holds the whole truth: `sample(params, profile, t, duration) -> SubjectPose` and
  `flags(params) -> {translates, stops, lands}`. `flags` feeds `motion_flags()` in `applies.py`, so
  realism (`wheel_roll`, `landing_settle`, `suspension`) sees what this clip really does.
- `build.py` adds only props or guards the path cannot express. The compiler keys the empty from
  `path.py` (Task 56).
- R4 time scale: product-scale drops and tosses use `timeScale` 0.3–0.5 (eng). This is the one place a
  clock is slowed, and never for weather.

**Shared motion rules.** Put them in `engine/motion_rules.py`, which the checker calls after the
motion-path gates. Register every code.

| code | severity | rule |
|---|---|---|
| `motion_needs_profile` (existing name; check at HEAD) | error → `unsupported` | `requiresProfile` fact absent or low confidence, e.g. roll without a high-confidence `rollAxis`. The pipeline moves the ask to `unsupported` with the block's plain reason (PHASING §3.6) |
| `motion_needs_ground` | error | a ground-contact motion (drop, roll, topple, slide, drive) in a `placement: "float"` script |
| `spin_rate_cap` | repaired | any rotation > 45 °/s at the peak is clamped (P-C11 cap) |
| `spin_needs_camera_move` | error | `plinth_spin` in a shot whose camera is a locked, constant-speed programme: the turntable negative control. At least one shot must move the camera |
| `motion_ends_unsettled` | repaired | a motion that `stops`/`lands` must reach rest ≥ 0.8 s before the clip ends (TG-06 hero stillness). Its start is shifted earlier, else its duration is shortened |
| `wheel_strobe` | repaired | drive only (Task 79) |
| `vehicle_speed_cap` | repaired | drive only (Task 79) |

Tests for each rule go in `engine/tests/test_motion_rules.py`, written first.

### Task 74: `drop_settle` (spec `drop_in`; bounces)

**Pure** `engine/blocks/motion/drop_settle/path.py`:

```python
"""Drop in from above and settle with analytic bounces (METHODS RB-01): heights h*e^(2n), restitution e,
air time from real gravity scaled by timeScale (R4), a small seeded tilt that returns to the rest pose
before the last contact. Ends in the ingest rest pose (placed z = 0)."""
import math

from engine.motion_path import SubjectPose

G = 9.81


def _plan(params, profile):
    h0 = params["heightFrac"] * profile.sizeM[2]
    e = params["restitution"]
    ts = params["timeScale"]
    hs = [h0] + [h0 * e ** (2 * k) for k in range(1, int(params["bounces"]) + 1)]
    fall = math.sqrt(2 * h0 / G) / ts
    arcs = [2 * math.sqrt(2 * h / G) / ts for h in hs[1:]]
    return hs, fall, arcs


def total_s(params, profile):
    _, fall, arcs = _plan(params, profile)
    return fall + sum(arcs)


def height(params, profile, t):
    hs, fall, arcs = _plan(params, profile)
    ts = params["timeScale"]
    t0 = params["startS"]
    u = t - t0
    if u <= 0:
        return hs[0]
    if u < fall:
        s = u * ts
        return max(0.0, hs[0] - 0.5 * G * s * s)
    u -= fall
    for h, a in zip(hs[1:], arcs):
        if u < a:
            s = (u - a / 2) * ts
            return max(0.0, h - 0.5 * G * s * s)
        u -= a
    return 0.0


def sample(params, profile, t, duration):
    tilt = params.get("tiltDeg", 0.0)
    end = params["startS"] + total_s(params, profile)
    k = 0.0 if t >= end else max(0.0, 1.0 - (t - params["startS"]) / max(1e-6, end - params["startS"]))
    return SubjectPose(offset=(0.0, 0.0, height(params, profile, t)), pitch=math.radians(tilt) * k)


def flags(params):
    return {"lands": True, "stops": True}
```

**Tests** `engine/tests/test_motion_drop.py` (the sneaker profile):
- the height at `startS` equals `heightFrac × h`;
- the first contact happens at `sqrt(2h/g)/timeScale` ± 1 frame;
- each bounce peak is `h·e^(2n)`;
- z ≥ 0 always;
- the subject is at rest after `total_s`, and the pitch is 0 there;
- `flags` makes `landing_settle` apply (the realism resolver lists it for the sneaker);
- `motion_ends_unsettled` shifts the start when `startS + total_s > duration − 0.8`.

**Manifest:** `heightFrac` 0.2–1.5 **0.6**; `bounces` 0–3 **1**; `restitution` 0.2–0.5 **0.35**;
`timeScale` 0.3–1 **0.5**; `startS` 0–8 **0.3**; `tiltDeg` 0–12 **4**. It has
`subjectMotion: {"lands": true, "stops": true}`, `physics.timeScaleParam: "timeScale"`,
`subjectSizeM: [0.02, 3.0]` (a car does not drop in), `capabilities: ["motion.drop"]`, and tags mood
[playful, premium], energy [medium, hype].

**Taste TG-36:** "Small products can arrive by drop-in: 0.4–0.8 of their height, one soft bounce,
slowed to 0.4–0.5 so the weight reads. The camera holds still or pushes gently during the landing."
Blocks: `motion/drop_settle.bounces`, `motion/drop_settle.timeScale`.

**Prompts:** `drop_bounce` "the sneaker drops in and bounces" (delivered, `motion.drop`);
`car_drop` "drop the car in from the sky" on `sports_car` (unsupported: size range; note "large
subjects don't drop in").

**Blender test:** the `valora_motion` z keys equal `height()` at 5 frames (Task 56 proves the generic
match; this test proves the bounce sequence), and `landing_settle`'s overshoot keys follow the last
contact.

Commit: `feat(motion): drop_settle with analytic bounces (spec drop_in)`.

---

### Task 75: `float_drift` and `plinth_spin`

**`float_drift`** (spec `hover_bob`, generalised, RB-08):
- z = `liftFrac·h + bobFrac·h·sin(2π f t + φ)` with f 0.2–0.5 Hz;
- yaw = `yawDegS · t`, where |yawDegS| ≤ 20 (eng; the P-C11 cap is 45);
- tiny pitch/roll noise ≤ 2°.
- `placement` must be `float` (the checker repairs `ground` → `float` with a `repaired` issue named
  `placement_for_motion`), so contact and ground realism turn off, as they already do for float.
- Flags `{}` (no translate, stop or land).
- Params: `liftFrac` 0.05–0.4 **0.15**; `bobFrac` 0.01–0.03 **0.02**; `bobHz` 0.2–0.5 **0.3**;
  `yawDegS` −20–20 **6**.
- `capabilities: ["motion.float"]`.

**`plinth_spin`** (the owner's "spin-on-plinth" seed):
- The subject turns on a visible plinth prop. The prop is a cylinder of radius 0.6 × the footprint
  diagonal and height 0.04 × longest, with a material matched to the world (studio: satin
  tone-matched; others: stone).
- The turn is **bounded**: `turnDeg` 30–180 **90**, eased (`in_out_cubic`), inside one window
  `[startS, startS + turnS]`, with a peak rate ≤ 45 °/s (`spin_rate_cap`).
- It is **never** a continuous loop. `spin_needs_camera_move` forbids a locked camera during the turn.
  This keeps the harness's `turntable` negative control distinct: a test asserts that no
  `plinth_spin` script can produce a constant-rate 360° loop at any params, and that
  `camera/turntable` stays unselectable.
- The plinth raises the subject: `placement` stays `ground` and the pose offset is the plinth height,
  so realism contact applies against the plinth top. Pass the plinth top as the contact plane; check
  `contact_ground`'s build for a plane-height input and add one if it is missing (tested).
- Flags `{"stops": true}`.
- `capabilities: ["motion.spin"]`, `subjectSizeM: [0.02, 2.5]`.

**Tests** `engine/tests/test_motion_float_spin.py`:
- float z stays within [lift − bob, lift + bob];
- the yaw rate ≤ 20 °/s;
- the spin peak rate ≤ 45 °/s;
- the total turn equals `turnDeg`;
- the rate is 0 outside the window;
- `spin_needs_camera_move` fires with a `turntable`-like fixture camera (use a fixture camera manifest
  with `constantSpeed: true`, since the real turntable is not selectable);
- a `placement: "ground"` float script is repaired to `float`.

**Taste TG-37:** "Floating is for tech and luxury small objects: slow bob, a few degrees of yaw per
second. A plinth spin is one eased quarter-to-half turn while the camera also moves. Never a full
constant spin (that is a T1 turntable)." Blocks: `motion/float_drift.yawDegS`,
`motion/plinth_spin.turnDeg`.

**Prompts:** `levitate` "levitating product shot" (delivered, `motion.float`); `spin_plinth` "spin it on
a pedestal" (delivered, `motion.spin`); `turntable_ask` "360 turntable" (delivered as a bounded plinth
spin, and the assumption line says "a slow partial turn replaces a full turntable"; add
`expectAssumption` if `director_eval` supports it, otherwise leave it to the honesty review).

Commit: `feat(motion): float_drift and bounded plinth_spin (never a turntable)`.

---

### Task 76: `slide_in`

The subject glides in along the ground from off-frame and stops with friction deceleration. It uses the
drive lane when the world has one, else a short in-set slide (≤ 0.2 × longest; the studio has
`driveLaneM` 0, so the only permitted travel is the swept bound allowance).

- **Path:** x(t) = d·(1 − (1 − τ)²) for τ = (t − start)/T on [0, 1] (constant deceleration), with
  heading along the slide.
- **Studio:** `distanceFrac` capped at 0.2 so `path_through_world` passes. **Outdoor worlds:** up to
  `driveLaneM`.
- Flags `{"translates": true, "stops": true}`. For wheeled subjects this means `wheel_roll` applies
  (the wheels turn as it slides; correct for a rolling stop).
- Params: `distanceFrac` 0.1–3 **0.6**; `durationS` 0.6–3 **1.4**; `startS` 0–8 **0.2**;
  `directionDeg` −180–180 **seeded**.
- `capabilities: ["motion.slide"]`. Add the vocabulary tag `motion.slide` (Task 85) with phrases
  `slid(?:e|es|ing) in`, `glid(?:e|es|ing) in`.

**Tests:** position continuity; velocity 0 at the end; ≤ 0.2 × longest travel in the studio (the
checker keeps it); a drive-lane cap outdoors; `motion_ends_unsettled`.

**Taste TG-38:** "A slide-in is a clean product entrance: short, decelerating to a crisp stop, then hold.
Enter across the frame, never toward the camera." Blocks: `motion/slide_in.durationS`.

**Prompts:** `slide_in` "product slides into frame" (delivered).

Commit: `feat(motion): slide_in with a friction stop`.

---

### Task 77: `roll` and `topple`

**`roll`** (RB-02):
- It needs `rollAxis` with high confidence (Task 55): `requiresProfile: ["rollAxis"]`.
- Rotation about that axis equals distance / `rollRadius`, with no slip. Travel is perpendicular to
  the axis and horizontal, with a rolling-resistance decay (eng speed × e^(−t/τ), τ 2 s).
- The subject starts with the axis horizontal (the placed pose already has it horizontal, or the
  capability is false).
- Params: `distanceFrac` 0.5–4 **1.5**; `direction` enum [left, **right**]; `startS` 0–6 **0.5**.
- Flags `{"translates": true, "stops": true}`.
- `path_through_world` applies.
- Tests: the angle × radius equals the distance at every sample (slip < 1%); the subject stops; a box
  profile is blocked with `motion_needs_profile`, and the pipeline reports `motion.roll` unsupported
  with the note "this shape can't roll convincingly" (PHASING §3.6).

**`topple`** (RB-03):
- It needs `supportPolygon` (≥ 3 points).
- It pivots about the support-polygon edge nearest the `direction`. The angle follows a
  gravity-driven pendulum inverted to the fall (analytic, eng) until the subject lands on its side.
  The **landing pose** is the principal-axis pose with the longest axis horizontal, found by rotating
  about the edge until the centroid height is minimal.
- `rock: true` adds a 1–2 rock settle.
- Only subjects with aspect (height / min footprint) ≥ 1.3 topple convincingly; below that,
  `motion_needs_profile` with the note "this shape is too squat to tip over".
- Flags `{"stops": true, "lands": true}`.
- Tests: the pivot edge stays on the ground (the pivot's z = 0 at every sample); the final pose is at
  rest; the watch profile is blocked (squat) and the helmet or a synthetic bottle is allowed.

**Taste TG-39:** "Rolls and topples are playful entrances for round or tall products; they end in a
held rest, then the camera finds the hero angle." Blocks: `motion/roll.distanceFrac`,
`motion/topple.rock`.

**Prompts:** `roll_in` "the can rolls in" (delivered where a roll axis exists; use a synthetic can
profile fixture, `engine/tests/fixtures/profiles/can.json`, generated by the shape-test cylinder
helper with a written material list). `roll_chair` "the chair rolls across" (unsupported).
`topple` "it tips over" (delivered on the bottle fixture; unsupported on the watch).

Commit: `feat(motion): roll and topple from shape facts, honest when the shape can't`.

---

### Task 78: `toss_tumble`

RB-04:
- A ballistic arc (apex `arcHeightFrac` × h) with its time scaled by `timeScale`.
- Spin about the principal axis of max or min inertia (a stable axis: the first or last
  `principal_axes` vector). Never the intermediate axis, which reads as Dzhanibekov noise; that
  exception is only for flat thin objects, deferred.
- `spins` 0.5–3 **1**, with the landing orientation equal to the rest pose.
- Lands with `landing_settle`.
- Travel runs across the frame from `direction`.
- Params: `arcHeightFrac` 0.5–3 **1.2**; `spins` 0.5–3 **1**; `timeScale` 0.3–1 **0.45**;
  `startS` 0–6 **0.4**; `direction` enum [left, **right**].
- Flags `{"translates": true, "lands": true, "stops": true}`.
- `subjectSizeM: [0.02, 1.5]`.
- `spin_rate_cap` applies (peak ≤ 45 °/s after time scale; a clamp lowers `spins`).
- Tests: the apex height; the landing at rest pose (orientation error < 1°); the spin axis equals a
  stable principal axis; z ≥ 0; `spin_rate_cap` lowers `spins` when needed.

**Taste TG-40:** "Toss-and-tumble is high energy: hype pace, one clean spin, slowed to 0.4–0.5, landing
into a hold." Blocks: `motion/toss_tumble.spins`.

**Prompts:** `toss` "toss the sneaker into frame" (delivered); `toss_car` (unsupported, size).

Commit: `feat(motion): toss_tumble about a stable principal axis`.

---

### Task 79: `drive` (the hand-off H5 contract)

**Pure** `engine/blocks/motion/drive/path.py` holds the path geometry and speed profile:
- `path` enum [**straight**, arc_left, arc_right, s_curve, stop];
- `accel` enum [**cruise**, launch, brake_to_stop];
- `speedKmh` 5–120 **40**.

The rules:
- **Heading comes from the path tangent**, never from the sign of ingest `forwardAxis` (H5). The
  subject's long axis is aligned to the tangent. **Which end leads** is `nose_sign(profile)` (Task 55),
  and `facing` [**auto**, forward, reverse] can override it.
- When `nose_sign` confidence is low and `facing` is auto, the drive is restricted to a **side
  pass-by**: `straight`, with cameras kept on the side, so the nose ambiguity is not visible. The
  issue `vehicle_nose_uncertain` (info) records it.
- Arcs: curvature κ = 1/R, with R ≥ 3 × wheelbase (eng). The arc length follows the speed profile.
- Speed profiles: cruise is constant; launch ramps 0 → v over 2 s (eng 0.3 g); brake_to_stop ramps
  v → 0 at 0.6 g (eng) and ends ≥ 0.8 s before the clip ends.
- `flags(params)`: `{"translates": true, "stops": accel == "brake_to_stop" or path == "stop"}`.
- Pitch and roll come from `suspension`, not from the drive path.

**Realism side (H5)**, in `engine/physics/wheel_spin.py` and `engine/physics/suspension.py`:
- **Curvature-aware slip.** Add `wheel_angles_contact(contact_pos, axle_world_by_frame, radius)`. It
  integrates each wheel's **own contact-point path** (subject pose × wheel contact in placed space),
  so on an arc the inner and outer wheels turn different amounts. Add `slip_curved(angles,
  contact_pos, radius)`, where the per-wheel path length is the sum of the contact displacements.
  `wheel_roll/build.py` switches to the contact-point form when the motion's path is not straight.
  Tests: on an arc of R = 10 m with track 1.6 m, the outer/inner angle ratio is
  (R + 0.8)/(R − 0.8) ± 1%, and slip < 1% on every wheel. The existing straight-line tests stay green.
- **`rollDegPerG`** param on `suspension` (0.5–7, default by `vehicleClass`: sport 2, comfort 5,
  offroad 6, toy 0; eng from METHODS VD-04/05). Body roll = `rollDegPerG × a_lat/g` with
  a_lat = v²κ, lagged by 0.15 s (first-order, eng), leaning **out of** the turn. Test the sign: on an
  arc_left, the body rolls to the right, i.e. the positive local-X side goes down. Pitch on
  brake/launch uses the existing `pitch_after_stop` / `PITCH_DEG_PER_G`.
- **Strobe guard** (vehicles.md V-M01) is a checker repair `wheel_strobe`. Take the wheel rate
  ω = v/r, and for spoke counts n ∈ {5, 6, 7, 10} (eng; the spoke count is unknown) check
  `frac(n·ω/(2π·fps))` in [0, 0.1] ∪ [0.9, 1]. If any n hits and the shutter is < 0.5, nudge
  `speedKmh` by ±3% steps (max ±9%) to the nearest clear speed; else keep it and record info. Tests:
  a speed that strobes for 5 spokes at 30 fps is nudged; a clear one is untouched.
- **`vehicle_speed_cap`** repair:
  - `speedKmh` ≤ what the world's `driveLaneM` allows for the clip's drive window (distance =
    ∫v dt ≤ lane);
  - the camera angular rate ≤ 80 °/s (T3-14): for anchor cameras, sample the subject's bearing rate
    from the camera, and lower `speedKmh` until it passes. `rolling_track` is exempt, because it
    follows.
- `wheel_roll` already `appliesWhen motion translates`, so flags make it apply. `suspension` applies
  on wheels + body separable. `tyre_contact` stays static per wheel (a patch at z = 0 each frame is
  stateless with the pose).

**Manifest:** as above, plus `requiresProfile: ["wheels"]`, `subjectSizeM: [0.1, 8.0]`,
`capabilities: ["motion.drive"]`, `physics.taxonomy: ["VD-02","VD-03","VD-04","VD-05","VD-06"]`, and
tags mood [cinematic, hype, night], energy [medium, hype]. It is allowed only in worlds with
`driveLaneM > 0`; the studio has 0, so `path_through_world` rejects drive in the studio, and the
pipeline reports the ask as unsupported with the note "driving needs a street, courtyard or field; the
studio video keeps the car parked".

**Coupling to weather (report only in phase 5):** a wet world or rain plus drive would want tyre spray
(VD-12), which is phase 6. So the checker adds an `unsupported` line "Road spray isn't available yet;
the car drives through the wet without spray" when the prompt did not ask for spray. That is an
**info** issue plus an assumption line, never an error, so the render proceeds.

**Tests** `engine/tests/test_motion_drive.py`:
- heading = the path tangent at every sample;
- an s_curve has continuous heading;
- brake_to_stop ends at rest ≥ 0.8 s before the end;
- the speed never exceeds the cap;
- low nose confidence forces a straight side pass-by;
- `flags` per params;
- the realism resolver lists `wheel_roll` and `suspension` on `sports_car`;
- the `toycar` (vehicleClass toy) gets roll 0.

**Blender test** (`sports_car`, `night_street`, arc_left, 40 km/h):
- the probe's wheel verts show contact-point slip < 2% per wheel (the existing `wheel_roll_no_slip`,
  extended to arcs);
- the body roll sign is correct at the arc apex;
- the tyre patch is present every key frame (`tyre_patch_present`).

**Taste TG-41:** "Cars drive with intent: a straight pass or a gentle arc at 30–60 km/h on a street,
courtyard or field, framed by rolling_track or a low anchor camera the car passes. Brake to a stop and
hold for the hero. Never drive in the studio." Blocks: `motion/drive.speedKmh`, `motion/drive.path`.

**Prompts:**
- `drive` "make the car drive" changes from unsupported to `expectDelivered: ["motion.drive"]` on
  `sports_car`/`toycar`.
- `drive_studio` "drive it around the white studio" (unsupported: studio).
- `drive_watch` "make the watch drive" (unsupported: no wheels; the note "we couldn't find wheels on
  this model").
- `night_drive` "night drive through the rain" (delivered: drive + night_street + rain).

**Look-check `[render ≤ 3]`:** 2 frames (the arc apex, and the braking dive frame).

Commit: `feat(motion): drive with path heading, curvature-aware slip, body roll and strobe guard (H5)`.

**Chunk 5 gate:** full suite green, frozen baseline 90/90, growth contract green for 8 motions.

---

## Chunk 6: The remaining v1 cameras, plus the tracking camera

Start with the re-rank checkpoint. Every camera is a pure `path.py`
(`sample(params, profile, u, target=None) -> Pose`), keyframed by the compiler with real motion blur.
Each one declares:
- `framing` (full | detail);
- `move` (the T3-11 primitive);
- `follows` (anchor | subject);
- `constantSpeed` (false for all of these);
- `tierMax: "T3"`.

The checker's distance repair, clearance and coverage run unchanged, because they call `sample`. Every
path is tested at `u ∈ {0, 0.5, 1}` with exact expected positions from its formula, and every camera is
tested for:
- the 80 °/s bearing cap (T3-14) at default params over a 3 s shot;
- the easing (the velocity is 0 at u = 0 and u = 1 when `settleFrac > 0`);
- the hook rule (a `framing: full` camera can open, so `axes._opener_ok`; a detail one cannot).

`macro_slide` from the spec list is **already** `macro_detail` (slideFrac). It gets a vocabulary alias
only, and no block.

### Task 80: `reveal_rise` (crane rise, CATALOG-GAPS rank 12)

- Start low and tight on a detail height (`startHeightFrac` 0.05–0.4 **0.15**, at
  `startDistance` × radius). Hold `holdFrac` 0–0.3 **0.2** of the shot, then rise to `endHeightFrac`
  0.4–1.5 **0.9** while pulling back to `endDistance`, with ease-out-quad (P-C07: hold 0.7 s, rise
  2.7–4.3 s).
- `framing: full` (it ends on the whole subject), `move: "crane"`.
- Opener-eligible? No. The first 20% is not full-frame. `_opener_ok` requires full framing at u = 0,
  so add a manifest key `"hookable": false` and check it in `_opener_ok`. Test that the axes never
  offer it as an opener.

**Tests:** z is monotone after the hold; the subject is fully in frame at u = 1 (checker
`frame_stats`); the hold is honoured.

**Taste TG-42:** "reveal_rise lands a middle or final shot: it starts on a detail and rises to the whole
subject. Use it once. Good after a drop-in or at the end of a slide." Blocks:
`camera/reveal_rise.holdFrac`.

**Prompts:** `crane_reveal` "rising crane reveal" (delivered, `camera.crane`; add the vocabulary tag in
Task 85).

---

### Task 81: `dutch_hero`

- The low hero push (reuse the `low_hero_push` maths by importing its `sample`) plus a camera roll of
  `rollDeg` 6–20 **12** (sign seeded by `ctx`? No: it is a **param**, `rollSide` enum [left, **right**],
  so replay is exact).
- `framing: full`, `move: "dolly"`.
- The roll changes the frame's footprint, so the checker's `frame_stats` must account for camera roll.
  Check whether `Pose` carries roll and whether `project` uses it. If not, add `roll` to `Pose`
  (default 0) and rotate NDC by −roll in `project`, with a test that a 90° roll swaps the footprint
  width and height. Existing cameras have roll 0, so nothing changes (the frozen baseline gate proves
  it).
- The compiler applies `rotation_euler` roll about the view axis.
- `maxPerClip: 1` (the shared rule counts cameras too; extend `effect_max_per_clip` to a generic
  `block_max_per_clip`, or add `camera_max_per_clip`, and register it).

**Taste TG-43:** "A dutch angle is a hype accent: one shot, 8–15 degrees, never the opener or the hero
landing." Blocks: `camera/dutch_hero.rollDeg`.

**Prompts:** `dutch` "tilted dramatic angle" (delivered, `camera.dutch`).

---

### Task 82: `handheld_operator` (port of `film_camera._operate`)

**Source:** `film_camera.py` `_operate()` (≈ :180–334): walking pace, footfalls, sway and aim lag;
`_wander` (≈ :88), `_bezier` (≈ :100), `_smooth` (≈ :104). The five car-specific shots (`_shots`,
`anchors` by wheel and lamp mesh names) are **not** ported. The operator moves along a base path
(`path` enum [**walk_arc**, walk_in, stand]) around the subject.

**Pure** `engine/blocks/camera/handheld_operator/path.py`:
- Base position on an arc at `distance` × radius, height `heightFrac`.
- Footfall bob: vertical 4–12 mm at the step rate 1.6–2.0 Hz (eng) when walking.
- Sway and aim lag: `_wander`-style seeded smooth noise with amplitude `shake` 0–1 **0.35**, mapped
  to ≤ 1.5° rotation and ≤ 2 cm translation at 1 m scale (METHODS R5: scale translation with
  subject radius, clamp rotation).
- The noise is a **pure function of (seed, u)**: a sum of sines with seeded phases, so replay and farm
  splits are exact (no stateful filter).
- The seed comes in through params: `noiseSeed` int 0–65535, which layer 1 varies (Task 89). The
  script stays the full description.

**Tests:** same `noiseSeed` gives the same path; the shake amplitude bound holds; the footfall frequency
peak (a DFT of z on 256 samples) lies within the step rate; the bearing rate cap holds; `shake 0` +
`stand` gives a still camera.

**Taste TG-44:** "Handheld gives life to street and courtyard scenes: shake 0.2–0.4, walk around the
subject. Not for clean studio product shots, and never with a dutch shot in the same clip." Blocks:
`camera/handheld_operator.shake`.

**Prompts:** `handheld` "handheld documentary feel" (delivered, `camera.handheld`, a tag that exists).

---

### Task 83: `profile_slide` (CATALOG-GAPS rank 13)

- A lateral truck at a 90° profile (or `angleDeg` 60–120 **90** from the long axis), travel
  `slideFrac` 0.1–0.6 **0.3** of the subject length.
- Optional `foreground` bool **false**: an out-of-focus foreground occluder card at 0.3 × the camera
  distance, travelling at ≥ 2× parallax (F-C08). It is taken from the world's prop list when the world
  has props (a bench, a lamp post or grass tufts) and is omitted in the studio.
- `framing: full`, `move: "truck"`.

**Tests:** the camera moves parallel to the long axis; the angle is preserved; the foreground card
(when present) sits between the camera and the subject for every u, and never inside the bounds +
margin.

**Taste TG-45:** "Side slides show a vehicle's or product's silhouette; add a foreground layer outdoors
for depth." Blocks: `camera/profile_slide.foreground`.

**Prompts:** `side_slide` "side profile slide" (delivered, `camera.slide`).

---

### Task 84: `rolling_track` (camera-car, CATALOG-GAPS rank 5)

- `follows: "subject"`: the camera is solved against the live subject pose (Task 56).
- `mode` enum [**side**, lead, tail, flyby]:
  - side / lead / tail sit at a fixed offset in the subject's heading frame (distance × radius,
    height `heightFrac`), with 0.1–0.3 s lag smoothing done analytically (the camera targets the pose
    at t − lag);
  - flyby: the camera is anchored and the subject passes, with the closest approach at `passU`
    0.3–0.7 **0.5**.
- `shutter` note: vehicles look right at 0.5–0.75. The compiler's shutter is set by the tier, so record
  the need and do not add a param in phase 5.
- **Requires a translating motion:** the manifest key `requiresMotion: ["translates"]`, checked by the
  checker (new code `camera_needs_motion`, error). A static subject keeps anchor cameras.
- The subject stays in frame by construction for side/lead/tail; the checker still verifies it.
- Camera shake coupling (VD-06) is phase 7 or later; record it.

**Tests:** with the drive fixture, the side-mode camera stays at a constant offset in the heading frame
(± lag); the flyby's closest approach happens at `passU`; `camera_needs_motion` fires on a static
script; the checker coverage passes at every sample on `sports_car` at 40 km/h.

**Taste TG-46:** "Driving is shot from a tracking car: side for speed, lead for the face, tail for the
chase, flyby for impact. Pair with drive; one flyby per clip." Blocks: `camera/rolling_track.mode`.

**Prompts:** `tracking_shot` "tracking shot alongside the car" (delivered on `sports_car` with drive;
`camera.tracking` tag in Task 85); `tracking_static` "tracking shot of the parked watch" (unsupported:
the note "a tracking camera needs the subject to move; the camera orbits instead").

**Chunk 6 gate:** full suite green, frozen baseline 90/90, growth contract green for the five cameras.
The turntable test still proves that `camera/turntable` is not selectable and never an opener.

---

## Chunk 7: Director integration: vocabulary, rulebook, dice unlock, fallback, details

Start with the re-rank checkpoint. **Re-read** `adherence.py`, `dice.py`, `fallback.py`, `pipeline.py`,
`sanitize.py` and `details.py` before editing. The phase-4 lane may have moved them.

### Task 85: Vocabulary, capabilities and honest notes

**Files:** `engine/director/vocabulary.json`, `engine/director/capabilities.py` (only if the note
selection needs a world or profile reason), `engine/tests/test_capabilities.py`.

- [ ] **Step 1: Write the failing tests** (append to `engine/tests/test_capabilities.py`):

```python
import pytest

from engine.catalog import Catalog
from engine.director.capabilities import detect, unsupported
from engine.tests.test_director_package import _p


@pytest.mark.parametrize("text,tag", [
    ("light drizzle", "weather.rain"), ("a downpour", "weather.rain"), ("after the rain", "surface.wet"),
    ("puddles", "surface.wet"), ("misty morning", "atmosphere.fog"), ("snowy", "weather.snow"),
    ("slides in", "motion.slide"), ("rising crane reveal", "camera.crane"), ("dutch angle", "camera.dutch"),
    ("tracking shot", "camera.tracking"), ("side profile slide", "camera.slide"), ("spin it on a pedestal", "motion.spin"),
    ("golden hour", "world.nature"), ("neon street", "world.street")])
def test_new_phrases_detect(text, tag):
    assert tag in {a["capability"] for a in detect(text)}


@pytest.mark.parametrize("text,not_tag", [("rolling fog", "motion.roll"), ("falling leaves", "motion.drop"),
                                          ("snow white backdrop", "weather.snow"), ("rain-free", "weather.rain")])
def test_phrase_collisions(text, not_tag):
    assert not_tag not in {a["capability"] for a in detect(text)}


def test_rain_is_delivered_outdoors_and_honest_in_the_studio():
    cat, p = Catalog.load(), _p("sports_car")
    asks = detect("rain")
    studio = {"world": {"id": "studio_cyc"}, "effects": [], "subject": {"placement": "ground", "motion": {"id": "static"}}}
    out = unsupported(asks, cat, p, script=studio)   # extend the signature only if HEAD lacks a script arg
    assert out and "outdoor" in out[0]["note"].lower()
```

  "snow white backdrop" must not trigger snow: add a negative look-ahead `snow(?!\s*white)` or list
  "snow white" as a negating phrase. Decide in the test. "Falling leaves" must not trigger
  `motion.drop` (BLOCKS §4 collision list: a negative look-ahead on `leaves|petals|snow|rain`).
- [ ] **Step 2: Run them.** Expected: several FAIL.
- [ ] **Step 3: Update `vocabulary.json`:**
  - **New tags** (with phrases and notes): `motion.slide`, `camera.crane`, `camera.dutch`,
    `camera.tracking`, `camera.slide`, `world.street` phrases (add `neon street|city street|downtown`),
    and `world.nature` (add `golden hour|field|meadow|wheat`).
  - **Weather phrases:** `weather.rain` gains `drizzl(?:e|y|ing)`, `downpour`, `pouring rain`;
    `surface.wet` keeps its list; `atmosphere.fog` gains `mist(?:y)?`, `haz(?:e|y) morning`;
    `weather.snow` gains `winter(?:y)?`, `blizzard`.
  - **Aliases:** `camera.macro` gains `macro slide` (it is `macro_detail`).
  - **Notes for world-blocked asks** (used when a capability exists in the catalog but the pinned or
    chosen world blocks it, e.g. rain in the studio): `weather.rain` "Rain needs an outdoor world; the
    studio video stays dry." Do the same for snow, wet, fog, drive and tracking (the last one's note is
    "a tracking camera needs the subject to move").
  - **Partial-support notes (PHASING §3.3):** `liquid.run_down` "Water running down surfaces isn't
    available yet; the subject has still droplets instead" when droplets are in the script.
    `vehicle.spray` "Road spray isn't available yet; the car drives through the wet without spray."
- [ ] **Step 4:** Make `unsupported()` pick the world-blocked note when a block providing the tag
  exists but `effect_needs_world` / `path_through_world` / `camera_needs_motion` fired. The pipeline
  already maps checker errors to unsupported (PHASING §3.6). Confirm the wiring in `pipeline.py` and
  extend the code list it maps from with `effect_needs_world`, `effect_needs_profile`,
  `motion_needs_profile`, `motion_needs_ground`, `camera_needs_motion`, `effect_needs_source` and
  `path_through_world`. Test each: a script with that error ends as an `unsupported` entry (not a
  failed job) with the block's note, and the video renders without the block.
- [ ] **Step 5: Run** `engine/tests/test_capabilities.py`, `engine/tests/test_director_pipeline.py` and
  the frozen baseline gate.
- [ ] **Step 6: Commit** `feat(director): phase-5 vocabulary, phrase collisions, world-blocked and
  partial-support notes`.

---

### Task 86: Rulebook, output schema and menu for the grown catalog

- [ ] **Step 1: Output schema.** `LIST_FIELDS["effects"]` enumerates effect ids from the catalog
  automatically. Confirm that the new motion, camera and world ids appear. Schema size: the phase-3
  plan has a `schema_too_complex` fallback, so measure the schema's JSON length before and after,
  record both in the register, and run the existing schema-complexity test. If the new schema exceeds
  the provider limit the phase-3 lane recorded, use the compact-ref helper (`_compact_ref`) for motion
  and camera params, as it already does for other kinds.
- [ ] **Step 2: Menu.** Regenerate `rulebook/rulebook.txt`. Test that every growth-contract block
  appears in the menu with its description and ranges (`test_director_rulebook.py`: a new
  parametrized case over `catalog_growth.json`).
- [ ] **Step 3: Taste guide ordering.** The taste rules TG-24..TG-46 were added per task. Now check
  `validate_rules` passes on all of them, and that the rulebook renders `family: any` first, then per
  family (existing behaviour). Add a test that the rulebook's taste section stays under the length
  budget the phase-3 plan set (find the constant in `rulebook.py`; if there is none, record the length
  in the register).
- [ ] **Step 4: Empty-prompt default text.** It now mentions that worlds, weather and wind come from
  the direction card. Update the default text in `rulebook.py`, keeping its existing structure.
- [ ] **Step 5: Run** the director rulebook, output schema and menu tests plus the frozen baseline gate.
- [ ] **Step 6: Commit** `feat(director): rulebook and schema cover the grown catalog`.

---

### Task 87: Dice unlock: weather and wind through the floor

**Files:** `engine/director/dice.json`, `engine/director/axes.py`, `engine/director/dice.py` (only if the
viable-pool code needs the weather-world pairing), `engine/director/adherence.py`,
`engine/director/pins.py` + `dice.json["pins"]`, `engine/director/floor.py` (viability includes the
package), tests `engine/tests/test_director_weather_axes.py`.

- [ ] **Step 1: Write the failing tests** `engine/tests/test_director_weather_axes.py`:

```python
import json

from engine.catalog import Catalog
from engine.director.axes import DICE, axis_values, compatible, weather_package, wind_speed
from engine.director.floor import make_viable
from engine.director.job import make_job
from engine.director.pins import read_direction_pins
from engine.tests.test_director_package import _p

FMT = {"aspect": "9:16", "durationS": 10, "fps": 30}


def test_weather_and_wind_are_now_rollable():
    v = axis_values(_p("sports_car"), Catalog.load(), FMT)
    assert set(v["weather"]) == {"dry", "wet", "rain", "snow", "fog"} and set(v["wind"]) == {"calm", "breeze", "windy"}


def test_weather_must_suit_the_world():
    assert not compatible({"world": "studio_cyc", "weather": "rain", "mood": "clean", "tone": "grey", "wind": "calm"})
    assert compatible({"world": "night_street", "weather": "rain", "mood": "teal_night", "tone": "na", "wind": "breeze"})
    assert not compatible({"world": "golden_field", "weather": "rain", "mood": "warm_golden", "tone": "na", "wind": "calm"})
    assert not compatible({"world": "night_street", "weather": "fog", "mood": "teal_night", "tone": "na", "wind": "windy"})


def test_packages_map_to_effects():
    assert weather_package("dry") == []
    assert [e["id"] for e in weather_package("rain")] == ["rain"]          # the checker couples wet+droplets
    assert [e["id"] for e in weather_package("wet")] == ["wet_surface"]
    assert [e["id"] for e in weather_package("fog")] == ["ground_fog"]


def test_wind_speed_mapping_calm_is_the_world_default():
    cat = Catalog.load()
    assert wind_speed("calm", cat.get("world", "golden_field"), seed=1) == 0.8
    assert 2.5 <= wind_speed("breeze", cat.get("world", "golden_field"), seed=1) <= 5.0
    assert 7.0 <= wind_speed("windy", cat.get("world", "golden_field"), seed=1) <= 11.0


def test_weather_pins_are_negation_aware():
    assert read_direction_pins("rainy night")["weather"] == "rain"
    assert read_direction_pins("no rain, sunny")["weather"] == "dry"
    assert read_direction_pins("after the rain")["weather"] == "wet"
    assert read_direction_pins("light drizzle")["weather"] == "rain"


def test_every_viable_weather_direction_meets_the_floor():
    cat, p = Catalog.load(), _p("sports_car")
    job = make_job("", p, cat, seed=0)
    for d in make_viable(job, p, cat)[:40]:                 # adapt to make_viable's real return shape
        assert d.weather == "dry" or d.world != "studio_cyc"
```

  Check `make_viable`'s real signature and return type at HEAD (phase-4 Task 41: lazy viability). Adapt
  the last test to iterate its ranked candidates.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Edit `dice.json`:**

```jsonc
"weather": {"values": ["dry", "wet", "rain", "snow", "fog"], "rollable": ["dry", "wet", "rain", "snow", "fog"]},
"wind":    {"values": ["calm", "breeze", "windy"], "rollable": ["calm", "breeze", "windy"]},
"weatherPackages": {"dry": [], "wet": [{"id": "wet_surface", "params": {"ripples": "off"}}],
                    "rain": [{"id": "rain", "params": {}}], "snow": [{"id": "snow", "params": {}}],
                    "fog": [{"id": "ground_fog", "params": {}}]},
"windSpeeds": {"calm": "world", "breeze": [2.5, 5.0], "windy": [7.0, 11.0]},
"implausible": [{"weather": "fog", "wind": "windy"}],
"weatherWeights": {"dry": 3, "wet": 1.5, "rain": 1.5, "fog": 1, "snow": 0.7}
```

  The weights are (eng) and go in the register; the corpus replaces them when trusted.
  `rain` intensity is left to layer 1 / TG-28 (by mood and pace), never rolled as an axis.
- [ ] **Step 4: `axes.py`:**
  - `compatible(axes)` adds three rules: the weather must be in `world.weathers` (read the world
    manifest through a module-level catalog accessor, or pass `catalog=`; prefer an explicit argument,
    and update the phase-4 call sites in `dice.py`); no `implausible` pair; the tone rule per world
    (Task 73).
  - Add `weather_package(value)` and `wind_speed(value, world_manifest, seed)` (seeded uniform inside
    the band, rounded to 0.1).
  - Update the module docstring: weather and wind now come from dice.json **∩ each world's
    `weathers`**.
- [ ] **Step 5: Adherence.** `enforce_direction` (vague prompts) inserts the rolled package's effects
  that are missing: effects are data, so this is a deterministic insert, like the grade swap. It sets
  `script["wind"] = {"id": "wind", "params": {"speedMs": wind_speed(...)}}` with `pinned: ["speedMs"]`
  when the rolled wind is not calm and the script's wind is unset. Both are repairs with codes
  `direction_weather_applied` / `direction_wind_applied` (register them). On long prompts only pinned
  weather and wind are enforced; anything else is measured drift (`info`), as in phase 4.
- [ ] **Step 6: Pins.** Add `weather` and `wind` pin phrase lists to `dice.json["pins"]`:
  - weather rain: `rain(?:y|ing)?`, `drizzl…`, `downpour`, `storm(?:y)?`;
  - wet: `after (?:the )?rain`, `wet (?:street|ground|road)`, `puddles?`;
  - snow: `snow(?:y|ing)?(?!\s*white)`, `winter(?:y)?`, `blizzard`;
  - fog: `fog(?:gy)?`, `mist(?:y)?`;
  - dry: `sunny`, `dry`, `clear (?:day|sky)`, `no rain`;
  - wind breeze: `breez…`, `wind(?:y)?`; windy: `strong wind`, `gale`, `storm(?:y)?`.

  `read_direction_pins` handles them with the existing negation logic ("no rain" → pin `dry`; test it).
  A weather pin also implies a world when the pinned world cannot host it: `rain` + no world pin →
  the dice pick among worlds whose `weathers` contain rain (the pool filter does this), never the
  studio.
- [ ] **Step 7: Floor and viability.** `make_viable` builds the direction's fallback **with the
  package** (Task 88 makes the fallback apply it) and requires the checker pass plus the floor. Record
  the viable count per subject before and after, like phase 4 Task 41 Step 6, in the register: this
  is spec §6's honest limit becoming bigger. Expected: the counts grow by at least ×3 for vehicles.
- [ ] **Step 8: Run** the new tests, `engine/tests/test_director_{dice,axes,pins,floor,adherence,variety}.py`,
  the full suite and the frozen baseline gate (90/90: the interim direction is still `dry`/`calm` and
  writes nothing).
- [ ] **Step 9: Commit** `feat(director): weather and wind roll through world compatibility and the
  quality floor`.

---

### Task 88: Fallback scripts for the grown catalog

The fallback (refusing provider) must produce a finished T3 script for any viable direction.

**Changes in `engine/director/fallback.py`** (anchor on `_world`, `_script` and `slot_camera`):
- `_world(direction, details)` returns world params for every world: `timeOfDay` from the world's
  `timeOfDay.values` (layer 1 picks the value when details are on; otherwise the manifest default), and
  `tone` only for worlds with a `toneParam` (Task 73).
- Lighting comes from `allowed_lighting(world)` (Task 72), with gloss logic (TG-08) preserved for the
  studio exactly as today (frozen baseline).
- Weather: `weather_package(direction.weather)` appended to the effects. The checker then adds the
  couplings.
- Wind: calm = nothing written (the resolver defaults it); otherwise the Task 87 mapping.
- Motion: the fallback **never invents motion** on vague prompts, which stay static. It honours a
  *detected* motion ask (`motion.*` capability in the job's asks) when the catalog block's
  `requiresProfile`/world allow it, picking a pace-matched default:
  - drive: `straight`, 40 km/h, `rolling_track side` as a middle shot plus an anchor low hero for the
    landing;
  - drop_settle: at 0.3 s, then the camera holds;
  - float_drift: `placement: float`;
  - plinth_spin: in the second shot, with a moving camera.

  An ask that cannot be honoured goes to `unsupported` (Task 85 notes).
- Camera slots: `slot_camera` gains `reveal_rise` (the last middle shot when pace is calm),
  `profile_slide` (a middle shot for vehicles in outdoor worlds), `handheld_operator` (outdoor worlds,
  medium or hype pace, one shot) and `dutch_hero` (hype only, at most one). Each is added only where
  TG-42..46 say so, and **never** for `studio_cyc` directions. That keeps every studio fallback
  byte-identical to phase 4, which the frozen baseline gate and the phase-4 fallback tests prove.

**Tests** `engine/tests/test_director_fallback_phase5.py`:
- For each new world × each eval family (vehicle `sports_car`, product `pocket_watch`, furniture
  `mid_century_lounge_chair`, character `cesium_man`), the fallback passes the checker and
  `script_tier == "T3"` or the world is not viable for that subject (and `make_viable` agrees).
- Rain/snow/fog/wet packages are present and coupled.
- A drive ask on `sports_car` in `night_street` has a `rolling_track` shot and ends settled.
- Studio directions produce exactly the phase-4 scripts: compare to fixtures captured **before** this
  task. Add them in Step 1 by running today's fallback for 5 seeds × 3 subjects and saving the JSON in
  `engine/tests/fixtures/director/fallback_phase4/`.

Commit: `feat(director): fallback scripts for new worlds, weather, motions and cameras; studio unchanged`.

---

### Task 89: Layer 1 details for the new params

`dice.json["detailParams"]` gains taste windows for the new blocks' look params. Only params that
**do not change how fast a move runs** are varied on LLM scripts; motion timings are `timed: true`
(fallback only, phase-4 rule).

| param | rule | why |
|---|---|---|
| `world/night_street.neonHue` | `{"lo": 180, "hi": 330}` | TG-33 palette window |
| `world/night_street.windowsLit` | `{"pm": 0.15}` | set dressing |
| `world/golden_field.sunAzimuthDeg` | `{"pm": 35}` around the hero back-light azimuth | TG-34 rim |
| `world/golden_field.timeOfDay`, `world/night_street.timeOfDay` | enum pick among the world's `timeOfDay.values`, excluding `overcast` unless the mood is `clean` | layer-1 enum support: add `{"choice": true}` to `rule_value` if it does not exist, with a test |
| `effect/rain.intensity` | `{"choice": true, "byMood": {...}}` drizzle for calm moods, steady for most, downpour only for hype pace | TG-28 |
| `effect/ground_fog.heightM` | `{"lo": 0.3, "hi": 0.6}` | TG-25 |
| `field/wind.directionDeg` | `{"pm": 60}` around a back-to-front wind relative to the hero camera | wind reads in rain/grass when it crosses the frame |
| `camera/handheld_operator.noiseSeed` | `{"choice": true}` over 0–65535 | a new operator walk per seed |
| `grade/mood_grade.grain` | `{"lo": 0.15, "hi": 0.35}` except the `clean` preset | TG-26 (after the Task 61 look-check only) |

**Tests** (`engine/tests/test_director_details.py`, appended):
- every new rule stays inside the catalog range;
- the same seed gives the same values;
- a script-set value is kept;
- `--hold-direction` script distance grows: record it in the register, measured like the phase-4
  register row, on the same 3 models × 4 prompts × 5 runs;
- the frozen baseline gate stays 90/90, because the phase-3 default has details off.

Commit: `feat(director): layer-1 detail windows for new worlds, weather, wind and handheld`.

**Chunk 7 gate:** full suite green, frozen baseline 90/90, `py -m harness variety` (offline) shows
0 tier regressions and 0 exact repeats where the viable pool ≥ 5.

---

## Chunk 8: Harness, look-check command, finish

### Task 90: Eval harness: delivered recall, exercises, and the unsupported-ask sweep

Individual block tasks already added their prompts. This task makes the harness score them.

**Files:** `harness/director_eval.py`, `harness/prompts/v1.json` (note text), `harness/tests/test_director_eval_phase5.py`.

- [ ] **Step 1: Write the failing tests:**

```python
from harness.director_eval import expected_delivered, run_eval_offline   # adapt names at HEAD


def test_expect_delivered_is_scored_as_recall():
    case = {"id": "x", "prompt": "rainy night", "expectDelivered": ["weather.rain"]}
    m = run_eval_offline([case], models=["sports_car"], seeds=[0])[0]
    assert m["deliveredRecall"] == 1.0


def test_unsupported_and_delivered_never_overlap():
    import json
    from pathlib import Path
    doc = json.loads(Path("harness/prompts/v1.json").read_text(encoding="utf-8"))
    for c in doc["prompts"]:
        exp_u = c.get("expectUnsupported")
        exp_u = set(exp_u if isinstance(exp_u, list) else sum((v for v in (exp_u or {}).values()), []))
        assert not exp_u & set(c.get("expectDelivered", [])), c["id"]


def test_every_growth_block_is_exercised_by_a_prompt():
    import json
    from pathlib import Path
    g = json.loads(Path("engine/catalog_growth.json").read_text(encoding="utf-8"))
    ex = {b for c in json.loads(Path("harness/prompts/v1.json").read_text(encoding="utf-8"))["prompts"] for b in c.get("exercises", [])}
    assert set(g["blocks"]) <= ex
```

- [ ] **Step 2: Implement.**
  - `expected_delivered(case, profile, catalog)` mirrors `expected_unsupported` (per-profile variants
    allowed).
  - `deliveredRecall` = |delivered ∩ provided-by-final-script| / |expected|, where "provided" means a
    block in the final script carries the capability (`Catalog.capabilities(profile, script)`).
  - Report it next to `unsupportedRecall` in the markdown report.
  - Also report per run: `ungradedBlocks`, the list of growth blocks in the script whose
    `golden` is null (spec §4.3 made visible), and `weather`/`wind` of the final direction.
- [ ] **Step 3: Offline sweep.** Run `py -m harness director --offline` (the phase-3 eval, with the
  refusing provider = fallback-only, no API) over all prompts × the 9 eval subjects × seeds 0–2.
  Record in the register:
  - deliveredRecall;
  - unsupportedRecall (must be 1.0 for every case that expects it);
  - the tier distribution (0 T1; the T2 count and why);
  - wall time.

  Check the exact subcommand name in `harness/__main__.py`.
- [ ] **Step 3a: Physics prompts.** BLOCKS §6's physics prompt list must all be present ("a car parked
  in the rain", "leaves blowing past the chair", "a tumbleweed rolls by the truck", "the can drips with
  condensation", "liquid running down the can", "the sneaker drops and bounces", "smoke rolls around the
  car", "a silk sheet slides off the watch", "sparks fly", "confetti falls on the sofa", "windy",
  "ice-cold drink", "burnout"). Add the missing ones with the correct `expectDelivered` /
  `expectUnsupported` for phase 5: rain, drop and wind are delivered; leaves, tumbleweed, runners,
  smoke, cloth, sparks, confetti and burnout are unsupported (phase 6 / backlog).
- [ ] **Step 4: Run** `harness/tests`, then the full suite and the frozen baseline gate.
- [ ] **Step 5: Commit** `feat(harness): delivered recall, exercises coverage, phase-5 physics prompts`.

---

### Task 91: `py -m harness look`: the budgeted look-check

**Files:** `harness/look.py`, `harness/__main__.py`, `harness/tests/test_look.py`.

- `py -m harness look --script <path> --profile <name> --frames N --at <t,...>`:
  - compiles at the preview tier;
  - reserves N frames from `RenderBudget` **before** rendering (N ≤ 3; refused otherwise);
  - renders exactly those frames;
  - writes the PNGs plus a `look.json` (script sha, frame times, GPU-seconds) under
    `harness/out/look/<sha>/`.
- `--dry-run` prints the frames it would render and renders nothing. It is what CI and tests use.
- Tests (no rendering): N = 4 raises; `--dry-run` lists the times; a reservation happens before the
  render callable is invoked (monkeypatch the renderer to assert `budget.used == N` when called); a
  failing render does not refund.

Commit: `feat(harness): budgeted look-check command (<= 3 frames, reserve before render)`.

---

### Task 92: Finish: full loop, register, handoff

- [ ] **Step 1: Ownership re-check.** Run `engine/tests/test_director_ownership.py`. The LLM never
  writes `realism` or `field`; `wind` only through the schema (Task 58). Run
  `engine/tests/test_catalog_growth.py::test_turntable_is_never_under_growth_or_selectable`.
- [ ] **Step 2: Full suite** `py -m pytest engine/tests harness/tests corpus/tests -q -m "not live"`.
  Compare with the Task 51 counts: new failures must be zero, and other lanes' pre-existing reds are
  listed.
- [ ] **Step 3: Frozen baseline gate**: 90/90 and the regression gate green.
- [ ] **Step 4: Offline variety.** Run `py -m harness variety` with the same groups as the phase-4
  register (3 models × 4 prompts × 5 runs, memory on, refusing provider). Record:
  - 0 tier regressions;
  - the exact-repeat count;
  - the mean direction distance and script distance **before vs after** phase 5 (spec §6: variety
    grows with the catalog);
  - the viable directions per subject.
- [ ] **Step 5: Corpus re-rank.** Run `py -m corpus backlog` and paste its top 10 into the register
  with a one-line "next pass" recommendation (the backlog candidates that outrank what was built).
- [ ] **Step 6: Fill in the calibration register** below. Every number needs its population and
  date.
- [ ] **Step 7: Owner look-check list.** Write the list of PNGs produced by the `[render ≤ 3]` steps
  (paths + what to look for) into the handoff. Every `golden` in `catalog_growth.json` stays null until
  the owner grades.
- [ ] **Step 8: Commit** the register, then write
  `.handoffs/YYYY-MM-DD-HHMM-renderer-director-phase5-catalog-motion-weather-done.md`
  (`track: renderer-director`) and commit it with `git commit -- <that path>`.

---

## Calibration register: every (eng) number this plan introduces

None of these may be quoted as a quality fact until measured.

| Number(s) | Where | Calibrated through |
|---|---|---|
| Fast-loop and full-suite counts; phase-4 signatures | Task 51 | Task 51 / Task 92 |
| `TRUST_N` 30, `FIT` by area | `corpus/backlog.py` | Corpus at ≥ 30 records; owner review of the first trusted ranking |
| `ROUND_CV` 0.08, `SUPPORT_Z` 0.01, `UP_DOT` 0.7, `DOWN_DOT` −0.3, nose-sign 3% | `engine/physics/shape.py` | Which eval subjects pass (Task 55 Step 6); synthetic can/bottle fixtures |
| `SWEEP_SAMPLES` 24; rotate-only sweep allowance 0.2 × longest | `engine/motion_path.py`, checker | Motion fixtures; `path_through_world` false-positive count on the eval set |
| `FF_STRENGTH_PER_MS` 0.8; `perMs` per consumer (haze 0.6, fog 0.5, snow 0.9, rain slant exact) | `wind_calibration.py`, manifests | `wind_coherent` probe; ≤ 3-frame look-checks; phase-6 cloth for the force field |
| Fog `FOG_EXTENT` 6×, `POCKET`, mist 3× height / 0.4× density | `ground_fog` | Task 60 look-check |
| Halation/lens/grain mappings (grain 0.5 ≈ ffmpeg alls=13) | `grade_plan.py` | Task 61 look-check vs a render-studio frame |
| `COURT_K` 6; street length 8×; field 10×; blade cap 60k; clearing 1.2× | layouts | Look-checks; compile time per world |
| Rain `INTENSITY` table, `DROPS_PER_MM_H_M3` 90, `MAX_DROPS` 60000; fall-speed fit | `engine/physics/rain.py` | Task 64 look-check (drizzle/downpour) vs render-studio's rain frame |
| Wet albedo 0.6 / roughness 0.1 at wetness 1; puddle threshold mapping | `engine/physics/wet.py` | Task 65 look-check |
| Snow speeds, wobble A and f, accumulation growth | `engine/physics/snow.py` | Task 67 look-check |
| Drop `restitution` 0.35, `timeScale` 0.5, tilt 4°; toss 0.45; slide 1.4 s; roll τ 2 s; topple aspect 1.3 | motion manifests | PH-09 VLM question once a judge exists; owner grading |
| Drive: R ≥ 3 × wheelbase, launch 0.3 g, brake 0.6 g, roll lag 0.15 s, `rollDegPerG` by class, spoke set {5,6,7,10}, nudge 3% steps | drive/suspension | Blender probe (slip, roll sign); owner grading |
| Handheld footfall 1.6–2.0 Hz, bob 4–12 mm, shake → 1.5° / 2 cm | `handheld_operator` | Look-check strip (3 frames), then owner |
| Cost weights: courtyard 3.0, street 2.6, field 3.2, fog 2.0, rain 1.8, snow 1.6 | manifests | Spec §4.7 cost logging (phase 7) |
| Street `SLAB_CLEAR_M` 0.3 (dropped-kerb gap ±`CAM_CLEAR_M`) | `engine/worlds/street_layout.py` (review chunk 4 #5) | Look-check of a low hero camera on the street |
| `reveal_rise` startDistance 1.4, end distance 4.0; `profile_slide` `FG_DEPTH` 0.3, `FG_SIDE` 0.7, `FG_WIDTH` 0.12, `FG_OVER` 1.2 (a generic post card) | camera `path.py` (Tasks 80, 83) | Look-check; owner grading |
| Handheld `BOB_M` 4–12 mm × radius, `STEP_HZ` 1.6–2.0, `TRANS_M` 0.02 × radius, `ROT_DEG` 1.5, `AIM_LAG_S` 0.15, `ROLL_SHARE` 0.6; `DEFAULT_SHOT_S` 3.0 (context-free calls) | `handheld_operator/path.py`, `engine/camera_context.py` (Task 82) | Look-check strip (3 frames), then owner |
| `rolling_track` distance 2.5 radii, heightFrac 0.35, lag 0.2 s, fstop 5.6; heading central difference 1/120 s, stopped-heading scan 0.1 s × 200 | `rolling_track/path.py`, `engine/camera_context.py` (Task 84) | Blender probe of a drive; owner grading |
| `weatherWeights`, `windSpeeds` bands, `implausible` pairs | `dice.json` | Corpus co-occurrence once trusted; owner "does this feel different" grading |
| Output-schema size before and after | Task 86 | Measured |
| Viable directions per subject, before and after | Task 87 Step 7 | Measured (refusing provider, seed 0, 10 s) |
| deliveredRecall / unsupportedRecall / tier distribution | Task 90 | Measured offline |
| Variety distances before and after | Task 92 | Measured offline |
| Review chunk 5 fixes: `RULE_ROUNDS` 4 (settle/rate fixed point); subject keys `KEY_TOL` 1e-3 x longest, `KEY_MAX_TURN` 90 deg, `KEY_MIN_STEP` 1/16 frame; `GUST_FD_S` 0.005 s; `landing_settle.UPRIGHT_COS` (5 deg); drips `RELEASE_DF` 0.05 frame, `RELEASE_KEY_GAP` 0.01 frame; gust test margin 0.25 (measured snow gap 0.300, rain 2.82, 0.0 with gusts off) | `motion_rules.py`, `compiler/subject_keys.py`, `weather_nodes.py`, `landing_settle`, `droplets/build.py`, `test_blocks_phase5_blender.py` | Blender compile probes (done, 2026-09-25); owner grading of a bounce, roll and drip strip |
| Chunk 7 measured 2026-09-25: output schema full 10857 -> 25064 chars, compact (default) 6438 -> 8050, complexity limits pass; rulebook 32335 -> 52144 chars (~13k tokens); taste section 9310 chars (cap (eng) 12000, no phase-3 constant) | Task 86 | Measured |
| Viable directions (refusing provider, seed 0, 10 s, 9:16), before (studio, dry, calm) -> after: sports_car 36 -> 696, pocket_watch 54 -> 1044, cesium_man 36 -> 696 (x19; every combination viable). `reachable()` over the grown pool: 50-90 s per subject | Task 87 Step 7 | Measured |
| `DRIVE_KMH` 40, the drive window = the first non-detail middle shot (brake_to_stop; the path caps v0 at 0.6 g x window), `MAX_UNBLOCK` 3, fallback camera slots (profile_slide vehicles outdoors; medium handheld, hype dutch, calm reveal_rise), wind still indoors | `fallback.py`, `pipeline.py`, `axes.py` | Owner grading; corpus camera-move shares once trusted |
| Layer-1 windows: neonHue 180-330, windowsLit +-0.15, sunAzimuthDeg +-35, timeOfDay choice (field: overcast only for clean), rain intensity by pace, fog heightM 0.3-0.6, wind directionDeg +-60 wrapped around back-to-front, handheld noiseSeed / shake 0.2-0.4 / azimuth +-20, dutch roll 8-15 / side / azimuth +-20, reveal_rise azimuth +-20 / endHeightFrac +-0.1, profile_slide angle +-15 / heightFrac +-0.1 / side. mood_grade grain NOT varied (studio byte-identity; owner's Task 61 look-check) | `dice.json` detailParams | Offline variety (3 models x empty/cool/luxury/rainy_night x 5 runs): held direction mean script distance 0.115, near-dup pairs 4.33/group, 0 tier regressions (phase-4 row was studio-only, median 0.156, 2.08/group: a different population); unheld mean direction distance 0.52 (min 0.276), script distance 0.345, 0 near-dups, 0 exact repeats, 0 tier regressions. Frame distance owner-gated |
| Chunk 8 measured 2026-09-25 (refusing provider, offline). Task 90 sweep (`py -m harness direct --provider fallback-only --runs 3`, 76 prompts x their subjects (9, or the case's own) x seeds 1000-1002 = 1443 runs, 17.7 min): unsupportedRecall 0.836 (n=366) before the slot_missed fix, 1.0 after on the three failing prompts (add_rain, lens_drops_dry, sunset_music; n=54); deliveredRecall 0.748 (n=753; misses are camera/effect asks the fallback does not honour: dutch, handheld, crane, side_slide, dewy, rain_on_lens, toss on non-sneakers, lighting under a rolled world); tiers 0 T1, 6 T2 (lounge chair toss x3 and studio drive_studio x3: last-resort plans failing T3-01..04 / T3-14), 1437 T3; expectCheck 54/54. Variety (3 models x empty/cool/luxury/rainy_night x 5 runs, memory on): held mean script distance 0.139, near-dups 1.83/group, 0 tier regressions (chunk 7: 0.115 / 4.33; phase-4 held run l1-after-held: 0.136 / 2.08); unheld direction distance 0.52 (min 0.276), script distance 0.371, 0 near-dups, 0 exact repeats (phase 4: 0.263 / 0.27). Viable directions (min per group): sports_car 24-696, pocket_watch 36-1044, cesium_man 24-696. Premium car look (TG-47): camera 0.3-0.7 m, 35-50 mm, f/5.6, width 0.82, puddles 0.6-0.8, detail 85 mm; held-variety coins MIDDLE_FLIP 0.5, HERO_PUSH 0.5 | `fallback.py` (PREMIUM_*, MIDDLE_FLIP, HERO_PUSH), `dice.json` detailParams, `capabilities.slot_missed` | Owner look-check of the premium frame; corpus camera-height shares once trusted |
| Corpus re-rank 2026-09-25 (`py -m corpus backlog`, 11 records, untrusted < TRUST_N 30): 1 motion:static .655 (exists), 2 effect:depth of field .382 (no block), 3 weather:haze .327 (haze_volume), 4 world:cyclorama .273 (studio_cyc), 5 world:nature .273 (golden_field), 6 motion:driving .245 (drive), 7 motion:floating .245 (float_drift), 8 weather:fog .245 (ground_fog), 9 effect:watermark .191 (no block; not wanted), 10 camera:fpv .182 (no block). Next pass: a director-controlled depth-of-field/rack-focus param (the only unbuilt top-3 key), then an FPV/drone camera; re-rank once the corpus is trusted | `research/corpus/backlog.json` | Corpus >= 30 records |

## Deferred (and why)

- **Stateful physics (liquids, cloth, rigid scatter, destruction, VDB smoke and fire, tyre spray,
  dust kick, runners, condensation, bubbles):** phase 6, which needs the bake stage (PHASING §2
  Phase 6). The phase-5 notes say so honestly.
- **Falling leaves, tumbleweed, steam, heat haze, exhaust, dust motes, blowing debris, confetti:**
  PHASING puts some in 5b, but this plan keeps phase 5 to the spec §10 list plus the owner's seeds. The
  corpus backlog (Task 53) ranks them for the next pass. Falling leaves as a **stateless** analytic
  flutter is the first candidate.
- **`moody_top` lighting, `interior_daylight` world, transitions (`edit` kind), `crash_zoom`,
  `light_sweep`:** CATALOG-GAPS ranks, ordered by the corpus backlog.
- **Snow sink in `ground_conform`** (snow as a ground type while it snows) and tracks in snow, sand or
  mud (CD-05).
- **Rain on field worlds.** Excluded by taste (eng) until the corpus or owner says otherwise.
- **Camera shake coupling to a car-mounted camera (VD-06)** and a shutter param per camera: phase 7,
  tied to the farm's shutter handling.
- **Owner grading → `golden` status**, and rulebook golden examples for the new worlds: at the
  all-phases grading session (the owner's standing deferral).
- **Rollable-but-ungraded blocks.** The dice roll growth blocks now, which lets the harness measure
  them. Whether the **site** may deliver an ungraded block is an owner decision before web wiring
  (`apps/web` stays `not_connected`). Task 88 built the gate for the recommended answer:
  `engine/director/site.py` (`site_catalog`, `site_rulebook`, `site_deliverable`) keeps every golden-null block
  off the site's menu; the web wiring must use it.
- **mood_grade grain in layer 1 (TG-26).** Not varied in Task 89: it is a block every studio script uses (the
  studio fallback must stay byte-identical) and the plan gates it on the owner's Task 61 look-check.

## Owner-only items

- **Look-checks beyond 3 frames.** Every `[render ≤ 3]` step stays within the per-invocation budget.
  Any larger strip or film needs the owner's OK.
- **Grading** the look-check frames and flipping `golden` in `catalog_growth.json`.
- **Corpus clip sourcing** (spec §9a): hand-picking Pexels, Mixkit and Pixabay clips and recording
  YouTube/Vimeo links. Automated collection is forbidden (Pexels ToS). Only the owner, or an agent the
  owner supervises, picks clips.
- **Downloads that need a click or a licence read, never scripted:**
  - Between Two Pines loopable smoke (Gumroad; the licence text must be read on the page), for
    phase 6;
  - the VFX Assets commercial cloud pack (paid);
  - the JangaFX CC0 VDBs (6+ GB; a phase-6 storage decision);
  - ambientCG leaf sets (CC0, not needed until falling leaves);
  - any Poly Haven asset **not** already on disk in render-studio's pinned `assets/`.
- **Decision:** whether the dice may roll blocks whose `golden` is still null once the site is wired
  (recommend: yes in the harness, no on the site until graded).
- **Decision:** rain on `golden_field` (recommend: keep excluded until the corpus shows it).

## Done when

- The full suite (`-m "not live"`) has no new failures against the Task 51 baseline, and the frozen
  phase-3 baseline is **90/90** at every chunk end.
- `engine/catalog_growth.json` covers every new selectable block, and `test_catalog_growth.py` is green:
  taste rules, registered gates, delivered and unsupported prompts, and a floor test for each block.
- Four worlds, eight new motions, five new cameras, the weather package (rain with drizzle, steady and
  downpour; wet ground with reflecting puddles; droplets and drips; snow with accumulation; fog and
  mist; lens drops) and three new lights compile headless with every asset missing (procedural
  fallbacks), and with it present.
- Wind is director-selectable only through the schema; the LLM never writes realism or a field; the
  turntable is still a harness-only negative control.
- The dice roll weather and wind through world compatibility and the floor. Offline variety shows
  0 tier regressions and larger direction and script distances than the phase-4 register.
- Offline eval: unsupportedRecall 1.0, deliveredRecall recorded, no T1 scripts.
- No render ever exceeded 3 frames per invocation, and every look-check PNG is listed for the owner.


---

## Review amendments (binding)

From the independent review against HEAD, 2026-09-25. Blockers 1–9 are already fixed inline (play_clip
identity, no identity keys without `path.py`, rain couplings added in Task 67, coupling insert cursor,
coupled child skipped when the profile does not fit, `maxPerClip` absent = unlimited, normals
estimated from bare samples, profile facts routed through `_has`). Blocker 6 and the rows below apply
to the named tasks and override their text.

| Task(s) | Amendment |
|---|---|
| 58 | Add `"field"` to `KIND_ORDER` in `engine/director/menu.py` (without it `Catalog.capabilities` and `render_menu` skip wind, so `wind.breeze` is never delivered). The schema builder is `scene_output_schema`, not `build_output_schema`. |
| 56, 57, recipe | Every new **error** code also gets an `ERROR_HINTS` entry in `engine/director/repair.py` (`test_director_repair.py::test_every_error_code_has_a_hint` scans for them). Add this as block-recipe step 5b. |
| 85 | HEAD's `direct()` does **not** map checker errors to `unsupported`; it sends them to `repair_message` or the fallback. Task 85 builds that mapping in `pipeline.py` (and `sanitize` where needed) with its own tests per code; drop the sentence claiming it exists. |
| 63, 70, 79 | Lower `subjectSizeM` minimums to 0.03 m for `rain_courtyard`, `night_street` and `drive` (`pocket_watch` is 0.076 m, `toycar` 0.074 m); keep the eval tests on those subjects. |
| 56 | `path_through_world` measures **horizontal pivot travel** (`hypot(pose.offset.x, pose.offset.y)` max over the clip), not swept-AABB growth, so turning in place never counts as travel. Allowance = `max(world.driveLaneM, 0.2 × profile.longest)`. Over the allowance: a `motion_travel_capped` repair (scale the motion's distance param down) when the block declares a distance param, else the error. |
| 56 | Moving subjects: `timeline._key` focus distance, `resolve_target` marker targets and `camera_clearance` use the **posed** profile, markers and centre at that frame. Add a test that a detail shot's aim follows a glide. |
| motion rules, 77, 78 | `spin_rate_cap` applies only to `plinth_spin` and `float_drift` yaw. Rolling contact (roll, drive wheels) and airborne tumbles (toss) are exempt; toss gets its own cap on **perceived** rate after `timeScale` of 360 °/s (eng). |
| 77 | Add `pivot` (placed-space point) to `SubjectPose`, default `(cx, cy, 0)`; the compiler sets the empty's origin per motion from it. Roll uses the roll-axis line at height r; topple uses the support edge. Test: the topple pivot edge stays at z = 0 at every sample; roll's contact line stays at z = 0. The PCA roll axis is arbitrary, so rotate about that axis vector, not local X. |
| 78 | `spins` takes whole numbers only (1, 2, 3; default 1), so the landing orientation equals the rest pose. |
| 79 | Add `startS` (0–8, **0.5**) and `driveS` (1–10, **4**) params: the car moves only inside that window, so 40 km/h × 4 s = 44 m; `vehicle_speed_cap` compares ∫v dt over the window to `driveLaneM`, and `rolling_track`/pass-by shots can reset the path per shot (`perShot` bool, **false**). |
| 64, 71, 76 | No "unset = derived" or "seeded" numeric defaults (`_repair_params` fills defaults). `rateMmH`/`dropSizeMm` default **0 = from intensity**; `sunAzimuthDeg` and `directionDeg` default **0**, and layer 1 (Task 89) varies them. |
| 52, 60 | The growth test requires `unsupportedPrompt` only when **some catalog world fails** the block's `requiresWorld`. Every world has a ground, so `ground_fog` needs none. |
| 59 | `dangling_sway` and `shaft_dust` are already `windDriven: true`; add `windCalibration` to both manifests (read their current constants; no look change) and add them to the commit. |
| 63→88, 64→88 | New blocks land with `directorSelectable: false` and are flipped to true in Task 88 once fallback, lighting, tone, vocabulary and dice support exist. Until then `dice.json` gets `"worlds": ["studio_cyc"]` (filtered in `axis_values`), removed in Task 87. Tasks 71/72 update the `sunset_music` prompt (`world.nature`/`lighting.sun` become delivered). |
| recipe step 8 | Floor tests in chunks 2–6 use a hand-written fixture script per block (`check(...).ok` and `script_tier == "T3"` on the task's subject). Task 88 adds the fallback-based floor tests (pinned world/weather/motion) for every growth block. |
| 73 | The per-world tone rule in `compatible()` (`na` for worlds without `toneParam`) lands in Task 73, not Task 87. |
| 74, 78, 79 | Extend `_compat` to size-check motions and effects (existing blocks allow 0.02–8/30 m; the 90 baseline cases are unaffected — verify at the chunk gate). The new error code gets a hint. |
| 87 | Pinned or rolled wind overrides the LLM's wind on vague prompts (spec §6); on long prompts only a pinned wind overrides. Make Step 5 match the architecture text. `make_viable` returns a callable at HEAD: iterate the ranked candidates through it. `compatible()` gains `catalog=`; update every call site. Use `dice_seeds.seed_matching` in direction-sensitive tests instead of a fixed seed. |
| 90 | `run_eval_offline` does not exist; use `run_director_eval` with the refusing provider. |
| 85, 90 | "burnout" is a `motion.drive` phrase, so it is **delivered** in phase 5 (a drive), not unsupported; spray is the unsupported part. Fix the vocabulary so "drops and bounces" hits `motion.drop` and not `sim.rolling`. |
| 54 | The valid `WORLD` fixture needs `params: {"timeOfDay": {"type": "enum", "values": ["dusk", "night"], "default": "night"}}`. Add validators for `requiresMotion` and `hookable` (Tasks 80, 84). |
| 53 | The top-candidate assertion allows the tied set (`camera:push` ties `world:street`); compare against the set of max-score keys. |
| 52 | Reuse `test_director_repair.engine_error_codes` for the scan (it sees the `err("...")` helper) plus an allowlist for dynamic `f"bad_{key}"` codes. |
| 82 | No `int` param type exists: `noiseSeed` is a `number` rounded in `sample`. |
| 64 | The point-count assertion counts points **before** the shelter delete. |
| Deferred | `dust_motes` (spec v1 effect list, PHASING 5b, stateless) is added as optional Task 69a using `particle_box_group` with a slow drift and no fall, re-rank permitting; if skipped, the Deferred list says why. |
