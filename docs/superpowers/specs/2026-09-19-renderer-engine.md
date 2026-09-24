# Renderer Engine — prompt-to-video, any subject

    date:     2026-09-19
    track:    renderer-engine
    status:   DRAFT — no owner approval on anything in "Proposed" below
    supersedes: nothing
    fills:    the artifact deferred twice in .handoffs/2026-09-19-0353-renderer-engine-realism-strategy.md

    plans:    ModVision  → C:\Users\deand\Projects\ModVision\docs\superpowers\plans\2026-09-20-renderer-engine-modvision.md
              Rendering  → docs/superpowers/plans/2026-09-20-renderer-engine-rendering.md

---

## This document is the shared layer

Three documents, one track:

| Document | Covers |
|---|---|
| **This spec** | Shared architecture, the DSL, the enforcement model, the judging/learning loop, and the conflicts both products inherit. Product-neutral. |
| **ModVision plan** | Cars only. Curated fleet, no uploads, no ingest, no simulation. Vehicle motion and driving cameras are its headline work. |
| **Rendering plan** | Any uploaded model. Ingest, measurement-keyed detail, simulation, environments, credits, the edited-video output layer. |

Read this spec's §3 (architecture) and §8 (judging and learning) before executing either
plan — neither plan repeats them. Sections §4 (ingest), §5 (DSL), §6.2 (simulation) and §9
(edited output) are **Rendering-first**; ModVision inherits only §3, §6.1, §7 and §8.

---

## 0. How to read this document

Three labels appear throughout. They are not decoration — they mark how much weight a
statement carries.

| Label | Meaning |
|---|---|
| **SETTLED** | Decided in a prior session with the owner, or enforced by shipped code/tests. Do not relitigate without a new owner request. |
| **MEASURED** | A fact read out of the tree on 2026-09-19 by survey, with a `file:line`. Re-verify before acting if the tree has moved. |
| **PROPOSED** | Originated in the 2026-09-19 design conversation. **No owner sign-off.** Argue with it freely. |

Anything unlabelled is connective prose.

The owner runs parallel Claude terminals on these repos. This document is the
`renderer-engine` track's plan. It does not authorise changes on any other track.

---

## 1. What is being built

Two products, one engine.

| | **ModVision** | **Rendering** |
|---|---|---|
| Subject | Cars only, from a curated fleet | Any user-uploaded 3D model |
| Subject knowledge | Full semantics (slots, wheels, specs) | Measured at ingest, no names trusted |
| Business model | Configurator; render is a feature | Credits + subscription; render *is* the product |
| Output | Build showcase clips | Advertisements, social clips |
| Needs simulation | Motion yes, sim mostly no | Yes — fluid, cloth, particles, rigid body |

**SETTLED** — the renderer is shared. Memory `rendering-prototype-decisions.md`:
*"the renderer is the same one we have in ModVision"*. Rendering does not grow its own
second renderer.

**PROPOSED** — the sharing is layered, not wholesale: a common engine core, with
ModVision as a *vertical specialisation* (car primitives, car director prompt) rather
than a separate stack. §7.

### The goal, in the owner's words

From the 2026-09-19 03:53 handoff, verbatim:

> "how the system works from prompt then the ai has a default peramters and baseline so it
> can create a master peice with a basic prompt and have no defects... i want to spend a
> month on perfecting the renderer so it can one shot someones idea. Also the goal id like
> users to use it for it advertisments or social media clips or edits."

> "this business idea is for any 3d model the user give and any way they choose to render it
> they say what they want and they get it which is why a ai api is connected but that ai needs
> to read a file so it don't make the same mistakes when writing the script the user wants"

**"No defects" is the product.** Not "infinite knobs". That ordering decides several
tradeoffs below.

---

## 2. Correlating documents — what each one binds

This plan must not contradict any of these. Read the binding column before changing
anything in its area.

### 2.1 Rendering repo

| Document | Binds |
|---|---|
| `.handoffs/2026-09-19-0353-renderer-engine-realism-strategy.md` | **SETTLED.** No from-scratch path tracer. Realism is scene authoring, not light transport. LLM emits a structured spec, not raw `bpy`. Four enforcement tiers; a rule with no enforcer is a wish. Ingest is mandatory and missing. Month shape (wk1 eval+consolidation, wk2 motion, wk3 environments, wk4 validators). Pitfalls list — do not retry those. |
| `docs/superpowers/specs/2026-09-17-website-prototype-design.md` | **SETTLED.** §2 scope: *"The rendering process itself"* is **out of scope for the web prototype**. §7: `RenderService` types only, active impl returns `{ok:false, error:{code:"not_connected"}}`, **"No fake job state machine, no sample MP4, no simulated progress."** §8 visual language: `#0d0d0d/#171717/#212121/#2f2f2f`, **no accent colour**. §14: no third-party renders shown as product output. |
| `docs/superpowers/plans/2026-09-17-website-prototype.md` | **SETTLED.** Chunks 1–6. Only T13 (`plan:1508`) and T27 (`plan:2407`) touch the renderer, and both only to keep it disconnected. |
| `assets-in/refs/MANIFEST.md` | **SETTLED as the eval target set.** 12 clips, 11 unique (ref07==ref06). Zero turntables. 9 of 11 have non-camera motion. All vertical 9:16 except ref10 (1:1). All have audio. Current pipeline matches on **1 of 11** (ref06 ≈ ModVision `rainy_courtyard`). |
| Memory `rendering-prototype-decisions.md` | **SETTLED.** Renderer intentionally blank in `apps/web`. Owner 2026-09-18: *"don't focus on the backend and especially the actual rendering process"* — that ruling scopes the **web prototype**, and the 2026-09-19 entry confirms engine work belongs in render tooling. Machine: RTX 5080 16 GB, Blender 5.0, Node 24. M4 G82 traced/not commercially usable. |

