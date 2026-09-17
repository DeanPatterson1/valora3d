# Website Prototype — Design Spec

Date: 2026-09-17
Status: approved in brainstorm, pending written review

## 1. Purpose

Frontend-only prototype of the AI 3D rendering product ("upload a model, describe the shot, get a cinematic render"). Its job is to lock the user experience — flow, layout, motion, and persuasion — before any real backend exists. The code is kept as the base of the real frontend, so structure matters as much as looks.

Audience: the owner only. Runs locally with `npm run dev`. No deployment.

Priorities, in order: UI quality, animation quality, applied UX psychology, clean seams for later backends.

## 2. Scope

In scope:

- Landing page, projects dashboard, studio, pricing + credits.
- Real in-browser 3D viewer with real model loading (GLB, GLTF, FBX, OBJ).
- Heuristic model analysis and keyword prompt-to-scene-plan mapping, both local and fake.
- Scene version history, manual sliders, output settings.
- Fake credits.
- Render UI surfaces (render choice, job progress, result) as visual states only.

Out of scope:

- The rendering process itself. The owner has a separate plan for it. See section 7.
- Auth, database, real AI calls, payments, object storage, deployment, Tauri agent.
- Mobile-optimised layout. Pages must not break below 768px, but the studio targets desktop.

## 3. Stack

- Next.js (App Router), TypeScript strict, Tailwind CSS.
- three, @react-three/fiber, @react-three/drei for the viewer.
- Motion (`motion/react`) for UI animation.
- Zustand with `persist` for state, `idb-keyval` for model blobs, zod for schemas.
- Vitest for unit tests, Playwright for one end-to-end path.

The product name is a single constant in `lib/brand.ts` (working name: "Render Studio").

## 4. Routes

| Route | Purpose |
|---|---|
| `/` | Landing page |
| `/projects` | Dashboard: project grid, create, rename, delete |
| `/projects/[id]` | Studio |
| `/pricing` | Plans, credit packs, action cost table |

A shared header shows logo, Projects, Pricing, and the credit balance.

## 5. Architecture

Three layers with one-way dependencies: UI components → stores → services.

```
app/                    routes and layouts
components/
  landing/  dashboard/  studio/  pricing/  ui/ (primitives)
  viewer/               R3F canvas, model, environment presets, camera path
lib/
  brand.ts
  schema/               zod schemas + inferred types
  services/             interfaces + local implementations
  stores/               Zustand stores
  motion/               shared motion tokens and variants
public/samples/         bundled CC0 models
```

### 5.1 Schemas (`lib/schema`)

`Project`, `Asset`, `ModelAnalysis`, `ScenePlan`, `ScenePatch`, `SceneVersion`, `RenderJob`, `CreditTransaction`.

`ScenePlan` follows the owner's scene JSON: `scene`, `subject`, `camera`, `shots[]`, `lighting`, `effects`, `output`. Enumerated fields (environment, camera style, shot action, lighting style, ground material) are zod enums limited to the MVP library: environments `studio_black`, `studio_white`, `outdoor_road`, `urban_night`; cameras `slow_orbit`, `hero_push_in`, `low_tracking`, `handheld_walk`; effects `fog`, `rain`, `depth_of_field`, `motion_blur`, `wet_ground`. This schema is written carefully because it later becomes the shared `scene-schema` package.

`RenderJob.status` is the enum `QUEUED | PREPARING | RENDERING | ENCODING | UPLOADING | COMPLETE | FAILED`, defined now so UI states and the future backend agree.

### 5.2 Services (`lib/services`)

Each is a TypeScript interface with one local implementation. UI never imports an implementation directly; a `services` module exports the active set.

| Interface | Local implementation |
|---|---|
| `ProjectStore` | Metadata in localStorage, model files in IndexedDB |
| `AnalysisService.analyze(sceneStats)` | Heuristics, section 6.2 |
| `DirectorService.plan(prompt, analysis)` and `.edit(prompt, plan)` | Keyword mapper, section 6.3 |
| `CreditService` | Local ledger of `CreditTransaction` |
| `RenderService` | Not implemented, section 7 |

