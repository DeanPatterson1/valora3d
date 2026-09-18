# Website Prototype — Design Spec

Date: 2026-09-17
Status: approved in brainstorm, revised after spec review, pending owner review

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
- Undo for destructive actions (confirmation only) and any offline or session-only storage mode.

## 3. Stack

- Next.js (App Router), TypeScript strict, Tailwind CSS.
- three, @react-three/fiber, @react-three/drei for the viewer.
- Motion (`motion/react`) for UI animation.
- Zustand for in-memory state, `idb-keyval` for IndexedDB, zod for schemas.
- Vitest for unit tests, Playwright for one end-to-end path.

The product name is a single constant in `lib/brand.ts` (working name: "Render Studio").

## 4. Routes

| Route | Purpose |
|---|---|
| `/` | Landing page |
| `/projects` | Dashboard: project grid, create, rename, delete |
| `/projects/[id]` | Studio |
| `/pricing` | Plans, credit packs, action cost table |
| `/dev/tokens` | Design-token and primitive style sheet, the phase 2 approval gate |
| `/dev/render-states` | Design review page for render surfaces (section 7) |

A shared header appears on every route: logo, Projects, Pricing, credit balance.

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
  scene/                pure functions: applyPatch, defaultPlan, inferUnits, classify
  services/             interfaces + local implementations
  stores/               Zustand stores
  motion/               shared motion tokens and variants
  pricing.ts            all credit and plan numbers
public/samples/         bundled CC0 models
```

### 5.1 Schemas (`lib/schema`)

`Project`, `Asset`, `SceneStats`, `ModelAnalysis`, `ScenePlan`, `ScenePatch`, `SceneVersion`, `RenderJob`, `CreditTransaction`.

**`Project`**: `id`, `name`, `createdAt`, `updatedAt`, `assetId | null`, `analysis: ModelAnalysis | null`, `selectedVersionId | null` (so selection survives reload). The dashboard state label is derived, not stored: no asset → `No model`; asset and zero versions → `Model ready`; otherwise `Scene ready`.

**`Asset`**: `id`, `projectId`, `fileName`, `format: "glb" | "gltf" | "fbx" | "obj"`, `sizeBytes`, `source: "upload" | "sample"`, `blobKey | null` (IndexedDB key, uploads only), `sampleUrl | null` (samples are referenced by their `/samples` URL and never copied), `thumbnailKey | null`.

**`CreditTransaction`**: `id`, `amount` (signed integer), `reason: "starting_balance" | "scene_generation" | "prompt_edit" | "pack_purchase" | "plan_grant"`, `projectId | null`, `createdAt`. Balance is the sum of the ledger.

**`SceneStats`** (viewer output, analysis input): `triangleCount`, `meshCount`, `materialCount`, `objectNames: string[]`, `materialNames: string[]`, `extents: [x, y, z]` in file units, `hasSkeleton`, `animationClipCount`.

**`ModelAnalysis`**: `category: "car" | "product"`, `confidence: 0–1`, `unitGuess: "m" | "mm" | "cm" | "in" | "unknown"`, `scaleFactor`, `dimensionsMeters: [l, w, h]`, `parts: Record<string, string>` (role → object name), `capabilities: string[]`, `rigged: boolean`.

**`ScenePlan`**:

```
scene:    { environment: Environment, time: "day" | "dusk" | "night",
            ground: Ground, fogDensity: 0–0.1 }
subject:  { category, position: [x,y,z] metres, motion: "stationary" }
camera:   { style: "smooth" | "handheld", lensMm: 18–135, heightM: 0.2–3,
            motionStrength: 0–1 }
shots:    Shot[]  (1 or 2)
          Shot = { id, start: s, end: s, action: ShotAction,
                   distanceMultiplier: 0.4–2.5 }
lighting: { style: LightingStyle, exposure: -3–3 EV, rim: boolean,
            practicals: boolean }
effects:  { rain: 0–1, wetGround: 0–1, motionBlur: 0–1,
            depthOfField: 0–1 }
output:   { fps: 24 | 30 | 60, durationS: 5 | 10 | 15 | 30,
            resolution: "720p" | "1080p" | "1440p" | "4k",
            quality: "draft" | "standard" | "high" | "ultra" }