### 2.2 ModVision repo

| Document | Binds |
|---|---|
| `docs/superpowers/specs/2026-07-20-ad-grade-render-design.md` | **SETTLED.** Lighting lives entirely in pinned `.blend` scene templates — there is no `hdri` field. The renderer **consumes resolved per-mesh finishes and never re-implements glob logic.** Standing ban on generative passes over car geometry. |
| `docs/superpowers/specs/2026-09-14-metallic-paint-design.md` + `plans/2026-09-14-metallic-paint.md` | **SETTLED and SHIPPED** (`js/metallic-paint.js`, merged to `origin/main`, `0b083f1`, 2026-09-17). Flake 0.15 mm. Orange-peel default 0.006. Triplanar flake perturbs the **base** normal only; clearcoat keeps `nonPerturbedNormal`. Rig is an **env map, not lights**. |
| `docs/superpowers/specs/2026-09-07-realistic-paint-design.md` | **SETTLED — owner-rejected and rolled back.** *"Do not resume without a new user request."* |
| `docs/superpowers/specs/2026-04-26-zone-paint-system-design.md` | **SETTLED.** Zone/preset resolution is the source of per-mesh finishes the ad-grade renderer consumes. |
| `docs/superpowers/plans/2026-09-09-render-performance.md` | Chunk 1 landed; Tasks 3–8 owed. Not this track's work, but the governor rules below come from it. |
| `.handoffs/2026-09-14-2110-realism-pass-...md` | **HISTORICAL.** Its "owed" list is stale — that work shipped 2026-09-17. Surviving rulings: cabin glass stays opaque (*"do not revisit"*); realism ships to dev preview until judged. |
| `CLAUDE.md` | Verification gate after any renderer/composer/bloom/reflector change: `node scripts/render-performance-check.mjs --mode=exact` (0 failures) **and** `node --test js/render-governor.test.js`. |

### 2.3 Corrections to the 2026-09-19 03:53 handoff

Found by survey on 2026-09-19. The handoff is otherwise accurate and remains the
architectural authority.

1. **MEASURED** — `spec_to_look()` emits **16** keys, not 15 (`tools/render-studio/spec.py:169-192`).
2. **MEASURED** — `checks/claude-pass/` is **not tracked code**. `.gitignore:146` ignores
   `tools/render-studio/checks/`. `mkjob3.py` / `mkjob4.py` / `encode_clip.py` are local
   scratch and may not exist on another machine. The handoff's "Relevant files" entry for
   it is a dead path for anyone but this box.
3. **MEASURED** — the three divergent pipelines are
   `ModVision/tools/render-studio`, `ModVision/tools/beauty-render`, and
   `Rendering/tools/product-render`. A survey scoped to ModVision alone will report
   `product-render` missing; it lives in the Rendering repo.
4. **MEASURED** — `spec.py:1` cites `docs/superpowers/specs/2026-09-17-render-spec-design.md`,
   **which does not exist**. RenderSpec is undocumented. §11 owes it.

---

## 3. Architecture

**SETTLED** in the 03:53 handoff. Reproduced here because everything below hangs off it.

```
user model + prompt
  │
  INGEST        measure the mesh, emit a subject report (FACTS, not guesses)
  │
  LLM           reads: API reference + rules file + subject report + prompt
  │             emits: a scene spec (structured), NOT bpy
  │
  COMPILER      spec → verified bpy; clamps, applies invariants
  │
  PREFLIGHT     scene-graph validators; fail in seconds, reason feeds back to LLM
  │
  PROXY         low-res, low-spp, full sequence
  │
  POSTFLIGHT    pixel validators; reason feeds back
  │
  FULL RENDER
```

**SETTLED** — the four enforcement tiers. Use the highest that works for each rule:

1. **Impossible** — the API does not expose the knob.
2. **Auto-corrected** — the compiler clamps or fixes it silently.
3. **Detected** — a validator fails the job; the reason feeds back for retry.
4. **Documented only** — last resort. Taste, not correctness.

> Anything in tier 4 gets violated eventually. **A rule with no enforcer is a wish.**

---

## 4. Ingest

