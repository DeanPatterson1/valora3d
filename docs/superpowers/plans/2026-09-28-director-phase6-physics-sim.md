# Director Layer Phase 6: Physics and Simulation

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The director can ask for real, subject-interacting simulations and get them:

- pieces that rain onto and around the subject and settle (rigid scatter);
- floating debris and props that shatter;
- runners and condensation on a cold can;
- sparks, confetti and bubbles;
- spray and dust kicked up by a driving car;
- a cloth that slides off to reveal the subject, plus flags and silk ribbons;
- smoke plumes, steam and fire, smoke that wraps round the subject, and tyre smoke;
- liquid splashes, pours and thick honey-like flows, and ink in water.

Every simulation is **baked once, before rendering**. The preview and the final render read the same
bake, and it is stored as a hashed job asset that a future farm worker can pick up and render in any
frame order. The simulation never touches the uploaded mesh. It collides with a closed **collision
shell** built from the upload. Every new visual effect reaches the owner as a graded golden render
before its `golden` flag flips. The frozen phase-3 baseline stays 90/90 throughout.

**Architecture:**

- **A `sim` block has two halves: `bake(ctx)` and `build(ctx)`.** `bake` runs in a separate headless
  Blender job (stage **4b BAKE**, between the checker and the compiler; PHASING §2 Phase 6.1). It
  simulates and writes a cache. `build` runs inside the normal compile. It **only reads** the cache,
  so a compile never simulates (a test enforces this). That split is what makes METHODS R2 ("bake
  once, then split") and R9 ("the preview uses the same bake") true by construction.
- **Every cache is a portable format with a known frame offset.** The Task 94 probe decides the exact
  API; these are the plan's defaults:

  | Method | Bake | Cache (read by `build`) |
  |---|---|---|
  | Bullet | step with `frame_set` | per-piece transforms, JSON → keyframes |
  | Cloth | step with `frame_set` | PC2 point cache → Mesh Cache modifier |
  | Geometry Nodes simulation zone | bake to disk | the GN bake directory |
  | Mantaflow gas | `fluid.bake_all` | an OpenVDB sequence → a Volume object |
  | Mantaflow liquid | `fluid.bake_all` | an Alembic mesh with velocity → MeshSequenceCache |

  No format keeps Blender's own `blendcache_*` folders, because those are tied to a saved `.blend`
  path.
- **The bake key is content-addressed:**
  `sha256(block id + params + window + seed + profile_key + model sha256 + Blender version + block
  source hash + wind + subject motion + world ground)`. It never contains the tier, so the preview and
  the final share one bake (R9). An upgraded Blender or an edited `bake.py` gives a new key, so a stale
  cache can never be reused. Caches live under `var/bake/<key>/` (gitignored) with a `bake.json`
  manifest (files, sha256, bytes, bake seconds). Writes are atomic and every read is verified.
- **Collision shells, never the raw upload** (METHODS R6/R8). `engine/blender/collision_proxy.py`
  builds the shell:
  - a closed voxel shell (Mesh to SDF Grid → Grid to Mesh) at a voxel of about 0.5–1% of `longest`;
  - thickened by one voxel, so single-sided glass becomes a wall;
  - decimated to ≤ 20k triangles.

  Bullet also gets a convex-hull variant for active pieces. The shell is cached by the same store,
  keyed by the model's sha256 and the voxel size. The render mesh is untouched (the
  `uploadMaterials before/after` guard already exists in `blender_main.main`).
- **No new SubjectProfile fields.** `profile_key` (`engine/director/baseline_phase3.py`) hashes
  `profile.to_dict()`, and variety memory and the floor cache key on it. Sim facts therefore come
  from two places:
  - `engine/physics/sim_facts.py`, which is pure: containers, fill lines and emitters from markers,
    detail points and surface samples, plus the up-facing samples and low edges that
    `engine/physics/shape.py` already computes;
  - the bake job's proxy report (watertight, thickness, volume).

  `valora.profile/1` does not change. The phase-5 register's "`noseSign` ingest fact" goes into
  `sim_facts` in the same way.
- **The checker budgets sims before anything bakes.** `engine/sim_rules.py` sits beside
  `engine/weather_rules.py`:
  - `sim_window`: clamps the window and adds pre-roll;
  - `sim_budget`: at most one heavy sim per clip;
  - `time_scale_range`, `spawn_in_subject` and `path_through_subject` over sim zones;
  - `sim_needs_world` and `sim_needs_profile`: the ask goes to `unsupported` with its note, never
    silently dropped;
  - `wind_param_on_effect`, extended to sims.

  The checker stays pure and stays at milliseconds.
- **Sims are asked for, never rolled.** The owner's realism direction (memory
  `feedback_renderer_realism_direction.md`) is readable light over added effects, and no showpiece
  accents. So the dice gain no sim axis, adherence never inserts a sim into a vague prompt, and the
  empty-prompt default never contains one. A sim appears only when the prompt or a marker asks for
  it. This also keeps every direction id, and the frozen baseline, unchanged.
