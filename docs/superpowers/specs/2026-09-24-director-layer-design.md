# Director Layer — any model + any prompt → a unique, high-quality video

    date:     2026-09-24
    track:    renderer-engine
    status:   APPROVED by owner 2026-09-24 (approach A: catalog + AI director, plus §9a research corpus)
    builds on: docs/superpowers/specs/2026-09-19-renderer-engine.md (the "engine spec")
              docs/superpowers/plans/2026-09-20-renderer-engine-rendering.md

The engine spec describes the whole renderer. This document designs one part of it in
detail: the **director layer**. That is the "default script and parameters for the AI API"
the owner asked for. It turns an uploaded model plus a short prompt into a scene script
that Blender/Cycles renders. Engine-spec sections not repeated here still apply.

---

## 1. Goal, in the owner's words (2026-09-24)

> "The goal is to make somewhat of a Higgsfield but instead it's with 3D models they put in.
> The user describes what they want, every render is unique and high quality … make a good
> enough default script to the point where the AI API the user prompts to, when looking at
> the script, knows what to do and how, and no matter what type of vague and short prompt it
> is I still want it to be amazing because most people testing aren't going to write an
> essay … and maybe have an option where it asks questions … but we just need to perfect
> that default script and set parameters for the API. And lastly this same rendering
> software is being used in ModVision, but ModVision only uses the cars it has on the site."

**Success means**, for any uploaded model:

1. **A near-empty prompt still yields a finished-looking clip.** Examples: `""`,
   `"make it look cool"`, `"ad"`.
2. **The same model and prompt, run twice, gives two clearly different videos.**
3. **No shipped video has a visible defect.** No clipping camera, no floating subject, no
   subject off-screen or out of focus, no black or blown frames, no flicker.

---

## 2. Owner decisions, 2026-09-24 (SETTLED)

| # | Decision | Resolves engine-spec §13 |
|---|---|---|
| D1 | **Valora3D first.** ModVision adopts the same director later, with its catalog restricted to its fleet and its car-only blocks (driving rig, wheel shots). | Q1 |
| D2 | **Any subject.** Products, furniture, vehicles, characters — "legit any 3D model". The eval set must span all of them. | Q6 |
| D3 | **The AI writes a full scene script for every prompt.** Anything the prompt leaves out, the AI decides for the user. | — |
| D4 | **Every render is unique** (see §6). "More like this" is an opt-in. | — |
| D5 | **Default output is vertical 9:16, 8–12 s**, when the prompt says nothing about format. | — |
| D6 | **Approach A.** The AI picks and tunes blocks from a tested catalog and never writes code in v1. A free-form `bpy` escape hatch (approach B) comes later. | Q4 (v1 = catalog only) |
| D7 | **Rendering runs on rented GPU servers.** Frames are split across machines. | — |
| D8 | **A "clarifying questions" mode comes later.** The answers become extra prompt text; the design leaves a slot for them (§4.2 `assumptions`). | — |

**Not decided, so v1 does not do it:**
- AI-generated backgrounds (engine-spec Q3). v1 renders every pixel in Cycles.
- Credit re-pricing (Q5). Held until §9 measures cost per clip on rented GPUs.

**Engineering calls made in this doc** (engine-spec Q2/Q7, owner may overrule):
- product-render seeds the compiler; render-studio's look work is ported in as blocks (§4.5).
- ModVision's `beauty-render` scheduled task and render-studio are **not touched**.

---

## 3. Pipeline

```
upload.glb ──► 1 INGEST ──► SubjectProfile ─┐
                                            ├─► 3 DIRECTOR (LLM) ──► scene script
prompt ──► 2 CREATIVE DICE ──► direction ───┘           │
          (+ variety memory)                            ▼
                                               4 CHECKER ──(errors)──► back to 3, max 2×
                                                        │ pass          then safe fallback
                                                        ▼
                                               5 COMPILER (Blender) ──► .blend scene
                                                        │
                                   ┌────────────────────┴───────────────────┐
                                   ▼                                        ▼
                             6a PREVIEW tier                          6b FINAL tier
                          (fast, low res, 1 GPU)            (frame ranges across N GPUs)
                                   │                                        │
                                   └───────────► 7 FRAME QC ◄───────────────┘
                                                   │ pass          fail → re-render range / reroll
                                                   ▼
                                               8 ENCODE (colour-tagged MP4)
```