**SETTLED** — mandatory, currently missing. "Any 3D model" plus "the LLM cannot see the
mesh" means that without a factual subject report every script is a coin flip.

### 4.1 Measure, never trust names

**PROPOSED.** ModVision keys detail off semantics (`mvSlot`, `tire-*`, `rotor-[fr][lr]`).
On an arbitrary upload there are no trustworthy names. Rewrite every rule from
*"tyres get X"* to *"surfaces with property P at scale S get X"*.

Measurable with zero semantics:

- **glTF declarations** — metallic, roughness, transmission, IOR, emission, alpha
- **geometry** — per-edge dihedral angle, curvature histogram, planarity, wall thickness
  (interior raycast), surface area, symmetry
- **spatial** — ground-contact set, concavity/AO, interior vs exterior
- **texel density** — texture px ÷ world-space UV area = mm/texel
- **screen-space** — mm/px from the camera, per shot

The detail library then keys off properties:

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

Zero-radius edges are the single most generalisable realism rule available. No real
manufactured object has one. Free on every upload, no subject knowledge required.

### 4.2 Never gate the baseline on recognition

**PROPOSED, and the most important rule in this section.**

Ingest emits a subject class. Keep it — but as a **modifier over a universal baseline,
never a gate**. The classifier will be wrong: a robot, a spaceship, a stylised tree, the
toy car already in the test set.

This is the `MANTHEY_992` bug generalised. **MEASURED** — `rain_look.py:178` gates car art
direction to `MANTHEY_992` only; every other car falls through to generic calibration.
Do not rebuild that at species scale. **Baseline always; class pack on top.**

The same bug already exists a second time on the web side. **MEASURED** —
`apps/web/lib/scene/classify.ts:15-23` decides `car` from a name regex
(`/wheel|tire|tyre|headlight|windshield|bumper|brake/i`) or proportion bands, else
`{product, 0.6}`; `capabilities.ts:3-11` then gates capability on that class. The tell is
in the repo: `apps/web/public/samples/LICENSES.md` records that the sample car's wheel
groups were **hand-renamed** `Wheel_FL/FR/RL/RR` so the analyser would succeed. A curated
sample needing a rename means user uploads will not survive it.

### 4.3 True scale is a prerequisite, not a detail

**MEASURED, and blocking.** `Rendering/tools/product-render/render_product.py:133-152`
`normalise()` scales the longest axis to exactly 1 m. Observed factors: toycar 13.52×,
flighthelmet 1.397×. A pocket watch, a lounge chair and a building all come out 1 m.

Every measurement rule in §4.1 is in real millimetres — flake 0.15 mm, bevel radius
0.3–1 mm, orange-peel period 1–3 mm, mm/texel, mm/px. After `normalise()` none of them is
computable.

Fluid simulation makes this fatal rather than merely wrong: viscosity, surface tension and
gravity all operate in real units. A can at 100× scale gets honey-thick water.

**PROPOSED fix, first code change of the month** — keep true scale as metadata and pass it
to every shader, or normalise the **camera rig** instead of the subject.

### 4.4 Ingest emits capabilities, not just facts

**PROPOSED.** Facts are for validators. Capabilities are the LLM's menu.

- wheels separate → `wheel_rotation` available
- separate roots with distinct transforms → `part_animation`, `explode`
- skinned → `rigged_motion`
- transmission materials present → `caustics_shot` worth enabling
- single welded blob → static only, **and say so up front**
- no UVs → no decal or label swap

Derive these from geometry, not names: *4+ near-identical meshes, radially symmetric about
a shared axis, touching the ground plane* → wheel rotation. Works on a skateboard, a
trolley, a robot.

**Caveat, PROPOSED** — that heuristic false-positives on office chairs (5 casters, radial
symmetry, wrong axis), shopping carts and table legs. Offer detected capabilities as a
menu; do not auto-fire motion from them.

Seeds to promote into one shared stage: `render_product.py:133` `normalise()`,
`render_product.py:156` `fix_materials()`, ModVision `material_classes.py:24-57`
`classify()`. **MEASURED** — `fix_materials()` currently writes nothing; it only records
notes despite a docstring claiming it fixes transmission. Material enhancement there is
greenfield.

### 4.5 Gate before you charge

**PROPOSED.** Most uploads will be bad — missing textures, flipped normals, no UVs, welded
blobs, wrong axis, wrong unit scale. Realism is bounded by the asset and the user will
blame the product.

- `model_analysis` already costs 0 credits (**MEASURED**, `apps/web/lib/pricing.ts:3-45`).
  Correct. Keep it.
- That free analysis must return a **plain-language verdict** before any credits are spent:
  *"no UV map — surface detail limited"*, *"single welded mesh — no motion shots available"*,
  *"scale ambiguous — is this 4 cm or 4 m?"*
- Auto-repair what is safe: normals, weld, scale, axis, missing-texture fallback to
  material-class defaults.

