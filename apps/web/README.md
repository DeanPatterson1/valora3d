# Render Studio — web prototype

Render Studio: upload a 3D model, cut it down to the parts the shot needs, describe the shot in plain words, and render it to video. The design follows the ChatGPT / Higgsfield language (neutral near-black surfaces, one white primary action, strict progressive disclosure).

## Run

```bash
npm install
npm run dev        # http://localhost:3000
npm run test       # vitest (jsdom)
npm run typecheck  # next typegen + tsc
npm run lint
npm run e2e        # Playwright (chromium, headless WebGL via swiftshader); reuses a running dev server
npm run build
```

First e2e run: `npx playwright install chromium`. Everything the studio spec loads is served locally: `/samples/car.glb` and the HDR environments under `public/hdri/` (`next/font` fetches Inter at build time). Reports land in `playwright-report/`, traces for failures in `test-results/` (both git-ignored).

## What is and is not here

- The app runs in the browser. Projects, versions and credits persist in IndexedDB.
- **The viewport is a workspace, not the product.** It shows the model as untextured clay so geometry reads clearly while it is being cut down. Atmosphere — rain, fog — belongs to the render, not the preview: what is sold is the video.
- **Local rendering is connected.** "Render" hands the scene to the Blender + ffmpeg pipeline in `tools/render-studio/` and gives back an MP4. Start the server with `py tools/render-studio/server.py`; its README covers assets and prerequisites.
- **Cloud rendering is not connected**, and shows a designed state rather than an error.
- Services (storage, credits, planning, rendering) are swapped at one seam: `lib/services/index.ts`. Replace the local implementations there to talk to a real backend.

## Editing geometry

The Model tab in the scene drawer is the outliner. It opens as soon as a model loads, before any prompt.

- Click a part in the viewport or the outliner; shift-click adds to the selection.
- **Separate** (`P`) splits a mesh into its loose parts, like Blender. GLB exporters duplicate vertices wherever normals or UVs break, so `splitIslands.ts` welds by position first.
- **Delete** (`Del`) removes geometry from the render too. **Hide** (the eye, `H`) is viewport-only.
- `Ctrl+Z` undoes. Edits are stored per project under `rs.edits` as stable node paths, so they replay on the next load.

## Before wiring a backend

Known shortcuts in the prototype that a real backend will expose; fix these first.

- In-flight store actions are not cancelled by `open()` / `reset()`: a slow `submitPrompt` can land on the next project. Guard each resolution with a project-id check.
- `useLabourStore` and `useIngestStore` are module singletons and are not reset on project change.
- The credit-balance refresh is triggered from `Composer` (`onDone`); move it into the studio store so every credit-spending action refreshes.
- Models are parsed twice on ingest: `useModelIngest` (for stats) and then `useStudioModel` (for the viewer). Parse once and hand the root over.
- `Result` has no auth or network error taxonomy yet: only domain codes. Add `unauthorized`, `offline`, `server` before the first real call.
- Renders are not charged for. `CREDIT_COSTS` are displayed beside the buttons but the ledger is only touched when a version is appended.
- A render is followed in memory: reloading the page loses the job, though the pipeline keeps going and the file lands in `tools/render-studio/out/`.
- `plan.scene.fogDensity` and `effects.wetGround` are carried to the renderer but not yet mapped onto the rain scene's own fog and surface controls.

## Layout

- `app/` — routes (`/` landing, `/projects` dashboard, `/projects/[id]` studio, `/pricing`).
- `components/viewer/` — the three.js viewer, environments and camera paths.
- `components/studio/` — composer, drawer, analysis and version history.
- `e2e/` — Playwright specs (`studio.spec.ts` full flow, `pages.spec.ts` landing and pricing).
- `lib/scene/` — model analysis and the prompt → scene-plan director.
- `lib/render/` — GLB snapshot export, render job builder, the render server client.
- `tools/render-studio/` (repo root) — the Blender + ffmpeg pipeline behind "Local GPU".
- `docs/superpowers/` (repo root) — spec and plan this prototype follows.
