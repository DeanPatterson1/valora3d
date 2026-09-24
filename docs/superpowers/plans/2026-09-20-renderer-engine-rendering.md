# Plan — Rendering site: any model, any prompt, LLM-directed

    date:     2026-09-20
    track:    renderer-engine
    product:  Rendering (any uploaded 3D model, credits + subscription)
    status:   DRAFT — no owner approval
    spec:     docs/superpowers/specs/2026-09-19-renderer-engine.md
    sibling:  C:\Users\deand\Projects\ModVision\docs\superpowers\plans\2026-09-20-renderer-engine-modvision.md

---

## 0. Scope

This plan covers **the Rendering site's renderer** — the engine that takes a user's uploaded
3D model plus a natural-language prompt and returns a finished video for advertising or
social media.

The sibling plan covers ModVision (cars only, curated fleet, no uploads). The shared
architecture lives in the spec; read its §3 (architecture) and §8 (judging and learning)
before executing. This document does not repeat them.

### What makes this product harder than ModVision

| | ModVision | **This product** |
|---|---|---|
| Subject | Curated fleet, semantics known | **Anything. No name is trustworthy.** |
| Geometry guarantees | Parted, scaled, ground-snapped | **None. Welded blobs, flipped normals, no UVs, wrong units.** |
| Ingest | Not needed | **Mandatory and currently missing.** |
| LLM role | Pick scene + camera + look | **Author the scene. Compose primitives freely.** |
| Simulation | Rain only, solved | **Fluid, cloth, particles, rigid body — all new.** |
| Output | A clip | **An edited advertisement: multi-shot, audio, multi-aspect.** |
| Money | Feature of a configurator | **The product. Credits burn per render.** |
| Failure cost | A bad clip | **A burned subscription and a chargeback.** |

**"No defects" is the product**, not "infinite knobs". That ordering decides several
tradeoffs below.

---

## 1. Binding constraints

### 1.1 Do not touch the web prototype's renderer

**SETTLED, and enforced by passing tests.** This is the single easiest way to break
something valuable.

- Spec §2 scope: *"The rendering process itself. The owner has a separate plan for it."* —
  out of scope for `apps/web`.
- Spec §7: `RenderService` types only; the active implementation returns
  `{ok:false, error:{code:"not_connected"}}`; **"No fake job state machine, no sample MP4,
  no simulated progress."**
- Memory `rendering-prototype-decisions.md`: renderer intentionally blank; owner 2026-09-18
  *"don't focus on the backend and especially the actual rendering process"* — that ruling
  scopes the **web prototype**, and the 2026-09-19 entry confirms engine work belongs in
  render tooling.
- **MEASURED** — a Playwright e2e assertion and `services.test.ts:79` both assert the
  not-connected state. Connecting a real renderer to `apps/web` **breaks green tests by
  design.**

**Therefore:** every chunk below happens in `tools/`. Web wiring is a separate, later,
owner-gated decision and is explicitly out of this plan.

### 1.2 Other settled rules

1. **No from-scratch path tracer.** Settled with evidence: identical Cycles produces both
   the film-grade and the CG-looking tier. From-scratch pays only for a *real-time preview*
   so users iterate before a slow bake.
2. **The LLM emits a structured spec, not raw `bpy`.** A script can only be executed; a spec
   can be validated before spending an hour.
3. **Four enforcement tiers** — impossible / auto-corrected / detected / documented-only.
   *A rule with no enforcer is a wish.*
4. **The renderer is shared with ModVision.** Memory: *"the renderer is the same one we have
   in ModVision."* Do not grow a second independent stack.
5. **Spec §14** — no third-party renders presented as product output.
6. **Visual language** (`#0d0d0d/#171717/#212121/#2f2f2f`, **no accent colour**, Inter) is
   the web prototype's, already settled. Not this plan's concern, but do not contradict it
   in any tooling UI.
7. **Machine:** RTX 5080 16 GB, Blender 5.0 (spec targets 5.2 LTS), Node 24.

---

## 2. Where this product actually stands

**MEASURED 2026-09-19.**

### 2.1 `normalise()` destroys the thing every rule needs — blocking