**Who does what:**

- **Deterministic code** does stages 1, 2, 4, 5, 7 and 8. **The LLM does stage 3 only.**
- **Variety comes from the dice (stage 2), not the LLM.** An LLM asked twice tends to give
  the same safe answer, so the system rolls the dice and hands the LLM a direction.
- **The LLM's output is data** (a JSON script), never code.

---

## 4. Components

Everything lives in a new top-level `engine/` package in this repo. It is Python, because
stage 5 runs inside Blender and sharing one language keeps schema, checker and compiler in
agreement. ModVision consumes it later (D1).

### 4.1 Ingest → `SubjectProfile`

Runs headless in Blender with the flags product-render already uses:
`--background --factory-startup --disable-autoexec`.

It measures the upload and **trusts no names**. It returns:

- **True size** in metres. It corrects unit mistakes with the plausible-size logic from
  `apps/web/lib/scene/inferUnits.ts`, and **never normalises to 1 m**. That fixes the scale
  loss in `render_product.py:111-152`, the engine spec's §4.3 blocker.
- **Up axis, likely facing, ground-contact plane**, and the bounding box and centre.
- **Material classes, judged by properties**: metallic, glossy, rough, glass
  (transmission), emissive, fabric-like (rough and non-metal), skin-like
  (subsurface). Per-material coverage share.
- **Rig and animation**, whether each is present, plus polygon count and texture memory.
- **Category hint** such as "small product" or "vehicle-like". It is only a hint (engine
  spec §4.2). It shifts taste weights and **never unlocks or blocks a feature**.

### 4.2 Scene script — `valora.scene/1`

One JSON document describes the whole video. Every `id` names a catalog block (§4.3), and
every number must sit inside the range that block declares.

```jsonc
{
  "schema": "valora.scene/1",
  "seed": 184467,
  "direction": { "id": "neon-night/low-hero/slow", "source": "dice" },
  "prompt": "make it look cool",
  "assumptions": ["no format given → 9:16, 10 s", "no mood given → dice: neon night"],
  "format":   { "aspect": "9:16", "durationS": 10, "fps": 30 },
  "subject":  { "placement": "ground", "motion": { "id": "static" }, "finishOverrides": [] },
  "world":    { "id": "night_street", "params": { "wetness": 0.6, "neonHue": 285 } },
  "lighting": { "id": "rim_neon", "params": { "keyAzimuthDeg": 140, "rimStrength": 1.4 } },
  "shots": [
    { "startS": 0,   "endS": 4.5, "camera": { "id": "low_hero_push",
      "params": { "lensMm": 35, "fstop": 2.8, "heightFrac": 0.15 } }, "focus": "subject" },
    { "startS": 4.5, "endS": 10,  "camera": { "id": "macro_slide",
      "params": { "lensMm": 85, "fstop": 2.0, "detail": "brightest_glossy" } }, "focus": "subject" }
  ],
  "effects":  [ { "id": "haze_volume", "params": { "density": 0.02 } },
                { "id": "rain", "params": { "rate": 0.5 } } ],
  "grade":    { "id": "teal_magenta_crush", "params": { "contrast": 1.15 } }
}
```

- **`assumptions`** records every gap the AI filled. It makes vague prompts transparent,
  and it is where clarifying-question answers go later (D8).
- **`seed`** also drives everything procedural: handheld noise, rain and particle
  placement, micro-jitter.
- **Shots must be contiguous** from 0 to `durationS`. This matches ScenePlan's rule
  (`apps/web/lib/schema/scene-plan.ts:64-77`), so the web app can adopt it later.
- **Not in v1:** `audio` and simulation `effects`. They are reserved names, and the checker
  rejects them until the blocks exist (§8).

### 4.3 Catalog — the menu

A block is two files:

- **`block.json`** holds:
  - `id` and `kind` (world | lighting | camera | motion | effect | grade)
  - a **plain-English description** written for the AI
  - `params`, each with a type, range and default
  - the subject sizes it supports, in metres
  - the aspects it supports
  - relative render-cost weight
  - `tags` used by the dice: mood, energy, palette
- **`build.py`**: a function that takes (scene, params, SubjectProfile, seed) and applies
  the block in Blender.

**The rulebook's menu is generated from the `block.json` files** (§4.4). The menu the AI
reads and the code that builds it therefore cannot disagree. A block ships only with at
least one golden render (§9).