```

Enums, limited to the MVP library:

- `Environment`: `studio_black`, `studio_white`, `outdoor_road`, `urban_night`
- `Ground`: `studio_floor`, `dry_asphalt`, `wet_asphalt`, `concrete`
- `ShotAction`: `slow_orbit`, `hero_push_in`, `low_tracking`, `handheld_walk_toward`
- `LightingStyle`: `soft_studio`, `dramatic_three_point`, `night_city`, `sunset`, `overcast`

Shots must be contiguous, non-overlapping and end at `output.durationS`; the schema refines this. This schema later becomes the shared `scene-schema` package.

**`ScenePatch`** is a discriminated union on `operation`:

- `update_lighting { exposureDelta?, style?, rim?, practicals? }`
- `modify_camera { shotId?, distanceMultiplier?, heightDelta?, lensMm?, style?, motionStrength? }`
- `set_shot_action { shotId, action }`
- `set_effect { effect: keyof effects, value }`
- `set_scene { environment?, time?, ground?, fogDensity? }`
- `set_output { partial output }`

Patch semantics: `exposureDelta` and `heightDelta` are relative; callers holding an absolute target (the light slider) compute the delta from the current plan. `distanceMultiplier` multiplies the shot's current value, so repeated "closer" keeps moving in. An omitted `shotId` in `modify_camera` means all shots. Shot-action words in an edit target the last shot. Edit step sizes live in `lib/scene/editSteps.ts`: darker/brighter ±0.7 EV, closer/further ×0.75 / ×1.33, lower/higher ±0.3 m, wider/tighter to the next lens in 24, 35, 50, 85, longer/shorter to the next allowed duration, effect add/remove to 0.5 / 0. An edit whose every patch is already at its limit returns `ok: false` with `code: "at_limit"` and no charge.

Every change to a plan after creation — prompt edit, slider, output setting — is a `ScenePatch` applied by `applyPatch`. When `set_output` changes `durationS`, `applyPatch` rescales every shot's `start` and `end` proportionally so the contiguity invariant holds.

**`SceneVersion`**: `id`, `projectId`, `index`, `prompt` (or `"manual: <control>"`), `parentId | null`, `plan`, `createdAt`.

**`RenderJob.status`**: `QUEUED | PREPARING | RENDERING | ENCODING | UPLOADING | COMPLETE | FAILED`, defined now so UI states and the future backend agree.

**Capability table** (category → capabilities): car → `drive, brake, steer, wheel_rotation` (only if four wheel parts are detected, else `static, rotate`); product → `rotate, pedestal`; any model with a skeleton adds `rigged_motion`.

### 5.2 Services (`lib/services`)

Each is a TypeScript interface with one local implementation. UI and stores never import an implementation directly; `lib/services/index.ts` exports the active set.

| Interface | Local implementation |
|---|---|
| `ProjectRepository` | Projects, versions and asset metadata in localStorage; model blobs and thumbnails in IndexedDB |
| `AnalysisService.analyze(stats: SceneStats)` | Heuristics, section 6.2 |
| `DirectorService.plan(prompt, analysis)` and `.edit(prompt, plan)` | Keyword mapper, section 6.3 |
| `CreditService` | Ledger of `CreditTransaction` in localStorage |
| `RenderService` | Not implemented, section 7 |

All methods are async and return:

```
type Result<T> =
  | { ok: true; value: T; warnings?: Warning[] }
  | { ok: false; error: ServiceError }