`tools/product-render/render_product.py:133-152` scales the longest axis to exactly 1 m.
Observed: toycar **13.52×**, flighthelmet **1.397×**. A pocket watch, a lounge chair and a
building all come out 1 m.

Every detail rule worth writing is in real millimetres — flake 0.15 mm, bevel radius
0.3–1 mm, orange-peel period 1–3 mm, mm/texel, mm/px. After `normalise()` **none of them is
computable.**

Simulation makes it fatal rather than merely wrong: viscosity, surface tension and gravity
operate in real units. A can at 100× scale gets honey-thick water.

**This is task one of the month.** Everything downstream depends on it.

### 2.2 Recognition-gated capability — the bug is already here, twice

- **MEASURED** — `apps/web/lib/scene/classify.ts:15-23`: category is `car` iff a name regex
  (`/wheel|tire|tyre|headlight|windshield|bumper|brake/i`) hits, or proportions land in
  L 3–6 / M 1.5–2.3 / S 1–2 m; else `{product, 0.6}`. `capabilities.ts:3-11` then gates
  capability on that category. Part roles are name regexes too.
- **The tell is in the repo:** `apps/web/public/samples/LICENSES.md` records that the sample
  car's wheel groups were **hand-renamed** `Wheel_FL/FR/RL/RR` so the analyser would
  succeed. A curated sample needing a rename means user uploads will not survive it.
- ModVision has the same bug at species scale: `rain_look.py:178` gates art direction to
  `MANTHEY_992` only; every other car falls through to generic.

**Rule for this plan: baseline always, class pack on top. Never gate the baseline on
recognition.**

### 2.3 Three settings cap the product half of the business

`render_product.py:522-526`:

```
caustics_reflective   = False
caustics_refractive   = False
sample_clamp_indirect = 8.0
blur_glossy           = 0.5
```

These suppress exactly the highlights that sell glass, chrome, liquid, jewellery, bottles
and watches. **ref10 is a Rolex** — that whole category is capped by config, not by the
renderer.

### 2.4 The non-car output already shows the real bottleneck

From two rendered frames (chair, microscope):

- **Framing solver works** — `solve_framing()` (`:409-446`) hits fill 0.6 exactly. But fill
  is a fraction of frame **height** and output is 16:9, so a tall narrow subject at 0.6
  height occupies **~15% of frame width.** The eval set is **12/12 vertical.**
- **DOF is on (f/2–2.8) and barely reads** — a featureless gradient backdrop has nothing to
  defocus.
- **Chrome and brass reflect a grey ramp.** `DEFAULT_HDRI` (`:32`) is **1k at strength 0.3**.
  Same disease as ModVision's turntable, and it hits every reflective subject this product
  will ever receive.
- **Contact shadows are detached blobs.** The chair's five feet do not each bite the floor;
  the microscope floats.

**No micro-detail rescues a subject reflecting a grey ramp.** Environment carries realism.

### 2.5 `fix_materials()` writes nothing

`render_product.py:156-177` only records notes, despite a docstring claiming it fixes
transmission. Material enhancement here is **greenfield** — nothing to retrofit.

### 2.6 Credit where due — keep both

- `:449-472` keyframes the camera from −1 to n+1 **specifically so motion blur has data past
  both ends.** Correct. This is the pattern ModVision's orbit path is missing.
- `:409-446` `solve_framing()` binary-searches silhouette fill and hits its target exactly.
  Its problem is the aspect it solves against, not the solver.

### 2.7 The schema cannot express the target

**MEASURED** — `apps/web/lib/schema/scene-plan.ts`:

```
subject.motion  = "stationary"     ← a literal. Not an enum. The only value.
shots           = 1..2 items
ShotAction      = slow_orbit | hero_push_in | low_tracking | handheld_walk_toward
                                   ← all camera-only; slow_orbit contradicts "zero turntables"
Resolution      = 720p|1080p|1440p|4k          ← implies 16:9; refs are 12/12 vertical
DurationS       = 5|10|15|30                   ← ref11 is 35.4 s
```

No simulation fields. No audio. No aspect ratio. A `superRefine` (`:64-77`) requires shots
contiguous from 0 ending exactly at `output.durationS`, so widening touches it and every
`applyPatch` clamp test.