**v1 block set** (target, refined in the plan):

| Kind | v1 blocks | Source |
|---|---|---|
| world | `studio_cyc` (light and dark), `rain_courtyard` (generalised), `night_street`, `golden_field` | product-render cyclorama; render-studio rain scene with car and GT3 RS gates removed; two new |
| lighting | `softbox_three_point`, `rim_neon`, `hard_sun`, `moody_top`, `hdri_only` | product-render rigs, re-authored in true metres (engine spec §10.8) |
| camera | `low_hero_push`, `macro_slide`, `reveal_rise`, `handheld_operator`, `arc_orbit` (keyframed), `dutch_hero` | product-render framing solver + keyframed blur; `film_camera.py` operator de-carred |
| motion | `static`, `slow_spin`, `hover_bob`, `drop_in` | new, simple keyframes |
| effect | `haze_volume`, `ground_fog`, `rain`, `dust_motes` | `rain_look.py:308-322, 391-443`; `rain_atmosphere.py` |
| grade | 6 presets built from the `rain_look.py:335-388` compositor | parameterised, no longer rain-gated |

**Why this matters:** the reference set shows camera language (FPV, chase, low hero, macro)
and environment matter more than turntables (`assets-in/refs/MANIFEST.md`). v1 therefore
spends its effort on worlds and camera programmes. Subject motion stays simple, and
simulation is phase 2.

### 4.4 Rulebook — the "default script"

The rulebook is what the owner called the default script. It is one versioned text the
LLM reads before every job, assembled from:

1. **Menu.** Generated from the catalog: every block, what it looks like, its parameters
   and ranges.
2. **Taste guide.** Hand-written, and the real craft. Examples:
   - "small glossy products: 50–100 mm lenses, shallow focus, a rim that draws the
     silhouette"
   - "large subjects: wider lenses, low camera, atmosphere for depth"
   - "first shot establishes, last shot lands on the hero angle"
   - "never more than 3 shots in 10 s"
3. **Hard rules**, each tagged with the checker test that enforces it (engine spec §8,
   `enforced_by`). Examples:
   - "subject ≥ 25% of the frame along its dominant axis at every sampled moment"
   - "camera stays outside subject bounds + 10%"
4. **The empty-prompt default.** What to make when the prompt carries no intent: take the
   dice direction and produce a finished ad-style clip. This is the baseline everything
   is judged on first.
5. **Golden examples.** 10–20 full scripts that rendered beautifully, each paired with
   the prompt and SubjectProfile that produced it.

A hard rule that exists only as prose is a bug. If the checker cannot test it, it goes in
the taste guide instead.

### 4.5 Compiler

Blender Python that reads SubjectProfile and the script, then builds the scene by calling
each block's `build.py` in a fixed order: world → subject placement → lighting → effects →
cameras and cuts → grade → render settings for the tier.

- **Camera motion is always keyframed** (product-render `:449-472`), so every camera path
  gets real motion blur. That fixes the gap in `render_snapshot.py:318-321`.
- **Cuts fall in the closed-shutter gap**, as `film_camera.py:367-407` already does.
- **Materials are left alone in v1**, apart from the per-zone `finishOverrides` the
  script names. The engine spec's resolved-finish compiler (§10.6) is later work.

### 4.6 Checker

This is a pure-Python stage. Anything that needs geometry uses cheap maths on the
SubjectProfile bounds, with no Blender call, so it runs in milliseconds.

- **Schema.** Every id exists, every param is inside its range, shots are contiguous,
  and the world supports this subject's size and aspect.
- **Geometry.** Sample each camera path at 12 points per shot:
  - the camera is never inside bounds plus margin
  - the subject stays inside the frame
  - the subject meets minimum screen coverage, measured along its dominant screen axis
    (max of width and height fraction). A wide car in 9:16 fills the width, not the
    height.
- **Guaranteed by construction, not checked.** The compiler owns these, so the checker
  does not test them:
  - focus: v1 supports `focus: "subject"` only, and the compiler sets the focus distance
    to the subject centre;
  - ground contact: the compiler places the subject's lowest point at z = 0, and the
    checker only verifies that a `ground` placement uses a world with a ground.
- **Repair.** Small issues are fixed in place: clamp a value to its range, nudge the
  camera out, extend lens coverage. Larger errors go back to the LLM as a list, up to 2
  retries. After that the direction's **fallback script** is used: a pre-verified script
  for that direction, re-fitted to this subject. **A failing script never renders.**