type ServiceError = { code: string; message: string; hints?: string[] }
type Warning = { code: string; message: string }
```

`DirectorService.edit` returns `ScenePatch[]` (one per recognised intent, so "darker and add rain" yields two); the store applies them in order with the pure function `applyPatch(plan, patch)` from `lib/scene` as one version for one credit. `applyPatch` which clamps to schema ranges and preserves the shot invariant.

### 5.3 Stores (`lib/stores`)

Stores are in-memory caches over services. They do not use Zustand `persist`; services own persistence.

| Store | Holds | Talks to |
|---|---|---|
| `useProjectsStore` | Project list, load state; create, rename, delete | `ProjectRepository` |
| `useStudioStore` | Open project, asset, `SceneStats`, analysis, versions, selected version id, derived current plan, pending warning, busy flags; actions `loadModel`, `analyze`, `submitPrompt`, `applySlider`, `selectVersion` | `ProjectRepository`, `AnalysisService`, `DirectorService`, `CreditService` |
| `useCreditsStore` | Balance, ledger; `spend`, `add` | `CreditService` |

## 6. Behaviour

### 6.1 Upload and viewer

- Drag-and-drop or file picker. Accepted: `.glb`, `.gltf`, `.fbx`, `.obj`. Cap 200 MB in the prototype (constant `MAX_UPLOAD_BYTES`; the product target is 500 MB). Two bundled CC0 sample models (car, product) are offered on the empty state so the studio works with no upload.
- Parsed in the browser with GLTFLoader, FBXLoader, OBJLoader. Single-file only. A `.gltf` referencing external files is rejected with a "use GLB" hint. An `.obj` loads untextured with a neutral default material and a notice that materials were not included.
- A model with zero meshes, or any extent that is zero or non-finite, is rejected as "no usable geometry".
- After load: compute bounds, centre on origin, rest on ground plane, auto-frame camera. Orbit, zoom, pan. Ground grid.
- `SceneStats` is read from the loaded scene.
- A project holds one model. Replacing it is allowed only from the missing-blob state (section 11); otherwise the user creates a new project.
- Deleting a project removes its versions, asset metadata, model blob and thumbnail.
- A dashboard thumbnail is captured right after the first rendered frame (`gl.render` then `toDataURL` in the same tick, so `preserveDrawingBuffer` is not needed), downscaled to 480px wide, stored in IndexedDB. It is recaptured whenever a version is appended, so the dashboard reflects the current scene.

### 6.2 Analysis (fake, half real)

Pure functions in `lib/scene`, wrapped by the local `AnalysisService`.

- **Axis-agnostic extents.** Sort the three extents descending into `L ≥ M ≥ S`. No assumption about which axis is up.
- **Car name signal.** True if any object or material name matches `wheel|tire|tyre|headlight|windshield|bumper|brake`.
- **Unit inference.** Target range for `L` is 3–6 m when the car name signal is true, otherwise 0.1–12 m. Try factors in priority order `1` (m), `0.001` (mm), `0.01` (cm), `0.0254` (in); take the first where `L × factor` is in range. None fits → factor 1, `unitGuess: "unknown"`. Known limitation, pinned by a test: a centimetre-unit car with no name signal (`L` = 450) resolves to millimetres and becomes a 0.45 m product.
- **Category.** `car` if the name signal is true, or if scaled extents satisfy `L` 3–6, `M` 1.5–2.3, `S` 1–2. Otherwise `product`. Confidence: 0.5 base, +0.3 name signal, +0.2 proportions match, capped at 0.97; `product` by default is 0.6.
- **Parts.** Wheel roles from names containing `FL|FR|RL|RR` or front/rear + left/right; body, windshield, headlights by keyword.
- **Capabilities.** From the table in 5.1.

The analysis card presents category, confidence, normalised dimensions, detected parts, capabilities, rig status.

### 6.3 Director (fake)

- `plan`: start from `defaultPlan(category)`, then apply keyword rules (night, rain, wet, fog, studio, road, city, handheld, orbit, push in, tracking, close, low, cinematic, duration and resolution mentions). Emits two shots when the prompt contains a sequence word (`then`, `after that`), otherwise one; with two shots the first takes 40% of the duration and the second 60%. Unknown prompts still return the valid default plan.
- The first prompt in a project calls `plan`; every later prompt calls `edit` against the selected version's plan. A "Start over" action beside the prompt box calls `plan` again (2 credits, appended as a new version like any other).
- `edit`: follow-up prompts return `ScenePatch[]`. Vocabulary: darker / brighter, closer / further, lower / higher, wider / tighter, add or remove rain / fog / wet ground, more or less blur, handheld / smooth, rim light on / off, environment names, day / dusk / night, orbit / push in / tracking / walk toward, longer / shorter, resolution and fps mentions. Unrecognised edits return `ok: false` with `code: "edit_not_understood"`, a friendly message, and `hints` holding three example phrasings.
- Compatibility check: vehicle verbs (drive, accelerate, drift) against a model whose capabilities lack `drive` return `ok: true` with a valid static-subject plan plus a warning `code: "capability_mismatch"`. The studio shows the warning with "Use this scene" and "Rewrite prompt". No version is created and no credits are charged until the user accepts.
- **Versions are append-only.** Every accepted plan or edit appends a `SceneVersion` whose `parentId` is the version selected at the time. Selecting an older version makes its plan current; nothing is ever dropped, so no confirmation is needed. The rail shows versions in creation order and marks the selected one.
- Manual sliders preview live in memory and, on release, append a version labelled `manual: <control>` through a patch: handheld → `camera.motionStrength` (style becomes `handheld` above 0.15, `smooth` at or below); depth of field → `effects.depthOfField`; motion blur → `effects.motionBlur`; fog → `scene.fogDensity`; light → `lighting.exposure`.
- Output settings (duration, resolution, fps, quality) behave like sliders: `set_output` patch, version labelled `manual: output`, free.
- Credits are charged at the moment a version is appended, never earlier.

### 6.4 Viewer reflection of the plan

The viewer shows intent, not final quality: the environment preset changes background, lighting rig, fog and ground look; rain is a light particle layer; the camera path for each shot is drawn as a line. A timeline scrubber under the viewer switches the main viewport to the preview camera travelling along the path; releasing it or pressing Escape returns to the orbit camera. Handheld amount adds visible sway to the preview camera.

### 6.5 Credits and pricing

All numbers live in `lib/pricing.ts` and are placeholders.

| Action | Credits | Charged in prototype |
|---|---|---|
| Model analysis | 0 | — |
| Scene generation (`plan`) | 2 | yes |
| Prompt edit (`edit`) | 1 | yes |
| Slider or output-setting change | 0 | — |
| Preview render | 3 | displayed only |
| Local final render | 5 | displayed only |
| Cloud final: standard / high / ultra / 4K | 30 / 60 / 90 / 160 | displayed only |

Charges happen only when a version is appended. Starting balance is 100 as a prototype convenience, independent of the Free plan's 50. Plan entitlements (watermark, resolution caps) are display-only; no current-plan state is modelled and "Choose plan" can be clicked repeatedly.

Plans: Free ($0, 50 credits once, watermark, 720p), Creator ($19/mo, 500 credits, 1080p, local + cloud) — highlighted, Pro ($49/mo, 2,000 credits, 4K, priority). Credit packs: 100 for $5, 500 for $20, 2,000 for $70. "Buy" and "Choose plan" add the credits to the ledger with no payment. Insufficient balance blocks the action with an inline link to `/pricing`.

## 7. Render surfaces (process intentionally blank)

The owner will supply the rendering process later. The prototype contains only the surfaces around it:

- `RenderService` interface is declared (`requestPreview`, `requestFinal`, `subscribe(jobId)`) with types only. The active implementation returns `{ ok: false, error: { code: "not_connected", … } }`.
- Render tab UI: Generate Preview button, Local GPU vs Cloud GPU choice cards with credit prices and trade-offs, output summary, Render button. Pressing either action shows a deliberate, designed "Renderer not connected yet" state, not an error.
- Presentational components `JobProgress` (all seven states, frame counter, progress bar) and `RenderResult` (player frame, download, regenerate) are built and driven purely by props.
- `/dev/render-states` renders those components in every state with fixture props so the design can be reviewed. No timers, no simulated process.

No fake job state machine, no sample MP4, no simulated progress.

Because of this, the prototype's terminal user state is **Scene ready**. The studio step indicator reads Upload → Understand → Direct → Render, with Render shown as the next, not-yet-connected step.

## 8. Visual design

Revised 2026-09-18 after owner review: the look follows ChatGPT and Higgsfield, not a "cinematic film tool" aesthetic.

**Reference language.** Neutral cool near-black surfaces (`#0d0d0d` page, `#171717` sidebar, `#212121` panels, `#2f2f2f` raised/hover), white text `#ececec`, muted `#b4b4b4`, hairline borders `rgba(255,255,255,0.1)`. No accent colour: the primary button is white with black text; selection and focus use white at low alpha. Inter (or a metric-compatible sans) everywhere; no display face. Radii: 8px controls, 12px cards, full pill for the composer and chips. Shadows minimal.

