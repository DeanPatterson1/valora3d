# Render Studio — web prototype

A frontend-only prototype of Render Studio: upload a 3D model, describe the shot in plain words, and see the scene planned live in a WebGL viewer. The design follows the ChatGPT / Higgsfield language (neutral near-black surfaces, one white primary action, strict progressive disclosure).

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

- Everything runs in the browser. Projects, versions and credits persist in IndexedDB.
- The **renderer is intentionally not connected**: "Render" surfaces are designed but produce no output. The footer and the local/cloud section say so.
- Services (storage, credits, planning) are swapped at one seam: `lib/services/index.ts`. Replace the local implementations there to talk to a real backend.

## Layout

- `app/` — routes (`/` landing, `/projects` dashboard, `/projects/[id]` studio, `/pricing`).
- `components/viewer/` — the three.js viewer, environments and camera paths.
- `components/studio/` — composer, drawer, analysis and version history.
- `e2e/` — Playwright specs (`studio.spec.ts` full flow, `pages.spec.ts` landing and pricing).
- `lib/scene/` — model analysis and the prompt → scene-plan director.
- `docs/superpowers/` (repo root) — spec and plan this prototype follows.