### 4.7 Render tiers and the farm

- **Preview.** One GPU, low resolution and low sample count with denoising, at the final
  frame rate. Its job is showing composition and motion in minutes, not quality.
- **Final.** The job is split into frame ranges across N rented GPUs, then merged and
  encoded.
  - Every worker in a job uses the **same GPU model, Blender build and asset hashes**.
    Different GPU types produce different noise and would flicker at range boundaries.
  - Each worker gets a whole range, never alternating frames, so any residual difference
    lands on a cut or one boundary rather than every frame.
- **Measured baseline** (RTX 5080, 1080p, 192 spp, per engine survey):
  - film-grade rain scene: about **35 s/frame**, so a 10 s, 30 fps clip is about 2.9
    GPU-hours
  - product-render: about **2–4 s/frame**
- **Cost per clip is measured, not guessed.** Each final render logs GPU-seconds per
  block combination, which feeds a later pricing decision.

### 4.8 Frame QC

These automatic checks run on rendered frames; object-index and depth passes are
rendered for this:

- **Clipping:** blown or crushed pixel share above a threshold.
- **Black or empty frames.**
- **Flicker:** frame-to-frame luminance jump outside the shot's own motion.
- **Subject coverage:** the object-index mask is on screen and big enough.
- **Subject in focus:** sharpness inside the mask.

A failure re-renders that range once. A second failure re-rolls the direction. Thresholds
are calibrated on known-good renders before they gate anything (see memory
[[feedback-calibrate-before-you-model]]).

### 4.9 LLM interface

- **Provider-neutral**, with Claude by default (the latest model at build time).
  Structured output is constrained to the `valora.scene/1` schema.
- **Server-side only.** This differs from ModVision's `prompt.js`, which uses the user's
  key in the browser. The rulebook is a cacheable prefix.
- **One director call per job, plus at most 2 repair calls.** That is cents, against
  dollars of GPU.

---

## 5. How a vague prompt becomes a great video

Example: a 30 cm sneaker, prompt `"make it look cool"`.

1. **Ingest:** 0.30 m, fabric and rubber with glossy plastic accents, sits flat.
2. **Dice**, weighted by taste for a small product and excluding this user's last 5
   directions: `neon-night / low-hero / slow`.
3. **Director:**
   - reads the rulebook
   - picks `night_street` sized to the subject, `rim_neon`, a 2-shot sequence (low hero
     push, then a macro slide over the glossiest part), light rain and haze
   - fills `assumptions`
4. **Checker:** the macro shot's 85 mm lens puts the camera 4 cm inside the toe cap's
   margin. The checker nudges it back 6 cm, which passes.
5. **Compiler → preview (minutes) → final across GPUs → QC → encode.**

---

## 6. Uniqueness

Variety comes in three layers:

1. **Details always differ.** A new seed means different light angles, noise, particles,
   camera micro-path and parameter picks within ranges. Two runs cannot be identical.
2. **Direction differs by design.** The dice pick a combination of world family, mood,
   camera style, pacing and palette from catalog tags, weighted by what suits the
   subject.
3. **Variety memory.** Per user and per subject, the last N directions are stored and
   excluded from the next roll. A small catalog therefore rotates through everything
   before repeating.

**Rules:**

- **An explicit request beats the dice.** "Rainy night" pins the world and mood; the
  dice only fill what the prompt left open.
- **"More like this"** keeps a direction and rerolls only layer 1.
- **Honest limit:** perceived variety scales with catalog size. The plan grows worlds
  and camera programmes first, because each new block multiplies the combinations.

---

## 7. Security

- **The LLM emits data.** The schema and checker validate it before anything executes.
  v1 has no path from prompt text to Python.
- **Uploads are untrusted.** Blender always runs with `--factory-startup
  --disable-autoexec`. There are size and polygon limits at upload. Farm workers run
  jobs in disposable containers with no credentials beyond job I/O.
- **The approach-B escape hatch, when it comes, needs its own sandbox design.** It is
  not in scope here.

---

## 8. Out of scope for v1 (sequenced after)