**Shell (all routes).** Left sidebar 260px, collapsible to icons: product name, "New project", project list (history), Pricing, credit balance at the bottom. No top header bar. Main area edge-to-edge.

**Studio.** The viewer fills the main area. A pill-shaped prompt composer floats at bottom-centre (max-width ~768px): `+` button on the left (upload / sample models / presets menu), textarea in the middle, round send button on the right; output settings as small chips inside the composer's lower row. Version history lives in the sidebar under the current project. Analysis, controls and render live in a slim right drawer (360px) that opens from an icon button in the viewer's top-right; it is closed by default. Step indicator becomes a quiet text status in the viewer's top-left ("Model ready · 2 versions").

**Landing, dashboard, pricing.** Same shell. Dashboard is a card grid inside the main area. Pricing uses three white-bordered cards with the middle one white-filled.

**Accessibility baseline:** visible focus rings (white 2px), full keyboard operation of chips, sliders, tabs, rail; text contrast at least 4.5:1; ARIA labels on icon buttons.

## 9. Motion

Tokens in `lib/motion`: durations (fast 150ms, base 250ms, slow 450ms), two easings (standard, emphasised), spring presets. Shared variants for fade-rise, stagger list, panel slide, scale-press.

Applied motion:

- Landing: hero reveal, scroll-triggered section entrances, animated three-step flow, environment cross-fade when a hero prompt chip is chosen.
- Dashboard: staggered grid entrance, hover lift on cards. Card → studio uses a fade plus the viewer's model settle; no cross-route shared-layout animation.
- Studio: model drop-in with camera settle on load; analysis card fields revealing one by one; plan changes cross-fading environment and easing the camera path; version rail items sliding in; slider and chip micro-interactions; credit counter ticking on change; step indicator advancing.
- Route transitions are short fades that never block input for more than 300ms. During the analysis and planning sequences the prompt input is disabled and shows progress; everything else stays interactive.
- Rain particles represent scene state, not decoration; under reduced motion they render as a static streak layer.
- `prefers-reduced-motion` replaces movement with opacity changes and removes camera settle and sway.