On scale ambiguity: **MEASURED** — `apps/web/lib/scene/inferUnits.ts:26-48` has a logged
failure where a cm-unit car with no name signal becomes a 0.45 m product. The product sells
one-click rendering, so prefer *infer → show in the proxy → let the user correct* over a
blocking form field. The proxy is the confirmation step.

---

## 5. The scene DSL

### 5.1 Why not templates

**PROPOSED.** A fixed menu of complete scenes (`fluid_drip`, `cloth_drape`, …) cannot cover
"any layout a prompt asks for". It is the same wall, moved.

The LLM should be a **programmer writing in a constrained DSL**, not a selector picking from
a menu. Finite primitives, unlimited composition.

### 5.2 Primitive vocabulary

**PROPOSED.**

**Objects & placement** — `$subject`, `surface(shape, material)`, `prop(type, position)`

**Motion** — `rotate(target, axis, speed)`, `translate(target, path|direction, speed)`,
`oscillate(target, axis, amplitude, frequency)`, `follow_path(target, curve, speed_profile)`,
`spring(target, anchor, stiffness, damping)`

**Physics** — `fluid(source, colliders, liquid_type, flow)`, `cloth(mesh, pin_points, fabric)`,
`rigid_body(objects, gravity, restitution)`, `soft_body(mesh, stiffness)`,
`particles(emitter, type, count, lifetime, physics)`, `volume(shape, material, animation)`,
`wind(direction, strength, turbulence)`, `gravity(strength, direction)`

**Camera** — `static`, `orbit`, `arc`, `push`, `track`, `flyby`, `crane`,
`handheld(path, intensity)` ← this one wraps the existing `film_camera.py` operator sim

**Lighting** — `area`, `spot`, `point`, `hdri`, `sun`

**Time** — `duration`, `sim_fps`, `render_fps` (slow-mo = high sim / low render),
`speed_ramp`, `keyframe(target, property, time, value)`

**Grade** — exposure, contrast, saturation, lift/gamma/gain, `bloom`, `vignette`, `grain`,
`lens_distortion`, `chromatic_aberration`, `fog_glow`

Each primitive maps to one **builder** — a Python function that takes validated spec input,
emits deterministic `bpy`, and returns what it created so validators can check it. The LLM
never writes `bpy`. The compiler does.

### 5.3 The escape hatch

**PROPOSED.** The DSL caps out at what has builders. *"Make the can crumple as if crushed"*
has no primitive.

**SETTLED** in the handoff: *"Escape hatch for genuinely novel requests: LLM writes `bpy`
inside a sandboxed hook, validators still gate output."*

Sandbox contract (**PROPOSED**): cannot delete `$subject`; cannot touch render settings
(the compiler owns those); cannot write outside the job directory; hard timeout on `bpy`
execution; all preflight/postflight validators still run.

DSL is the safe fast path. The hatch removes the ceiling. Validators catch both.

### 5.4 Extend `spec.py`, do not restart

**SETTLED** in the handoff. **MEASURED** state of the thing being extended:

- `SCHEMA = "modvision.render-spec/0"` (`spec.py:14`); `GROUPS = ("world","camera","look","lamps")` (`:19`)
- Top level: `schema, scene, seed, provenance` + the 4 groups (`:118`)
- `provenance` (`:111-117`) = `{source ∈ ("default","random","prompt"), prompt ≤2000, model, sampler}`
  — **the LLM path was already designed in**
- **14 spec fields total** across all three manifests: `world.{time,weather,wind}`,
  `camera.programme`, `look.{grade,exposure,saturation,fog,bloom,halation,veil,grain}`,
  `lamps.{drl,tail}`
- `rain_look.LOOK` has **50 keys**; `spec_to_look()` reaches **16** (`:169-192`)
- The other 34 are CLI-only: `render_snapshot.py:125` calls `rain_look.configure(job['look'])`,
  but `jobs.py:41` `SPEC_FIELDS` excludes `look` — **API jobs cannot reach them**
- **`camera.programme` is a single-option enum per scene.** Camera is nominally in the
  schema with **zero degrees of freedom.** This is the biggest gap for a video engine.
- Sampling, bounces and motion blur are not LOOK keys at all — they live in `jobs.PRESETS`
  and the pipeline.

Widen this schema toward §5.2. Do not throw it out.

---

## 6. Motion and simulation

**SETTLED** — the gap is motion + simulation + environment + camera language, **not surface
detail**. 9 of 11 unique reference clips have something moving that is not the camera. Zero
turntables in twelve clips. ref12 (grey clay fluid sim, no textures at all) already reads as
real.

**MEASURED** — genuinely absent in both pipelines: wheel rotation, suspension travel, tyre
contact-patch deformation. The car is a static imported GLB; **nothing keyframes car objects
in any scene.** No rigid body, cloth, particles or fluid anywhere.

### 6.1 Real-world physics rules

**PROPOSED.** Universal, both products.