- **One machine, bakes serialised.** A machine-wide lock, `var/bake/.lock`, allows one bake at a time.
  `BakeBudget` caps the bake minutes per invocation. Heavy bakes are `slow`-marked tests. Several
  subagents can write code in parallel, but their Blender bakes queue on the lock (see the pitfall in
  the renderer-engine hand-offs: "two builders on one checkout collide; serialise Blender renders and
  slow tests").

**Tech Stack:** Python 3.12 dev; **Blender 5.0.1** (bundled 3.11), pinned. The upgrade decision is
below. The simulation tools are Bullet (`rigidbody`), legacy Cloth, Mantaflow (`FLUID`, GAS and LIQUID
FLIP/APIC), the Geometry Nodes Simulation zone with its Bake node, the 5.0 volume-grid nodes (Mesh to
SDF Grid, Sample Grid, Grid to Mesh), OpenVDB Volume objects, and the Alembic and PC2 caches. pytest 8.
`engine/` stays stdlib-only at import time; numpy is allowed inside Blender only. There are no new pip
dependencies and no network at bake or render time.

---

## Decision: Blender 5.0.1 vs 5.2 LTS (made at phase start, 2026-09-28)

**Installed and used:** `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe` reports
**5.0.1** (build 2025-12-16). It is the only Blender under `Program Files\Blender Foundation`.
`engine/blender_cli.py` defaults to it (`BLENDER_EXE` overrides). Probed 5.0.1 constants are baked into
`engine/blender/weather_nodes.py`, `engine/blocks/motion/play_clip/build.py`, `engine/clips.py`
(`MAX_NLA_REPEAT`) and `engine/physics/wet.py`.

**Decision: stay on 5.0.1 for all of phase 6. Do not install 5.2 into the pipeline.**

1. **Every method this phase needs is already in 5.0.1:** Bullet, legacy cloth with pressure and
   self-collision, Mantaflow gas and liquid (FLIP/APIC, viscosity, mesh upres, spray), GN simulation
   zone and Bake node, 30 grid nodes including Mesh to SDF Grid, Volume velocity grids, and Alembic
   and PC2 caches (METHODS §0.2, probed [P]).
2. **What 5.2 LTS adds for physics** is Geometry Nodes hair and cloth dynamics (XPBD), and they are
   **still experimental** (code.blender.org, 2026-07, METHODS R10). Rigid bodies (Jolt) and a fluid
   solver are only on its roadmap. None of the phase-6 blocks needs XPBD. XPBD matters for character
   garments and hair, which is phase 8.
3. **An upgrade would reset graded work.** The owner graded realism round 16 on 5.0.1 on 2026-09-27
   ("all good now"). Changing the Blender build changes noise, the volume stepping and the Principled
   defaults the realism lane tuned against. Every graded look would have to be re-checked, and
   PHASING §5.1 already flags that "an upgrade later means re-baking the golden renders".
4. **5.0 is not an LTS**, so it gets no more bug fixes. **Fallback:** if a 5.0.1 solver crash blocks
   a task (a Mantaflow or Bullet segfault that Task 94 cannot work around), install 5.2 LTS **side by
   side** and point `BLENDER_EXE` at it for that one probe only. Record the finding and do not switch
   the pipeline without the owner.
5. **The switch is mechanical when it comes.** The bake key includes `bpy.app.version_string`, so an
   upgrade invalidates every cache automatically. `engine/tests/test_blender_pin.py` (Task 93) fails
   if the installed build drifts from `PINNED_BLENDER`, so the change is deliberate.

**Re-evaluate at the start of phase 8** (character cloth and hair), or earlier only if Task 117's
liquids fail the owner's grade **and** 5.2 has by then shipped a non-experimental GN fluid. Otherwise the
next step for liquids is the FLIP Fluids licence, not 5.2 (PHASING §5.3).

---

**Spec and research:**
- `docs/superpowers/specs/2026-09-24-director-layer-design.md`:
  - §2a (tiers)
  - §4.2 (sims were reserved)
  - §4.5 (compile order; materials left alone)
  - §4.6 (checker)
  - §4.7 (tiers, cost logging, same build per job)
  - §4.8 (frame QC)
  - §10 physics re-phasing (phase 6)
- `research/physics/PHASING.md`: §2 Phase 6 (pipeline, ingest, sim kind, order, probes, exit gate),
  §2 Phase 7 (farm requirements a–c), §3 (unsupported contract), §4 (risks), §5 (decisions).
- `research/physics/METHODS.md`: R1–R10, §0.1 cost classes, §0.2 5.0.1 facts, §1 toolbox, §2.3 (RB-05,
  RB-07, DS-01..03), §2.4 (SC-01, SC-02, SC-05), §2.6 (PT-06, PT-08, PT-09, PT-10), §2.7 (GS-01, GS-02,
  GS-06, GS-09), §2.8 (FL-04, FL-05, FL-08..10, FL-13, FL-14, FL-16), §3 (ingest).
- `research/physics/BLOCKS.md`: §1 (`sim` kind, manifest keys), §2.5 (the sim block list), §3
  (dependencies), §4 (tags), §5 (checker codes, compile probes), §6 (PH-03..PH-11).
- `research/physics/ASSETS.md` §1 (VDB licences: JangaFX CC0; Between Two Pines only after the licence
  is read; OpenVDB samples never shipped).
- Phase 5 plan `docs/superpowers/plans/2026-09-25-director-phase5-catalog-motion-weather.md`: its
  conventions, its block recipe, its register, its Deferred list and its phase-6 deferrals (listed under
  "What grew from the seed").
- Phase-5 done hand-off `.handoffs/2026-09-25-2000-renderer-director-phase5-catalog-motion-weather-done.md`.
- Realism-lane standing rules:
  `ModVision/.handoffs/2026-09-27-2200-renderer-engine-r16-graded-paused-overnight.md` and the r16 and
  r7–r9 hand-offs it points to.

**Task numbering** continues after phase 5's last task (Task 92). This plan uses **Tasks 93–123**.

**Conventions (same as phase 5, plus the bake rules):**

- Run every command from the repo root `C:\Users\deand\Projects\rendering`, on branch
  `renderer/director`. Use `py`, never bare `python`. **Never touch `main`, never push.**
- **Fast loop:** `py -m pytest engine/tests harness/tests corpus/tests -q -m "not blender and not live"`.
- **Full suite (the chunk gate):** `py -m pytest engine/tests harness/tests corpus/tests -q -m "not live"`.
  Heavy bakes carry the `slow` marker, so they run only with `-m slow` or `VALORA_SLOW=1`. The sim
  chunk gate runs them **once**, serially, at the end of each chunk.
- **Frozen baseline gate (every chunk end):**
  `py -m pytest engine/tests/test_director_floor.py engine/tests/test_director_baseline.py harness/tests/test_baseline_regressions.py -q`.
  All 90 `test_phase3_default_still_reproduces_the_frozen_baseline[...]` cases must pass. Never
  regenerate the fixture.
- **No live API.** Director tests use `FakeProvider` or the refusing provider.
- **Render budget.** At most 3 rendered frames per `py -m harness look` invocation (`harness/budget.py`,
  reserved and never refunded). A sim's golden checkpoint uses those 3 frames:
  - before the event, the peak, and settled;
  - rendered at the preview tier from the **same bake**.

  Motion can't be judged from stills, so each checkpoint also offers an **owner-OK motion strip**
  (Owner-only item O2). It is never rendered without the owner's go.
- **Bake budget.** `harness/budget.py` gains `BakeBudget` (Task 93): at most `MAX_BAKE_MIN` minutes
  (eng: 90) of estimated bake per invocation, reserved from the block's `bake.estimateS` before the
  bake starts. A heavy bake over it needs `--owner-ok`. Only one bake runs at a time on the machine
  (`var/bake/.lock`).
- **Licence-clean assets only.** Allowed: CC0, owned, or procedural by construction. A pinned VDB
  sequence gets a row in `engine/assets/manifest.json` with its sha256, and its licence goes in
  `engine/assets/CREDITS.md` when it is not CC0. Downloads that need an owner click are Owner-only and
  never scripted. Every block builds **with its asset missing**, using a procedural fallback, so tests
  never need a download.
- **Shared working tree.** Other lanes commit here too.
  - Run `git diff --cached --name-only` before every commit, and commit only the task's paths with
    `git commit -m "..." -- <paths>`.
  - Never `git stash` and never `git add -A`.
  - **Re-read before you edit** `job.py`, `pipeline.py`, `fallback.py`, `sanitize.py`, `adherence.py`,
    `rulebook.py`, `output_schema.py`, `engine/checker.py`, `engine/script.py`, `engine/catalog.py`,
    `engine/compiler/blender_main.py` and `engine/compiler/run.py`. Code blocks below are anchored on
    function and constant names, never on line numbers.
- **Parallel lanes never edit shared registries.** Block tasks in Chunks 2–6 touch only:
  - their own `engine/blocks/sim/<id>/` (or `effect/<id>/`) folder;
  - their own `engine/physics/<topic>.py` and `engine/blender/<topic>.py`;
  - their own test files.

  Each lane ends by writing a **registry patch** into its task's section of the register: the exact
  `gates.py` codes, `catalog_growth.json` entry, `TG-` taste rule, `v1.json` prompts and vocabulary
  flips. The lead applies all the patches serially in Chunk 7. That removes merge fights over
  `engine/gates.py`, `engine/catalog_growth.json`, `engine/director/taste/rules.json`,
  `harness/prompts/v1.json` and `engine/director/vocabulary.json`.
- **Verification commands are PowerShell-safe:** `py` scripts or pytest, never `grep`/`sed`/`head`.
- Each commit message ends with the two attribution lines given in the session.
- Every number marked **(eng)** is an engineering guess and goes in the calibration register (Task 123).
- **Blender builders:**
  - `build.py` and `bake.py` import `bpy` only inside their functions (`test_blocks_complete.py`).
  - Sizes are a fraction of `profile.longest`, or real-world metres for scale cues (beans, drops,
    sparks, confetti and bubbles stay real-size; METHODS R4/R5).
  - Seeds come from `ctx.seed` and `ctx.rng` only. Force-field seeds go through `ff_seed` (1–128).
  - Nodes are looked up by **type**.
  - Enum identifiers are read from `bl_rna` before use, never hard-coded blind.
- **The owner's grading rules (realism lane, standing):**
  - The owner grades each look. Send each sheet in its **own** SendUserFile call, with a caption naming
    the effect.
  - Every sheet puts the effect's **own** reference frame beside ours.
  - The owner answers with KEEP / CHANGE / STOP.
  - **Apply colour and shape asks in measured steps** (about half the requested shift per round; the
    r16 field lesson).
  - Do exactly the owner's asks, with no extra "improvements".
  - Realism beats showpiece: sims default to restrained counts and sizes.

---

## Realistic budgets for this machine (RTX 5080 16 GB, Ryzen 7 9800X3D 8C/16T, 31 GB RAM, 826 GB free on C:)

Bullet, cloth and Mantaflow all bake on the **CPU**; the GPU only renders. Every number here is (eng)
until Task 122 measures it, and each one goes in the register.

| Sim | Bake cap (phase 6) | Estimate (eng) | Cache cap | RAM (eng) |
|---|---|---|---|---|
| `rigid_scatter` ≤ 500 pieces, 60 substeps, ≤ 240 f | 5 min | 0.5–3 min | 20 MB (JSON keys) | < 2 GB |
| `shatter` ≤ 200 shards | 10 min | 1–5 min | 20 MB | < 2 GB |
| GN point sims (sparks, confetti, bubbles, runners, spray) ≤ 100k points | 10 min | 0.5–5 min | 500 MB | < 4 GB |
| cloth `drape_reveal` ≤ 8k verts, quality ≤ 12, self-collision, ≤ 240 f | 20 min | 3–15 min | 200 MB (PC2) | < 3 GB |
| gas (`smoke_sim`, library bakes) `resolution_max` ≤ 160, noise upres ×2, ≤ 180 f | 60 min | 10–45 min | 4 GB (VDB, float16) | 6–10 GB |
| liquid FLIP `resolution_max` ≤ 192, mesh upres 2, ≤ 180 f | 90 min | 30–90 min | 6 GB (particles dropped after meshing, Alembic kept) | 8–14 GB |

- **Total cache cap:** `VALORA_BAKE_CACHE_GB`, default 60 (eng). Least-recently-used caches are pruned
  first, and a pinned golden bake is never pruned.
- **Render cost:** volumes multiply the final-tier render time by about 1.5–3 (eng; METHODS §0.1).
  From the rain scene's 35 s/frame, a 10 s smoke clip is about 4–9 GPU-hours at the final tier.
- **Preview tier:** it uses the same bake (R9). Only render-side knobs change, and they are clamped for
  the preview in `tiers.py`:
  - `volume_step_rate` 4 (final 1);
  - `volume_max_steps` 256;
  - `volume_bounces` 0.

  They never change the simulation.
- **Heavy sims:** at most **1 per clip** (`sim_budget`). Liquids and gas are heavy; cloth is medium;
  rigid and GN are medium or cheap.

---

## File structure

| File | Status | Responsibility |
|---|---|---|
| `engine/blender_pin.py`, `engine/tests/test_blender_pin.py` | create (T93) | `PINNED_BLENDER = "5.0.1"`; the test compares `blender --version` |
| `harness/budget.py` | modify (T93) | `BakeBudget` (minutes, reserve-before-bake, never refunded); `RenderBudget` untouched |
| `engine/bake/lock.py` | create (T93) | `machine_lock()`, an exclusive `var/bake/.lock` (msvcrt on Windows), with a timeout and a stale-pid check |
| `engine/bake/formats.py` | create (T94) | The probed 5.0.1 API facts per cache format: frame-offset mapping, velocity names, operator overrides |
| `engine/tests/test_sim_api_probe_blender.py` | create (T94) | Blender probes that pin those facts |
| `engine/catalog.py` | modify (T95) | The `sim` manifest contract: `bake` object, `costClass`, `window`, required `timeScaleParam` |
| `engine/script.py` | modify (T95) | Validate `sims: [{id, params, startS, endS}]` |
| `engine/sim_rules.py` | create (T95) | `sim_window`, `sim_budget`, `time_scale_range`, `sim_spawn_in_subject`, `sim_needs_world`, `sim_needs_profile`, `sim_param_wind` |
| `engine/physics/sim_facts.py` | create (T95) | Pure sim facts: `container`, `fill_line`, `emitters`, `nose_sign` (with markers), `pile_zone` |
| `engine/bake/key.py`, `engine/bake/store.py`, `engine/bake/window.py` | create (T96) | Content hash, atomic verified cache store with LRU prune, sim window → bake frame range with pre-roll |
| `engine/physics/proxy.py`, `engine/blender/collision_proxy.py` | create (T97) | Voxel rule (pure); closed shell, convex hull and thick shell (Blender); proxy report |
| `engine/bake/run.py`, `engine/bake/blender_bake.py` | create (T98) | Host bake runner and the headless bake entry |
| `engine/compiler/context.py` | modify (T98) | `BuildContext.bake` (the manifest dict, or None) |
| `engine/compiler/run.py`, `engine/compiler/blender_main.py` | modify (T98) | `compile_scene(..., bakes=)`, and sims in `_refs` after effects |
| `engine/__main__.py`, `harness/look.py` | modify (T98) | `py -m engine bake`; `look` bakes first |
| `engine/tests/fixtures/catalog_sim/` | create (T98) | A test-only catalog with `sim/_test_drop` (one cube, Bullet), which proves the stage |
| `engine/blender/sim_probe.py`, `harness/physics.py` | create/modify (T99) | `no_particles_in_subject`, `sim_stable`, `velocity_present`, `bake_cost`; PH-03/04/05/11 |
| `engine/blocks/sim/{rigid_scatter,debris_float,shatter}/` | create (T100–T102) | Rigid lane |
| `engine/physics/scatter.py`, `engine/physics/fracture.py`, `engine/blender/pieces.py` | create (T100–T102) | Spawn layout, procedural piece meshes (CC0 by construction), Voronoi cells |
| `engine/blender/gn_sim.py` | create (T103) | The shared GN point-sim base (spawn, gravity, drag, wind, SDF collide, velocity, bake to disk) |
| `engine/blocks/sim/{runners,condensation,sparks,confetti,bubbles,tyre_spray,dust_kick}/`, `engine/blocks/effect/embers/` | create (T104–T106) | GN lane |
| `engine/blender/cloth.py`, `engine/physics/cloth.py` | create (T107) | Cloth base and presets (silk, satin, canvas); the `FF_STRENGTH_PER_MS` calibration |
| `engine/blocks/sim/{drape_reveal,flag,silk_ribbon}/` | create (T108–T109) | Cloth lane |
| `engine/blender/vdb.py`, `engine/blender/gas.py` | create (T110–T111) | VDB playback (retime, velocity, placement); Mantaflow gas bake helper |
| `tools/bake_vdb_library.py`, `engine/assets/manifest.json` | create/modify (T111) | Our own CC0 VDB library, baked once |
| `engine/blocks/effect/{smoke_plume,steam,fire}/`, `engine/blocks/sim/{smoke_sim,tyre_smoke}/` | create (T112–T113) | Smoke and fire lane |
| `engine/blender/liquid.py`, `engine/physics/liquid.py` | create (T114) | Domain sizing, thick obstacle, inflow curve, Alembic mesh with velocity, liquid materials |
| `engine/blocks/sim/{liquid_splash,liquid_pour,viscous_flow,ink_cloud}/` | create (T115–T117) | Liquid lane |
| `engine/director/{vocabulary.json,capabilities.py,output_schema.py,sanitize.py,fallback.py,adherence.py,rulebook/rulebook.txt}`, `engine/director/taste/rules.json`, `engine/gates.py`, `engine/catalog_growth.json`, `harness/prompts/v1.json`, `harness/director_eval.py` | modify (T118–T121) | Director integration: the lead applies the lane registry patches |
| `engine/tests/test_bake_portable.py` | create (T122) | A copied cache under another root renders the same (farm readiness) |

---

## What grew from the seed

The seed named: block kind `sim`, a bake step, collision shells, VDB smoke and fire, Mantaflow liquids,
cloth, rigid-body scatter and destruction, a Blender version decision, and FLIP only on a failed grade.
This plan grows it into:

1. **The bake as a content-addressed asset**, not just a step. A hash key, a verified store, a least-
   recently-used cap and a portability test (T96, T122) give the phase-7 farm "bake once, ship by hash"
   (PHASING §2 Phase 7a) for free.
2. **A split `bake(ctx)` / `build(ctx)` contract**, with a test that a compile never simulates. That
   makes R9 (preview equals final) mechanical rather than remembered.
3. **One format per method, each with a proven frame offset** (T94). Pre-roll works without negative
   frames, and any frame renders in any order.
4. **Our own VDB library** baked from Mantaflow (T111): plume, chimney, campfire, tyre-smoke burst and
   dust billow. It is CC0 by construction, so the 6+ GB JangaFX download becomes optional, not blocking
   (ASSETS §1: "bake our own library").
5. **Proxy variants per consumer:**
   - a closed shell for Mantaflow and cloth;
   - a thick shell for single-sided glass;
   - convex hulls for active Bullet pieces;
   - an SDF grid for GN point collisions.

   One report says whether each is watertight.
6. **More effects than the seed named, in PHASING score order:** runners and condensation (this closes
   the phase-5 `liquid.run_down` partial note), sparks, confetti, bubbles, embers, tyre spray, dust
   kick, flags, silk ribbons, steam and fire (with a flicker light), ink in water, and viscous honey
   flows.
7. **The phase-5 deferrals, closed:**
   - `FF_STRENGTH_PER_MS` is calibrated with a cloth strip (T107);
   - runners (T104);
   - VDB smoke and steam (T112);
   - tyre spray and dust kick (T106), which replace the phase-5 "Road spray isn't available yet" note;
   - the `noseSign` fact, via `sim_facts` (T95).
8. **Honest refusals.** A sim the profile or world can't support goes to `unsupported` with a plain
   note, for example "This model has no closed shape to pour into, so the pour was left out."
9. **Safety for props:** `shatter` breaks only **props** (glass pane, ice block, thin wall). It never
   breaks the customer's product (DS-01 brand risk).
10. **Cost you can price.** Bake-seconds and GPU-seconds are logged separately per block (PH-11, spec
    §4.7). That is the input to the phase-7 CPU bake worker class.

---

## Parallel map

```
Chunk 0  T93 ─► T94 (probe)                                    sequential
Chunk 1  T95 ║ T96 ║ T97   (parallel, after T93; T97 after T94)
         └──────► T98 (bake stage) ─► T99 (probes + recipe)     sequential
Chunks 2–6: five lanes, each independent after T99; bakes queue on var/bake/.lock
  R  rigid   T100 ║ T101 ─► T102
  P  points  T103 ─► (T104 ║ T105) ─► T106
  C  cloth   T107 ─► (T108 ║ T109)
  S  smoke   T110 ─► T111 ─► (T112 ║ T113)
  L  liquid  T114 ─► T115 ─► T116 ─► T117     (T117 ink_cloud also needs T111's gas helper)
Chunk 7  T118 ─► T119 ─► T120 ─► T121   (lead only; applies the lane registry patches)
Chunk 8  T122 ─► T123
```

**Recommended landing order when lanes can't all run:** R → P → C → S → L. This puts cheap, visible and
quick-to-bake work first; liquids go last because their bakes run for hours and they carry the most
risk. Chunk 7 can run after any subset of lanes: blocks from an unfinished lane stay
`directorSelectable: false`.

---

## Chunk 0: Gate and decisions

### Task 93: Gate, Blender pin, bake budget and machine lock

**Files:**
- Create: `engine/blender_pin.py`, `engine/tests/test_blender_pin.py`, `engine/bake/__init__.py`,
  `engine/bake/lock.py`, `engine/tests/test_bake_lock.py`
- Modify: `harness/budget.py`, `harness/tests/test_budget.py`

- [ ] **Step 1: Record the baseline.** A full `pytest` run was in progress when this plan was written.
  Read its result, or re-run the full suite on a quiet box, and write the pass/fail/skip counts and any
  reds into the Task 123 register. Other lanes' reds are listed, not fixed. Run the frozen baseline gate
  and record `90 passed`. Confirm the HEAD facts this plan relies on with a scratch script under
  `C:\Users\deand\AppData\Local\Temp\p6_gate.py`:

```python
import inspect
from engine.catalog import KINDS, Catalog
from engine.script import RESERVED
from engine.director.output_schema import LIST_FIELDS, SINGLE_FIELDS
from engine.compiler.context import BuildContext
from engine.compiler.run import compile_scene
from engine.physics.shape import up_facing, low_edges, nose_sign
from engine.physics.wind_calibration import FF_STRENGTH_PER_MS, ff_seed
assert "sim" in KINDS, KINDS
print("RESERVED", RESERVED, "LIST_FIELDS", LIST_FIELDS, "SINGLE_FIELDS", SINGLE_FIELDS)
print("compile_scene", inspect.signature(compile_scene))
print("BuildContext", [f for f in BuildContext.__dataclass_fields__])
print("sim blocks at HEAD:", Catalog.load().ids("sim"))
print("ok")
```

  Expected: `sim` is in `KINDS`, `RESERVED == ("audio",)`, `LIST_FIELDS == {"effects": "effect"}`, no
  sim blocks, then `ok`. **At HEAD a `sims` key is neither reserved nor validated**, so a hand-written
  one would be silently ignored. Task 95's first test pins that gap.
- [ ] **Step 2: Failing tests.** Create `engine/tests/test_blender_pin.py`:

```python
import subprocess
import pytest
from engine.blender_cli import BLENDER
from engine.blender_pin import PINNED_BLENDER, parse_version
from engine.tests.conftest import requires_blender


def test_parse_version():
    assert parse_version("Blender 5.0.1\n\tbuild date: 2025-12-16") == "5.0.1"


@pytest.mark.blender
@requires_blender
def test_installed_blender_is_the_pinned_build():
    out = subprocess.run([BLENDER, "--version"], capture_output=True, text=True, timeout=120).stdout
    assert parse_version(out) == PINNED_BLENDER, "Blender changed: re-probe (Task 94) and re-grade before moving the pin"
```

  Then add to `harness/tests/test_budget.py`:

```python
from harness.budget import BakeBudget, BudgetExceeded, MAX_BAKE_MIN


def test_bake_budget_reserves_before_and_never_refunds():
    b = BakeBudget()
    b.reserve_s(60 * 30)
    with pytest.raises(BudgetExceeded):
        b.reserve_s(60 * MAX_BAKE_MIN)
    assert b.used_s == 1800


def test_owner_ok_lifts_the_cap_but_still_counts():
    b = BakeBudget(owner_ok=True)
    b.reserve_s(60 * (MAX_BAKE_MIN + 60))
    assert b.used_s == 60 * (MAX_BAKE_MIN + 60)
```

  And `engine/tests/test_bake_lock.py`: a second `machine_lock(timeout_s=0.2)` while the first is held
  raises `LockBusy`; a lock file whose recorded pid is dead is taken over; the lock path is
  `var/bake/.lock` under the repo root.
- [ ] **Step 3: Run them.** Expected: FAIL (no modules).
- [ ] **Step 4: Implement.**
  - `engine/blender_pin.py`: `PINNED_BLENDER = "5.0.1"` plus `parse_version(text)`, a regex on
    `Blender (\d+\.\d+\.\d+)`. Put the decision paragraph above in its docstring.
  - `BakeBudget` in `harness/budget.py`: seconds-based, `MAX_BAKE_MIN = 90` (eng); `reserve_s(n)`
    raises `BudgetExceeded` over the cap unless `owner_ok`.
  - `engine/bake/lock.py`: `msvcrt.locking` on Windows and `fcntl` elsewhere. The pid is written into
    the file.
- [ ] **Step 5: Run** the three test files, the fast loop and the frozen baseline gate.
- [ ] **Step 6: Commit**

```bash
git diff --cached --name-only
git commit -m "feat(bake): pin Blender 5.0.1, bake budget and machine-wide bake lock (phase 6 T93)" -- engine/blender_pin.py engine/tests/test_blender_pin.py engine/bake/__init__.py engine/bake/lock.py engine/tests/test_bake_lock.py harness/budget.py harness/tests/test_budget.py
```

### Task 94: Blender 5.0.1 simulation API probe (decides every cache format)

**Files:**
- Create: `engine/bake/formats.py`, `engine/tests/test_sim_api_probe_blender.py`,
  `engine/tests/fixtures/sim/make_props.py` (a headless script that builds the test props)

The probe replaces guesses with facts, the way phase 5 probed node idnames and NLA APIs. Each test is
`@pytest.mark.blender`. Tests that bake more than 30 s are also `slow`. They run small scenes, render
nothing, and write their measurements to `var/probe/sim_api.json`.

- [ ] **Step 1: Test props, procedural and CC0 by construction.** `make_props.py` writes GLBs into
  `var/fixtures/sim/`:
  - `can.glb`: a closed cylinder, 66 mm × 122 mm, with metal and label zones;
  - `glass.glb`: a **single-sided** tumbler, 80 mm × 95 mm, with a 0 mm wall, to exercise the thick
    shell;
  - `plate.glb`: a 0.5 m × 0.3 m × 4 mm prop pane for `shatter`;
  - `cube.glb`: a 0.1 m cube.

  The props are regenerated when missing and never committed.
- [ ] **Step 2: Write the probe tests** (each asserts **and** records):
  1. **Bullet by `frame_set`.** A cube falls 0.5 m onto a passive plane. Stepping `scene.frame_set(f)`
     from `point_cache.frame_start` to the end gives monotonic z until contact, and the resting z is
     within 1 mm of 0.05 m. Run it twice and assert the transforms are **bit-identical** (R3:
     determinism on the bake machine). Also record whether `bpy.ops.rigidbody.bake_to_keyframes` works
     headless under `bpy.context.temp_override(...)`: it is the fallback path.
  2. **Cloth → PC2 → Mesh Cache.** Step a 20 × 20 pinned cloth. Write the evaluated vertices each frame
     to PC2 with `struct`: a 32-byte header, then little-endian float32 xyz. Build a fresh plane with a
     `MESH_CACHE` modifier (`cache_format='PC2'`) and check its evaluated vertices equal the recorded
     ones to 1e-6 at 3 frames, **with a frame offset** (record the modifier's `frame_start` semantics).
     Record whether deformation motion blur sees the modifier (`vertex velocity` via
     `use_motion_blur`).
  3. **GN simulation zone baked to disk.** A zone with a gravity point cloud and a `velocity` attribute,
     using a NodesModifier bake with `bake_target='DISK'` and `bake_directory` set. Bake it through the
     operator under `temp_override`, then open a fresh scene with the same node tree pointing at the
     directory. Check that frames 1, 40 and 20 (out of order) read the baked positions with no
     re-simulation. Record how a **frame offset** is applied: the Bake node's frame, or a `Time`
     remap. If there is no offset API, record that GN sims start their pre-roll at frame 1 of the bake
     scene and the render scene maps clip frames by an offset.
  4. **Mantaflow gas → VDB.** Domain `resolution_max` 32, a smoke flow, `cache_type='ALL'`,
     `cache_data_format='OPENVDB'` and `cache_directory` set; run `bpy.ops.fluid.bake_all()` under
     `temp_override(object=domain, active_object=domain)`. Assert the `.vdb` files exist and list them.
     Load the sequence into a new Volume object with `is_sequence`, `frame_offset` and
     `sequence_mode='CLIP'`. Check that the grids include `density` and `velocity`, and record
     `velocity_grid`, `velocity_scale` and `velocity_unit` (R7). Record the bake seconds.
  5. **Mantaflow liquid → Alembic.** Domain `resolution_max` 32, an inflow, `use_mesh=True`,
     `use_speed_vectors=True`, bake, then `bpy.ops.wm.alembic_export` of the domain's evaluated mesh.
     Import it with a `MESH_SEQUENCE_CACHE` modifier and record the velocity attribute name the cache
     exposes (`CacheFile.velocity_name`, `velocity_unit`) and the frame-offset controls
     (`CacheFile.frame_offset` / `override_frame`). If Alembic loses velocity, record it: the fallback
     is Mantaflow's own mesh cache read in place with `cache_type='ALL'` and matching settings.
  6. **Force-field seed and strength.** A WIND field with `seed=200` is rejected or clamped (confirm the
     R3 range). Record how `strength` scales the drift of a legacy particle over 1 s: this is the input
     to T107's calibration.
- [ ] **Step 3: Run** `py -m pytest engine/tests/test_sim_api_probe_blender.py -q -m "blender"`, then
  `-m "blender and slow"`. Serialise: nothing else may bake or render while this runs.
- [ ] **Step 4: Write `engine/bake/formats.py`.** It holds constants and small pure helpers only, built
  from the measurements:
  - `FORMATS = {"rigid_keys": ..., "cloth_pc2": ..., "gn_disk": ..., "gas_vdb": ..., "liquid_abc": ...}`,
    each with `offset_mode`, `velocity`, `operator_override` and `probed="5.0.1 2026-09-xx"`;
  - `pc2_header(n_verts, start, rate, n_samples)` and `pc2_frame_bytes(verts)` (pure, stdlib `struct`).

  The docstring cites the probe test for each fact. If a probe **fails** (for example, Alembic drops
  velocity), switch that format to the recorded fallback and say so in the docstring. If **no** path
  works for a method, stop and report: that method's lane is blocked (see Blockers).
- [ ] **Step 5: Pure test** `engine/tests/test_bake_formats.py`: a PC2 header round-trips through
  `struct.unpack`, and `FORMATS` names exactly the five methods.
- [ ] **Step 6: Commit**

```bash
git diff --cached --name-only
git commit -m "test(bake): probe the Blender 5.0.1 sim cache APIs and pin one format per method (T94)" -- engine/bake/formats.py engine/tests/test_sim_api_probe_blender.py engine/tests/test_bake_formats.py engine/tests/fixtures/sim/make_props.py
```

**Chunk 0 gate:** fast loop green, frozen baseline 90/90, probe tests green (the slow ones included), and
`FORMATS` filled.

---

## Chunk 1: The sim contract, the bake stage and collision shells

### Task 95: `sim` manifest contract, the `sims` script field and the sim checker rules (pure) [parallel A]

**Files:**
- Create: `engine/sim_rules.py`, `engine/physics/sim_facts.py`, `engine/tests/test_sim_contract.py`,
  `engine/tests/test_sim_rules.py`, `engine/tests/test_sim_facts.py`
- Modify: `engine/catalog.py` (the sim manifest validator), `engine/script.py` (the `sims` shape),
  `engine/checker.py` (call `check_sims` beside `check_weather`)

- [ ] **Step 1: Failing contract tests.** In `engine/tests/test_sim_contract.py`:

```python
import copy
import pytest
from engine.catalog import Catalog, CatalogError
from engine.script import validate_and_repair
from engine.tests.test_director_package import _p   # profile loader used across phase-5 tests

SIM = {"id": "_t", "kind": "sim", "description": "test", "params": {
          "timeScale": {"type": "number", "min": 0.1, "max": 1.0, "default": 0.5}},
       "subjectSizeM": [0.03, 30.0], "aspects": ["9:16", "16:9", "1:1", "4:5"], "costWeight": 2.0,
       "tags": {"mood": [], "energy": [], "palette": []}, "tierMax": "T4", "directorSelectable": False,
       "capabilities": ["rigid.scatter"],
       "physics": {"taxonomy": ["RB-05"], "state": "baked", "touchesSubject": True, "windDriven": False,
                   "timeScaleParam": "timeScale", "bakeCostS": 0},
       "bake": {"method": "rigid_keys", "costClass": "medium", "prerollS": 0.5, "maxFrames": 240,
                "estimateS": 120, "cacheMBMax": 20}}


def test_sim_manifest_requires_baked_state_bake_object_and_time_scale(tmp_path):
    from engine.catalog import check_manifest          # the validator phase 5 extended (check its name at HEAD)
    check_manifest(SIM, "sim/_t")
    for broken in (("physics", "state", "stateless"), ("physics", "timeScaleParam", None),
                   ("bake", "method", "bogus"), ("bake", "costClass", "huge")):
        m = copy.deepcopy(SIM); m[broken[0]][broken[1]] = broken[2]
        with pytest.raises(CatalogError):
            check_manifest(m, "sim/_t")


def test_sims_key_is_validated_not_ignored():
    cat = Catalog.load()
    s = copy.deepcopy(_committed_studio_script())       # helper: any committed fallback script
    s["sims"] = [{"id": "no_such_sim", "params": {}, "startS": 0, "endS": 2}]
    _, issues = validate_and_repair(s, cat)
    assert any(i.code == "unknown_id" and i.path.startswith("sims[0]") for i in issues)


def test_a_script_without_sims_is_byte_identical_after_the_change():
    cat = Catalog.load()
    s = _committed_studio_script()
    out, _ = validate_and_repair(s, cat)
    assert "sims" not in out
```

  Write `_committed_studio_script()` in the test file: it loads one script from
  `engine/director/examples/` (check the file names at HEAD). Use the existing unknown-id issue code
  (check its spelling in `engine/script.py::_block`). `check_manifest` may have a different name at
  HEAD (`_check_manifest`); use whatever `Catalog.load` calls.
- [ ] **Step 2: Failing rule tests.** In `engine/tests/test_sim_rules.py`, with synthetic manifests in a
  temporary catalog (copy the fixture pattern `test_weather_rules.py` uses):
  - `sim_window`: `startS < 0` or `endS > durationS` is **repaired**, clamped to the clip.
    `bake_range(s, ref, manifest)` returns `(first_frame, last_frame, preroll_frames)` with
    `preroll = ceil(prerollS × fps)` and `last ≤ ceil(endS × fps) + 1`. A zero-length window is an
    **error**.
  - `sim_budget`: two refs with `costClass == "heavy"` give an **error**; one heavy and one medium
    pass.
  - `time_scale_range`: a value outside the manifest range is **repaired** (clamp). A `weather` effect
    whose time scale is not 1.0 still fails with `time_scale_weather` (existing code, untouched).
  - `sim_spawn_in_subject`: a sim that declares `physics.spawnZone`
    (`{"kind": "above", "heightFrac": 1.5, "radiusFrac": 0.6}`) intersecting bounds × 1.1 gives an
    **error**, using the same maths as `weather_rules.spawn_in_subject`.
  - `sim_needs_world` and `sim_needs_profile`: `requiresWorld` / `requiresProfile` unmet →
    **error**. `pipeline.py` maps both to `unsupported` in Task 120 (the phase-5 amendment for Task 85
    says HEAD's `direct()` does **not** map errors to unsupported by itself).
  - `sim_param_wind`: a sim param named like wind (`windSpeed`, `windDir`, `gust*`) gives an
    **error**, reusing the `wind_param_on_effect` regex.
  - Coupling: a sim may declare `physics.couplings`, and the coupled blocks are added through the
    existing `coupled_added` machinery (a sim can couple an effect, never another heavy sim).
- [ ] **Step 3: Failing fact tests.** In `engine/tests/test_sim_facts.py`, using
  `engine/tests/shape_profiles.py`'s synthetic `bottle` and `bare_tube`:
  - `container(profile, markers)` returns `{"opening": [x, y, z], "radiusM": r, "confidence"}` from a
    marker whose text matches `opening|rim|top|mouth`, else from the top-most up-facing ring when the
    top ring's radius is ≥ 0.6 × the body radius (`confidence: "low"`), else None.
  - `fill_line(profile, markers)` takes a marker's z when present, else the default `"full"` at 0.85 ×
    height (PHASING §2: markers first).
  - `emitters(profile, markers)` takes marker points first, then detail points of kind `emissive` /
    `exhaust`, with confidence.
  - `nose_sign(profile, markers)` takes a marker labelled front/nose as `high`, else defers to
    `engine/physics/shape.nose_sign`.
  - `pile_zone(profile)` is the ground annulus between 1.05 × and 1.6 × the footprint radius, used by
    `rigid_scatter zone=around`.
- [ ] **Step 4: Run them.** Expected: FAIL.
- [ ] **Step 5: Implement.**
  - **Catalog.** For `kind == "sim"`, require:
    - `physics.state == "baked"`, except for blocks with `bake.method == "none"` (the stateless sim
      kind, `debris_float`, `flag`);
    - a non-null `physics.timeScaleParam` that names a param, unless the method is `none`;
    - a `bake` object with `method` in `FORMATS` plus `"none"`, `costClass` in
      `("cheap", "medium", "heavy")`, and `prerollS`, `maxFrames`, `estimateS` and `cacheMBMax` as
      positive numbers;
    - an optional `physics.spawnZone`.

    Keep `Catalog.load` accepting an empty `engine/blocks/sim/` folder.
  - **Script.** `sims` must be a list of ≤ 3 objects of `{id, params, startS, endS}`, each run through
    `_block(ref, "sim", f"sims[{i}]", ...)`. `startS` and `endS` must be finite numbers.
  - **Rules.** `engine/sim_rules.py::check_sims(s, catalog, profile, issues)` is called from
    `engine/checker.check` right after `check_weather`. Register every new code in `engine/gates.py`
    **in this task**: Chunk 1 is sequential, so there is no registry conflict yet. Give every new
    **error** an `ERROR_HINTS` entry in `engine/director/repair.py` (a binding phase-5 amendment).
- [ ] **Step 6: Run** the three new files, `test_gates_registry.py`, `test_director_repair.py`, the fast
  loop and the frozen baseline gate. Expected: green, with baseline 90/90.
- [ ] **Step 7: Commit** only the task's files, with the message
  `feat(sim): sim manifest contract, sims script field, sim checker rules and pure sim facts (T95)`.

### Task 96: Bake key, cache store and the sim window (pure) [parallel A]

**Files:**
- Create: `engine/bake/key.py`, `engine/bake/store.py`, `engine/bake/window.py`,
  `engine/tests/test_bake_store.py`

- [ ] **Step 1: Failing tests.**

```python
import json
import pytest
from engine.bake.key import bake_key
from engine.bake.store import BakeStore, CacheCorrupt
from engine.bake.window import bake_frames

REF = {"id": "rigid_scatter", "params": {"count": 150}, "startS": 1.0, "endS": 4.0}
ENV = {"seed": 7, "profileKey": "abc", "modelSha": "m1", "blender": "5.0.1", "blockSha": "b1",
       "wind": {"speedMs": 0}, "motion": {"id": "static"}, "ground": "studio"}


def test_key_is_stable_and_ignores_tier_and_key_order():
    k = bake_key(REF, ENV)
    assert k == bake_key(json.loads(json.dumps(REF)), dict(reversed(list(ENV.items()))))
    assert len(k) == 64


@pytest.mark.parametrize("field,val", [("seed", 8), ("blender", "5.2.0"), ("blockSha", "b2"),
                                       ("modelSha", "m2"), ("motion", {"id": "drop_settle"})])
def test_every_input_changes_the_key(field, val):
    assert bake_key(REF, {**ENV, field: val}) != bake_key(REF, ENV)


def test_store_is_atomic_verified_and_prunes_lru(tmp_path):
    st = BakeStore(tmp_path, cap_bytes=3000)
    with st.writer("k1") as w:
        (w.dir / "a.json").write_bytes(b"x" * 1000)
        w.report({"bakeSeconds": 1.5})
    m = st.read("k1")
    assert m["files"]["a.json"]["bytes"] == 1000 and m["bakeSeconds"] == 1.5
    (tmp_path / "k1" / "a.json").write_bytes(b"y" * 1000)      # tamper
    with pytest.raises(CacheCorrupt):
        st.read("k1")
    for k in ("k2", "k3", "k4"):
        with st.writer(k) as w:
            (w.dir / "a.bin").write_bytes(b"z" * 1000)
            w.report({})
    assert not (tmp_path / "k1").exists() and (tmp_path / "k4").exists()   # oldest-read pruned first


def test_a_crashed_writer_leaves_no_cache(tmp_path):
    st = BakeStore(tmp_path)
    with pytest.raises(RuntimeError):
        with st.writer("k") as w:
            (w.dir / "a").write_bytes(b"1")
            raise RuntimeError("bake crashed")
    assert st.read("k") is None


def test_pinned_caches_are_never_pruned(tmp_path):
    st = BakeStore(tmp_path, cap_bytes=1000)
    with st.writer("gold") as w:
        (w.dir / "a").write_bytes(b"g" * 900); w.report({})
    st.pin("gold", reason="golden G1")
    with st.writer("new") as w:
        (w.dir / "a").write_bytes(b"n" * 900); w.report({})
    assert (tmp_path / "gold").exists()


def test_bake_frames_adds_preroll_without_negative_frames():
    # 30 fps clip, sim 1.0-4.0 s, 0.5 s preroll -> the bake scene starts at 1; clip frame f = bake frame f - 30 + 15
    r = bake_frames(start_s=1.0, end_s=4.0, fps=30, preroll_s=0.5, max_frames=240)
    assert r.bake_first == 1 and r.clip_first == 31 and r.offset == r.clip_first - r.preroll - 1
    assert r.bake_last - r.bake_first + 1 <= 240
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `bake_key`: canonical JSON (`sort_keys`, `separators=(",", ":")`) of `{"ref": REF, "env": ENV}`,
    then sha256.
  - `BakeStore(root=var/bake, cap_bytes=VALORA_BAKE_CACHE_GB × 2^30)`:
    - `writer(key)` writes into `root/.tmp-<key>-<pid>/`. On a clean exit it hashes every file into
      `bake.json` (`{files: {rel: {sha256, bytes}}, ...report}`) and `os.replace`s the folder to
      `root/<key>`.
    - `read(key)` verifies every file's size **and** sha256. Hashing a 4 GB VDB set costs about 10 s,
      which is acceptable per compile, and `read(key, verify="size")` exists for preview loops. It
      updates `lastRead` in `bake.json`.
    - `pin` and `unpin` are recorded in `root/pins.json`.
    - `prune()` runs after every write and removes least-recently-read, unpinned keys until the total
      is under the cap.
  - `bake_frames` returns a small dataclass: `bake_first`, `bake_last`, `clip_first`, `clip_last`,
    `preroll` and `offset`.
- [ ] **Step 4: Run** the file and the fast loop. **Commit** with the message
  `feat(bake): content-addressed bake key, verified atomic cache store with LRU and pins, sim frame window (T96)`.

### Task 97: Collision shells from the upload [parallel A, after T94]

**Files:**
- Create: `engine/physics/proxy.py`, `engine/blender/collision_proxy.py`,
  `engine/tests/test_proxy_rule.py`, `engine/tests/test_collision_proxy_blender.py`

- [ ] **Step 1: Failing pure test** `engine/tests/test_proxy_rule.py`:
  - `voxel_m(profile, purpose)`:
    - `"shell"` → `clamp(0.006 × longest, 0.001, 0.05)`;
    - `"liquid"` → `clamp(0.004 × longest, 0.0008, 0.03)`;
    - `"bullet"` → `clamp(0.01 × longest, 0.002, 0.08)` (all eng; METHODS R5/R6).
  - `thickness_m(profile)` is one shell voxel.
  - `max_tris(purpose)`: shell 20000, liquid 60000, bullet 20000.
  - Check exact values for `pocket_watch` (longest 0.076 m) and `sports_car` (about 4.6 m, read from
    `engine/director/examples/profiles/sports_car.json`).
- [ ] **Step 2: Failing Blender test** `engine/tests/test_collision_proxy_blender.py`
  (`@pytest.mark.blender`). For `sports_car`, `pocket_watch`, `flighthelmet` (non-manifold with
  overlapping parts) and T94's single-sided `glass.glb`, `build_proxy(meshes, profile, purpose)` returns
  `(obj, report)` where:
  - `report.watertight` is True: every edge has exactly 2 faces, checked with `bmesh`;
  - `report.tris ≤ max_tris`;
  - `report.coverage95 ≤ 1.5 × voxel`: the 95th-percentile distance from the profile's
    `surfaceSamples` to the proxy, measured with a BVH;
  - `report.minWallM ≥ thickness_m` on the glass;
  - the upload's `material_digest` is unchanged;
  - the proxy object has `hide_render = True` and `valora_block = "proxy/<purpose>"`.

  `purpose="bullet_hull"` returns ≤ 16 convex hulls for an active subject: a greedy split along the
  principal axes until each part's hull volume ≤ 1.3 × its voxel volume, with a cap.
- [ ] **Step 3: Implement.**
  - Use a Geometry Nodes group, `valora_proxy`: Mesh to SDF Grid (voxel), SDF offset `+thickness`,
    Grid to Mesh, then a decimate modifier to `max_tris`.
  - If the grid nodes are missing on a machine, fall back to the Remesh modifier in VOXEL mode.
  - The shell is **applied** to a new mesh datablock; the upload is never modified. It is cached by
    `BakeStore` under key `proxy:<modelSha>:<purpose>:<voxel>`, as a `.ply` written by a small
    stdlib-free writer inside Blender.
  - The report goes into the bake manifest.
- [ ] **Step 4: Run** both files serially (Blender) and the fast loop. **Commit** with the message
  `feat(sim): closed collision shells, thick shells and convex hulls from the upload, cached and verified (T97)`.

### Task 98: The BAKE stage (stage 4b), end to end on a test sim

**Files:**
- Create: `engine/bake/run.py`, `engine/bake/blender_bake.py`,
  `engine/tests/fixtures/catalog_sim/sim/_test_drop/{block.json,bake.py,build.py}`,
  `engine/tests/test_bake_stage.py` (pure parts), `engine/tests/test_bake_stage_blender.py`
- Modify: `engine/compiler/context.py` (`bake: dict | None = None` at the end of `BuildContext`),
  `engine/compiler/run.py` (`compile_scene(..., bakes=None)`, which bakes when needed),
  `engine/compiler/blender_main.py` (`_refs` yields `("sim", ref)` after effects and before realism;
  `_ctx` passes the bake manifest), `engine/__main__.py` (`bake` subcommand), `harness/look.py` (bake
  first, under the `BakeBudget`)

- [ ] **Step 1: Failing pure tests** (`test_bake_stage.py`):
  - `plan_bakes(script, profile, model, catalog)` returns one `BakeJob` per sim ref that has
    `bake.method != "none"`, with its key (from T96), frame range and estimate.
  - `plan_bakes` of a script without sims is `[]`, and `compile_scene` then behaves exactly as today.
    Mock `subprocess.run` and assert the `job.json` has no `bakes` key.
  - The env passed to `bake_key` includes `profile_key(profile)`, the sha256 of the model file,
    `PINNED_BLENDER`, and the sha256 of the block folder's `bake.py` **and** `build.py`.
- [ ] **Step 2: Failing Blender tests** (`test_bake_stage_blender.py`, `@pytest.mark.blender`), using
  the fixture catalog:
  1. `bake_sims(...)` on a 3 s clip with `sims: [{id: "_test_drop", startS: 0.5, endS: 2.5}]` writes
     `var/bake/<key>/` with `keys.json`, `proxy.ply` and `bake.json` (`bakeSeconds > 0`).
  2. A second call is a cache **hit**: no Blender process starts (mock `subprocess.run`, call count
     0).
  3. `compile_scene(..., bakes=...)` keys the cube from the cache. `compile.json.sims["_test_drop"]`
     reports `{"key", "frames", "fromCache": true}`. The render compile's scene has **no**
     `rigidbody_world`, **no** CLOTH / FLUID modifiers, and no unbaked simulation zone. A new assert in
     `blender_main` raises `SimInCompile` if one is found after `build_all`.
  4. The compile deletes the cache folder mid-way (rename), and `build` raises `BakeMissing`. The host
     never re-bakes silently inside a compile.
  5. Preview and final compiles of the same script reference the **same** key (R9).
- [ ] **Step 3: Implement.**
  - **Host (`engine/bake/run.py`).** `bake_sims(script, profile, model, *, catalog, store=None,
    budget=None, timeout_s=...)`:
    1. `check()`, then `plan_bakes`.
    2. For each miss: `machine_lock()`, then `budget.reserve_s(estimate)`.
    3. Write a `bake_job.json` (script, profile, model, catalog root, ref, frames, cache tmp dir,
       proxy purposes) and run `blender_argv(engine/bake/blender_bake.py, [job])` with
       `capture_output`.
    4. Read `bake_report.json`, and let `store.writer` commit it.

    It returns `{ref_id: manifest}`.
  - **Blender (`engine/bake/blender_bake.py`).** Import and place the subject exactly as
    `blender_main.main` does: reuse `import_subject`, `place_subject` and `rest_animation`. Then build
    only the dependencies:
    - the world's ground (`valora_ground` objects), via a new `ground_only=True` in the world's
      `build(ctx)`, or by building the world and deleting everything not tagged `valora_ground`
      (pick one and document it);
    - the wind field (`ensure_force_field`);
    - the subject motion keys (`key_subject_motion`), so a moving subject is an animated collider.

    Then build the proxies (T97) and call the block's `bake(ctx)`. `ctx.bake` =
    `{"dir": tmp, "frames": ..., "proxy": {...}}`. Set `scene.frame_start` / `frame_end` to the bake
    range (pre-roll included, T96). `bake(ctx)` returns its report; the runner adds `bakeSeconds`
    (`time.perf_counter`) and the proxy report.
  - **Compile.** `compile_scene` calls `bake_sims` first when `plan_bakes` is non-empty, then passes
    `job["bakes"] = {id: manifest_path}`. `blender_main` loads each manifest into `ctx.bake` for the
    sim's `build(ctx)`.
  - **CLI.** `py -m engine bake --script S --profile P --model M [--owner-ok]`.
  - **Look.** `py -m harness look` bakes first (its own `BakeBudget`), then renders ≤ 3 frames.
    `--at` defaults for scripts with sims to before, peak and settled: the window start, the midpoint,
    and the end minus 0.2 s.
- [ ] **Step 4: Run** the new tests (pure, then Blender, serially), `test_compile_*`,
  `test_blocks_complete.py`, the fast loop and the frozen baseline gate. **Commit** with the message
  `feat(bake): stage 4b - host bake runner, headless bake entry, cache-only sim builds, SimInCompile guard (T98)`.

### Task 99: Sim hygiene probes, PH items and the sim block recipe

**Files:**
- Create: `engine/blender/sim_probe.py`, `engine/tests/test_sim_probe_blender.py`
- Modify: `engine/compiler/blender_main.py` (a `simProbe` beside `realismProbe`), `harness/physics.py`
  (PH-03, 04, 05 and 11), `engine/catalog_growth.json` (add `"phase"` and the sim fields to the entry
  schema), `engine/tests/test_catalog_growth.py`

- [ ] **Step 1: Failing Blender test** on the `_test_drop` fixture plus a synthetic bad cache
  (a key file with a point inside the proxy, and one NaN frame):
  - `no_particles_in_subject`: points (or piece centres) inside the proxy SDF are counted per sampled
    frame, using the 5.0 Sample Grid on a `Mesh to SDF Grid` of the shell. It passes when the count is
    ≤ 0.1% of points; the synthetic bad cache fails.
  - `sim_stable`:
    - no NaN or inf;
    - max speed ≤ 3 × `bake.maxSpeedMs` (manifest, eng);
    - for rigid: kinetic energy at the last 10% of frames ≤ 1% of peak;
    - for cloth: max edge stretch ≤ 2.5 × rest;
    - for liquid: mesh volume change ≤ 15% after the inflow stops.
  - `velocity_present`: every moving point geometry has a `velocity` attribute, every Volume has
    `velocity_grid` set, and every Alembic liquid has its `velocity_name` set.
  - `bake_cost`: the manifest's `bakeSeconds` and total bytes, copied into `compile.json.simProbe`.
- [ ] **Step 2: Implement** `sim_probe(scene, meshes, profile, frames, bakes)`, which is report-only
  until calibrated (PHASING R: thresholds before gating). In `harness/physics.py`:
  - PH-03 and PH-04 [C] read `simProbe`;
  - PH-05 compares the measured streak length (motion-blur pass, object-index mask) with `v × shutter`
    within ±40%, report-only;
  - PH-11 logs `bakeSeconds` and `gpuSeconds` per block.
- [ ] **Step 3: Growth contract.** A `catalog_growth.json` entry may carry `"phase": 6` and, for sims,
  `bakeMethod`, `bakeSecondsMeasured`, `cacheMBMeasured` and `golden` (null). The
  `test_catalog_growth.py` rule is extended: a phase-6 director-selectable block needs its taste rule,
  gates, prompts (delivered **and** unsupported), a floor test and a measured bake. Blocks that are not
  director-selectable are exempt until Chunk 7 flips them.
- [ ] **Step 4: Run and commit** (`feat(sim): sim hygiene probes, PH-03/04/05/11 and the phase-6 growth contract (T99)`).

---

## The sim block recipe (used by every block task from here on)

This extends phase 5's block recipe (manifest test first, pure maths first, then build and gates). A
task below gives only what is specific to it.

1. **Manifest test first**, in `engine/tests/test_blocks_phase6.py` (created on first use). Assert the
   params and ranges, `tierMax`, `capabilities`, `physics` (with `taxonomy` ids from TAXONOMY),
   `bake.method`, `costClass`, `maxFrames`, `cacheMBMax` and `estimateS`. Start with
   `directorSelectable: false`; Chunk 7 flips it. Run: FAIL.
2. **Pure maths test first**, in `engine/tests/test_<block>.py`: spawn layout, counts, sizes, time
   scale, domain sizing. Use exact expected numbers from the task. Run: FAIL.
3. **Write `block.json`, the pure module, `bake.py` and `build.py`.**
   - `bake(ctx)` simulates and writes files into `ctx.bake["dir"]` **only**, then returns its report.
   - `build(ctx)` reads `ctx.bake` **only**. It never adds a rigid world, a CLOTH or FLUID modifier,
     or an unbaked simulation zone (the `SimInCompile` guard).
   - Tag every object `valora_block = "sim/<id>"`.
   - Seeds come from `ctx.rng` and `ff_seed`.
   - Real-size scale cues stay real-size.
   - Every moving thing carries velocity (R7).
4. **Blender bake + compile test**, in `engine/tests/test_blocks_phase6_blender.py`. It is
   `@pytest.mark.blender`, and also `slow` when the bake exceeds 30 s. It bakes and compiles with
   `frames="key"` and `render=False`, then asserts the task's `simProbe` conditions:
   `no_particles_in_subject`, `sim_stable`, `velocity_present`, and a cache under `cacheMBMax`.
5. **Measure** `bakeSeconds` and cache MB on the named eval subject. Write them to the register, and
   set `physics.bakeCostS` from the measurement. Never ship a guess as a measurement.
6. **Registry patch (do not apply):** write the `gates.py` codes, the `catalog_growth.json` entry, the
   `TG-` taste rule (with its citation), the prompts (a delivered one, plus an unsupported one when the
   block has `requiresProfile` or `requiresWorld`), the vocabulary flips and the fallback slot into the
   task's register section. The lead applies them in Chunk 7.
7. **Owner golden checkpoint `[render ≤ 3]`.** Run
   `py -m harness look --script <fixture> --profile <subject> --frames 3`. The frames are before, peak
   and settled, from the same bake. Save them under `harness/out/look/sim_<id>/`. Build one
   side-by-side sheet: the reference frame (named in the task) beside ours, in the realism-round sheet
   format (`harness/realism_round.py` SHEETS). Send each sheet in its **own** SendUserFile call, with a
   caption naming the effect. The owner answers with KEEP / CHANGE / STOP.
   - Apply colour and shape asks in **measured steps** (about half the asked shift), then re-check.
   - `golden` stays null until the owner grades KEEP.
   - Pin the bake (`BakeStore.pin`) when it is KEEP.
   - A motion strip is rendered only with the owner's explicit OK (O2).
8. **Commit** only the task's files.

**Lane done-criterion:** every block in the lane passes recipe steps 1–5, has its registry patch
written, and has a checkpoint sheet waiting for the owner. The chunk's full suite and slow bakes are
green, and the frozen baseline is 90/90.

---

## Chunk 2 (lane R): Rigid bodies (cheapest visible win)

### Task 100: `rigid_scatter` [parallel with T101] — golden checkpoint G1

**Subject:** `sneaker`, plus `pocket_watch` for scale. **Reference:** owner ref01 (beans) in
`assets-in/refs/`.

- **Manifest.**
  - `pieces` enum: beans, coffee_beans, ice, gems, coins, pills, candies, pebbles.
  - `count`: 30–500, default 150.
  - `zone` enum: onto (the default), around, behind.
  - `timeScale`: 0.3–1.0, default 0.5.
  - `drop`: 0.3–1.5 × height, default 0.8.
  - `physics.spawnZone` `{"kind": "above", "heightFrac": 1.2, "radiusFrac": 0.6}`;
    `touchesSubject: true`.
  - `bake`: method `rigid_keys`, costClass medium, `prerollS` 0, `maxFrames` 240, `estimateS` 180,
    `cacheMBMax` 20.
  - `requiresWorld {hasGround: true}`; capability `rigid.scatter`.
- **Pure** (`engine/physics/scatter.py`):
  - `piece_size_m(pieces)` gives **real sizes**: beans 0.015, coffee_beans 0.011, ice 0.025, gems
    0.012, coins 0.024, pills 0.012, candies 0.018, pebbles 0.02 m. Scale cues are never scaled with
    the subject.
  - `spawn(params, profile, seed)` gives non-overlapping spawn points: Poisson-disc in a disc of
    radius `radiusFrac × longest` at height `drop`, per zone. `onto` is over the up-facing samples,
    `around` over `sim_facts.pile_zone`, `behind` in a wedge behind the hero pose.
  - Assert that no spawn is inside bounds × 1.1, and that the counts are exact.
  - `count_for(profile)` caps the count so the pile covers ≤ 60% of the zone area.
- **Bake.**
  - Pieces are procedural meshes from `engine/blender/pieces.py`: a bean is a squashed, UV-sphere
    kidney; a coin is a cylinder with a bevel; ice is a rounded cube; a gem is a cut octahedron; a pill
    is a capsule. Each has Principled presets and a seeded 0.85–1.15 size jitter.
  - Bullet: the subject proxy is passive `MESH`, margin 0.001 × longest; pieces are `CONVEX_HULL`
    with margin 3% of the piece size; the ground is passive `BOX`. Substeps 60 and solver iterations
    20 (METHODS RB-05). Friction 0.6 and restitution 0.2 (eng) per preset. `time_scale` =
    `timeScale`.
  - Step with `frame_set` and record loc and quat per piece per frame into `keys.json`, float32 at
    rounding 1e-5.
- **Build.** Instance the same piece meshes (linked data), key them from `keys.json` with LINEAR
  keys (so object motion blur works), and apply the clip-frame offset from the manifest.
- **Probe asserts:**
  - the kinetic-energy decay rule;
  - 0 pieces inside the proxy;
  - no piece below z = −1 mm;
  - `bakeSeconds ≤ 300`.
- **Checker:** the `sim_spawn_in_subject` fixture fails for `zone=onto` with `heightFrac = 0.5`
  (inside the bounds).
- **Registry patch:** a taste rule (restraint: counts under 200 unless the prompt says "raining down";
  a slow time scale for products, METHODS R4) and a prompt like "beans pouring onto the sneaker" →
  `rigid.scatter`. Unsupported: "coins falling" pinned to a world without ground (`studio_cyc` has
  ground; use a float placement) → note "Falling pieces need a floor to land on, so they were left out."

### Task 101: `debris_float` (stateless sim kind, `bake.method: "none"`) [parallel with T100] — G2

**Subject:** `pocket_watch`.

- **Manifest:** `count` 5–60 (default 20), `sizeFrac` 0.02–0.15 (default 0.05), `pieces` enum
  (pebbles, gems, shards, leaves_dry), `timeScale` n/a. Capability `rigid.float_debris`.
- **Pure** (`engine/physics/debris.py`):
  - analytic drift at 1–5% of the subject per second and a spin of 5–20 °/s (RB-07);
  - `path_through_subject` over 12 samples per shot;
  - a phase per piece.
- **Build:** keyed analytic paths (METHODS M-KIN). This proves the `none` path of the contract and the
  `path_through_subject` gate reused for sims.
- **Checkpoint:** 3 frames; the reference is ref12 or the corpus floating-product records.

### Task 102: `shatter` (props only, never the subject) [after T100] — G3

**Subject:** `sneaker` (the subject stays whole). **Prop:** T94's `plate.glb` built procedurally as a
glass pane or ice block.

- **Manifest:**
  - `target` enum: prop_glass (the default), prop_ice, prop_wall;
  - `impact` enum: subject_through (keyed by the existing `slide_in` / `drop_settle` motion), burst;
  - `cells` 20–200, default 60;
  - `timeScale` 0.2–1.0, default 0.4.
  - Capability `destruct.shatter`. `physics.touchesSubject: true`; `requiresProfile: []`. Never the
    subject: the manifest has no subject target, and a checker rule rejects any param that would name
    it.
- **Pure** (`engine/physics/fracture.py`): seeded Voronoi sites, dense near the impact point (radial
  falloff, DS-01). `cells(box, sites)` returns the convex cell planes by half-space intersection.
  Tests: the cell volumes sum to the box volume within 1e-6, and there are no empty cells.
- **Bake:** cut the pane with `bmesh.ops.bisect_plane` per cell (the Cell Fracture extension is not
  bundled; METHODS M-FRAC). Shards are active `CONVEX_HULL` with a tiny margin. The moving subject is
  a kinematic proxy. Bullet as in T100, then `keys.json`. Glints: shard edges get a bevel weight for
  the render material.
- **Probe:** no shard inside the subject proxy, and the kinetic-energy decay rule.
- **Checkpoint:** 3 frames (before, the impact frame, settled). **Brand-risk note** in the taste rule:
  only when asked, and never as a default reveal.

---

## Chunk 3 (lane P): Geometry Nodes point sims (runners, particles, vehicle spray)

### Task 103: The shared GN point-sim base (`engine/blender/gn_sim.py`)

**Files:** `engine/blender/gn_sim.py`, `engine/physics/gn_sim.py` (pure counts and rates),
`engine/tests/test_gn_sim_blender.py`.

- `ensure_point_sim(name, *, spawn, forces, collide, life, attrs)` builds one node group with a
  Simulation zone. It contains:
  - **spawn by rate:** points per second from a mesh, points or a marker set, seeded;
  - **forces:** gravity, linear drag `k·v`, and wind **from `valora_wind`** (the one group, H4), never
    its own noise;
  - **collision:** push-out along the SDF gradient of the **proxy** grid (Sample Grid, 5.0) and the
    ground plane (z = 0), with restitution and friction params;
  - **ageing and death**;
  - **attributes:** `velocity`, `age` and `size`, always.
- Bake to disk (T94 `gn_disk`) into `ctx.bake["dir"]`. The build reads the same group with the bake
  directory set.
- **Blender test:** 5k points dropped onto a proxy sphere. After the bake, 0 points lie inside the
  proxy, every point has a `velocity` attribute, and out-of-order frame reads match. Measure the bake
  seconds per 10k points per 100 frames and record it (it calibrates `estimateS` for T104–T106).

### Task 104: `runners` and `condensation` [parallel with T105, after T103] — G4

**Subject:** T94's procedural `can.glb`, which needs an owner-sourced real can for grading (O4).
**Reference:** a beverage frame from the corpus (P-M03).

- **`condensation`** (a sim with `bake.method: "none"`; it is stateless):
  - it distributes micro-droplets at 20–60 per cm² on up-facing **and** side samples **below the fill
    line** (`sim_facts.fill_line`), with a fogged-glass roughness change there;
  - droplets are real-size (0.2–1.5 mm);
  - it couples `runners` with count 3 (`physics.couplings`, BLOCKS §3);
  - capability `liquid.condensation`.
- **`runners`** (GN sim, FL-04):
  - it seeds 3–30 drops on the side surface below the fill line;
  - each step: tangential gravity `g − (g·n)n`, stick-slip pauses of 0.1–1 s (seeded), speed 1–10
    cm/s, re-projection with Sample Nearest Surface on the **render mesh's** evaluated copy (read-only)
    or the fine proxy, merging within a radius, and a trail as a wetness attribute;
  - drops that leave a convex edge detach (they become drips, reusing phase-5 `droplets` drips);
  - capability `liquid.run_down`.

  **This closes the phase-5 partial note** (vocabulary `liquid.run_down.partialNote`, updated in
  T118).
- **Requires** `sim_facts.container` (or `upFacing`) at high confidence, else `sim_needs_profile` →
  unsupported with "Water running down surfaces needs a smooth closed shape like a can or bottle."
- **Probe:** runners stay on the surface (distance ≤ 1.5 mm, 99%) and never run upward (dz ≤ 0 per step,
  except for stick jitter ≤ 0.2 mm).

### Task 105: The particle pack: `sparks`, `confetti`, `bubbles` and `embers` [parallel with T104] — G5

Each is small once T103 exists. It is one task with four manifests; the lane may split it across
subagents per block (each touches only its own folder).

- **`sparks`** (PT-08):
  - an emitter at `sim_facts.emitters` or a marker (`effect_needs_source` otherwise);
  - speed 3–15 m/s, gravity, drag, 2–3 ground bounces, and a life of 0.3–1.5 s;
  - emission by age, from about 1800 K blackbody down to dark;
  - rendered as short curves or points with velocity blur (PH-05 applies).
- **`confetti`** (PT-06): a burst impulse, strong drag, flutter torque, 1–3 cm two-sided cards, and a
  mixed metallic/matte palette seeded from the grade palette.
- **`bubbles`** (PT-10): needs a liquid region (a container marker). Rise speed 8–33 cm/s by size,
  zig-zag below 2 mm, grow while rising; glass material.
- **`embers`** (PT-09): an **effect**, stateless (analytic curl drift, flicker). It lives here because
  it shares the palette and emitter facts.
- **Checkpoint:** one sheet per block, one frame each (3 frames total per `look` call). The reference
  is a matching frame from `assets-in/refs` or the corpus.

### Task 106: `tyre_spray` and `dust_kick` (couplings of `drive`) [after T104/T105] — G6

**Subject:** `sports_car` on `rain_courtyard` (wet) and on `golden_field` (dirt/grass).

- These are coupled by `drive` through `physics.couplings` with conditions: wet world or
  `wet_surface` present → `tyre_spray`; world `groundType` dirt, gravel or sand → `dust_kick`. The
  checker adds them as `coupled_added` when the drive's speed is ≥ 15 km/h.
- Emitters come from the `wheels[].contact` points; the source is the rolling contact, whose velocity
  comes from the drive's pose function (`engine/motion_path.py`).
- **`tyre_spray`:** a rooster tail from the rear tyres plus a side sheet, with droplets at 1–4 mm.
- **`dust_kick`:** grains plus a small billow from T111's VDB library once it exists, else from
  points → Points to Volume.
- **Replaces** the phase-5 checker note "Road spray isn't available yet" (Task 79). The T118 registry
  patch removes it.
- **Checkpoint:** one frame of the wet drive and one of the field drive, against v04 (the rain Cayman),
  the owner's reference for wet car shots.

---

## Chunk 4 (lane C): Cloth

### Task 107: The cloth base and the wind force-field calibration (phase-5 deferral)

**Files:** `engine/blender/cloth.py`, `engine/physics/cloth.py`, `engine/physics/wind_calibration.py`
(modified), `engine/tests/test_cloth_calibration_blender.py`.

- **Presets** in the pure module, (eng) and scaled per METHODS R5:
  - silk: mass 0.15, tension 5, bending 0.05, air 1.5;
  - satin: mass 0.25, tension 10, bending 0.2;
  - canvas: mass 0.6, tension 40, bending 5.

  Vertex spacing is about 1% of the subject length, capped at 8k vertices. The collision
  `distance_min` is 0.3–0.5% of `longest`; `quality` is 8–12; self-collision is on for drapes.
- **Calibration test.** A 1 m × 0.5 m silk strip pinned at one edge sits in the one WIND force field
  (`ensure_force_field`) at 2, 5 and 10 m/s. Measure the trailing edge's mean deflection angle after
  2 s. Fit `FF_STRENGTH_PER_MS` so the deflection matches a quasi-static drag model (drag ∝ v²,
  `tan θ = F_drag / W`, with a C_d of about 1.2 for a flapping flag (eng)).
  - Replace the 0.8 (eng) with the fitted value, and add a `windCalibration` block to cloth manifests.
  - The `wind_coherent` probe must pass for cloth at speeds ≥ 1.5 m/s.
  - Record the before and after numbers in the register (the phase-5 register row
    "`FF_STRENGTH_PER_MS` 0.8 … phase-6 cloth for the force field").
- **Frozen check.** No phase-5 consumer reads `force_field_strength` (Task 59 says there are none), so
  the change moves no committed look. Assert this with a scan of `engine/blocks/**/build.py`.

### Task 108: `drape_reveal` [parallel with T109] — G7

**Subject:** `sports_car` (the thin-protrusion risk: mirrors and the aero disc) and `pocket_watch`.
**Reference:** a launch-reveal frame from the corpus.

- **Manifest:**
  - `fabric` enum: silk (the default), satin, canvas;
  - `pull` enum: rear_to_front, side (the default), up;
  - `colour` enum from a restrained set: black, charcoal, ivory, deep_red;
  - `revealS` 1.0–4.0, default 2.0;
  - `timeScale` 0.6–1.0.
  - Capability `cloth.drape_reveal`. `bake`: `cloth_pc2`, heavy for vehicles and medium for small
    subjects (per-profile `costClass` is not supported, so heavy is declared and `sim_budget` counts
    it), `prerollS` 1.5, `maxFrames` 240.
- **Pure:**
  - the sheet is 1.5 × the footprint plus the height;
  - it is pre-shaped from a top-down height map of the surface samples, starting 2 voxels above the
    proxy (SC-02: "start above the proxy + small offset");
  - the pull points are keyed by hook empties along `pull`;
  - it is off-screen by `revealS + 0.5`.
- **Bake:** cloth against the **closed shell**. A thin-protrusion list comes from `parts` boxes with
  an aspect > 6; those are thickened in the proxy only. Pre-roll 1.5 s settles the drape before the
  clip starts.
- **Probe:** max stretch ≤ 2.5; 0 cloth vertices inside the proxy; the sheet is fully off the subject's
  bounds at `revealS + 0.5`.
- **Checker:** `drape_reveal` must start in the first shot, and the first shot's camera must see the
  covered subject (`effect_off_screen` warns otherwise).

### Task 109: `flag` and `silk_ribbon` [parallel with T108] — G8

- **`flag`** (SC-01): a stateless travelling wave (`bake.method: "none"`). The flutter frequency rises
  with the wind speed; the direction comes from WD-01. `hero: true` switches it to cloth (`cloth_pc2`)
  with a pinned pole edge. It is a world prop: `requiresWorld {outdoor: true}`. The
  `wind_implausible` warning under 2 m/s already exists.
- **`silk_ribbon`** (SC-05): stateless by default (a spline around the subject outside the bounds plus
  a margin, a travelling twist, and width modulation at 3–10% of height). `hero: true` → cloth.
- **Checkpoint:** one frame each, plus the owner's reference choice.

---

## Chunk 5 (lane S): Smoke and fire (VDB)

### Task 110: VDB playback infrastructure

**Files:** `engine/blender/vdb.py`, `engine/tests/test_vdb_blender.py`, `engine/assets.py`
(`resolve_sequence`).

- `place_vdb(seq, *, anchor, scale_m, retime, rotate_deg, velocity=True)` builds a Volume object from a
  pinned sequence:
  - `frame_offset` and `sequence_mode` come from T94's facts;
  - velocity grid and scale are set (R7);
  - the density and flame shader is Principled Volume with blackbody from the `flame` / `temperature`
    grid when present.
- **Scale guard:** a plume keeps its physical width. The checker refuses a scale factor above ×3 of the
  sequence's native size (GS-01: "a campfire scaled ×10 reads wrong").
- **Proxy-resolution copies:** `tools/resample_vdb.py` makes a half-resolution copy with the 5.0 grid
  nodes, for previews. The preview tier may pick it (render-side only; the motion is identical because
  it is the same simulation resampled). Document why this does not violate R9: same simulation, same
  timing, only voxel density.
- `engine/assets.py` gains `resolve_sequence(aid)` (a pinned directory with a per-file sha256 list).
- **Blender test:** the T94 probe VDB plays at frames 5, 1 and 9 out of order, has a velocity grid, and
  its bounds scale exactly with `scale_m`.

### Task 111: Our own VDB library, baked once from Mantaflow (CC0 by construction)

**Files:** `engine/blender/gas.py` (the Mantaflow gas bake helper, reused by T113 and T117),
`tools/bake_vdb_library.py`, `engine/assets/manifest.json` (entries), `engine/assets/CREDITS.md` (a
"Valora-baked, CC0" row).

- **Presets** (all (eng) and tuned only through owner grading):
  - `plume_soft`: a ground smoke plume, 2 m domain, res 128, 180 f;
  - `chimney_thin`;
  - `campfire`: fire plus smoke, 1 m domain, res 128, 150 f;
  - `tyre_smoke_burst`: a wide low billow, 6 m domain, res 160, 150 f;
  - `dust_billow`: dust, 4 m domain, res 128, 120 f.
- Use `use_noise` upres ×2 only where it is under the cache cap.
- **Bake:** one command, `py tools/bake_vdb_library.py --preset all --owner-ok`. This is **heavy**,
  about 1–3 h in total (eng), and runs once. It writes into `assets-in/library/valora_vdb/<preset>/`
  (gitignored) and pins the sha256 values in the manifest.
- Every block that uses the library has a procedural fallback (M-VOL noise volume) when the files are
  missing, so tests stay download-free.
- **JangaFX CC0 sequences** can be added later as extra manifest rows (owner download O3). The code does
  not depend on them.

### Task 112: `smoke_plume`, `steam` and `fire` (effects, VDB or stateless) [parallel with T113] — G9

**Subject:** `sports_car` on `night_street` (plume), `camera_01` (steam from a marker), `golden_field`
(campfire). **References:** v03 (night) for the plume, and a corpus frame for fire.

- **`smoke_plume`** (effect, GS-01 ambient): places library plumes behind or around the subject, out
  of bounds × 1.1 (`spawn_in_subject`, existing), retimed and rotated per seed, and drifting with the
  wind (`windCalibration`). Capability `smoke.plume`.
- **`steam`** (effect, GS-02, stateless M-VOL): a thin density above an emitter, rising at 0.2–0.5
  m/s, fading within 10–20 cm, **real size**. Capability `smoke.steam`. It needs an emitter (marker or
  `sim_facts.emitters`).
- **`fire`** (effect, GS-06): the campfire VDB plus a **flicker light**. The point light's intensity is
  seeded noise at 5–12 Hz, or the VDB's emission integral when measured (LM-08: "fire without light
  change" is the failure mode). Capability `fire.flame` (a new tag in T118).
- **Checkpoint:** one frame per block. The owner's realism rule applies: restrained density, and no
  showpiece colours.

### Task 113: `smoke_sim` (interactive Mantaflow gas) and `tyre_smoke` [parallel with T112] — G10

- **`smoke_sim`** (sim, GS-01 interactive and GS-09):
  - a Mantaflow gas domain sized to the subject plus the camera-seen region (≤ 3 × longest), with the
    **closed shell** as an effector obstacle and a moving obstacle when the subject moves;
  - `colour` enum: white, grey (the default), and a small coloured set;
  - `source` enum: ground, marker, tyres;
  - res ≤ 160;
  - `bake` method `gas_vdb`, heavy, `prerollS` 2.0 (the smoke exists before the clip starts), and
    `maxFrames` 180;
  - capabilities `smoke.interactive` and `smoke.coloured`.
- **`tyre_smoke`** (sim, VD-10): the library `tyre_smoke_burst` placed at the rear wheels by default
  (`bake.method: "none"` while it uses the library). `interactive: true` switches it to a `gas_vdb`
  bake with the car as a moving obstacle. It is coupled from a `drive` whose params ask for a burnout
  (a new drive enum value, `launch: burnout`; this is a **drive param change**, so it goes in the
  registry patch and needs the frozen-baseline check). Capability `vehicle.tyre_smoke`.
- **Probe:** 0 density voxels inside the proxy above ε, `velocity_present`, and `sim_stable` (no NaN,
  and the density sum grows smoothly).
- **Measure** bake minutes and GB. If the final-tier render estimate goes over the budget table,
  lower `resolution_max` and not the render samples, and record it.

---

## Chunk 6 (lane L): Liquids (Mantaflow; built-in, no FLIP Fluids)

### Task 114: The liquid base (`engine/blender/liquid.py`, `engine/physics/liquid.py`)

- **Pure:**
  - `domain_for(event, profile)` sizes the domain to the event, never the scene: a pour covers the
    container plus the stream, a splash is 2 × the subject footprint by 1.5 × its height;
  - `resolution_for(domain, voxel_m)` targets a voxel of 1–2 mm for a glass-scale pour (FL-08) and
    caps at 192. When the cap binds, the manifest's `costClass` stays heavy and the report records the
    effective voxel;
  - `time_scale` defaults 0.1–0.2 for hero liquids (R4, P-M02).
- **Blender:**
  - FLIP (APIC as an option), `use_mesh` with `mesh_scale` 2, `use_speed_vectors` on (R7);
  - obstacles are the **thick shell** (T97 `liquid` purpose), so single-sided glass does not leak;
  - inflow along a seeded curve (for pours);
  - spray and foam particles **off** in phase 6 (cost); record this as a FLIP-Fluids trigger if the
    owner grades whitewater as missing;
  - after the bake, export the mesh to Alembic (T94) and **delete the particle data** from the cache
    to stay under `cacheMBMax`.
- **Materials:** water, soda (with T105 bubbles as an option), juice, milk (subsurface), coffee, wine,
  oil. All are Principled with measured IOR 1.33–1.47 (eng) and absorption colour by depth.
- **Blender test (slow):** a 0.1 m cube of water falls into a 0.2 m open box proxy at res 64. The mesh
  volume is conserved within 15% after settling, nothing is inside the box walls, Alembic plays out of
  order, and velocity is present.

### Task 115: `liquid_splash` (the subject drops into liquid) — G11

**Subject:** `sneaker` or `pocket_watch` with `drop_settle` into a pool (a world prop: a shallow tray),
or a `crown` mode onto a thin film. **Reference:** owner ref12 or ref01 (liquid frames).

- **Manifest:**
  - `mode` enum: drop_in (the default), crown, wave_hit;
  - `liquid` enum as in T114;
  - `timeScale` 0.1–0.4, default 0.15;
  - `requiresMotion ["drop_settle", "toss_tumble"]` for `drop_in`. **New:** a sim may name the
    motions it pairs with; the checker enforces this with `sim_needs_motion`, registered here.
- The subject's **keyed motion drives an animated obstacle** (proxy parented to `valora_motion`).
  `bake` is `liquid_abc`, heavy, `prerollS` 0.3, `maxFrames` 150.
- **Probe:** volume conservation, no liquid inside the subject proxy, and `bakeSeconds` recorded.
- **Checkpoint:** before, impact and crown. **Grade gate:** this is the first FLIP-Fluids decision
  point (see T117).

### Task 116: `liquid_pour` (into a container) — G12

**Subject:** T94's procedural `glass.glb` (single-sided on purpose), and a real licensed glass or bottle
for the owner's grading (O4).

- **Requires** `sim_facts.container` at high confidence (a marker on the rim) plus `fill_line`,
  otherwise it is unsupported with "Pours need a marked opening to pour into, so the pour was left
  out."
- The stream starts above the opening. The inflow stops at the fill line (the stop time is computed
  from the interior volume, which is computed from the thick shell's inner cavity).
- `timeScale` 0.2. An optional T105 `bubbles` coupling for soda.
- **Probe:** the liquid stays inside the inner cavity (≤ 0.5% of the mesh volume outside after the
  stream ends), and volume conservation.

### Task 117: `viscous_flow` and `ink_cloud` — G13, plus the FLIP-Fluids decision point

- **`viscous_flow`** (FL-14): Mantaflow liquid with `use_viscosity`, honey, caramel, chocolate and
  paint presets (viscosity base and exponent (eng)), dripping over the subject's top surface or pouring
  onto it. The ref12 note says grey clay-like fluid reads as real without texturing, so the materials
  stay simple.
- **`ink_cloud`** (FL-13): a Mantaflow **gas** with gravity about 0, low dissipation and vorticity
  0.1–0.5, dark density, and `timeScale` 0.2–0.4, inside a water tank world prop. It reuses T111's
  `gas.py`.
- **FLIP-Fluids decision (owner):** it applies when the owner grades G11, G12 or G13 **CHANGE** for a
  reason built-in Mantaflow can't meet within the budget table: whitewater or foam, thin sheets
  breaking into droplets, or viscosity banding. Then record the reason and the measured res and time,
  and raise Owner decision D2. Do not buy or install anything.

---

## Chunk 7: Director integration (lead only, sequential; applies the lane registry patches)

### Task 118: Vocabulary, capabilities and honest notes

- Apply every lane's vocabulary flips. Each delivered tag keeps its `note` for the unsupported case.
  `liquid.run_down.partialNote` changes from "the subject has still droplets instead" to a
  profile-blocked note, because runners now exist.
- Add `fire.flame`.
- Add the coarse `sim.*` fallbacks' routing, so that `sim.liquid` → `liquid.pour` / `splash` /
  `run_down` by phrase, and `sim.cloth` → `cloth.*`.
- **Tests:** `test_detect` cases for every new phrase, including the phase-5 eval phrases ("liquid
  running down the can", "smoke rolls around the car", "a silk sheet slides off the watch", "sparks
  fly", "confetti falls on the sofa", "burnout").

### Task 119: Output schema, sanitize, rulebook and taste

- `LIST_FIELDS["sims"] = "sim"` in `output_schema.py`. The sims appear only when at least one sim block
  is director-selectable, so a catalog with none produces a byte-identical schema: a test compares it
  with the committed compact schema.
- `sanitize` keeps a schema-valid `sims` list.
- Regenerate the rulebook. Measure the schema and rulebook sizes before and after (register).
- Apply the `TG-` taste rules from the lanes, and add a **restraint rule**: "a sim only when the prompt
  or a marker asks; at most one heavy sim; product time scale slow; never shatter the product".
- Flip `directorSelectable: true` **only** for blocks whose lane finished recipe steps 1–5.

### Task 120: Fallback, adherence and the unsupported mapping for sims

- **`pipeline.py`:** `sim_needs_world`, `sim_needs_profile`, `sim_needs_motion` and
  `effect_needs_source` for sims become `unsupported` lines carrying the block's `profileNote` or
  `note` (the Task-85 mapping extended).
- **`fallback.py`:** when a detected capability maps to a selectable sim and the checker passes with
  it, the fallback adds it. It uses the default window (the first `motion` or `hero` shot) and at most
  1 heavy sim.
- **Dice and adherence:** no change. Test that `AXES` is still the frozen 7, that a vague prompt never
  yields `sims`, and that the frozen baseline is 90/90.

### Task 121: Eval prompts and harness recall

- Apply the lanes' `v1.json` prompts: one delivered and one unsupported per sim.
- `director_eval` gains `simDeliveredRecall` and records `sims` in the tier breakdown.
- Run `py -m harness direct --provider fallback-only --runs 3` over the new prompts. Expect
  unsupportedRecall 1.0, and record deliveredRecall (register).

---

## Chunk 8: Cost, farm readiness, finish

### Task 122: Bake cost logging and cache portability

- `compile.json` and `look.json` record `bakeSeconds`, `cacheBytes` and `gpuSeconds` per block (PH-11,
  spec §4.7).
- **`test_bake_portable.py` (blender):** bake `rigid_scatter`, copy `var/bake/<key>` to a temporary
  root, point `VALORA_BAKE_ROOT` at it, compile at frames 12 and 3 (out of order), and assert the same
  piece transforms as from the original root. Also assert the manifest has **no absolute paths**.
- Write the phase-7 hand-off facts:
  - (a) caches ship by key, so workers never simulate;
  - (b) the CPU bake class: measured bake minutes per block against its GPU render minutes;
  - (c) the split between bake-seconds and GPU-seconds.

### Task 123: Finish

- [ ] Ownership re-check. The LLM never writes `realism` or `field`, `wind` only through the schema,
  and `sims` only through the schema.
- [ ] Full suite (`-m "not live"`), then `-m slow` **once, serially**, and compare with the Task 93
  counts.
- [ ] Frozen baseline 90/90.
- [ ] Offline variety (the phase-5 groups). There must be 0 tier regressions and the distances must be
  unchanged, because sims are never rolled.
- [ ] Fill in the calibration register (below). Every number needs its population and date.
- [ ] Owner look list: every `harness/out/look/sim_*` sheet (G1–G13), with its reference and what to
  look for. Every `golden` stays null until graded.
- [ ] Commit the register, then write
  `.handoffs/YYYY-MM-DD-HHMM-renderer-director-phase6-physics-sim-done.md` (`track: renderer-director`)
  and commit it.

---

## Calibration register: every (eng) number this plan introduces

| Number(s) | Where | Calibrated through |
|---|---|---|
| Fast-loop and full-suite counts; HEAD signatures | Task 93 | Task 93 / 123 |
| `MAX_BAKE_MIN` 90; `VALORA_BAKE_CACHE_GB` 60; the per-sim bake and cache caps (budget table) | `harness/budget.py`, manifests | Measured bakes (recipe step 5); Task 122 |
| Voxel rules 0.006 / 0.004 / 0.01 × longest; max tris 20k / 60k; ≤ 16 hulls | `engine/physics/proxy.py` | T97 coverage95 and watertight on 4 subjects |
| Probe thresholds: inside ≤ 0.1%; speed ≤ 3 × max; KE ≤ 1%; stretch ≤ 2.5; volume ≤ 15% | `sim_probe.py` | Report-only until the good and bad fixtures separate |
| Piece real sizes, counts ≤ 60% of the zone, friction 0.6 / restitution 0.2, substeps 60 / iterations 20 | `scatter.py`, `rigid_scatter` | G1 owner grade; KE decay |
| Debris drift 1–5% per second, spin 5–20 °/s | `debris.py` | G2 |
| Voronoi density falloff, `cells` 60 | `fracture.py` | G3 |
| Condensation 20–60 per cm², runner speed 1–10 cm/s, stick 0.1–1 s | `runners`, `condensation` | G4; P-M03 |
| Spark speed, life and blackbody; confetti drag; bubble rise 8–33 cm/s | particle pack | G5; PH-05 |
| Spray and dust thresholds (≥ 15 km/h), droplet sizes | `tyre_spray`, `dust_kick` | G6 vs v04 |
| Cloth presets; `FF_STRENGTH_PER_MS` 0.8 → fitted | `cloth.py`, `wind_calibration.py` | T107 strip test; G7/G8 |
| VDB library presets (domains, res, frames) | `tools/bake_vdb_library.py` | G9/G10; the ×3 scale guard |
| Flicker 5–12 Hz | `fire` | G9 |
| Liquid voxel 1–2 mm, res ≤ 192, time scale 0.1–0.2, IOR and absorption | `liquid.py` | G11–G13; volume conservation |
| Preview volume step rate 4 / max steps 256 / bounces 0 | `tiers.py` | A preview vs final look-check on the same bake |

## Deferred (and why)

- **Character garments and hair** (SC-04, HF-04): phase 8, after the Blender 5.2 re-evaluation.
- **Soft-body `jiggle`** (SC-07) and a cloth-pressure `soft_rest` upgrade: the stateless `soft_rest` and
  `dangling_sway` realism blocks already cover the common case. Revisit after corpus counts.
- **Powder burst** (PT-12), **dry-ice fog pour** (GS-05), **ocean / underwater worlds** (FL-12, FL-15):
  backlog, ordered by `py -m corpus backlog`.
- **Liquid spray, foam and bubbles (whitewater):** off in phase 6 because of cost. Turning them on, or
  FLIP Fluids, is the D2 decision.
- **Sims in the dice:** never by default (the owner's realism direction). Revisit only if the owner asks
  for surprise effects.
- **Farm-side bake workers:** phase 7. This plan only makes caches portable and measures bake-seconds.

## Owner-only items

- **O1 Grading** G1–G13 (KEEP / CHANGE / STOP per sheet) and flipping `golden`.
- **O2 Motion strips.** Physics is judged in motion, but `RenderBudget` caps a look at 3 frames. The
  recommendation: for each graded sim, one 540p preview-tier strip of its window (about 60–120 frames,
  same bake). It runs only on the owner's explicit go per strip.
- **O3 Downloads** (never scripted): JangaFX CC0 VDBs (6+ GB; optional, because T111 bakes our own), and
  Between Two Pines smoke (read the Gumroad licence first).
- **O4 A real, licensed beverage can and glass** for grading T104, T116 and T117. Tests use procedural
  props.

## Decisions for the owner

- **D1 Blender:** stay on 5.0.1 (recommended; see the Decision section). Re-evaluate at phase 8.
- **D2 FLIP Fluids licence:** only if G11–G13 get CHANGE for a reason Mantaflow can't meet within the
  budget table (T117 records the evidence).
- **D3 Strip budget** (O2): allow a per-sim 540p strip for grading. The recommendation is yes, one per
  sim, on request.
- **D4 Cache disk:** the 60 GB default for `var/bake` (826 GB free today). Raise it only if golden pins
  crowd it out.

## Blockers

1. **Motion can't be graded on 3 stills.** Without D3, golden grades for sims rest on before, peak and
   settled frames only. That is a weak signal for timing and weight (PH-09).
2. **No container subject among the 9 eval models.** Runners, condensation, pours and bubbles are
   tested on procedural props. The owner's grade needs a real licensed can or glass (O4).
3. **Blender 5.0.1 gets no fixes.** A Mantaflow or Bullet crash that T94 can't route around blocks that
   method's lane. The only way out is a side-by-side 5.2 probe (Decision point 4).
4. **Heavy bakes serialise on one CPU.** Liquid and gas grading rounds cost 0.5–1.5 h of bake each, so
   iteration on lane L is slow by nature. Budget owner rounds accordingly.
5. **The Task 93 baseline depends on the in-flight full `pytest` run.** Do not start Chunk 1 until its
   counts are recorded.

## Done when

- The full suite has no new failures against the Task 93 baseline; the slow sim bakes are green, run
  once and serially; the frozen baseline is **90/90** at every chunk end.
- Every sim bakes once, and the preview and final compiles read the same key. A compile never
  simulates (`SimInCompile`), and a copied cache renders the same frames out of order (Task 122).
- Every sim block has measured `bakeSeconds` and cache MB, passes its probes, and has an owner sheet
  waiting (G1–G13). `golden` flips only on KEEP.
- The director can ask for each selectable sim through the schema only. A vague prompt never yields a
  sim. unsupportedRecall is 1.0 on the new prompts.
- No render exceeded 3 frames per invocation without the owner's OK, and no bake exceeded `BakeBudget`
  without `--owner-ok`.