Motion always communicates state change or hierarchy. No looping decoration in the studio.

## 10. Applied psychology

| Principle | Application |
|---|---|
| Hick's law | One primary action per screen state. Studio reveals steps progressively: upload → analysis → prompt → scene ready. |
| Progressive disclosure | Manual sliders and output settings collapsed until a plan exists. No Blender-style control wall. |
| Goal gradient | Step indicator; each completed step visibly fills. |
| Labour illusion | Analysis and planning show named steps ("reading geometry", "identifying parts", "choosing lens") with a minimum total of 1.2s. Under reduced motion the steps still list, without animation. |
| Zeigarnik effect | Dashboard state labels (`Model ready`, `Scene ready`) signal unfinished work. |
| Blank-page avoidance | Sample models, preset chips and example prompts on every empty state. |
| Recognition over recall | Presets, chips, and version history labelled with the user's own prompt text. |
| Anchoring and decoy | Three plans with the middle highlighted; cloud price shown beside local price so local reads as a bargain. |
| Loss aversion | Low-credit warning before an action would fail; delete needs confirmation. History is append-only so work is never lost. |
| Peak-end rule | Peaks in the prototype: the model landing in the viewer, and the first scene plan transforming the viewer. `RenderResult` is designed to the same bar for when rendering is connected. |
| Doherty threshold | Visible feedback begins within 400ms of every action; the labour-illusion sequence counts as feedback. |
| Aesthetic-usability | Consistent tokens, generous spacing, restrained accent use. |
| Social proof | No testimonials or usage numbers in the prototype; slots are left out rather than filled with invented claims. |

Persuasion stays honest: no fake urgency, no fake scarcity, no hidden costs, no confirm-shaming.

## 11. Error handling

Inline, specific, recoverable messages for:

- Unsupported format; file over the cap; parse failure; `.gltf` with external files; no usable geometry.
- IndexedDB quota exceeded on save: the model is not saved, the project stays `No model`, and the message offers to delete old projects.
- localStorage data is zod-validated on read; corrupt or unreadable data is treated as empty with a notice. A localStorage write failure surfaces the same quota message.
- IndexedDB unavailable: blocking notice on `/projects` explaining that a normal (non-private) browser window is required.
- Uploaded asset metadata present but model blob missing: the studio opens in a "re-upload model" state, keeping versions.
- Project id not found: redirect to `/projects` with a notice.
- Insufficient credits; edit not understood; capability mismatch (warning flow, 6.3).

A route-level error boundary wraps the studio; a viewer-level boundary keeps a WebGL failure from taking down the page and offers reload.

## 12. Testing

- Vitest: schemas (including shot contiguity), `inferUnits`, `classify`, director keyword rules, `applyPatch` clamping and shot rescaling, the unit-inference known limitation, charge-on-append, append-only version behaviour, credit ledger.
- Playwright (Chromium with `--use-gl=swiftshader --enable-unsafe-swiftshader`): open dashboard → create project → load sample car → wait for the app-level `data-model-loaded` attribute → analysis appears → enter prompt → plan and version appear → edit prompt → second version → render tab shows the not-connected state.
- Manual visual review through `/dev/tokens`, `/dev/render-states` and the running app.

## 13. Build phases

1. Foundation: project scaffold, schemas, `lib/scene` pure functions, services, stores, tests. `useStudioStore.loadModel` takes a `SceneStats` argument, so it is testable with fixtures before the viewer exists.
2. Design tokens and UI primitives; owner approves `/dev/tokens`.
3. Viewer and upload.
4. Studio: analysis, director, versions, sliders, render surfaces.
5. Dashboard, pricing and credits, landing (independent of each other; can run in parallel).
6. Motion and psychology polish, accessibility pass, end-to-end test.

## 14. Assets

Two CC0 sample models (car, product) under `public/samples` with licences noted in `public/samples/LICENSES.md`. Landing imagery uses the live viewer and gradient placeholders; no third-party renders presented as product output. The landing page uses exactly one WebGL canvas.