| Rule | Meaning | Enforcement |
|---|---|---|
| Gravity | nothing floats unless specified | validator: non-flying objects have ground contact at frame 0 |
| Contact deformation | soft flattens against hard | auto lattice at contact points for soft material classes |
| Momentum | moving things do not stop instantly | compiler: ease curves on velocity changes, never step functions |
| Weight | heavy moves differently from light | ingest estimates mass from volume × material density |
| Inertia | turning things lean into the turn | auto roll/pitch from acceleration vectors |
| Friction | things on surfaces do not slide unfree | rigid-body friction from material class |
| Flex | long thin things flex under load | soft body on detected thin geometry |
| Settle | falling things eventually stop | rigid-body damping until kinetic energy < threshold |

### 6.2 Simulation, as primitives

**PROPOSED.** `fluid`, `cloth`, `rigid_body`, `particles`, `volume`, `wind` per §5.2, each
auto-sizing its domain/emitters from the subject bounds ingest measured.

Engineering consequences:

- **Bake time is separate from render time** and can dominate. Sim jobs must price
  differently (§9).
- **Collision meshes.** User uploads are rarely watertight; fluid leaks through
  non-manifold geometry. Ingest generates a simplified hull, or voxel-remesh for concave
  subjects (a mug needs interior collision), and reports *"mesh not watertight — fluid may
  leak"* at preflight.
- **Sim element materials come from the primitive, not the upload.** `liquid_type: water`
  always means transmission 0.95 / IOR 1.33 / roughness 0. The LLM parameterises colour and
  viscosity; it never authors the shader graph.
- **Rain already does not fall through objects.** **SETTLED** — `rain_atmosphere.py:58-103`
  does a per-column BVH raycast for `rain_stop_height`. The owner's example is solved; do
  not cite it as an open bug.

### 6.3 Three settings capping the product half of the business

**MEASURED** — `render_product.py:522-526`:

```
caustics_reflective  = False
caustics_refractive  = False
sample_clamp_indirect = 8.0
blur_glossy          = 0.5
```

These suppress exactly the highlights that sell glass, chrome, liquid, jewellery, bottles
and watches. ref10 is a Rolex — that whole category is capped by config, not by the
renderer. **PROPOSED**: enable for macro/product shots; leave off for wides where they only
cost time.

### 6.4 Credit where due

**MEASURED**, keep both:

- `render_product.py:449-472` keyframes the camera from −1 to n+1 **specifically so motion
  blur has data past both ends.** Done right.
- `render_product.py:409-446` `solve_framing()` binary-searches silhouette fill; every clip
  hits its fill target exactly.

`solve_framing()`'s problem is not the solver. **Fill is a fraction of frame *height*,
output is 1920×1080, and the reference set is 12/12 vertical.** A tall narrow subject at
0.6 height occupies ~15% of frame width. **PROPOSED**: derive aspect from subject aspect and
target platform, never fix it at landscape.

---

## 7. ModVision as a vertical specialisation

**PROPOSED.** Same compiler, same validators, extended vocabulary.

### 7.1 Vehicle dynamics rig

Built once per car at import, from ingest measurements plus ModVision's existing spec data.

- **Wheel rotation** — exact math, not simulation. `angular_velocity = linear_velocity / radius`.
- **Suspension** — pre-baked f-curves, parameterised by car weight and spring rate
  (`data/bmw-specs.js` already holds the inputs). Sinusoidal with damping on smooth road,
  noise-modulated on rough.
- **Body dynamics** — `roll_angle = lateral_acceleration × roll_gradient`. Pure math from
  path curvature and speed.
- **Tyre contact patch** — lattice modifier, statically flat at the bottom with sidewall
  bulge. Cheap, large realism gain.
- **Steering** — front wheels on the vertical axis, Ackermann geometry, driven by path
  curvature.

No tyre model and no engine torque curve. Visually believable motion curves are the target,
not vehicle simulation.

### 7.2 Driving camera programmes

Car-specific additions to the §5.2 camera set: `rolling_shot(match_speed, offset)`,
`fly_by(car_speed, camera_offset)`, `chase(follow_distance, damping)`,
`hero_approach(stop_distance)`, `drone_track`, `wheel_detail`.

Motion blur is the shot-defining variable: heavy on fly-by (the car should streak and still
read), subtle on rolling (wheels sharp, background soft), none on interior.

**MEASURED, and a hard blocker for any orbit-path driving shot** —
`render_snapshot.py:318-321` sets the orbit camera position **per frame without
keyframing**, so Cycles has no motion vectors and orbit scenes get **no motion blur at
all**; that path also has no DOF. `render_product.py:449-472` already does this correctly.
Fix by adopting the product-render approach.

### 7.3 What ModVision does not inherit

No fluid/cloth/particle simulation is needed for cars in the near term. Rain is atmospheric
and already solved. Sim primitives are Rendering-first.

---

## 8. Judging and learning

This is the hardest operational problem: renders are slow, and quality cannot be judged at
proxy resolution.