**The renderer's own schema is ModVision's `spec.py`** (`SCHEMA = "modvision.render-spec/0"`),
which already has `provenance.source ∈ {default, random, prompt}` — the LLM path was
designed in. **Widen that; do not restart.** See the sibling plan §2.5 for its measured
state.

### 2.8 Money cannot currently record a render

- **MEASURED** — `apps/web/lib/schema/project.ts:89`: `CreditReason` is
  `starting_balance|scene_generation|prompt_edit|pack_purchase|plan_grant`. **There is no
  render reason.**
- **MEASURED** — `apps/web/lib/pricing.ts:3-45`: `preview_render: 3`, `local_final: 5`,
  `cloud_final: {standard:30, high:60, ultra:90, "4k":160}`, `STARTING_BALANCE = 100`,
  plans Free $0/50cr · Creator $19/500cr · Pro $49/2000cr.
- A 10 s 1080p clip at 24 fps is 240 frames × ~30–40 s/frame ≈ **2.3 GPU-hours** on the
  5080. Priced at 5 credits. **The table will not survive contact**, and simulation bakes
  are additional.
- **MEASURED** — `RenderJob` (`:72-86`) has **no seed, no cost, no timestamps, no log
  channel**, and `subscribe` is push-only with no reconnect or polling semantics.

### 2.9 The eval set encodes the wrong target

- **MEASURED** — `assets-in/refs/MANIFEST.md`: 12 clips, 11 unique (ref07 == ref06). **Zero
  turntables.** 9 of 11 have non-camera motion. All vertical except ref10 (1:1). **All have
  audio.** Current pipeline matches on **1 of 11** (ref06 ≈ ModVision `rainy_courtyard`).
  ref11 is the *"1400 hours"* benchmark.
- **But 9 of 12 refs are cars, and all six test models in `assets-in/` are
  product-category** (camera, flight helmet, lounge chair, pocket watch, toy car, vintage
  microscope).

**Score against that set and the month ships a car renderer.** Fix before Chunk 5 builds the
harness — the harness encodes the target.

---

## 3. Chunks

### Chunk 0 — Unblock (do first, nothing else works without it)

**T0.1 — True scale survives the pipeline.**
Kill `normalise()`'s subject scaling (`render_product.py:133-152`). Either keep true scale
as metadata passed to every shader, or normalise the **camera rig** instead of the subject.
*Gate:* a pocket watch and a lounge chair render correctly framed while reporting different
true spans. mm/px is computable for both.

**T0.2 — Aspect from subject and target platform.**
`solve_framing()` (`:409-446`) keeps its solver; the frame it solves against becomes a
variable. Vertical-first, since the eval set is 12/12 vertical.
*Gate:* a tall narrow subject fills the frame in 9:16 rather than occupying 15% of width.

**T0.3 — A real HDRI world.**
`DEFAULT_HDRI` (`:32`) is 1k at strength 0.3. Replace with a proper-resolution environment
so chrome and brass reflect something.
*Gate:* side-by-side on the microscope and the pocket watch — reflections carry detail.

**T0.4 — Caustics and glossy settings per shot class.**
Enable `caustics_reflective` / `caustics_refractive`, relax `sample_clamp_indirect` and
`blur_glossy` for macro and product shots; leave them off for wides where they only cost
time.
*Gate:* a glass or chrome subject shows caustics; wide-shot render time does not regress.

**T0.5 — Contact shadows that bite.**
Ground on **detected contact points, never bbox minimum** (the R-014 defect class). The
chair's five feet each meet the floor.
*Gate:* validator `ground_contact.py::check_contact` passes on all six test models.

### Chunk 1 — Ingest

**Mandatory and currently missing.** "Any 3D model" plus "the LLM cannot see the mesh" means
that without a factual subject report every script is a coin flip.

**T1.1 — Measure, do not read names.** Emit:
- **glTF declarations** — metallic, roughness, transmission, IOR, emission, alpha
- **geometry** — per-edge dihedral angle, curvature histogram, planarity, wall thickness
  (interior raycast), surface area, symmetry