All service methods are async and return a discriminated result (`{ ok: true, value } | { ok: false, error }`) so real network implementations drop in without changing call sites.

## 6. Behaviour

### 6.1 Upload and viewer

- Drag-and-drop or file picker. Accepted: `.glb`, `.gltf`, `.fbx`, `.obj`. Cap 500 MB. Two bundled sample models (one car, one product, CC0) are offered on the empty state so the studio works with no upload.
- Parsed in the browser with GLTFLoader, FBXLoader, OBJLoader. Multi-file glTF and OBJ with external textures are not supported in the prototype; the UI says so and suggests GLB.
- After load: compute bounds, centre on origin, rest on ground plane, auto-frame camera. Orbit, zoom, pan. Ground grid.
- Scene statistics read from the loaded scene: triangle count, mesh count, material count, object names, dimensions, presence of skeleton and animation clips.
- A dashboard thumbnail is captured from the canvas after first frame.

### 6.2 Analysis (fake, half real)

Input is the real scene statistics. Output is a `ModelAnalysis`.

- Unit inference: if the longest dimension is outside 0.05–30 units, test scale factors 0.001, 0.01, 0.0254, 100 and pick the one landing in a plausible range; report "likely millimetres" and so on.
- Category: object-name keywords (`wheel`, `tire`, `headlight`, `windshield` → car) plus proportions (3.5–5.5 m long, length > width > height → car). Otherwise `product`. Confidence is a simple score from how many signals matched.
- Capabilities from category and rig presence, per the owner's capability table (car: drive, steer, wheel_rotation; product: rotate, pedestal; rigged: depends on armature).
- The card presents category, confidence, normalised dimensions, detected parts, capabilities, rig status.

### 6.3 Director (fake)

- `plan`: start from a category default plan, then apply keyword rules (night, rain, wet, fog, studio, road, city, handheld, orbit, push in, tracking, close, low, cinematic, duration and resolution mentions). Unknown prompts still return the valid default plan.
- `edit`: follow-up prompts return a `ScenePatch` (`update_lighting` with `exposure_delta`, `modify_camera` with `distance_multiplier`, `set_effect`, `set_environment`) applied to the current plan. Unrecognised edits return an error result with a friendly message and example phrasings.
- Compatibility check: vehicle verbs (drive, accelerate, drift) against a non-vehicle category return a warning the user can accept ("place it on the road anyway, no driving animation") or dismiss.
- Every successful plan or edit creates a `SceneVersion` with its prompt. Selecting an older version restores it; new edits branch forward from the selected version and later versions are dropped.
- Manual sliders (handheld amount, motion smoothness, depth of field, fog, light level) write directly to the current plan and create a version on release, not on every tick.

### 6.4 Viewer reflection of the plan

The viewer shows intent, not final quality: environment preset changes background, lighting rig, fog and ground look; rain is a light particle layer; the camera path for each shot is drawn as a line with a timeline scrubber that moves a preview camera along it. Handheld amount adds visible sway to the preview camera.

### 6.5 Credits

Starting balance 100. `/pricing` "buy" buttons add credits to the ledger with no payment. Scene generation costs 2. Render prices are displayed on the render choice UI but never charged, because nothing renders. Insufficient balance blocks the action with an inline upsell to `/pricing`.

## 7. Render surfaces (process intentionally blank)

The owner will supply the rendering process later. The prototype contains only the surfaces around it:

- `RenderService` interface is declared (`requestPreview`, `requestFinal`, `subscribe(jobId)`) with types only. The active implementation returns `{ ok: false, error: "not_connected" }`.
- Render tab UI: Generate Preview button, Local GPU vs Cloud GPU choice cards with credit prices and trade-offs, output summary, Render button. Pressing either action shows a deliberate "Renderer not connected yet" state, not an error.
- Presentational components `JobProgress` (all seven states, frame counter, progress bar) and `RenderResult` (player frame, download, regenerate) are built and driven purely by props.
- A `/dev/render-states` page renders those components in every state with fixture props so the design can be reviewed. It contains no timers and simulates no process.