**MEASURED** — ~30–40 s/frame at 1080p / 192 spp on the RTX 5080. A 10 s clip at 24 fps is
240 frames ≈ **2.3 GPU-hours**. Nobody iterates on 2.3-hour cycles.

### 8.1 Tiered judgment

**PROPOSED.**

| Tier | Cost | Judges |
|---|---|---|
| **1 — Scene graph** | 0 s | placement, camera clipping, sim domain enclosure, materials assigned, textures resolved |
| **2 — Proxy** (low-res, low-spp, **full sequence**) | ~1 s/frame | motion, sim stability, composition across all frames, fluid contact vs leak, animation timing, camera smoothness |
| **3 — Key frames** (full res, full spp, **3–5 frames only**) | ~35 s/frame | material quality, DOF/bokeh, motion blur quality, noise, fine detail, colour, caustics |
| **4 — Full render** | hours | — runs only after 1–3 pass |

Pre-commit cost is minutes instead of hours, and it catches the large majority of defect
classes before the expensive render starts.

**Key frames are chosen, not sampled.** The compiler knows where the interesting moments are
because it built the scene: frame 0, the peak-physics frame (first fluid contact, cloth
settle), a composition frame around the golden ratio of the camera arc, the specular/caustic
peak frame, and the final frame. Cap at 5.

### 8.2 How the system actually learns

**PROPOSED, and the core claim of this section: the LLM is stateless; the validators are the
memory.**

Three mechanisms, stacked.

**1. Validators accumulate.** Every production defect becomes a mechanical enforcer. The
rules file only grows. The system stops repeating a mistake not because a model learned, but
because a validator physically prevents it. Rules-file format is **SETTLED** in the handoff:

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

`enforced_by` is mandatory. **SETTLED** — generate the API-reference half of the rules file
**from the code**; a hand-written API doc drifts and then the LLM is reading fiction.

**2. A vision model scores the key frames.** A human cannot watch every render. Score the
3–5 key frames against a fixed rubric — subject visible, rests naturally, no artifacts or
fireflies, lighting reads, physics plausible, materials hold up at this distance,
composition balanced, no geometry clipping. Failures return *specific reasons* that feed the
retry loop. Over time this matters less, because the defects it catches get promoted into
mechanical validators.

**3. Golden examples.** Every render that scores well has its spec added to a library, which
becomes the LLM's few-shot context. No fine-tuning, no training infrastructure — better
examples, not a better model.

**The failure feedback must name the specific violated rule.** That loop is what produces
"no defects" — not the rules file on its own.

### 8.3 Honest expectations

**PROPOSED, and explicitly a projection, not a measurement.** No first-attempt success rate
has been measured, because none of this is built. The defensible claim is directional:
first-attempt success rises as validators accumulate, because the defect space is finite and
validators only ever accumulate. Put real numbers here only once the week-1 harness produces
them.

---

## 9. The output is an edited video, not a render

**PROPOSED.** Everything above produces raw footage — one continuous shot. The reference set
says that is not the product: **all 12 clips have audio**, all but one are vertical, and
they are edited pieces.

An advertisement is a shot list plus an edit decision list plus audio plus graphics, and
then a platform-specific export. The LLM's job widens from *"write one scene spec"* to
*"write a production"*: several shots (each its own render job, independently
parallelisable), transitions, motion-graphic cards that never touch Blender, a
beat-synced music bed, SFX triggered off simulation contact events, loudness-normalised
mastering, and multi-aspect export (9:16, 16:9, 1:1, 4:5).

**MEASURED** — no pipeline emits audio today, and `pipeline.py:261-271` / `encode_clip.py`
ship **no `-color_primaries` / `-color_trc` / `-colorspace` flags**, so every MP4 is
untagged and players guess. That is the cheapest realism win available and belongs in week 4.

### 9.1 AI-augmented stages

**PROPOSED, all optional and all post-render** — none of these touch light transport, so
none violates the no-from-scratch-renderer ruling:

- **Upscale** — render 1080p, upscale to 4K. Changes 4K economics substantially.
- **Hybrid backgrounds** — path-trace the subject on a shadow catcher, generate or
  substitute the environment behind it, composite. Avoids hand-building 50 Blender worlds
  while keeping the *subject* physically rendered.
- **Audio** — generated ambience and SFX.
- **Motion graphics** — 2D, from a brand kit.

**Constraint check:** ModVision's ad-grade spec carries a **standing ban on generative
passes over car geometry** (§2.2). Hybrid backgrounds are compatible *only* where the
generated content is strictly behind a matted subject. On ModVision, treat any generative
pass as banned until the owner rules otherwise.

---

## 10. Conflicts to reconcile before code

These are the places where this plan and existing shipped code disagree. Each needs a
decision.

1. **`ScenePlan` cannot express the reference set.** **MEASURED**,
   `apps/web/lib/schema/scene-plan.ts`: `subject.motion` is the literal string
   `"stationary"`; `shots` is 1–2 items; the four `ShotAction`s are camera-only and include
   `slow_orbit` (against the "zero turntables" finding); there are no simulation fields, no
   audio, no aspect ratio; `Resolution` implies 16:9 while 12/12 refs are vertical;
   `DurationS` caps at 30 while ref11 is 35.4 s. A `superRefine` (`:64-77`) requires shots
   contiguous from 0 ending exactly at `output.durationS`, so widening touches that and
   every `applyPatch` clamp test.