| Item | Why later |
|---|---|
| Simulation blocks: fluid, rigid-body scatter, cloth (engine spec §6.2) | High value per the refs (ref01, ref02, ref12). They come first in phase 2, once the catalog and checker contract are proven on cheaper blocks. |
| Audio bed | All 12 refs have audio. It comes next after sim, as a separate output stage. |
| `bpy` escape hatch (approach B) | Needs sandboxing (§7) and a quality story. |
| AI-generated backgrounds | Not decided (§2). |
| Clarifying-questions mode | The slot exists (`assumptions`); the UI comes later. |
| Web app wiring (`apps/web`) | A deliberate `not_connected` tripwire (engine spec §10.2); a separate owner-gated step. |
| ModVision adoption | After v1 is proven here (D1). ModVision's pixel-exact gates (engine spec §10.10) stay untouched until then. |

---

## 9. Proving it: the eval harness

Improvement must be measured, not eyeballed (engine spec §11, week 1).

- **Test subjects:** the 6 models in `assets-in/models/`, which are camera, helmet,
  lounge chair, pocket watch, toy car and microscope. Add a character, a shoe/apparel
  item and a real-scale vehicle so D2's categories are all covered.
- **Test prompts:** a fixed list skewed to what real users type. Examples: `""`,
  `"make it look cool"`, `"ad"`, `"luxury"`, `"rainy night"`, plus a few longer prompts.
- **Scores per run:**
  - checker pass rate before repair
  - QC pass rate
  - **variety score**: 5 runs of the same model and prompt, measured as direction
    distance plus frame difference
  - GPU-seconds
  - a judged quality score, tiered per engine spec §8. The judged score is an automated
    vision judge against the 12 reference clips' frames, with **the owner's grades as
    ground truth**. The judge is never trusted until it agrees with the owner.
- **Golden set:** scripts the owner rates highly become rulebook examples (§4.4). That is
  how the default script improves over time.

---

## 9a. Render research corpus: mass-study real renders to set parameters

Owner, 2026-09-24: *"mass research renders to establish parameters. There might be some
things we never thought of and it might help with variety."*

The 12 reference clips set a quality bar, but 12 is too few to derive parameters or
variety from. This workstream studies a large sample of real 3D ads and social renders
and turns it into data the catalog, dice and taste guide are built from, instead of
guessing.

**Input.** 300–500 **curated** clips spread across D2's categories: product ads,
furniture/interiors, vehicles, characters/collectibles, abstract/sim showcases. A few
hundred useful clips beat thousands of random ones.

**Sourcing** (owner-approved 2026-09-24):

| Source | Use | Rule |
|---|---|---|
| Pexels, Mixkit, Pixabay | Main downloadable pool | Hand-picked, never bulk. Pexels forbids scraping and automated collection for ML. Check each Mixkit clip's licence, because some are restricted. |
| YouTube, Vimeo | High-end reference **by link only** | The record stores the URL + timestamps + analysis. Never downloaded; a Vimeo clip is downloaded only if its creator enabled download. |
| Our own Blender renders | Controlled A/B tests | Every setting is known, so we learn cause and effect. |
| Paid stock library | Gap-filler at the very end | Taken for about 1 month, only for gaps the free sources could not fill, then cancelled. |

**Coverage taxonomy:**

- camera movement
- subject interaction (for vehicles: rolling, tyre contact, suspension)
- lighting
- materials
- environment
- **camera imperfections**: motion blur, autofocus breathing, exposure adaptation,
  rolling shutter, sensor noise, micro-shake, lens flare

Every subject category is spanned, not only cars.

**Data use.** Records are observations that turn into renderer parameters ("why does this
look real"). Nothing is trained on clip pixels without a separate licence check (Coverr,
for one, bans AI training outright).

**Output: one structured record per clip** (`research/corpus/<id>.json`, schema
`valora.ref/1`):

- **Subject:** category, and size class (macro / hand / furniture / vehicle / architectural).
- **Format:** aspect, duration, fps, shot count, cut timings.
- **Per shot:**
  - camera move type (push, orbit arc, slide, rise, FPV, handheld, locked), with
    estimated lens class and height
  - focus behaviour (rack, deep, shallow)
  - subject motion
- **World:** type (cyclorama, interior, street, nature, abstract void, water…),
  time of day, weather and atmosphere.
- **Lighting:** setup (softbox, rim-heavy, hard sun, practicals, neon, silhouette), key
  direction, colour temperatures.