- **spatial** — bounds, ground-contact set, concavity/AO, interior vs exterior, up-axis
  guess, facing guess
- **scale** — true span, unit guess (mm / m / inches)
- **texel density** — texture px ÷ world-space UV area = mm/texel
- **quality** — poly count, normal consistency, UV presence, which textures resolved vs
  missing

**T1.2 — Capabilities, not just facts.** Facts are for validators; capabilities are the
LLM's menu. Derive from **geometry, not names**:
- 4+ near-identical meshes, radially symmetric about a shared axis, touching the ground →
  `wheel_rotation`
- separate roots with distinct transforms → `part_animation`, `explode`
- skinned → `rigged_motion`
- transmission materials present → `caustics_shot`
- single welded blob → static only, **and say so up front**
- no UVs → no decal or label swap

**Caveat:** the wheel heuristic false-positives on office chairs (5 casters, radial
symmetry, wrong axis), shopping carts and table legs. **Offer capabilities as a menu; do not
auto-fire motion from them.**

**T1.3 — Auto-repair what is safe.** Normals, weld, scale, axis, missing-texture fallback to
material-class defaults.

**T1.4 — Collision meshes.** Simplified hull for convex subjects; voxel remesh for concave
(a mug needs interior collision). Report *"mesh not watertight — fluid may leak"* at
preflight. Required before Chunk 3.

**T1.5 — Promote the existing seeds into one shared stage.**
`render_product.py:133` `normalise()`, `:156` `fix_materials()` (currently writes nothing —
greenfield), ModVision `material_classes.py:24-57` `classify()`.

*Chunk gate:* all six `assets-in/` models produce a complete subject report; none requires a
mesh rename to succeed; the classifier's output is a **modifier over a universal baseline,
never a gate.**

### Chunk 2 — The DSL and the compiler

**T2.1 — Primitive vocabulary.** Per spec §5.2: objects/placement, motion, physics, camera,
lighting, time, grade. Each primitive is one **builder** — a Python function taking validated
spec input, emitting deterministic `bpy`, returning what it created so validators can check
it. **The LLM never writes `bpy`. The compiler does.**

**T2.2 — Widen ModVision's `spec.py`, do not restart.** It already carries
`provenance.source = "prompt"`. Raise the 16 reachable LOOK keys toward the full 50, add
`look` to `SPEC_FIELDS`, and bring camera, sampling, bounces, motion blur and filter width
into the schema.

**T2.3 — Measurement-keyed detail library.** Rewrite every rule from *"tyres get X"* to
*"surfaces with property P at scale S get X"*:

| Rule | Keys off | Fires on |
|---|---|---|
| Edge bevel / curvature highlight | dihedral > θ, radius 0 | everything manufactured |
| Contact darkening + compression | ground-contact set | everything that sits |
| Edge wear | convex + metallic | tools, hardware, props |
| Cavity grime | concave / low AO | everything |
| Orange peel | coat > 0, low roughness | car paint, phone, fridge, guitar |
| Smudge / fingerprint | smooth dielectric, macro scale | glass, plastic, screens |
| Sheen | rough, non-metal, no transmission | fabric, leather |
| Thin-film / dust | transmission > 0.5 | glass |

**Zero-radius edges are the single most generalisable realism rule available.** No real
manufactured object has one. Free on every upload.

**T2.4 — Procedural fill vs trust the texture.** Compare the asset's mm/texel against the
shot's mm/px:
- asset finer than the shot → **trust the texture, add nothing**
- asset coarser → **procedural fills the gap, at the scale of the gap**

This is what stops a 512px-textured model disintegrating on a macro push, automatically,
with no per-asset work.

**T2.5 — The escape hatch.** For genuinely novel requests the LLM writes `bpy` inside a
sandbox: cannot delete `$subject`, cannot touch render settings, cannot write outside the job
directory, hard execution timeout, **all validators still run.**
*This is the difference between "any prompt" and "any prompt we have builders for." See
§6 Q3 — it may be deferred to v2.*

*Chunk gate:* a spec-driven job reproduces a known-good CLI render byte-for-byte.

### Chunk 3 — Simulation