2. **The blank renderer is a tripwire, not an oversight.** **MEASURED** — a Playwright
   assertion and `services.test.ts:79` both assert the not-connected state. Connecting a
   real renderer to `apps/web` **breaks green tests by design.** Engine work happens in
   render tooling; any web wiring is a separate, later, owner-gated decision.
3. **`RenderJob` is too thin for a real queue.** **MEASURED**,
   `apps/web/lib/schema/project.ts:72-86`: no seed, no cost, no timestamps, no log channel;
   `subscribe` is push-only with no reconnect/polling semantics.
4. **The credit ledger cannot record a render.** **MEASURED** — `CreditReason` (`:89`) is
   `starting_balance|scene_generation|prompt_edit|pack_purchase|plan_grant`. **No render
   reason exists.**
5. **The credit table will not survive contact.** **MEASURED** — `pricing.ts:3-45` prices
   `local_final: 5` and `preview_render: 3`. A 10 s 1080p clip is ~2.3 GPU-hours on the
   5080. Simulation bakes are additional and can dominate. Re-derive from measured
   GPU-minutes once the week-1 harness exists; sim-bearing jobs need their own tier.
6. **Three look systems are structurally incompatible, not merely duplicated.** **MEASURED**
   — render-studio is a validated document plus a 50-key `LOOK`; beauty-render is a
   name-matched if/elif chain with hardcoded RGBA constants (`render_job.py:152-223`), one
   HDRI Z-rotation as its only lighting control, and no schema/seed/manifest;
   product-render is a third `LOOKS` table. **A single compiler must sit upstream, emitting
   resolved per-mesh finishes** — exactly what the ad-grade spec already demands — rather
   than merging shader code.
7. **Environment name collision.** **MEASURED** — `studio_black` in the web viewer
   (`environmentLook.ts`) is a colour table; `studio_black` in `render_product.py:34-45,
   181-235` is a bent-plane cyclorama with light-linked rigs. Same name, different object,
   no shared source. Harmless while render returns `not_connected`; the day it connects,
   users receive something other than what they approved. One environment definition,
   renderer-authored; the viewer renders an approximation.
8. **Environments need a subject-size contract.** **MEASURED** — the product-render light
   rig is a fixed 3 m setup that is only "scale-independent" because the subject is forced
   to 1 m (`:276-311`). That breaks the moment there are 6–8 real worlds. Each environment
   declares a valid subject-size range, lights in true metres, a placement contract (ground
   anchor, up axis, facing, clear volume), and a frame aspect derived from subject aspect.
9. **beauty-render is live.** **MEASURED** — scheduled task `ModVision-Beauty-Render` fires
   every 5 minutes and is **Ready, not disabled**. Consolidation must not silently break a
   running task. Also `worker.py:56-60` re-derives `outDir`/`shots` defaults independently
   from `render_job.py` — a duplicated default that will desync.
10. **ModVision's pixel-exactness gates are shipped and binding.** **MEASURED** —
    `?render=legacy` must stay byte-for-byte pre-2026-08-26 (`render-profile.js:18`:
    *"Never 'improve' the legacy numbers — add a new profile instead"*);
    `js/render-governor.js` is the **sole** owner of quality/speed trades and **Auto may
    never change the look** (`AUTO_FLOOR = faster`, owner ruling 2026-09-10). Gate:
    `render-performance-check --mode=exact`, run alone, 0 failures, plus
    `node --test js/render-governor.test.js`.
11. **Material-class separation is load-bearing.** **MEASURED** — glass uses `transmission`,
    which metallic explicitly refuses to hook; light lenses are deliberately not shared with
    `_glassMat` (*"Do not change this"*); carbon source materials must never be disposed;
    live (`_flatPaintMeshes` rAF) and static paint meshes must not share a material.
12. **The eval set is 9/12 cars, and the six test models are all product-category.** Score
    against that and the month ships a car renderer. **Add reference targets for what the
    Rendering product will actually receive** — furniture, apparel, electronics, food,
    characters — *before* the week-1 harness exists, because the harness encodes the target.

---

## 11. Month plan

**SETTLED** shape from the handoff, with this document's additions marked.

### Week 1 — make improvement measurable
- **Eval harness** scored against the 12 reference clips. *Without scoring, everything after
  is vibes.*
- **PROPOSED, blocking, do first:** kill `normalise()`'s scale destruction (§4.3). Every
  later measurement rule depends on it.
- **PROPOSED:** broaden the eval set beyond cars (§10.12).
- Begin pipeline consolidation — decide which of the three becomes the compiler.
  `product-render` is the cleanest seed (framing solver, correct motion-blur keyframing);
  render-studio owns the only real schema and the operator sim.