- **Grade:** palette (dominant hues), contrast, saturation, bloom/halation, grain.
- **Effects and simulation:** fluid, particles, rigid-body, cloth, rain, smoke.
- **Pacing:** energy (calm / medium / hype), and whether cuts land on the music.
- **Notes:** free text on "something we'd never thought of".
- **Pilot additions** (the 11-clip pilot, `research/corpus/PILOT-NOTES.md`):
  - per-shot `renderPass`: final, clay, viewport or split. Clay-to-final reveals are
    the dominant format in the owner's refs.
  - `layout`: split-screen, rotated landscape, blurred fill.
  - `overlays`: hook text, end card, 2D graphics.
  - `transitions`, `surfaceState` and `secondarySubjects`.
  - per-field `evidence`: frame ids or timestamps.
  - camera-imperfection fields.

**Method.** The extraction is bulk and self-contained, so it is offloaded:

- Vision-capable subagents or Codex fill records from sampled frames. The owner's
  standing rule applies: Codex drafts, Claude re-verifies the population.
- Bulk tagging and clustering of free-text notes goes to Laya.
- A 30-clip hand-checked subset measures extraction accuracy before the other records
  are trusted.

**Uses:**

1. **Catalog backlog.** Cluster by world type, camera move and effect, and rank by
   frequency × fit with Valora3D. Clusters with no matching block become new blocks, in
   frequency order. This is the "things we never thought of" list.
2. **Parameter ranges.** Observed lens, shot-length, cut-count and grade values set each
   block's `params` ranges and defaults (§4.3), so the ranges come from real work.
3. **Dice tags and weights.** Real co-occurrence (for example neon grade + night street +
   rim light) sets the direction weights, and rare-but-good combinations are kept on
   purpose for variety (§6).
4. **Taste guide.** Recurring patterns become written rules, and each rule cites the
   clips it came from (§4.4). Example: "small products: 2–3 shots, macro detail shot
   last".
5. **Eval.** A held-out slice of the corpus becomes extra judge references (§9).

**Rights.** The clips are studied, not reused.

- The records and short notes are committed. The video files and frames are not; they
  stay local and gitignored, like `assets-in/`.
- Nothing from a clip is copied into an output: no footage, textures, music or logos.

**Timing.** This workstream needs no GPU and no engine code, so it runs **in parallel from
day one** alongside build-order steps 1–2. Its first cut (about 100 clips) lands before
step 3, because the director's taste guide and the dice weights consume it.

---

## 10. Build order (detail goes in the plan)

1. **Foundations, no GPU needed:**
   - `valora.scene/1` schema
   - block manifest format
   - ingest (true scale)
   - checker with repair
   - unit tests
2. **Compiler and first blocks:**
   - `studio_cyc`, 3 camera programmes, 2 lighting moods, 2 grades
   - keyframed blur
   - preview tier
   - harness v0: render fixed hand-written scripts and score them
3. **Director:**
   - rulebook generator, taste guide v1, empty-prompt default
   - LLM call with schema output
   - repair loop and fallback scripts
4. **Variety:** dice, variety memory, "more like this", variety score in the harness.
5. **Catalog growth:**
   - port the rain courtyard, haze, fog and grade compositor out of render-studio
   - add `night_street` and `golden_field`
   - add the remaining v1 cameras
6. **Farm:** frame-range splitting on rented GPUs, final tier, frame QC, encode,
   cost-per-clip logging.

**In parallel from the start:** the render research corpus (§9a). A first cut of about 100
clips must land before step 3; the full 300–500 lands during step 5, where it drives which
blocks get built.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| New worlds look CG next to the rain film | A world ships only with a golden render the owner has graded. The rain courtyard's compositor and volumetrics are reused, not rebuilt. |
| LLM output converges on one "safe" look | Variety comes from the dice and memory, not the LLM (§3). The variety score is in the harness. |
| Cost per clip too high for the business | Measured per block (§4.7). The preview tier absorbs iteration. Block cost weights let the dice prefer cheaper combinations when a budget asks for it. |
| Flicker between farm workers | Same GPU model and build per job, whole ranges per worker, and the QC flicker check (§4.7, §4.8). |
| Checker thresholds wrong at launch | Calibrated on known-good renders first. Until then QC reports but does not block. |

---

## 12. Open questions (none block phases 1–4)

1. **Rented GPU provider and GPU model.** This affects phase 6 only.
2. **Target price per clip.** It sets the default sample count and resolution for the
   final tier.
3. **Audio.** Licensed music library, generated, or silent-by-default in phase 2?