Each primitive auto-sizes its domain and emitters from the subject bounds Chunk 1 measured.

**T3.1 — `fluid`** (FLIP): source shape/position/flow, colliders, liquid type.
**T3.2 — `rigid_body`**: gravity, restitution and friction from material class, damping until
kinetic energy falls below a threshold.
**T3.3 — `cloth`**: pin points, fabric type.
**T3.4 — `particles`**: emitter, type, count, lifetime, physics.
**T3.5 — `volume`**: smoke/fog/mist with turbulence and rise.
**T3.6 — `wind`**, **`gravity`**: field primitives composable with all of the above.

**Sim element materials come from the primitive, not the upload.** `liquid_type: water`
always means transmission 0.95 / IOR 1.33 / roughness 0. The LLM parameterises colour and
viscosity; it never authors the shader graph.

**Bake time is separate from render time and can dominate.** Track it — Chunk 6 prices it.

**Do not re-solve rain.** ModVision `rain_atmosphere.py:58-103` already does a per-column BVH
raycast for `rain_stop_height`. Rain does not fall through objects. Reuse it.

*Chunk gate:* fluid contacts a non-watertight test mesh without leaking, or preflight refuses
the job with that reason. No sim may float, leak or explode on any of the six test models.

### Chunk 4 — Environments

**This is where most of the month actually goes.** Environment carries realism — §2.4.

**T4.1 — 6–8 hand-built pre-lit worlds**, each with its own volumetrics and grade baked in.
Candidates: studio black, studio white, tunnel, night highway, forest, coast road, garage,
abstract void.

**T4.2 — Every environment declares a contract:**
- **valid subject-size range** — a 4 cm perfume bottle in "night highway" is a dollhouse;
  either scale-adapt or **refuse with a reason**
- **placement contract** — ground anchor, up axis, facing, clear volume; ingest supplies
  measured contact points and the compiler mates them
- **lights in subject-relative true metres** — a softbox sized for a car is a wall for a
  watch
- **frame aspect** derived from subject aspect

**MEASURED justification:** the product-render light rig is a fixed 3 m setup that is only
"scale-independent" because the subject is forced to 1 m (`:276-311`). That breaks the moment
there are 6–8 real worlds.

**T4.3 — Resolve the environment name collision.** `studio_black` in the viewer
(`environmentLook.ts`) is a **colour table**; `studio_black` in `render_product.py:34-45,
181-235` is a **bent-plane cyclorama with light-linked rigs**. Same name, different object,
no shared source. Harmless while render returns `not_connected` — the day it connects every
user receives something other than what they approved. **One environment definition,
renderer-authored; the viewer renders an approximation.**

*Chunk gate:* every environment renders all six test models within its declared size range,
or refuses with a reason. No environment silently produces a dollhouse.

### Chunk 5 — Judging, validators, and the learning loop

Build the harness **before** tuning anything, or everything after is vibes.

**T5.1 — Broaden the eval set first.** 9/12 refs are cars and all six test models are
products. Add reference targets for what the product will actually receive — furniture,
apparel, electronics, food, characters — **before** the harness exists.

**T5.2 — Tiered judgment** (spec §8.1):

| Tier | Cost | Judges |
|---|---|---|
| 1 — scene graph | 0 s | placement, camera clipping, sim domain enclosure, materials assigned, textures resolved |
| 2 — proxy, **full sequence** | ~1 s/frame | motion, sim stability, composition across all frames, fluid contact vs leak, timing, camera smoothness |
| 3 — key frames, **3–5 only**, full res/spp | ~35 s/frame | material quality, DOF/bokeh, motion blur, noise, fine detail, colour, caustics |
| 4 — full render | hours | runs only after 1–3 pass |

**Key frames are chosen, not sampled** — frame 0, the peak-physics frame, a composition frame
near the golden ratio of the camera arc, the specular/caustic peak, and the final frame. Cap
at 5. The compiler knows where these are because it built the scene.

**T5.3 — Rules file, machine-checkable.** `enforced_by` is **mandatory**:

```yaml
- id: R-014
  defect: tyre floats ~4mm above ground plane
  seen_in: job-2026-09-12-porsche-a
  cause: normalise() rests bbox-min on Z=0; bbox includes wing mirror, not wheel contact
  rule: ground on detected wheel contact points, never bbox minimum
  enforced_by: validators/ground_contact.py::check_contact
  tier: 2
  severity: block
```

**Generate the API-reference half from the code.** A hand-written API doc drifts and then
the LLM is reading fiction.

**T5.4 — Vision-model scoring of the key frames** against a fixed rubric: subject visible,
rests naturally, no artifacts or fireflies, lighting reads, physics plausible, materials hold
up at this distance, composition balanced, no geometry clipping. Failures return **specific
reasons** that feed the retry loop.

**T5.5 — The retry loop.** Failure feedback names the **specific violated rule**. That loop
produces "no defects", not the file.

**T5.6 — Golden examples.** Every render that scores well has its spec added to a library
that becomes the LLM's few-shot context. **No fine-tuning.** Better examples, not a better
model.

**The LLM is stateless. The validators are the memory.** Every production defect becomes a
mechanical enforcer; the rules file only ever grows.

*Do not put predicted success-rate numbers anywhere until this harness produces measured
ones.*

**Iterate here, not on ModVision's rain scene** — **MEASURED**: product renders run
2–4 s/frame versus 29–40 s/frame for the rain scene. Sweeps are affordable on this pipeline
in a way they are not on the other.

### Chunk 6 — The product is an edited video

Everything above produces raw footage. The eval set says that is not the product: **all 12
clips have audio**, 11 of 12 are vertical, and they are edited pieces.

**T6.1 — Production spec.** The LLM's output widens from "one scene spec" to a shot list plus
an edit decision list: several shots (each its own render job, independently parallelisable),
transitions, motion-graphic cards that never touch Blender, and per-shot grades.

**T6.2 — Editor.** Assemble shots with transitions. Motion graphics from a brand kit (2D, no
Blender).

**T6.3 — Audio.** Beat-synced music bed, SFX triggered off simulation contact events,
loudness-normalised mastering. **No pipeline emits audio today.**

**T6.4 — Colour-tagged, multi-aspect export.** **MEASURED** — `pipeline.py:261-271` and
`encode_clip.py` ship **no `-color_primaries` / `-color_trc` / `-colorspace` flags**, so every
MP4 is untagged and players guess. **Cheapest realism win available.** Export 9:16, 16:9, 1:1,
4:5.

**T6.5 — EXR + AOVs + light groups.** Relight in post instead of re-rendering.

**T6.6 — Optional AI post-passes.** All post-render, none touching light transport, so none
violates the no-from-scratch ruling: upscale (render 1080p → 4K, changes 4K economics),
hybrid backgrounds (path-trace the subject on a shadow catcher, generate the environment
behind it, composite), generated audio, 2D motion graphics.
**Constraint:** ModVision carries a standing ban on generative passes over car geometry.
Treat generative passes as **banned on ModVision** until the owner rules otherwise; on this
product they are §6 Q4.

### Chunk 7 — Money

Do this after Chunk 5 produces measured GPU-minutes, not before.

**T7.1 — Re-derive the credit table** from measured cost. Current values (`pricing.ts:3-45`)
price a ~2.3 GPU-hour clip at 5 credits. **Simulation-bearing jobs need their own tier** —
bake time is separate from render time and can dominate.

**T7.2 — Add a render reason to the ledger.** `CreditReason` has none
(`project.ts:89`). Charging a render requires a schema change.

**T7.3 — Thicken `RenderJob`.** No seed, no cost, no timestamps, no log channel; `subscribe`
is push-only with no reconnect or polling semantics (`project.ts:72-86`). A real queue needs
all of them.

**T7.4 — Gate before you charge.** Most uploads will be bad, realism is bounded by the asset,
and the user will blame the product.
- `model_analysis` already costs **0** — correct, keep it.
- That free analysis must return a **plain-language verdict** before any credits are spent:
  *"no UV map — surface detail limited"*, *"single welded mesh — no motion shots available"*,
  *"scale ambiguous — is this 4 cm or 4 m?"*