- **PROPOSED:** write the missing `render-spec-design.md` that `spec.py:1` already cites.
- **PROPOSED:** build ingest first, since weeks 2–3 consume its output.

Iterate here, not on ModVision's rain scene: **MEASURED** — product renders run 2–4 s/frame
versus 29–40 s/frame for the rain scene. Sweeps are affordable on this pipeline in a way
they are not on the other.

### Week 2 — motion
- Vehicle dynamics rig (§7.1) and driving camera programmes (§7.2) for ModVision.
- General motion primitives (§5.2) and the first simulation primitives for Rendering.
- Fix the un-keyframed orbit camera (§7.2) so motion blur exists on that path at all.
- Product-side sim presets begin here and continue into week 3.

### Week 3 — environments
**SETTLED** — *this is where most of the month actually goes.* 6–8 hand-built pre-lit worlds
(tunnel, night highway, forest, coast road, garage, studio), each with its own volumetrics
and grade baked in, each declaring the §10.8 contract.

**MEASURED** justification: the compositor (`rain_look.py:335-388`) and volumetrics
(`:308-322, 391-443`) already exist and are richly built — but **gated to rainy scenes
only**. `turntable`/`night_garage` use a flat colour world, no volumetrics, no compositor,
no DOF, no motion blur, and look like CG on identical Cycles. **The month is generalisation,
not invention.**

Also here: the 1k `DEFAULT_HDRI` at strength 0.3 (`render_product.py:32`) gives chrome and
brass a grey ramp to reflect. Same disease as ModVision's turntable, and it hits every
reflective subject the product will ever receive.

### Week 4 — validators, output, polish
- Validator suite and the repair loop (§8).
- Vertical-first output and an audio bed.
- EXR/AOV output; light groups so relighting does not require re-rendering.
- Caustics enabled for lamp and product shots (§6.3).
- **Colour-tagged encode** (§9) — cheapest realism win available.

---

## 12. Pitfalls — do not retry

**SETTLED** from the handoff, verified still accurate on 2026-09-19.

- **Do not lead with "add an imperfection layer."** It was ranked #1 early in a prior session
  and the owner overturned it with the reference clips. It is the right lever for exactly one
  category — static hero macro (ref06, ref10) — and near-irrelevant for the other nine.
- **Do not claim ModVision lacks compositing / volumetrics / imperfections.** It has all
  three, richly — but only behind `if scene == rainy`. Easy to mis-audit from
  `render_product.py` alone.
- **Do not cite "rain falls through objects" as an open bug.** Solved at
  `rain_atmosphere.py:58-103`.
- **Do not propose a from-scratch path tracer.** Settled, with evidence: identical Cycles
  produces both the film-grade and the CG-looking tier. A from-scratch tracer improves
  neither and costs years to reach parity. It pays only for a *real-time preview* so users
  iterate before a slow bake.
- **Do not plan the month as "add realism features."** The features largely exist,
  hard-coded to one scene and one car.
- **PROPOSED addition:** do not gate any detail or capability on subject recognition (§4.2).
- **PROPOSED addition:** do not simulate rendering anywhere in `apps/web` — it breaks a
  deliberate test tripwire and an explicit memory rule.

---

## 13. Open questions for the owner

Nothing in this document has owner approval. These specifically need a ruling before the
work they block can start.

1. **Scope of the month** — both products, or Rendering first with ModVision inheriting
   later? §7 assumes shared-core-plus-specialisation.
2. **Which pipeline becomes the compiler.** `product-render` is the cleanest seed;
   `render-studio` owns the schema and the operator sim. Consolidation order follows this
   answer.
3. **Generative/AI post-passes (§9.1)** — allowed on Rendering? The ad-grade standing ban
   covers car geometry; hybrid backgrounds behind a matted subject are arguably outside it,
   but that is the owner's call, not this document's.
4. **Does the escape hatch (§5.3) ship**, or is v1 DSL-only? It is the difference between
   "any prompt" and "any prompt we have builders for".
5. **Credit re-pricing (§10.5)** — the current table is off by orders of magnitude against
   measured GPU time. Re-derive after week 1, or hold until the engine is real?
6. **Eval-set expansion (§10.12)** — which non-car categories matter most commercially?
   That choice encodes the target the whole month optimises toward.
7. **`beauty-render`'s live scheduled task (§10.9)** — pause during consolidation, or keep
   it running and consolidate around it?

---

## 14. Provenance

Written 2026-09-19. Sources:

- `.handoffs/2026-09-19-0353-renderer-engine-realism-strategy.md`, read in full
- Two read-only surveys run 2026-09-19 over the Rendering repo and the ModVision
  `modvision-renderer-quality-e9326d` worktree; all **MEASURED** citations come from those
- A design conversation on 2026-09-19; everything traceable only to it is marked
  **PROPOSED**

Numbers and line references are true of the tree as of 2026-09-19 and were not re-verified
afterwards. Re-check before acting on any of them.