No fake job state machine, no sample MP4, no simulated progress.

## 8. Visual design

Dark cinematic. Near-black layered surfaces, one accent colour, high-contrast type, the viewer as the hero of every studio screen. Panels recede; renders and the model get the light. Design tokens (colour, radius, spacing, type scale, shadow) live in Tailwind theme config, not scattered literals.

Studio layout: viewer centre; version history in a left rail; prompt, preset chips and output settings docked at the bottom; tabbed right panel (Analysis, Controls, Render).

## 9. Motion

Tokens in `lib/motion`: durations (fast 150ms, base 250ms, slow 450ms), two easings (standard, emphasised), spring presets. Shared variants for fade-rise, stagger list, panel slide, scale-press.

Applied motion:

- Landing: hero reveal, scroll-triggered section entrances, animated three-step flow, hover depth on gallery cards.
- Dashboard: staggered grid entrance, shared-layout transition from project card into studio.
- Studio: model drop-in with camera settle on load; analysis card fields revealing one by one as if being discovered; plan changes cross-fading environment and easing the camera path; version rail items sliding in; slider and chip micro-interactions; credit counter ticking on change.
- Route transitions are short fades; nothing blocks input for more than 300ms.
- `prefers-reduced-motion` disables non-essential motion and replaces it with opacity changes.

Motion always communicates state change or hierarchy. No looping decoration in the studio.

## 10. Applied psychology

Each principle maps to a concrete decision:

| Principle | Application |
|---|---|
| Hick's law | One primary action per screen state. Studio reveals steps progressively: upload → analysis → prompt → render. |
| Progressive disclosure | Manual sliders and output settings collapsed until a plan exists. No Blender-style control wall. |
| Goal gradient | Step indicator in the studio showing progress toward a finished render. |
| Labour illusion | Analysis and scene planning show staged, named steps ("reading geometry", "identifying parts") over a short minimum duration instead of an instant result. |
| Zeigarnik effect | Dashboard cards show unfinished state ("scene ready, not rendered") to pull users back. |
| Blank-page avoidance | Sample models, preset chips and example prompts on every empty state. |
| Recognition over recall | Presets, chips and version history labelled with the user's own prompt text. |
| Anchoring and decoy | Pricing shows three plans with the middle plan highlighted; cloud price shown beside local price so local reads as a bargain. |
| Loss aversion | Low-credit state warns before an action fails; destructive actions need confirmation and offer undo. |
| Peak-end rule | The result surface is the most polished moment; the model-load moment is the first peak. |
| Doherty threshold | Every interaction responds within 400ms; optimistic UI for local operations. |
| Aesthetic-usability | Consistent tokens, generous spacing, restrained accent use. |
| Social proof | Landing gallery and usage stats are marked as placeholder content in code so they are never shipped as fake claims. |

Persuasion stays honest: no fake urgency, no fake scarcity, no hidden costs, no confirm-shaming.

## 11. Error handling

Inline, specific, recoverable messages for: unsupported format, file over 500 MB, parse failure, multi-file model missing dependencies, storage quota exceeded (offer to delete old projects), insufficient credits, project id not found (redirect to dashboard with notice), IndexedDB unavailable (session-only mode with a banner). A route-level error boundary wraps the studio; a viewer-level boundary keeps a WebGL failure from taking down the page.

## 12. Testing

- Vitest: schemas, unit inference, category heuristics, director keyword rules and patches, version branching, credit ledger.
- Playwright: open dashboard → create project → load sample car → analysis appears → enter prompt → plan and version appear → edit prompt → second version → render tab shows not-connected state.
- Manual visual review through `/dev/render-states` and the running app.

## 13. Assets

Two CC0 sample models (car, product) under `public/samples` with licence noted in `public/samples/LICENSES.md`. Landing imagery uses viewer screenshots and gradient placeholders; no third-party renders presented as product output.