- **MEASURED** — `inferUnits.ts:26-48` has a logged failure where a cm-unit car with no name
  signal becomes a 0.45 m product. The product sells one-click rendering, so prefer
  *infer → show in the proxy → let the user correct* over a blocking form field. **The proxy
  is the confirmation step.**
- Make the proxy pass free or separately priced. Otherwise a doomed asset burns a
  subscription's credits.

**T7.5 — Entitlement enforcement.** **MEASURED** — `auth.ts:63` writes `user.plan` once at
signup and never again, with **no entitlement, watermark or resolution enforcement
anywhere.** Those get enforced in the render job schema. Define them **before** the renderer
connects, not after.

---

## 4. Sequencing

```
Chunk 0 ──> Chunk 1 ──┬──> Chunk 2 ──> Chunk 3 ──┐
                      │                          ├──> Chunk 6
                      └──> Chunk 4 ──────────────┘
                                                  │
                           Chunk 5 (start early) ─┴──> Chunk 7
```

- **Chunk 0 is blocking.** True scale gates every measurement rule and all of simulation.
- **Chunk 5 starts early and runs throughout** — the harness must exist before tuning, and
  T5.1 (broaden the eval set) must land before the harness encodes the wrong target.
- **Chunk 4 is the largest.** Budget accordingly.
- **Chunk 7 waits on Chunk 5's measured GPU-minutes.**

Against the settled month shape: Chunks 0+1+5 ≈ week 1, Chunks 2+3 ≈ week 2, Chunk 4 ≈
week 3, Chunks 5 (close-out) + 6 ≈ week 4. Chunk 7 slots wherever the measurements land.

---

## 5. Pitfalls — do not retry

**SETTLED**, verified still accurate 2026-09-19.

- **Do not lead with "add an imperfection layer."** Ranked #1 in a prior session and the
  owner overturned it with the reference clips. Right lever for exactly one category — static
  hero macro (ref06, ref10) — and near-irrelevant for the other nine.
- **Do not claim ModVision lacks compositing / volumetrics / imperfections.** It has all
  three, richly, behind `if scene == rainy`. Easy to mis-audit from `render_product.py` alone.
- **Do not cite "rain falls through objects" as an open bug.** Solved at
  `rain_atmosphere.py:58-103`.
- **Do not propose a from-scratch path tracer.**
- **Do not plan the month as "add realism features."** They largely exist, hard-coded to one
  scene and one car. **The month is generalisation.**
- **Do not gate any detail or capability on subject recognition.**
- **Do not simulate rendering anywhere in `apps/web`** — it breaks a deliberate test tripwire
  and an explicit memory rule.

---

## 6. Open questions for the owner

1. **Chunk order** — is Chunk 4 (environments) worth starting before Chunk 3 (simulation)?
   §2.4 argues environment carries more realism than anything else, which would swap them.
2. **How many environments in v1?** Six is the floor for credible coverage; eight is the
   settled target. Each one is real work.
3. **Does the `bpy` escape hatch (T2.5) ship in v1**, or is v1 DSL-only? This is the
   difference between "any prompt" and "any prompt we have builders for."
4. **AI post-passes (T6.6)** — allowed on this product? Hybrid backgrounds behind a matted
   subject are arguably outside ModVision's generative ban, but that is your call.
5. **Eval-set expansion (T5.1)** — which non-car categories matter most commercially?
   **That choice encodes the target the whole month optimises toward.**
6. **Credit re-pricing (Chunk 7)** — re-derive after Chunk 5, or hold until the engine is
   real and you have production data?
7. **Which pipeline becomes the compiler?** `product-render` is the cleanest seed (framing
   solver, correct motion-blur keyframing); ModVision's `render-studio` owns the only real
   schema and the operator sim. Consolidation order follows this answer, and it is shared
   with the sibling plan's T4.1.

---

## 7. Provenance

All **MEASURED** citations come from read-only surveys of this repo and the ModVision
`modvision-renderer-quality-e9326d` worktree run 2026-09-19, plus the audit in
`.handoffs/2026-09-19-0353-renderer-engine-realism-strategy.md`. Line numbers are true of
the trees as of 2026-09-19 and were not re-verified afterwards. Re-check before acting.

Nothing in this plan has owner approval.
