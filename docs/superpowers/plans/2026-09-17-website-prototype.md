# Website Prototype Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the frontend-only prototype described in `docs/superpowers/specs/2026-09-17-website-prototype-design.md`: landing, dashboard, studio with real 3D viewer, pricing, fake analysis/director/credits, blank render surfaces.

**Architecture:** Next.js App Router app in `apps/web`. Three layers: UI components → Zustand in-memory stores → service interfaces with local (localStorage + IndexedDB) implementations. All scene logic is pure functions in `lib/scene` over zod schemas in `lib/schema`. Rendering is intentionally not implemented; `RenderService` returns `not_connected`.

**Tech Stack:** Next.js 16, React 19, TypeScript strict, Tailwind 4, three 0.186 + @react-three/fiber 9 + @react-three/drei 10, motion 13, zustand 5, zod 4, idb-keyval 6, vitest 4, @playwright/test 1.63. Node 24, npm 11.

**Conventions for every task:**
- Working directory for all commands: `apps/web` (repository root is `C:\Users\deand\Projects\Rendering`).
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Run `npx tsc --noEmit` before every commit; it must pass.
- Tests colocated: `foo.ts` → `foo.test.ts` beside it.
- Never import a service implementation from UI or stores; always `import { services } from "@/lib/services"`.
- The spec is the source of truth for every number and enum. When this plan and the spec disagree, follow the spec and note it.

**Phase checkpoint:** after Chunk 2 (tokens), stop and get the owner's approval of `/dev/tokens` before building screens.

---

## File structure

```
apps/web/
  app/
    layout.tsx                 root layout: fonts, header, theme
    page.tsx                   landing
    projects/page.tsx          dashboard
    projects/[id]/page.tsx     studio
    pricing/page.tsx
    dev/tokens/page.tsx
    dev/render-states/page.tsx
    globals.css                Tailwind 4 @theme tokens
  components/
    ui/                        Button, Card, Slider, Tabs, Chip, Dialog, Toast, Field, Badge, Skeleton
    layout/Header.tsx
    landing/                   Hero, Steps, LocalVsCloud, PricingTeaser, FinalCta, Footer
    dashboard/                 ProjectGrid, ProjectCard, NewProjectDialog
    studio/                    StudioShell, StepIndicator, VersionRail, PromptDock, PresetChips,
                               OutputSettings, AnalysisPanel, ControlsPanel, RenderPanel,
                               JobProgress, RenderResult, WarningBanner, LabourSequence
    pricing/                   PlanCards, CreditPacks, ActionCostTable
    viewer/                    Viewer (Canvas), ModelLoader, useLoadModel, sceneStats, Environment,
                               CameraPath, PreviewCamera, Scrubber, RainLayer, thumbnail
  lib/
    brand.ts
    pricing.ts
    schema/                    scene-plan, scene-patch, project, index
    scene/                     defaultPlan, applyPatch, inferUnits, classify, editSteps,
                               director/planFromPrompt, director/editFromPrompt, capabilities
    services/                  types, result, index, local/projectRepository, local/analysis,
                               local/director, local/credits, local/render, local/storage
    stores/                    projects, studio, credits
    motion/                    tokens, variants
  public/samples/              car.glb, product.glb, LICENSES.md
  e2e/studio.spec.ts
  vitest.config.ts, playwright.config.ts
```

---

## Chunk 1: Foundation (schemas, scene logic, services, stores)

### Task 1: Scaffold the app

**Files:** Create `apps/web/*` via create-next-app; modify `apps/web/package.json`; create `apps/web/vitest.config.ts`, `.gitignore` at root.

- [ ] **Step 1: Scaffold**

Run from repository root:
```bash
npx create-next-app@16 apps/web --ts --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-npm --turbopack
```
Expected: `apps/web` exists with `app/`, `package.json`, `tsconfig.json`.

- [ ] **Step 2: Install dependencies**

```bash
cd apps/web
npm i three @react-three/fiber @react-three/drei motion zustand zod idb-keyval
npm i -D @types/three vitest @vitest/coverage-v8 jsdom @testing-library/react @testing-library/dom @playwright/test fake-indexeddb
```

- [ ] **Step 3: Vitest config**

Create `apps/web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["**/*.test.ts", "**/*.test.tsx"],
    exclude: ["node_modules", "e2e", ".next"],
    setupFiles: ["./vitest.setup.ts"],
  },
  resolve: { alias: { "@": path.resolve(__dirname) } },
});
```

Create `apps/web/vitest.setup.ts`:
```ts
import "fake-indexeddb/auto";
```

Add to `package.json` scripts: `"test": "vitest run"`, `"test:watch": "vitest"`, `"typecheck": "tsc --noEmit"`, `"e2e": "playwright test"`.

- [ ] **Step 4: Root .gitignore**

Create `C:\Users\deand\Projects\Rendering\.gitignore`:
```
node_modules/
.next/
out/
coverage/
playwright-report/
test-results/
.env*
```

- [ ] **Step 5: Verify**

Run: `npm run typecheck && npm run test`
Expected: typecheck passes; vitest reports "No test files found" (exit 0 with `--passWithNoTests`; add `"test": "vitest run --passWithNoTests"` if needed).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: scaffold Next.js app with test tooling"
```

### Task 2: Brand and pricing constants

**Files:** Create `apps/web/lib/brand.ts`, `apps/web/lib/pricing.ts`, `apps/web/lib/pricing.test.ts`.

- [ ] **Step 1: Write failing test**

`lib/pricing.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { CREDIT_COSTS, PLANS, CREDIT_PACKS, STARTING_BALANCE } from "./pricing";

describe("pricing", () => {
  it("matches the spec numbers", () => {
    expect(CREDIT_COSTS.scene_generation).toBe(2);
    expect(CREDIT_COSTS.prompt_edit).toBe(1);
    expect(CREDIT_COSTS.preview_render).toBe(3);
    expect(CREDIT_COSTS.local_final).toBe(5);
    expect(CREDIT_COSTS.cloud_final.standard).toBe(30);
    expect(CREDIT_COSTS.cloud_final["4k"]).toBe(160);
    expect(STARTING_BALANCE).toBe(100);
    expect(PLANS.map((p) => p.name)).toEqual(["Free", "Creator", "Pro"]);
    expect(PLANS[1].highlighted).toBe(true);
    expect(CREDIT_PACKS).toEqual([
      { credits: 100, priceUsd: 5 },
      { credits: 500, priceUsd: 20 },
      { credits: 2000, priceUsd: 70 },
    ]);
  });
});
```

- [ ] **Step 2: Run, expect FAIL** — `npx vitest run lib/pricing.test.ts` → "Cannot find module './pricing'".

- [ ] **Step 3: Implement**

`lib/brand.ts`:
```ts
export const BRAND = {
  name: "Render Studio",
  tagline: "You don't need to know Blender.",
} as const;
```

`lib/pricing.ts`:
```ts
export const STARTING_BALANCE = 100;

export const CREDIT_COSTS = {
  model_analysis: 0,
  scene_generation: 2,
  prompt_edit: 1,
  slider_change: 0,
  preview_render: 3,
  local_final: 5,
  cloud_final: { standard: 30, high: 60, ultra: 90, "4k": 160 },
} as const;

export type PlanDef = {
  name: string;
  priceUsd: number;
  period: "once" | "month";
  credits: number;
  features: string[];
  highlighted: boolean;
};

export const PLANS: PlanDef[] = [
  { name: "Free", priceUsd: 0, period: "once", credits: 50,
    features: ["50 credits", "720p renders", "Watermark", "7-day retention"], highlighted: false },
  { name: "Creator", priceUsd: 19, period: "month", credits: 500,
    features: ["500 credits / month", "1080p renders", "Local + cloud rendering", "30-day retention"], highlighted: true },
  { name: "Pro", priceUsd: 49, period: "month", credits: 2000,
    features: ["2,000 credits / month", "4K renders", "Priority GPU", "Commercial use"], highlighted: false },
];

export const CREDIT_PACKS = [
  { credits: 100, priceUsd: 5 },
  { credits: 500, priceUsd: 20 },
  { credits: 2000, priceUsd: 70 },
] as const;

export const MAX_UPLOAD_BYTES = 200 * 1024 * 1024; // prototype cap; product target 500 MB
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: brand and pricing constants"`

### Task 3: ScenePlan schema

**Files:** Create `lib/schema/scene-plan.ts`, `lib/schema/scene-plan.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect } from "vitest";
import { ScenePlanSchema } from "./scene-plan";

const valid = {
  scene: { environment: "urban_night", time: "night", ground: "wet_asphalt", fogDensity: 0.025 },
  subject: { category: "car", position: [0, 0, 0], motion: "stationary" },
  camera: { style: "handheld", lensMm: 45, heightM: 1.45, motionStrength: 0.18 },
  shots: [
    { id: "s1", start: 0, end: 4, action: "handheld_walk_toward", distanceMultiplier: 1 },
    { id: "s2", start: 4, end: 10, action: "slow_orbit", distanceMultiplier: 1 },
  ],
  lighting: { style: "night_city", exposure: 0, rim: true, practicals: true },
  effects: { rain: 0.4, wetGround: 0.75, motionBlur: 0.18, depthOfField: 0.5 },
  output: { fps: 30, durationS: 10, resolution: "1920x1080" as unknown as "1080p", quality: "high" },
};

describe("ScenePlanSchema", () => {
  it("accepts a valid plan", () => {
    expect(ScenePlanSchema.safeParse({ ...valid, output: { ...valid.output, resolution: "1080p" } }).success).toBe(true);
  });
  it("rejects unknown resolution", () => {
    expect(ScenePlanSchema.safeParse(valid).success).toBe(false);
  });
  it("rejects shots that do not end at durationS", () => {
    const bad = { ...valid, output: { ...valid.output, resolution: "1080p", durationS: 15 } };
    expect(ScenePlanSchema.safeParse(bad).success).toBe(false);
  });
  it("rejects non-contiguous shots", () => {
    const bad = { ...valid, output: { ...valid.output, resolution: "1080p" },
      shots: [{ ...valid.shots[0], end: 3 }, valid.shots[1]] };
    expect(ScenePlanSchema.safeParse(bad).success).toBe(false);
  });
  it("rejects more than two shots", () => {
    const bad = { ...valid, output: { ...valid.output, resolution: "1080p" },
      shots: [{ ...valid.shots[0], end: 2 }, { ...valid.shots[0], id: "x", start: 2, end: 4 }, valid.shots[1]] };
    expect(ScenePlanSchema.safeParse(bad).success).toBe(false);
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

```ts
import { z } from "zod";

export const Environment = z.enum(["studio_black", "studio_white", "outdoor_road", "urban_night"]);
export const Ground = z.enum(["studio_floor", "dry_asphalt", "wet_asphalt", "concrete"]);
export const ShotAction = z.enum(["slow_orbit", "hero_push_in", "low_tracking", "handheld_walk_toward"]);
export const LightingStyle = z.enum(["soft_studio", "dramatic_three_point", "night_city", "sunset", "overcast"]);
export const TimeOfDay = z.enum(["day", "dusk", "night"]);
export const CameraStyle = z.enum(["smooth", "handheld"]);
export const Category = z.enum(["car", "product"]);
export const Resolution = z.enum(["720p", "1080p", "1440p", "4k"]);
export const Quality = z.enum(["draft", "standard", "high", "ultra"]);
export const Fps = z.union([z.literal(24), z.literal(30), z.literal(60)]);
export const DurationS = z.union([z.literal(5), z.literal(10), z.literal(15), z.literal(30)]);

export const ShotSchema = z.object({
  id: z.string().min(1),
  start: z.number().min(0),
  end: z.number().min(0),
  action: ShotAction,
  distanceMultiplier: z.number().min(0.4).max(2.5),
});

export const OutputSchema = z.object({
  fps: Fps,
  durationS: DurationS,
  resolution: Resolution,
  quality: Quality,
});

export const ScenePlanSchema = z
  .object({
    scene: z.object({
      environment: Environment,
      time: TimeOfDay,
      ground: Ground,
      fogDensity: z.number().min(0).max(0.1),
    }),
    subject: z.object({
      category: Category,
      position: z.tuple([z.number(), z.number(), z.number()]),
      motion: z.literal("stationary"),
    }),
    camera: z.object({
      style: CameraStyle,
      lensMm: z.number().min(18).max(135),
      heightM: z.number().min(0.2).max(3),
      motionStrength: z.number().min(0).max(1),
    }),
    shots: z.array(ShotSchema).min(1).max(2),
    lighting: z.object({
      style: LightingStyle,
      exposure: z.number().min(-3).max(3),
      rim: z.boolean(),
      practicals: z.boolean(),
    }),
    effects: z.object({
      rain: z.number().min(0).max(1),
      wetGround: z.number().min(0).max(1),
      motionBlur: z.number().min(0).max(1),
      depthOfField: z.number().min(0).max(1),
    }),
    output: OutputSchema,
  })
  .superRefine((plan, ctx) => {
    const eps = 1e-6;
    let cursor = 0;
    for (const shot of plan.shots) {
      if (Math.abs(shot.start - cursor) > eps || shot.end <= shot.start) {
        ctx.addIssue({ code: "custom", path: ["shots"], message: "shots must be contiguous" });
        return;
      }
      cursor = shot.end;
    }
    if (Math.abs(cursor - plan.output.durationS) > eps) {
      ctx.addIssue({ code: "custom", path: ["shots"], message: "shots must end at output.durationS" });
    }
  });

export type ScenePlan = z.infer<typeof ScenePlanSchema>;
export type Shot = z.infer<typeof ShotSchema>;
export type ScenePlanOutput = z.infer<typeof OutputSchema>;
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat: ScenePlan schema with shot contiguity refinement"` (use `git add -A` first).

### Task 4: ScenePatch and remaining schemas

**Files:** Create `lib/schema/scene-patch.ts`, `lib/schema/project.ts`, `lib/schema/index.ts`, `lib/schema/project.test.ts`.

- [ ] **Step 1: Failing test** (`project.test.ts`)

```ts
import { describe, it, expect } from "vitest";
import { ProjectSchema, deriveProjectState, CreditTransactionSchema, ScenePatchSchema } from "./index";

describe("schemas", () => {
  it("derives project state", () => {
    expect(deriveProjectState({ assetId: null, versionCount: 0 })).toBe("No model");
    expect(deriveProjectState({ assetId: "a", versionCount: 0 })).toBe("Model ready");
    expect(deriveProjectState({ assetId: "a", versionCount: 2 })).toBe("Scene ready");
  });
  it("validates a project", () => {
    expect(ProjectSchema.safeParse({ id: "p1", name: "Car", createdAt: 1, updatedAt: 1,
      assetId: null, analysis: null, selectedVersionId: null }).success).toBe(true);
  });
  it("validates a patch union", () => {
    expect(ScenePatchSchema.safeParse({ operation: "set_effect", effect: "rain", value: 0.5 }).success).toBe(true);
    expect(ScenePatchSchema.safeParse({ operation: "nope" }).success).toBe(false);
  });
  it("rejects a non-integer credit amount", () => {
    expect(CreditTransactionSchema.safeParse({ id: "t", amount: 1.5, reason: "prompt_edit",
      projectId: null, createdAt: 1 }).success).toBe(false);
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

`lib/schema/scene-patch.ts`:
```ts
import { z } from "zod";
import { Environment, Ground, ShotAction, LightingStyle, TimeOfDay, CameraStyle, OutputSchema } from "./scene-plan";

export const EffectKey = z.enum(["rain", "wetGround", "motionBlur", "depthOfField"]);

export const ScenePatchSchema = z.discriminatedUnion("operation", [
  z.object({
    operation: z.literal("update_lighting"),
    exposureDelta: z.number().optional(),
    style: LightingStyle.optional(),
    rim: z.boolean().optional(),
    practicals: z.boolean().optional(),
  }),
  z.object({
    operation: z.literal("modify_camera"),
    shotId: z.string().optional(),
    distanceMultiplier: z.number().positive().optional(),
    heightDelta: z.number().optional(),
    lensMm: z.number().optional(),
    style: CameraStyle.optional(),
    motionStrength: z.number().optional(),
  }),
  z.object({ operation: z.literal("set_shot_action"), shotId: z.string(), action: ShotAction }),
  z.object({ operation: z.literal("set_effect"), effect: EffectKey, value: z.number() }),
  z.object({
    operation: z.literal("set_scene"),
    environment: Environment.optional(),
    time: TimeOfDay.optional(),
    ground: Ground.optional(),
    fogDensity: z.number().optional(),
  }),
  z.object({ operation: z.literal("set_output"), output: OutputSchema.partial() }),
]);

export type ScenePatch = z.infer<typeof ScenePatchSchema>;
export type EffectKey = z.infer<typeof EffectKey>;
```

`lib/schema/project.ts`:
```ts
import { z } from "zod";
import { Category, ScenePlanSchema } from "./scene-plan";

export const SceneStatsSchema = z.object({
  triangleCount: z.number().int().nonnegative(),
  meshCount: z.number().int().nonnegative(),
  materialCount: z.number().int().nonnegative(),
  objectNames: z.array(z.string()),
  materialNames: z.array(z.string()),
  extents: z.tuple([z.number(), z.number(), z.number()]),
  hasSkeleton: z.boolean(),
  animationClipCount: z.number().int().nonnegative(),
});
export type SceneStats = z.infer<typeof SceneStatsSchema>;

export const UnitGuess = z.enum(["m", "mm", "cm", "in", "unknown"]);

export const ModelAnalysisSchema = z.object({
  category: Category,
  confidence: z.number().min(0).max(1),
  unitGuess: UnitGuess,
  scaleFactor: z.number().positive(),
  dimensionsMeters: z.tuple([z.number(), z.number(), z.number()]),
  parts: z.record(z.string(), z.string()),
  capabilities: z.array(z.string()),
  rigged: z.boolean(),
});
export type ModelAnalysis = z.infer<typeof ModelAnalysisSchema>;

export const AssetSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  fileName: z.string(),
  format: z.enum(["glb", "gltf", "fbx", "obj"]),
  sizeBytes: z.number().int().nonnegative(),
  source: z.enum(["upload", "sample"]),
  blobKey: z.string().nullable(),
  sampleUrl: z.string().nullable(),
  thumbnailKey: z.string().nullable(),
});
export type Asset = z.infer<typeof AssetSchema>;

export const ProjectSchema = z.object({
  id: z.string(),
  name: z.string().min(1),
  createdAt: z.number(),
  updatedAt: z.number(),
  assetId: z.string().nullable(),
  analysis: ModelAnalysisSchema.nullable(),
  selectedVersionId: z.string().nullable(),
});
export type Project = z.infer<typeof ProjectSchema>;

export type ProjectState = "No model" | "Model ready" | "Scene ready";
export function deriveProjectState(p: { assetId: string | null; versionCount: number }): ProjectState {
  if (!p.assetId) return "No model";
  if (p.versionCount === 0) return "Model ready";
  return "Scene ready";
}

export const SceneVersionSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  index: z.number().int().nonnegative(),
  prompt: z.string(),
  parentId: z.string().nullable(),
  plan: ScenePlanSchema,
  createdAt: z.number(),
});
export type SceneVersion = z.infer<typeof SceneVersionSchema>;

export const RenderJobStatus = z.enum(["QUEUED", "PREPARING", "RENDERING", "ENCODING", "UPLOADING", "COMPLETE", "FAILED"]);
export const RenderJobSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  versionId: z.string(),
  kind: z.enum(["preview", "final"]),
  target: z.enum(["local", "cloud"]),
  status: RenderJobStatus,
  frame: z.number().int().nonnegative(),
  totalFrames: z.number().int().positive(),
  error: z.string().nullable(),
  resultUrl: z.string().nullable(),
});
export type RenderJob = z.infer<typeof RenderJobSchema>;
export type RenderJobStatus = z.infer<typeof RenderJobStatus>;

export const CreditReason = z.enum(["starting_balance", "scene_generation", "prompt_edit", "pack_purchase", "plan_grant"]);
export const CreditTransactionSchema = z.object({
  id: z.string(),
  amount: z.number().int(),
  reason: CreditReason,
  projectId: z.string().nullable(),
  createdAt: z.number(),
});
export type CreditTransaction = z.infer<typeof CreditTransactionSchema>;
```

`lib/schema/index.ts`: `export * from "./scene-plan"; export * from "./scene-patch"; export * from "./project";`

- [ ] **Step 4: Run all tests, expect PASS.**
- [ ] **Step 5: Commit** — `feat: patch, project, asset, version, job and credit schemas`

### Task 5: defaultPlan and capabilities

**Files:** Create `lib/scene/defaultPlan.ts`, `lib/scene/capabilities.ts`, `lib/scene/defaultPlan.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect } from "vitest";
import { defaultPlan } from "./defaultPlan";
import { ScenePlanSchema } from "@/lib/schema";
import { capabilitiesFor } from "./capabilities";

describe("defaultPlan", () => {
  it("produces valid plans for both categories", () => {
    expect(ScenePlanSchema.safeParse(defaultPlan("car")).success).toBe(true);
    expect(ScenePlanSchema.safeParse(defaultPlan("product")).success).toBe(true);
  });
  it("car defaults to outdoor road, product to studio", () => {
    expect(defaultPlan("car").scene.environment).toBe("outdoor_road");
    expect(defaultPlan("product").scene.environment).toBe("studio_black");
  });
});

describe("capabilitiesFor", () => {
  it("follows the capability table", () => {
    expect(capabilitiesFor("car", 4, false)).toEqual(["drive", "brake", "steer", "wheel_rotation"]);
    expect(capabilitiesFor("car", 2, false)).toEqual(["static", "rotate"]);
    expect(capabilitiesFor("product", 0, true)).toEqual(["rotate", "pedestal", "rigged_motion"]);
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

`lib/scene/capabilities.ts`:
```ts
import type { Category } from "./types";

export function capabilitiesFor(category: Category, wheelCount: number, rigged: boolean): string[] {
  const base =
    category === "car"
      ? wheelCount >= 4 ? ["drive", "brake", "steer", "wheel_rotation"] : ["static", "rotate"]
      : ["rotate", "pedestal"];
  return rigged ? [...base, "rigged_motion"] : base;
}
```

`lib/scene/types.ts`:
```ts
export type Category = "car" | "product";
```

`lib/scene/defaultPlan.ts`:
```ts
import type { ScenePlan } from "@/lib/schema";
import type { Category } from "./types";

export function defaultPlan(category: Category): ScenePlan {
  const car = category === "car";
  return {
    scene: {
      environment: car ? "outdoor_road" : "studio_black",
      time: car ? "dusk" : "day",
      ground: car ? "dry_asphalt" : "studio_floor",
      fogDensity: 0,
    },
    subject: { category, position: [0, 0, 0], motion: "stationary" },
    camera: { style: "smooth", lensMm: car ? 50 : 85, heightM: car ? 1.0 : 0.6, motionStrength: 0 },
    shots: [{ id: "shot-1", start: 0, end: 10, action: "slow_orbit", distanceMultiplier: 1 }],
    lighting: { style: car ? "sunset" : "soft_studio", exposure: 0, rim: true, practicals: false },
    effects: { rain: 0, wetGround: 0, motionBlur: 0.2, depthOfField: 0.3 },
    output: { fps: 30, durationS: 10, resolution: "1080p", quality: "high" },
  };
}
```

- [ ] **Step 4: Run, expect PASS.** **Step 5: Commit** — `feat: default scene plans and capability table`

### Task 6: applyPatch

**Files:** Create `lib/scene/applyPatch.ts`, `lib/scene/applyPatch.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect } from "vitest";
import { applyPatch } from "./applyPatch";
import { defaultPlan } from "./defaultPlan";
import { ScenePlanSchema } from "@/lib/schema";

const base = defaultPlan("car");

describe("applyPatch", () => {
  it("does not mutate the input", () => {
    const copy = structuredClone(base);
    applyPatch(base, { operation: "set_effect", effect: "rain", value: 0.5 });
    expect(base).toEqual(copy);
  });
  it("clamps exposure to schema range", () => {
    const p = applyPatch(base, { operation: "update_lighting", exposureDelta: -10 });
    expect(p.lighting.exposure).toBe(-3);
  });
  it("multiplies distance and clamps", () => {
    let p = applyPatch(base, { operation: "modify_camera", distanceMultiplier: 0.75 });
    expect(p.shots[0].distanceMultiplier).toBeCloseTo(0.75);
    p = applyPatch(p, { operation: "modify_camera", distanceMultiplier: 0.1 });
    expect(p.shots[0].distanceMultiplier).toBe(0.4);
  });
  it("rescales shots when duration changes", () => {
    const two = { ...base, shots: [
      { id: "a", start: 0, end: 4, action: "hero_push_in" as const, distanceMultiplier: 1 },
      { id: "b", start: 4, end: 10, action: "slow_orbit" as const, distanceMultiplier: 1 } ] };
    const p = applyPatch(two, { operation: "set_output", output: { durationS: 5 } });
    expect(p.shots.map((s) => [s.start, s.end])).toEqual([[0, 2], [2, 5]]);
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
  });
  it("sets scene fields and clamps fog", () => {
    const p = applyPatch(base, { operation: "set_scene", time: "night", fogDensity: 0.5 });
    expect(p.scene.time).toBe("night");
    expect(p.scene.fogDensity).toBe(0.1);
  });
  it("targets a specific shot for action", () => {
    const p = applyPatch(base, { operation: "set_shot_action", shotId: "shot-1", action: "low_tracking" });
    expect(p.shots[0].action).toBe("low_tracking");
  });
  it("always returns a schema-valid plan", () => {
    const p = applyPatch(base, { operation: "modify_camera", lensMm: 500, heightDelta: 99, motionStrength: 3, style: "handheld" });
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
    expect(p.camera.lensMm).toBe(135);
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

```ts
import type { ScenePlan, ScenePatch } from "@/lib/schema";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function applyPatch(plan: ScenePlan, patch: ScenePatch): ScenePlan {
  const p = structuredClone(plan);
  switch (patch.operation) {
    case "update_lighting":
      if (patch.exposureDelta !== undefined) p.lighting.exposure = clamp(p.lighting.exposure + patch.exposureDelta, -3, 3);
      if (patch.style) p.lighting.style = patch.style;
      if (patch.rim !== undefined) p.lighting.rim = patch.rim;
      if (patch.practicals !== undefined) p.lighting.practicals = patch.practicals;
      break;
    case "modify_camera":
      if (patch.lensMm !== undefined) p.camera.lensMm = clamp(patch.lensMm, 18, 135);
      if (patch.heightDelta !== undefined) p.camera.heightM = clamp(p.camera.heightM + patch.heightDelta, 0.2, 3);
      if (patch.style) p.camera.style = patch.style;
      if (patch.motionStrength !== undefined) p.camera.motionStrength = clamp(patch.motionStrength, 0, 1);
      if (patch.distanceMultiplier !== undefined) {
        for (const s of p.shots) {
          if (patch.shotId && s.id !== patch.shotId) continue;
          s.distanceMultiplier = clamp(s.distanceMultiplier * patch.distanceMultiplier, 0.4, 2.5);
        }
      }
      break;
    case "set_shot_action": {
      const s = p.shots.find((x) => x.id === patch.shotId);
      if (s) s.action = patch.action;
      break;
    }
    case "set_effect":
      p.effects[patch.effect] = clamp(patch.value, 0, 1);
      break;
    case "set_scene":
      if (patch.environment) p.scene.environment = patch.environment;
      if (patch.time) p.scene.time = patch.time;
      if (patch.ground) p.scene.ground = patch.ground;
      if (patch.fogDensity !== undefined) p.scene.fogDensity = clamp(patch.fogDensity, 0, 0.1);
      break;
    case "set_output": {
      const prev = p.output.durationS;
      p.output = { ...p.output, ...patch.output };
      if (p.output.durationS !== prev) {
        const k = p.output.durationS / prev;
        p.shots = p.shots.map((s) => ({ ...s, start: s.start * k, end: s.end * k }));
        p.shots[p.shots.length - 1].end = p.output.durationS;
      }
      break;
    }
  }
  return p;
}
```

- [ ] **Step 4: Run, expect PASS.** **Step 5: Commit** — `feat: applyPatch with clamping and shot rescaling`

### Task 7: inferUnits and classify

**Files:** Create `lib/scene/inferUnits.ts`, `lib/scene/classify.ts`, `lib/scene/analyze.ts`, `lib/scene/analyze.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect } from "vitest";
import { inferUnits } from "./inferUnits";
import { classify, hasCarNameSignal } from "./classify";
import { analyzeStats } from "./analyze";
import type { SceneStats } from "@/lib/schema";

const stats = (over: Partial<SceneStats>): SceneStats => ({
  triangleCount: 1000, meshCount: 5, materialCount: 2, objectNames: [], materialNames: [],
  extents: [1, 1, 1], hasSkeleton: false, animationClipCount: 0, ...over });

describe("inferUnits", () => {
  it("keeps metres when in range", () => {
    expect(inferUnits([4.7, 1.9, 1.4], true)).toEqual({ unitGuess: "m", scaleFactor: 1 });
  });
  it("detects millimetres for a car", () => {
    expect(inferUnits([4700, 1900, 1400], true)).toEqual({ unitGuess: "mm", scaleFactor: 0.001 });
  });
  it("detects centimetres for a named car", () => {
    expect(inferUnits([450, 190, 140], true)).toEqual({ unitGuess: "cm", scaleFactor: 0.01 });
  });
  it("known limitation: unnamed cm car resolves to mm product scale", () => {
    expect(inferUnits([450, 190, 140], false)).toEqual({ unitGuess: "mm", scaleFactor: 0.001 });
  });
  it("is axis agnostic", () => {
    expect(inferUnits([1400, 4700, 1900], true).unitGuess).toBe("mm");
  });
  it("returns unknown when nothing fits", () => {
    expect(inferUnits([1e9, 1, 1], false)).toEqual({ unitGuess: "unknown", scaleFactor: 1 });
  });
});

describe("classify", () => {
  it("detects car by names", () => {
    expect(hasCarNameSignal(["Body", "Wheel_FL"], [])).toBe(true);
    expect(classify([1, 1, 1], true)).toEqual({ category: "car", confidence: 0.8 });
  });
  it("detects car by proportions", () => {
    expect(classify([4.5, 1.9, 1.4], false)).toEqual({ category: "car", confidence: 0.7 });
  });
  it("caps confidence", () => {
    expect(classify([4.5, 1.9, 1.4], true).confidence).toBe(0.97);
  });
  it("defaults to product", () => {
    expect(classify([0.3, 0.2, 0.1], false)).toEqual({ category: "product", confidence: 0.6 });
  });
});

describe("analyzeStats", () => {
  it("assembles a full analysis for a car", () => {
    const a = analyzeStats(stats({ extents: [4700, 1900, 1400],
      objectNames: ["Body", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR", "Headlight_L"] }));
    expect(a.category).toBe("car");
    expect(a.unitGuess).toBe("mm");
    expect(a.dimensionsMeters).toEqual([4.7, 1.9, 1.4]);
    expect(a.parts.front_left_wheel).toBe("Wheel_FL");
    expect(a.parts.body).toBe("Body");
    expect(a.capabilities).toContain("drive");
    expect(a.rigged).toBe(false);
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

`lib/scene/inferUnits.ts`:
```ts
import type { ModelAnalysis } from "@/lib/schema";

const FACTORS: Array<{ unitGuess: ModelAnalysis["unitGuess"]; scaleFactor: number }> = [
  { unitGuess: "m", scaleFactor: 1 },
  { unitGuess: "mm", scaleFactor: 0.001 },
  { unitGuess: "cm", scaleFactor: 0.01 },
  { unitGuess: "in", scaleFactor: 0.0254 },
];

export function sortedExtents(extents: [number, number, number]): [number, number, number] {
  const s = [...extents].sort((a, b) => b - a);
  return [s[0], s[1], s[2]];
}

export function inferUnits(extents: [number, number, number], carNameSignal: boolean) {
  const [L] = sortedExtents(extents);
  const [lo, hi] = carNameSignal ? [3, 6] : [0.1, 12];
  for (const f of FACTORS) {
    const v = L * f.scaleFactor;
    if (v >= lo && v <= hi) return f;
  }
  return { unitGuess: "unknown" as const, scaleFactor: 1 };
}
```

`lib/scene/classify.ts`:
```ts
import type { Category } from "./types";
import { sortedExtents } from "./inferUnits";

const CAR_WORDS = /wheel|tire|tyre|headlight|windshield|bumper|brake/i;

export function hasCarNameSignal(objectNames: string[], materialNames: string[]): boolean {
  return [...objectNames, ...materialNames].some((n) => CAR_WORDS.test(n));
}

export function carProportions(metres: [number, number, number]): boolean {
  const [L, M, S] = sortedExtents(metres);
  return L >= 3 && L <= 6 && M >= 1.5 && M <= 2.3 && S >= 1 && S <= 2;
}

export function classify(metres: [number, number, number], nameSignal: boolean): { category: Category; confidence: number } {
  const proportions = carProportions(metres);
  if (!nameSignal && !proportions) return { category: "product", confidence: 0.6 };
  const confidence = Math.min(0.97, 0.5 + (nameSignal ? 0.3 : 0) + (proportions ? 0.2 : 0));
  return { category: "car", confidence };
}
```

`lib/scene/analyze.ts`:
```ts
import type { ModelAnalysis, SceneStats } from "@/lib/schema";
import { inferUnits } from "./inferUnits";
import { classify, hasCarNameSignal } from "./classify";
import { capabilitiesFor } from "./capabilities";

const ROLE_PATTERNS: Array<[string, RegExp]> = [
  ["front_left_wheel", /(wheel|tire|tyre).*(fl\b|front.*left|left.*front)|(fl\b|front.*left).*(wheel|tire|tyre)/i],
  ["front_right_wheel", /(wheel|tire|tyre).*(fr\b|front.*right|right.*front)|(fr\b|front.*right).*(wheel|tire|tyre)/i],
  ["rear_left_wheel", /(wheel|tire|tyre).*(rl\b|rear.*left|left.*rear)|(rl\b|rear.*left).*(wheel|tire|tyre)/i],
  ["rear_right_wheel", /(wheel|tire|tyre).*(rr\b|rear.*right|right.*rear)|(rr\b|rear.*right).*(wheel|tire|tyre)/i],
  ["body", /^body$|car_?body|chassis/i],
  ["windshield", /windshield|windscreen/i],
  ["headlight_left", /headlight.*(l\b|left)/i],
  ["headlight_right", /headlight.*(r\b|right)/i],
];

export function detectParts(objectNames: string[]): Record<string, string> {
  const parts: Record<string, string> = {};
  for (const [role, re] of ROLE_PATTERNS) {
    const hit = objectNames.find((n) => re.test(n));
    if (hit) parts[role] = hit;
  }
  return parts;
}

export function analyzeStats(stats: SceneStats): ModelAnalysis {
  const nameSignal = hasCarNameSignal(stats.objectNames, stats.materialNames);
  const units = inferUnits(stats.extents, nameSignal);
  const metres = stats.extents.map((e) => +(e * units.scaleFactor).toFixed(3)) as [number, number, number];
  const { category, confidence } = classify(metres, nameSignal);
  const parts = category === "car" ? detectParts(stats.objectNames) : {};
  const wheelCount = Object.keys(parts).filter((k) => k.endsWith("_wheel")).length;
  const rigged = stats.hasSkeleton;
  return {
    category, confidence, unitGuess: units.unitGuess, scaleFactor: units.scaleFactor,
    dimensionsMeters: metres, parts, capabilities: capabilitiesFor(category, wheelCount, rigged), rigged,
  };
}
```

- [ ] **Step 4: Run, expect PASS.** If a regex misses `Wheel_FL`, fix the regex, not the test. **Step 5: Commit** — `feat: unit inference, classification and analysis`

### Task 8: Director — planFromPrompt

**Files:** Create `lib/scene/director/planFromPrompt.ts`, `lib/scene/director/planFromPrompt.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect } from "vitest";
import { planFromPrompt } from "./planFromPrompt";
import { ScenePlanSchema } from "@/lib/schema";

describe("planFromPrompt", () => {
  it("returns the default for an unknown prompt", () => {
    const p = planFromPrompt("asdf qwerty", "car");
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
    expect(p.scene.environment).toBe("outdoor_road");
  });
  it("maps a rainy night handheld prompt", () => {
    const p = planFromPrompt("Cinematic rainy night city commercial, handheld camera walking toward the car", "car");
    expect(p.scene.environment).toBe("urban_night");
    expect(p.scene.time).toBe("night");
    expect(p.scene.ground).toBe("wet_asphalt");
    expect(p.effects.rain).toBeGreaterThan(0);
    expect(p.camera.style).toBe("handheld");
    expect(p.shots[0].action).toBe("handheld_walk_toward");
    expect(p.lighting.style).toBe("night_city");
  });
  it("splits two shots 40/60 on a sequence word", () => {
    const p = planFromPrompt("push in on the car, then orbit around it for 10 seconds", "car");
    expect(p.shots.map((s) => [s.start, s.end, s.action])).toEqual([[0, 4, "hero_push_in"], [4, 10, "slow_orbit"]]);
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
  });
  it("reads duration and resolution", () => {
    const p = planFromPrompt("studio shot, 15 seconds, 4k", "product");
    expect(p.output.durationS).toBe(15);
    expect(p.output.resolution).toBe("4k");
    expect(p.scene.environment).toBe("studio_black");
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

```ts
import type { ScenePlan, Shot } from "@/lib/schema";
import { defaultPlan } from "../defaultPlan";
import type { Category } from "../types";

type Rule = { re: RegExp; apply: (p: ScenePlan) => void };

const RULES: Rule[] = [
  { re: /\bnight\b|2 ?am|midnight/i, apply: (p) => { p.scene.time = "night"; p.lighting.style = "night_city"; p.lighting.practicals = true; } },
  { re: /\bsunset|golden hour|dusk\b/i, apply: (p) => { p.scene.time = "dusk"; p.lighting.style = "sunset"; } },
  { re: /\bovercast|cloudy\b/i, apply: (p) => { p.lighting.style = "overcast"; } },
  { re: /\bcity|urban|downtown|street\b/i, apply: (p) => { p.scene.environment = "urban_night"; p.scene.ground = "dry_asphalt"; } },
  { re: /\bstudio\b/i, apply: (p) => { p.scene.environment = /white/i.test(p._prompt) ? "studio_white" : "studio_black"; p.scene.ground = "studio_floor"; p.lighting.style = "soft_studio"; } },
  { re: /\broad|highway|mountain\b/i, apply: (p) => { p.scene.environment = "outdoor_road"; p.scene.ground = "dry_asphalt"; } },
  { re: /\brain|rainy|wet\b/i, apply: (p) => { p.effects.rain = /\bwet\b/i.test(p._prompt) && !/rain/i.test(p._prompt) ? 0 : 0.4; p.effects.wetGround = 0.75; if (p.scene.ground === "dry_asphalt") p.scene.ground = "wet_asphalt"; } },
  { re: /\bfog|foggy|haze|mist\b/i, apply: (p) => { p.scene.fogDensity = 0.03; } },
  { re: /\bhandheld|hand-held|walking\b/i, apply: (p) => { p.camera.style = "handheld"; p.camera.motionStrength = 0.18; } },
  { re: /\bcinematic\b/i, apply: (p) => { p.camera.lensMm = 45; p.effects.depthOfField = 0.5; p.lighting.rim = true; } },
  { re: /\bdramatic\b/i, apply: (p) => { p.lighting.style = "dramatic_three_point"; } },
  { re: /\bclose|close-up|closeup\b/i, apply: (p) => { for (const s of p.shots) s.distanceMultiplier = 0.7; } },
  { re: /\blow angle|low camera|\blow\b/i, apply: (p) => { p.camera.heightM = 0.5; } },
];

const SHOT_WORDS: Array<[RegExp, Shot["action"]]> = [
  [/walk(ing)? toward|approach/i, "handheld_walk_toward"],
  [/push[- ]?in|dolly in|move closer/i, "hero_push_in"],
  [/track(ing)?|drive by|alongside/i, "low_tracking"],
  [/orbit|circle|around/i, "slow_orbit"],
];

const DURATIONS = [5, 10, 15, 30] as const;

function detectShotActions(prompt: string): Shot["action"][] {
  const seq = prompt.split(/\bthen\b|after that|,\s*(?=then)/i);
  const actions: Shot["action"][] = [];
  for (const part of seq) {
    const hit = SHOT_WORDS.find(([re]) => re.test(part));
    if (hit) actions.push(hit[1]);
  }
  return actions.slice(0, 2);
}

export function planFromPrompt(prompt: string, category: Category): ScenePlan {
  const p = defaultPlan(category) as ScenePlan & { _prompt: string };
  p._prompt = prompt;
  for (const rule of RULES) if (rule.re.test(prompt)) rule.apply(p);

  const dur = prompt.match(/(\d+)\s*(s|sec|seconds?)\b/i);
  if (dur) {
    const n = Number(dur[1]);
    p.output.durationS = DURATIONS.reduce((best, d) => (Math.abs(d - n) < Math.abs(best - n) ? d : best), 10);
  }
  if (/\b4k\b/i.test(prompt)) p.output.resolution = "4k";
  else if (/\b1440p?\b/i.test(prompt)) p.output.resolution = "1440p";
  else if (/\b720p?\b/i.test(prompt)) p.output.resolution = "720p";

  const actions = detectShotActions(prompt);
  const D = p.output.durationS;
  const dm = p.shots[0].distanceMultiplier;
  if (actions.length === 2) {
    p.shots = [
      { id: "shot-1", start: 0, end: D * 0.4, action: actions[0], distanceMultiplier: dm },
      { id: "shot-2", start: D * 0.4, end: D, action: actions[1], distanceMultiplier: dm },
    ];
  } else {
    p.shots = [{ id: "shot-1", start: 0, end: D, action: actions[0] ?? (p.camera.style === "handheld" ? "handheld_walk_toward" : "slow_orbit"), distanceMultiplier: dm }];
  }
  const { _prompt, ...plan } = p;
  void _prompt;
  return plan;
}
```

- [ ] **Step 4: Run, expect PASS.** Adjust regexes until tests pass; keep rule order (environment before rain so wet ground can override). **Step 5: Commit** — `feat: keyword director for initial plans`

### Task 9: Director — editFromPrompt and editSteps

**Files:** Create `lib/scene/editSteps.ts`, `lib/scene/director/editFromPrompt.ts`, `lib/scene/director/editFromPrompt.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect } from "vitest";
import { editFromPrompt } from "./editFromPrompt";
import { defaultPlan } from "../defaultPlan";

const base = defaultPlan("car");

describe("editFromPrompt", () => {
  it("returns two patches for two intents", () => {
    const r = editFromPrompt("darker and add rain", base);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.patches).toEqual([
      { operation: "update_lighting", exposureDelta: -0.7 },
      { operation: "set_effect", effect: "rain", value: 0.5 },
    ]);
  });
  it("maps closer to a distance multiplier", () => {
    const r = editFromPrompt("move the camera closer", base);
    expect(r.ok && r.patches[0]).toEqual({ operation: "modify_camera", distanceMultiplier: 0.75 });
  });
  it("steps lenses", () => {
    const r = editFromPrompt("tighter lens", base); // base 50 -> 85
    expect(r.ok && r.patches[0]).toEqual({ operation: "modify_camera", lensMm: 85 });
  });
  it("targets the last shot for actions", () => {
    const r = editFromPrompt("orbit instead", base);
    expect(r.ok && r.patches[0]).toEqual({ operation: "set_shot_action", shotId: "shot-1", action: "slow_orbit" });
  });
  it("reports not understood with hints", () => {
    const r = editFromPrompt("make it pop", base);
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.error.code).toBe("edit_not_understood");
    expect(r.error.hints?.length).toBe(3);
  });
  it("reports at_limit when nothing can change", () => {
    const dark = { ...base, lighting: { ...base.lighting, exposure: -3 } };
    const r = editFromPrompt("darker", dark);
    expect(!r.ok && r.error.code).toBe("at_limit");
  });
  it("longer steps duration", () => {
    const r = editFromPrompt("make it longer", base); // 10 -> 15
    expect(r.ok && r.patches[0]).toEqual({ operation: "set_output", output: { durationS: 15 } });
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

`lib/scene/editSteps.ts`:
```ts
export const EDIT_STEPS = {
  exposureEv: 0.7,
  closerMultiplier: 0.75,
  furtherMultiplier: 1.33,
  heightM: 0.3,
  lenses: [24, 35, 50, 85] as const,
  durations: [5, 10, 15, 30] as const,
  effectOn: 0.5,
  effectOff: 0,
} as const;

export function nextLens(current: number, dir: 1 | -1): number | null {
  const L = EDIT_STEPS.lenses;
  const idx = L.findIndex((l) => (dir === 1 ? l > current : l < current));
  if (dir === 1) return idx === -1 ? null : L[idx];
  const lower = L.filter((l) => l < current);
  return lower.length ? lower[lower.length - 1] : null;
}

export function nextDuration(current: number, dir: 1 | -1): number | null {
  const D = EDIT_STEPS.durations;
  const i = D.indexOf(current as (typeof D)[number]);
  const j = i + dir;
  return j < 0 || j >= D.length ? null : D[j];
}
```

`lib/scene/director/editFromPrompt.ts`:
```ts
import type { ScenePlan, ScenePatch } from "@/lib/schema";
import { EDIT_STEPS, nextLens, nextDuration } from "../editSteps";

export type EditResult =
  | { ok: true; patches: ScenePatch[] }
  | { ok: false; error: { code: "edit_not_understood" | "at_limit"; message: string; hints?: string[] } };

const HINTS = ["Try: \"make it darker\"", "Try: \"move the camera closer\"", "Try: \"add rain\""];

type Intent = { re: RegExp; make: (p: ScenePlan) => ScenePatch | null | "limit" };

const S = EDIT_STEPS;
const INTENTS: Intent[] = [
  { re: /\bdarker|dimmer\b/i, make: (p) => (p.lighting.exposure <= -3 ? "limit" : { operation: "update_lighting", exposureDelta: -S.exposureEv }) },
  { re: /\bbrighter|lighter\b/i, make: (p) => (p.lighting.exposure >= 3 ? "limit" : { operation: "update_lighting", exposureDelta: S.exposureEv }) },
  { re: /\bcloser\b/i, make: (p) => (p.shots.every((s) => s.distanceMultiplier <= 0.4) ? "limit" : { operation: "modify_camera", distanceMultiplier: S.closerMultiplier }) },
  { re: /\bfurther|farther|back off\b/i, make: (p) => (p.shots.every((s) => s.distanceMultiplier >= 2.5) ? "limit" : { operation: "modify_camera", distanceMultiplier: S.furtherMultiplier }) },
  { re: /\blower\b/i, make: (p) => (p.camera.heightM <= 0.2 ? "limit" : { operation: "modify_camera", heightDelta: -S.heightM }) },
  { re: /\bhigher\b/i, make: (p) => (p.camera.heightM >= 3 ? "limit" : { operation: "modify_camera", heightDelta: S.heightM }) },
  { re: /\bwider\b/i, make: (p) => { const l = nextLens(p.camera.lensMm, -1); return l === null ? "limit" : { operation: "modify_camera", lensMm: l }; } },
  { re: /\btighter|zoom in\b/i, make: (p) => { const l = nextLens(p.camera.lensMm, 1); return l === null ? "limit" : { operation: "modify_camera", lensMm: l }; } },
  { re: /\b(add|more) rain\b|\brainy\b/i, make: () => ({ operation: "set_effect", effect: "rain", value: S.effectOn }) },
  { re: /\b(remove|no|less) rain\b/i, make: () => ({ operation: "set_effect", effect: "rain", value: S.effectOff }) },
  { re: /\b(add|more) fog\b|\bfoggy\b/i, make: () => ({ operation: "set_scene", fogDensity: 0.03 }) },
  { re: /\b(remove|no|less) fog\b/i, make: () => ({ operation: "set_scene", fogDensity: 0 }) },
  { re: /\bwet (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: 0.75 }) },
  { re: /\bdry (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: 0 }) },
  { re: /\bmore blur\b/i, make: () => ({ operation: "set_effect", effect: "motionBlur", value: S.effectOn }) },
  { re: /\bless blur|no blur\b/i, make: () => ({ operation: "set_effect", effect: "motionBlur", value: S.effectOff }) },
  { re: /\bhandheld\b/i, make: () => ({ operation: "modify_camera", style: "handheld", motionStrength: 0.18 }) },
  { re: /\bsmooth|steady\b/i, make: () => ({ operation: "modify_camera", style: "smooth", motionStrength: 0 }) },
  { re: /\brim light (on|off)\b/i, make: (p) => ({ operation: "update_lighting", rim: !p.lighting.rim }) },
  { re: /\bstudio white|white studio\b/i, make: () => ({ operation: "set_scene", environment: "studio_white", ground: "studio_floor" }) },
  { re: /\bstudio\b/i, make: () => ({ operation: "set_scene", environment: "studio_black", ground: "studio_floor" }) },
  { re: /\bcity|urban|street\b/i, make: () => ({ operation: "set_scene", environment: "urban_night" }) },
  { re: /\broad|highway\b/i, make: () => ({ operation: "set_scene", environment: "outdoor_road" }) },
  { re: /\bnight\b/i, make: () => ({ operation: "set_scene", time: "night" }) },
  { re: /\bdusk|sunset\b/i, make: () => ({ operation: "set_scene", time: "dusk" }) },
  { re: /\bday(time)?\b/i, make: () => ({ operation: "set_scene", time: "day" }) },
  { re: /\borbit\b/i, make: (p) => ({ operation: "set_shot_action", shotId: p.shots[p.shots.length - 1].id, action: "slow_orbit" }) },
  { re: /\bpush[- ]?in\b/i, make: (p) => ({ operation: "set_shot_action", shotId: p.shots[p.shots.length - 1].id, action: "hero_push_in" }) },
  { re: /\btracking\b/i, make: (p) => ({ operation: "set_shot_action", shotId: p.shots[p.shots.length - 1].id, action: "low_tracking" }) },
  { re: /\bwalk toward\b/i, make: (p) => ({ operation: "set_shot_action", shotId: p.shots[p.shots.length - 1].id, action: "handheld_walk_toward" }) },
  { re: /\blonger\b/i, make: (p) => { const d = nextDuration(p.output.durationS, 1); return d === null ? "limit" : { operation: "set_output", output: { durationS: d as 5 | 10 | 15 | 30 } }; } },
  { re: /\bshorter\b/i, make: (p) => { const d = nextDuration(p.output.durationS, -1); return d === null ? "limit" : { operation: "set_output", output: { durationS: d as 5 | 10 | 15 | 30 } }; } },
  { re: /\b4k\b/i, make: () => ({ operation: "set_output", output: { resolution: "4k" } }) },
  { re: /\b1080p?\b/i, make: () => ({ operation: "set_output", output: { resolution: "1080p" } }) },
  { re: /\b60 ?fps\b/i, make: () => ({ operation: "set_output", output: { fps: 60 } }) },
  { re: /\b24 ?fps\b/i, make: () => ({ operation: "set_output", output: { fps: 24 } }) },
];

export function editFromPrompt(prompt: string, plan: ScenePlan): EditResult {
  const patches: ScenePatch[] = [];
  let matched = 0;
  let limited = 0;
  for (const intent of INTENTS) {
    if (!intent.re.test(prompt)) continue;
    matched++;
    const out = intent.make(plan);
    if (out === "limit") limited++;
    else if (out) patches.push(out);
  }
  if (matched === 0) {
    return { ok: false, error: { code: "edit_not_understood", message: "I didn't catch what to change.", hints: HINTS } };
  }
  if (patches.length === 0 && limited > 0) {
    return { ok: false, error: { code: "at_limit", message: "That's already as far as it goes." } };
  }
  return { ok: true, patches };
}
```

- [ ] **Step 4: Run, expect PASS.** **Step 5: Commit** — `feat: keyword director for edits with step constants`

### Task 10: Service types and Result

**Files:** Create `lib/services/result.ts`, `lib/services/types.ts`.

- [ ] **Step 1: Write**

`lib/services/result.ts`:
```ts
export type ServiceError = { code: string; message: string; hints?: string[] };
export type Warning = { code: string; message: string };
export type Result<T> = { ok: true; value: T; warnings?: Warning[] } | { ok: false; error: ServiceError };

export const ok = <T>(value: T, warnings?: Warning[]): Result<T> => (warnings?.length ? { ok: true, value, warnings } : { ok: true, value });
export const fail = <T = never>(code: string, message: string, hints?: string[]): Result<T> => ({ ok: false, error: { code, message, ...(hints ? { hints } : {}) } });
```

`lib/services/types.ts`:
```ts
import type { Asset, CreditTransaction, ModelAnalysis, Project, RenderJob, ScenePatch, ScenePlan, SceneStats, SceneVersion } from "@/lib/schema";
import type { Result } from "./result";

export interface ProjectRepository {
  listProjects(): Promise<Result<Project[]>>;
  getProject(id: string): Promise<Result<Project>>;
  createProject(name: string): Promise<Result<Project>>;
  updateProject(id: string, patch: Partial<Omit<Project, "id" | "createdAt">>): Promise<Result<Project>>;
  deleteProject(id: string): Promise<Result<void>>;

  getAsset(id: string): Promise<Result<Asset>>;
  /** Stores metadata and (for uploads) the blob. Fails with "quota_exceeded" if storage is full. */
  saveAsset(asset: Omit<Asset, "id">, blob: Blob | null): Promise<Result<Asset>>;
  /** Returns null blob for samples (use sampleUrl) and for missing blobs. */
  getAssetBlob(asset: Asset): Promise<Result<Blob | null>>;
  saveThumbnail(assetId: string, blob: Blob): Promise<Result<void>>;
  getThumbnail(assetId: string): Promise<Result<Blob | null>>;

  listVersions(projectId: string): Promise<Result<SceneVersion[]>>;
  appendVersion(v: Omit<SceneVersion, "id" | "index" | "createdAt">): Promise<Result<SceneVersion>>;
}

export interface AnalysisService {
  analyze(stats: SceneStats): Promise<Result<ModelAnalysis>>;
}

export interface DirectorService {
  plan(prompt: string, analysis: ModelAnalysis): Promise<Result<ScenePlan>>;
  edit(prompt: string, plan: ScenePlan): Promise<Result<ScenePatch[]>>;
}

export interface CreditService {
  balance(): Promise<Result<number>>;
  ledger(): Promise<Result<CreditTransaction[]>>;
  /** amount negative to spend; fails with "insufficient_credits" */
  post(tx: Omit<CreditTransaction, "id" | "createdAt">): Promise<Result<CreditTransaction>>;
}

export interface RenderService {
  requestPreview(projectId: string, versionId: string): Promise<Result<RenderJob>>;
  requestFinal(projectId: string, versionId: string, target: "local" | "cloud"): Promise<Result<RenderJob>>;
  subscribe(jobId: string, onUpdate: (job: RenderJob) => void): () => void;
}

export interface Services {
  projects: ProjectRepository;
  analysis: AnalysisService;
  director: DirectorService;
  credits: CreditService;
  render: RenderService;
}
```

- [ ] **Step 2: Typecheck, commit** — `feat: service interfaces and Result type`

### Task 11: Local storage helpers

**Files:** Create `lib/services/local/storage.ts`, `lib/services/local/storage.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { z } from "zod";
import { readJson, writeJson, newId } from "./storage";

describe("storage", () => {
  beforeEach(() => localStorage.clear());
  it("round-trips valid json", () => {
    const r = writeJson("k", { a: 1 });
    expect(r.ok).toBe(true);
    expect(readJson("k", z.object({ a: z.number() }), { a: 0 })).toEqual({ value: { a: 1 }, corrupt: false });
  });
  it("treats corrupt data as empty and flags it", () => {
    localStorage.setItem("k", "{not json");
    expect(readJson("k", z.object({ a: z.number() }), { a: 0 })).toEqual({ value: { a: 0 }, corrupt: true });
  });
  it("generates unique ids", () => {
    expect(newId()).not.toBe(newId());
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

```ts
import type { ZodType } from "zod";
import { fail, ok, type Result } from "../result";

export const KEYS = { projects: "rs.projects", assets: "rs.assets", versions: "rs.versions", ledger: "rs.ledger" } as const;

export function readJson<T>(key: string, schema: ZodType<T>, fallback: T): { value: T; corrupt: boolean } {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return { value: fallback, corrupt: false };
    const parsed = schema.safeParse(JSON.parse(raw));
    return parsed.success ? { value: parsed.data, corrupt: false } : { value: fallback, corrupt: true };
  } catch {
    return { value: fallback, corrupt: true };
  }
}

export function writeJson(key: string, value: unknown): Result<void> {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return ok(undefined);
  } catch {
    return fail("quota_exceeded", "Storage is full. Delete an old project to free space.");
  }
}

export function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36);
}
```

- [ ] **Step 4: Run, expect PASS.** **Step 5: Commit** — `feat: localStorage helpers with zod validation`

### Task 12: Local ProjectRepository

**Files:** Create `lib/services/local/projectRepository.ts`, `lib/services/local/projectRepository.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { clear } from "idb-keyval";
import { LocalProjectRepository } from "./projectRepository";
import { defaultPlan } from "@/lib/scene/defaultPlan";

const repo = () => new LocalProjectRepository();

describe("LocalProjectRepository", () => {
  beforeEach(async () => { localStorage.clear(); await clear(); });

  it("creates, lists, renames, deletes", async () => {
    const r = repo();
    const p = await r.createProject("Car");
    expect(p.ok && p.value.name).toBe("Car");
    if (!p.ok) return;
    expect((await r.listProjects()).ok).toBe(true);
    const u = await r.updateProject(p.value.id, { name: "Car 2" });
    expect(u.ok && u.value.name).toBe("Car 2");
    await r.deleteProject(p.value.id);
    const g = await r.getProject(p.value.id);
    expect(!g.ok && g.error.code).toBe("not_found");
  });

  it("appends versions with incrementing index", async () => {
    const r = repo();
    const p = await r.createProject("X");
    if (!p.ok) return;
    const a = await r.appendVersion({ projectId: p.value.id, prompt: "night", parentId: null, plan: defaultPlan("car") });
    const b = await r.appendVersion({ projectId: p.value.id, prompt: "rain", parentId: a.ok ? a.value.id : null, plan: defaultPlan("car") });
    expect(a.ok && a.value.index).toBe(0);
    expect(b.ok && b.value.index).toBe(1);
    const list = await r.listVersions(p.value.id);
    expect(list.ok && list.value.length).toBe(2);
  });

  it("stores upload blobs and returns null for missing blobs", async () => {
    const r = repo();
    const p = await r.createProject("X");
    if (!p.ok) return;
    const a = await r.saveAsset({ projectId: p.value.id, fileName: "m.glb", format: "glb", sizeBytes: 3,
      source: "upload", blobKey: null, sampleUrl: null, thumbnailKey: null }, new Blob(["abc"]));
    expect(a.ok && a.value.blobKey).toBeTruthy();
    if (!a.ok) return;
    const b = await r.getAssetBlob(a.value);
    expect(b.ok && b.value && (await b.value.text())).toBe("abc");
    await clear();
    const missing = await r.getAssetBlob(a.value);
    expect(missing.ok && missing.value).toBeNull();
  });

  it("deleting a project removes versions, asset and blob", async () => {
    const r = repo();
    const p = await r.createProject("X");
    if (!p.ok) return;
    const a = await r.saveAsset({ projectId: p.value.id, fileName: "m.glb", format: "glb", sizeBytes: 3,
      source: "upload", blobKey: null, sampleUrl: null, thumbnailKey: null }, new Blob(["abc"]));
    await r.appendVersion({ projectId: p.value.id, prompt: "x", parentId: null, plan: defaultPlan("car") });
    await r.deleteProject(p.value.id);
    expect((await r.listVersions(p.value.id)).ok && (await r.listVersions(p.value.id)).value).toEqual([]);
    if (a.ok) expect(!(await r.getAsset(a.value.id)).ok).toBe(true);
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

```ts
import { z } from "zod";
import { get, set, del } from "idb-keyval";
import { AssetSchema, ProjectSchema, SceneVersionSchema, type Asset, type Project, type SceneVersion } from "@/lib/schema";
import { fail, ok, type Result } from "../result";
import type { ProjectRepository } from "../types";
import { KEYS, newId, readJson, writeJson } from "./storage";

const ProjectsFile = z.array(ProjectSchema);
const AssetsFile = z.array(AssetSchema);
const VersionsFile = z.array(SceneVersionSchema);

export class LocalProjectRepository implements ProjectRepository {
  /** Set to true when any file was unreadable; UI shows a one-time notice. */
  corruptDetected = false;

  private read<T>(key: string, schema: z.ZodType<T[]>): T[] {
    const r = readJson(key, schema, [] as T[]);
    if (r.corrupt) this.corruptDetected = true;
    return r.value;
  }
  private projects() { return this.read(KEYS.projects, ProjectsFile); }
  private assets() { return this.read(KEYS.assets, AssetsFile); }
  private versions() { return this.read(KEYS.versions, VersionsFile); }

  async listProjects() { return ok(this.projects().sort((a, b) => b.updatedAt - a.updatedAt)); }

  async getProject(id: string) {
    const p = this.projects().find((x) => x.id === id);
    return p ? ok(p) : fail<Project>("not_found", "Project not found.");
  }

  async createProject(name: string) {
    const now = Date.now();
    const p: Project = { id: newId(), name, createdAt: now, updatedAt: now, assetId: null, analysis: null, selectedVersionId: null };
    const w = writeJson(KEYS.projects, [...this.projects(), p]);
    return w.ok ? ok(p) : fail<Project>(w.error.code, w.error.message);
  }

  async updateProject(id: string, patch: Partial<Omit<Project, "id" | "createdAt">>) {
    const all = this.projects();
    const i = all.findIndex((x) => x.id === id);
    if (i === -1) return fail<Project>("not_found", "Project not found.");
    all[i] = { ...all[i], ...patch, updatedAt: Date.now() };
    const w = writeJson(KEYS.projects, all);
    return w.ok ? ok(all[i]) : fail<Project>(w.error.code, w.error.message);
  }

  async deleteProject(id: string): Promise<Result<void>> {
    for (const a of this.assets().filter((x) => x.projectId === id)) {
      if (a.blobKey) await del(a.blobKey).catch(() => {});
      if (a.thumbnailKey) await del(a.thumbnailKey).catch(() => {});
    }
    writeJson(KEYS.assets, this.assets().filter((x) => x.projectId !== id));
    writeJson(KEYS.versions, this.versions().filter((x) => x.projectId !== id));
    writeJson(KEYS.projects, this.projects().filter((x) => x.id !== id));
    return ok(undefined);
  }

  async getAsset(id: string) {
    const a = this.assets().find((x) => x.id === id);
    return a ? ok(a) : fail<Asset>("not_found", "Asset not found.");
  }

  async saveAsset(asset: Omit<Asset, "id">, blob: Blob | null) {
    const id = newId();
    let blobKey: string | null = null;
    if (blob && asset.source === "upload") {
      blobKey = `blob:${id}`;
      try { await set(blobKey, blob); }
      catch { return fail<Asset>("quota_exceeded", "Storage is full. Delete an old project to free space."); }
    }
    const full: Asset = { ...asset, id, blobKey };
    const w = writeJson(KEYS.assets, [...this.assets(), full]);
    if (!w.ok) { if (blobKey) await del(blobKey).catch(() => {}); return fail<Asset>(w.error.code, w.error.message); }
    return ok(full);
  }

  async getAssetBlob(asset: Asset): Promise<Result<Blob | null>> {
    if (!asset.blobKey) return ok(null);
    try { return ok((await get<Blob>(asset.blobKey)) ?? null); }
    catch { return fail("storage_unavailable", "Browser storage is unavailable."); }
  }

  async saveThumbnail(assetId: string, blob: Blob): Promise<Result<void>> {
    const key = `thumb:${assetId}`;
    try { await set(key, blob); } catch { return ok(undefined); } // thumbnails are best-effort
    const all = this.assets();
    const i = all.findIndex((x) => x.id === assetId);
    if (i !== -1) { all[i] = { ...all[i], thumbnailKey: key }; writeJson(KEYS.assets, all); }
    return ok(undefined);
  }

  async getThumbnail(assetId: string): Promise<Result<Blob | null>> {
    try { return ok((await get<Blob>(`thumb:${assetId}`)) ?? null); } catch { return ok(null); }
  }

  async listVersions(projectId: string) {
    return ok(this.versions().filter((v) => v.projectId === projectId).sort((a, b) => a.index - b.index));
  }

  async appendVersion(v: Omit<SceneVersion, "id" | "index" | "createdAt">) {
    const all = this.versions();
    const index = all.filter((x) => x.projectId === v.projectId).length;
    const full: SceneVersion = { ...v, id: newId(), index, createdAt: Date.now() };
    const w = writeJson(KEYS.versions, [...all, full]);
    return w.ok ? ok(full) : fail<SceneVersion>(w.error.code, w.error.message);
  }
}
```

- [ ] **Step 4: Run, expect PASS.** **Step 5: Commit** — `feat: local project repository over localStorage and IndexedDB`

### Task 13: Local analysis, director, credits, render services + index

**Files:** Create `lib/services/local/analysis.ts`, `local/director.ts`, `local/credits.ts`, `local/render.ts`, `lib/services/index.ts`, `lib/services/local/services.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { LocalCreditService } from "./credits";
import { LocalDirectorService } from "./director";
import { LocalRenderService } from "./render";
import { analyzeStats } from "@/lib/scene/analyze";

describe("LocalCreditService", () => {
  beforeEach(() => localStorage.clear());
  it("seeds the starting balance once", async () => {
    const c = new LocalCreditService();
    expect((await c.balance()).ok && (await c.balance()).value).toBe(100);
    expect((await new LocalCreditService().balance()).value).toBe(100);
  });
  it("refuses overspend", async () => {
    const c = new LocalCreditService();
    const r = await c.post({ amount: -500, reason: "scene_generation", projectId: null });
    expect(!r.ok && r.error.code).toBe("insufficient_credits");
  });
});

describe("LocalDirectorService", () => {
  const car = analyzeStats({ triangleCount: 1, meshCount: 1, materialCount: 1, objectNames: ["Wheel_FL","Wheel_FR","Wheel_RL","Wheel_RR"],
    materialNames: [], extents: [4.5, 1.9, 1.4], hasSkeleton: false, animationClipCount: 0 });
  const chair = analyzeStats({ triangleCount: 1, meshCount: 1, materialCount: 1, objectNames: ["Chair"],
    materialNames: [], extents: [0.5, 0.5, 0.9], hasSkeleton: false, animationClipCount: 0 });
  it("warns on capability mismatch", async () => {
    const r = await new LocalDirectorService().plan("make the car drive down the highway", chair);
    expect(r.ok && r.warnings?.[0].code).toBe("capability_mismatch");
  });
  it("does not warn for a drivable car", async () => {
    const r = await new LocalDirectorService().plan("make the car drive down the highway", car);
    expect(r.ok && (r.warnings ?? []).length).toBe(0);
  });
});

describe("LocalRenderService", () => {
  it("is not connected", async () => {
    const r = await new LocalRenderService().requestPreview("p", "v");
    expect(!r.ok && r.error.code).toBe("not_connected");
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

`local/analysis.ts`:
```ts
import { analyzeStats } from "@/lib/scene/analyze";
import { ok } from "../result";
import type { AnalysisService } from "../types";
export class LocalAnalysisService implements AnalysisService {
  async analyze(stats: Parameters<typeof analyzeStats>[0]) { return ok(analyzeStats(stats)); }
}
```

`local/director.ts`:
```ts
import type { ModelAnalysis, ScenePlan } from "@/lib/schema";
import { planFromPrompt } from "@/lib/scene/director/planFromPrompt";
import { editFromPrompt } from "@/lib/scene/director/editFromPrompt";
import { fail, ok } from "../result";
import type { DirectorService } from "../types";

const VEHICLE_VERBS = /\b(drive|driving|drives|accelerat\w*|drift\w*|speed(ing)? (down|along)|race|racing)\b/i;

export class LocalDirectorService implements DirectorService {
  async plan(prompt: string, analysis: ModelAnalysis) {
    const plan = planFromPrompt(prompt, analysis.category);
    const warnings = VEHICLE_VERBS.test(prompt) && !analysis.capabilities.includes("drive")
      ? [{ code: "capability_mismatch", message: "This model doesn't appear to be drivable. I can place it in the scene and move the camera as asked, but driving animation isn't available." }]
      : [];
    return ok(plan, warnings);
  }
  async edit(prompt: string, plan: ScenePlan) {
    const r = editFromPrompt(prompt, plan);
    return r.ok ? ok(r.patches) : fail(r.error.code, r.error.message, r.error.hints);
  }
}
```

`local/credits.ts`:
```ts
import { z } from "zod";
import { CreditTransactionSchema, type CreditTransaction } from "@/lib/schema";
import { STARTING_BALANCE } from "@/lib/pricing";
import { fail, ok, type Result } from "../result";
import type { CreditService } from "../types";
import { KEYS, newId, readJson, writeJson } from "./storage";

const Ledger = z.array(CreditTransactionSchema);

export class LocalCreditService implements CreditService {
  private ledgerSync(): CreditTransaction[] {
    const { value } = readJson(KEYS.ledger, Ledger, []);
    if (value.length === 0) {
      const seed: CreditTransaction = { id: newId(), amount: STARTING_BALANCE, reason: "starting_balance", projectId: null, createdAt: Date.now() };
      writeJson(KEYS.ledger, [seed]);
      return [seed];
    }
    return value;
  }
  async ledger() { return ok(this.ledgerSync()); }
  async balance() { return ok(this.ledgerSync().reduce((s, t) => s + t.amount, 0)); }
  async post(tx: Omit<CreditTransaction, "id" | "createdAt">): Promise<Result<CreditTransaction>> {
    const all = this.ledgerSync();
    const bal = all.reduce((s, t) => s + t.amount, 0);
    if (bal + tx.amount < 0) return fail("insufficient_credits", `You need ${-tx.amount} credits but have ${bal}.`);
    const full: CreditTransaction = { ...tx, id: newId(), createdAt: Date.now() };
    const w = writeJson(KEYS.ledger, [...all, full]);
    return w.ok ? ok(full) : fail(w.error.code, w.error.message);
  }
}
```

`local/render.ts`:
```ts
import { fail } from "../result";
import type { RenderService } from "../types";
const NOT_CONNECTED = () => fail<never>("not_connected", "Renderer not connected yet.");
export class LocalRenderService implements RenderService {
  async requestPreview() { return NOT_CONNECTED(); }
  async requestFinal() { return NOT_CONNECTED(); }
  subscribe() { return () => {}; }
}
```

`lib/services/index.ts`:
```ts
import type { Services } from "./types";
import { LocalProjectRepository } from "./local/projectRepository";
import { LocalAnalysisService } from "./local/analysis";
import { LocalDirectorService } from "./local/director";
import { LocalCreditService } from "./local/credits";
import { LocalRenderService } from "./local/render";

export const services: Services = {
  projects: new LocalProjectRepository(),
  analysis: new LocalAnalysisService(),
  director: new LocalDirectorService(),
  credits: new LocalCreditService(),
  render: new LocalRenderService(),
};
export type { Services } from "./types";
export * from "./result";
```

- [ ] **Step 4: Run all tests, expect PASS.** **Step 5: Commit** — `feat: local analysis, director, credit and stub render services`

### Task 14: Stores

**Files:** Create `lib/stores/credits.ts`, `lib/stores/projects.ts`, `lib/stores/studio.ts`, `lib/stores/studio.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { clear } from "idb-keyval";
import { useStudioStore } from "./studio";
import { useCreditsStore } from "./credits";
import { services } from "@/lib/services";

const carStats = { triangleCount: 10, meshCount: 5, materialCount: 1, objectNames: ["Body","Wheel_FL","Wheel_FR","Wheel_RL","Wheel_RR"],
  materialNames: [], extents: [4.5, 1.9, 1.4] as [number, number, number], hasSkeleton: false, animationClipCount: 0 };

describe("useStudioStore", () => {
  beforeEach(async () => { localStorage.clear(); await clear(); useStudioStore.getState().reset(); });

  it("runs the full flow: open, model loaded, analyze, plan, edit, select", async () => {
    const p = await services.projects.createProject("Car");
    if (!p.ok) throw new Error();
    const s = useStudioStore.getState();
    await s.open(p.value.id);
    await s.modelLoaded({ fileName: "car.glb", format: "glb", sizeBytes: 1, source: "sample", sampleUrl: "/samples/car.glb", blob: null }, carStats);
    expect(useStudioStore.getState().analysis?.category).toBe("car");

    const r1 = await useStudioStore.getState().submitPrompt("rainy night, handheld walking toward the car");
    expect(r1.ok).toBe(true);
    expect(useStudioStore.getState().versions.length).toBe(1);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(98);

    const r2 = await useStudioStore.getState().submitPrompt("darker and add fog");
    expect(r2.ok).toBe(true);
    const st = useStudioStore.getState();
    expect(st.versions.length).toBe(2);
    expect(st.versions[1].parentId).toBe(st.versions[0].id);
    expect(st.currentPlan?.lighting.exposure).toBeCloseTo(-0.7);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(97);

    await useStudioStore.getState().selectVersion(st.versions[0].id);
    expect(useStudioStore.getState().currentPlan?.lighting.exposure).toBe(0);
    const r3 = await useStudioStore.getState().submitPrompt("brighter");
    expect(r3.ok).toBe(true);
    const st2 = useStudioStore.getState();
    expect(st2.versions.length).toBe(3);
    expect(st2.versions[2].parentId).toBe(st.versions[0].id);
  });

  it("holds a warning until accepted and charges only then", async () => {
    const p = await services.projects.createProject("Chair");
    if (!p.ok) throw new Error();
    const s = useStudioStore.getState();
    await s.open(p.value.id);
    await s.modelLoaded({ fileName: "chair.glb", format: "glb", sizeBytes: 1, source: "sample", sampleUrl: "/samples/product.glb", blob: null },
      { ...carStats, objectNames: ["Chair"], extents: [0.5, 0.5, 0.9] });
    await useStudioStore.getState().submitPrompt("make the car drive down the highway");
    expect(useStudioStore.getState().pendingWarning?.code).toBe("capability_mismatch");
    expect(useStudioStore.getState().versions.length).toBe(0);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(100);
    await useStudioStore.getState().acceptPending();
    expect(useStudioStore.getState().versions.length).toBe(1);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(98);
  });

  it("slider changes are free and append a manual version", async () => {
    const p = await services.projects.createProject("Car");
    if (!p.ok) throw new Error();
    await useStudioStore.getState().open(p.value.id);
    await useStudioStore.getState().modelLoaded({ fileName: "car.glb", format: "glb", sizeBytes: 1, source: "sample", sampleUrl: "/samples/car.glb", blob: null }, carStats);
    await useStudioStore.getState().submitPrompt("studio");
    await useStudioStore.getState().commitSlider("fog", 0.05);
    const st = useStudioStore.getState();
    expect(st.versions[1].prompt).toBe("manual: fog");
    expect(st.currentPlan?.scene.fogDensity).toBe(0.05);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(98);
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

`lib/stores/credits.ts`:
```ts
import { create } from "zustand";
import { services } from "@/lib/services";
import type { CreditTransaction } from "@/lib/schema";

type CreditsState = {
  balance: number;
  ledger: CreditTransaction[];
  loaded: boolean;
  refresh: () => Promise<void>;
  add: (amount: number, reason: "pack_purchase" | "plan_grant") => Promise<void>;
};

export const useCreditsStore = create<CreditsState>((set) => ({
  balance: 0, ledger: [], loaded: false,
  refresh: async () => {
    const [b, l] = await Promise.all([services.credits.balance(), services.credits.ledger()]);
    set({ balance: b.ok ? b.value : 0, ledger: l.ok ? l.value : [], loaded: true });
  },
  add: async (amount, reason) => {
    await services.credits.post({ amount, reason, projectId: null });
    const b = await services.credits.balance();
    set({ balance: b.ok ? b.value : 0 });
  },
}));
```

`lib/stores/projects.ts`:
```ts
import { create } from "zustand";
import { services } from "@/lib/services";
import type { Project } from "@/lib/schema";
import type { ServiceError } from "@/lib/services";

type ProjectsState = {
  projects: Project[];
  versionCounts: Record<string, number>;
  loaded: boolean;
  error: ServiceError | null;
  refresh: () => Promise<void>;
  create: (name: string) => Promise<Project | null>;
  rename: (id: string, name: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
};

export const useProjectsStore = create<ProjectsState>((set, get) => ({
  projects: [], versionCounts: {}, loaded: false, error: null,
  refresh: async () => {
    const r = await services.projects.listProjects();
    if (!r.ok) { set({ error: r.error, loaded: true }); return; }
    const counts: Record<string, number> = {};
    await Promise.all(r.value.map(async (p) => { const v = await services.projects.listVersions(p.id); counts[p.id] = v.ok ? v.value.length : 0; }));
    set({ projects: r.value, versionCounts: counts, loaded: true, error: null });
  },
  create: async (name) => {
    const r = await services.projects.createProject(name);
    if (!r.ok) { set({ error: r.error }); return null; }
    await get().refresh();
    return r.value;
  },
  rename: async (id, name) => { await services.projects.updateProject(id, { name }); await get().refresh(); },
  remove: async (id) => { await services.projects.deleteProject(id); await get().refresh(); },
}));
```

`lib/stores/studio.ts`:
```ts
import { create } from "zustand";
import { services, type Result, type ServiceError, type Warning } from "@/lib/services";
import { CREDIT_COSTS } from "@/lib/pricing";
import { applyPatch } from "@/lib/scene/applyPatch";
import type { Asset, ModelAnalysis, Project, ScenePatch, ScenePlan, SceneStats, SceneVersion } from "@/lib/schema";

export type SliderKey = "handheld" | "depthOfField" | "motionBlur" | "fog" | "light";
export type ModelInput = { fileName: string; format: Asset["format"]; sizeBytes: number; source: Asset["source"]; sampleUrl: string | null; blob: Blob | null };
export type Busy = null | "loading" | "analyzing" | "planning" | "editing";

type StudioState = {
  project: Project | null;
  asset: Asset | null;
  blobMissing: boolean;
  stats: SceneStats | null;
  analysis: ModelAnalysis | null;
  versions: SceneVersion[];
  selectedVersionId: string | null;
  /** current plan = selected version's plan, or the live slider preview */
  currentPlan: ScenePlan | null;
  livePlan: ScenePlan | null;
  pendingWarning: (Warning & { plan: ScenePlan; prompt: string }) | null;
  busy: Busy;
  error: ServiceError | null;
  notFound: boolean;

  reset: () => void;
  open: (projectId: string) => Promise<void>;
  modelLoaded: (input: ModelInput, stats: SceneStats) => Promise<Result<Asset>>;
  submitPrompt: (prompt: string) => Promise<Result<SceneVersion | null>>;
  startOver: (prompt: string) => Promise<Result<SceneVersion | null>>;
  acceptPending: () => Promise<Result<SceneVersion | null>>;
  dismissPending: () => void;
  previewSlider: (key: SliderKey, value: number) => void;
  commitSlider: (key: SliderKey, value: number) => Promise<Result<SceneVersion | null>>;
  commitOutput: (output: Partial<ScenePlan["output"]>) => Promise<Result<SceneVersion | null>>;
  selectVersion: (id: string) => Promise<void>;
  clearError: () => void;
};

const initial = { project: null, asset: null, blobMissing: false, stats: null, analysis: null, versions: [], selectedVersionId: null,
  currentPlan: null, livePlan: null, pendingWarning: null, busy: null as Busy, error: null, notFound: false };

export function sliderPatches(key: SliderKey, value: number, plan: ScenePlan): ScenePatch[] {
  switch (key) {
    case "handheld": return [{ operation: "modify_camera", motionStrength: value, style: value > 0.15 ? "handheld" : "smooth" }];
    case "depthOfField": return [{ operation: "set_effect", effect: "depthOfField", value }];
    case "motionBlur": return [{ operation: "set_effect", effect: "motionBlur", value }];
    case "fog": return [{ operation: "set_scene", fogDensity: value }];
    case "light": return [{ operation: "update_lighting", exposureDelta: value - plan.lighting.exposure }];
  }
}

export const useStudioStore = create<StudioState>((set, get) => {
  const selectedPlan = () => {
    const { versions, selectedVersionId } = get();
    return versions.find((v) => v.id === selectedVersionId)?.plan ?? null;
  };

  const append = async (prompt: string, plan: ScenePlan, cost: number, reason: "scene_generation" | "prompt_edit" | null): Promise<Result<SceneVersion | null>> => {
    const { project, selectedVersionId } = get();
    if (!project) return { ok: false, error: { code: "no_project", message: "No project open." } };
    if (cost > 0 && reason) {
      const c = await services.credits.post({ amount: -cost, reason, projectId: project.id });
      if (!c.ok) { set({ error: c.error }); return c as Result<null>; }
    }
    const v = await services.projects.appendVersion({ projectId: project.id, prompt, parentId: selectedVersionId, plan });
    if (!v.ok) { set({ error: v.error }); return v; }
    await services.projects.updateProject(project.id, { selectedVersionId: v.value.id });
    set((s) => ({ versions: [...s.versions, v.value], selectedVersionId: v.value.id, currentPlan: plan, livePlan: null, pendingWarning: null }));
    return v;
  };

  const planFresh = async (prompt: string): Promise<Result<SceneVersion | null>> => {
    const { analysis } = get();
    if (!analysis) return { ok: false, error: { code: "no_model", message: "Load a model first." } };
    set({ busy: "planning", error: null });
    const r = await services.director.plan(prompt, analysis);
    set({ busy: null });
    if (!r.ok) { set({ error: r.error }); return r as Result<null>; }
    const warning = r.warnings?.[0];
    if (warning) { set({ pendingWarning: { ...warning, plan: r.value, prompt } }); return { ok: true, value: null, warnings: r.warnings }; }
    return append(prompt, r.value, CREDIT_COSTS.scene_generation, "scene_generation");
  };

  return {
    ...initial,
    reset: () => set({ ...initial }),
    clearError: () => set({ error: null }),

    open: async (projectId) => {
      set({ ...initial, busy: "loading" });
      const p = await services.projects.getProject(projectId);
      if (!p.ok) { set({ notFound: true, busy: null }); return; }
      const vs = await services.projects.listVersions(projectId);
      const versions = vs.ok ? vs.value : [];
      let asset: Asset | null = null;
      let blobMissing = false;
      if (p.value.assetId) {
        const a = await services.projects.getAsset(p.value.assetId);
        if (a.ok) {
          asset = a.value;
          if (asset.source === "upload") { const b = await services.projects.getAssetBlob(asset); blobMissing = !b.ok || b.value === null; }
        }
      }
      const selectedVersionId = p.value.selectedVersionId ?? versions[versions.length - 1]?.id ?? null;
      set({ project: p.value, asset, blobMissing, analysis: p.value.analysis, versions, selectedVersionId,
        currentPlan: versions.find((v) => v.id === selectedVersionId)?.plan ?? null, busy: null });
    },

    modelLoaded: async (input, stats) => {
      const { project } = get();
      if (!project) return { ok: false, error: { code: "no_project", message: "No project open." } };
      set({ busy: "analyzing", error: null, stats });
      const a = await services.projects.saveAsset({ projectId: project.id, fileName: input.fileName, format: input.format, sizeBytes: input.sizeBytes,
        source: input.source, blobKey: null, sampleUrl: input.sampleUrl, thumbnailKey: null }, input.blob);
      if (!a.ok) { set({ busy: null, error: a.error }); return a; }
      const an = await services.analysis.analyze(stats);
      const analysis = an.ok ? an.value : null;
      const up = await services.projects.updateProject(project.id, { assetId: a.value.id, analysis });
      set({ asset: a.value, blobMissing: false, analysis, project: up.ok ? up.value : project, busy: null });
      return a;
    },

    submitPrompt: async (prompt) => {
      const plan = selectedPlan();
      if (!plan) return planFresh(prompt);
      set({ busy: "editing", error: null });
      const r = await services.director.edit(prompt, plan);
      set({ busy: null });
      if (!r.ok) { set({ error: r.error }); return r as Result<null>; }
      const next = r.value.reduce(applyPatch, plan);
      return append(prompt, next, CREDIT_COSTS.prompt_edit, "prompt_edit");
    },

    startOver: (prompt) => planFresh(prompt),

    acceptPending: async () => {
      const pw = get().pendingWarning;
      if (!pw) return { ok: true, value: null };
      return append(pw.prompt, pw.plan, CREDIT_COSTS.scene_generation, "scene_generation");
    },
    dismissPending: () => set({ pendingWarning: null }),

    previewSlider: (key, value) => {
      const base = selectedPlan();
      if (!base) return;
      const live = sliderPatches(key, value, base).reduce(applyPatch, base);
      set({ livePlan: live, currentPlan: live });
    },
    commitSlider: async (key, value) => {
      const base = selectedPlan();
      if (!base) return { ok: false, error: { code: "no_plan", message: "Generate a scene first." } };
      const next = sliderPatches(key, value, base).reduce(applyPatch, base);
      return append(`manual: ${key}`, next, 0, null);
    },
    commitOutput: async (output) => {
      const base = selectedPlan();
      if (!base) return { ok: false, error: { code: "no_plan", message: "Generate a scene first." } };
      return append("manual: output", applyPatch(base, { operation: "set_output", output }), 0, null);
    },

    selectVersion: async (id) => {
      const { project, versions } = get();
      const v = versions.find((x) => x.id === id);
      if (!v || !project) return;
      await services.projects.updateProject(project.id, { selectedVersionId: id });
      set({ selectedVersionId: id, currentPlan: v.plan, livePlan: null });
    },
  };
});
```

- [ ] **Step 4: Run all tests, expect PASS.** Fix type errors from `Result` narrowing as needed; do not weaken the tests.
- [ ] **Step 5: Typecheck and commit** — `feat: studio, projects and credits stores`

**Chunk 1 done. All later chunks depend only on `lib/`.**

---

## Chunk 2: Design tokens, primitives, motion, layout (owner checkpoint)

Use skills @frontend-design and @ui-ux-pro-max in this chunk to pick a distinctive direction. Requirements from the spec: dark cinematic, near-black layered surfaces, one accent, high contrast (≥ 4.5:1 body text), viewer as hero. Avoid template defaults (no generic purple gradient, no Inter-only stack).

### Task 15: Tokens in Tailwind 4 and root layout

**Files:** Modify `app/globals.css`, `app/layout.tsx`; create `components/layout/Header.tsx`, `lib/motion/tokens.ts`, `lib/motion/variants.ts`.

- [ ] **Step 1: globals.css** — define an `@theme` block with: `--color-bg-0..3` (surface steps, near-black to raised), `--color-fg`, `--color-fg-muted`, `--color-accent`, `--color-accent-fg`, `--color-danger`, `--color-success`, `--radius-sm/md/lg`, `--shadow-raise`, font families (a display face + a text face + a mono face from Google Fonts via `next/font`), type scale `--text-xs..4xl`. Set `body` background to `--color-bg-0`, color `--color-fg`. Add a `.focus-ring` utility using `outline: 2px solid var(--color-accent); outline-offset: 2px`.
- [ ] **Step 2: motion tokens**

`lib/motion/tokens.ts`:
```ts
export const DUR = { fast: 0.15, base: 0.25, slow: 0.45 } as const;
export const EASE = { standard: [0.2, 0, 0, 1], emphasized: [0.3, 0, 0, 1] } as const;
export const SPRING = { gentle: { type: "spring", stiffness: 260, damping: 30 }, snappy: { type: "spring", stiffness: 500, damping: 35 } } as const;
```

`lib/motion/variants.ts`: export `fadeRise` (opacity 0→1, y 12→0, DUR.base, EASE.standard), `staggerList` (container with `staggerChildren: 0.05`), `panelSlide` (x 24→0), `scalePress` (whileTap scale 0.98). Each variant reads `useReducedMotion()` at the call site; provide `reduced(variant)` helper that strips transforms and keeps opacity.

- [ ] **Step 3: Header** — logo (BRAND.name), nav links Projects / Pricing, credit balance pill reading `useCreditsStore` (call `refresh` on mount). Credit number animates on change with `motion` `animate` from previous to current (count tick).
- [ ] **Step 4: layout.tsx** — fonts via `next/font/google`, `<Header />`, `<main>`, `<MotionConfig reducedMotion="user">`. Add `metadata.title = BRAND.name`.
- [ ] **Step 5: Verify** `npm run dev`, open `http://localhost:3000` → header visible, credit pill shows 100.
- [ ] **Step 6: Commit** — `feat: design tokens, motion tokens, header and root layout`

### Task 16: UI primitives

**Files:** Create `components/ui/{Button,Card,Chip,Slider,Tabs,Dialog,Toast,Field,Badge,Skeleton}.tsx`, `components/ui/index.ts`.

Contracts (props are the interface; keep them minimal):
- `Button`: `variant: "primary" | "secondary" | "ghost" | "danger"`, `size: "sm" | "md" | "lg"`, `loading?`, `icon?`; motion `scalePress`; focus ring.
- `Chip`: `selected?`, `onClick`; used for presets and example prompts; keyboard operable (`button` element).
- `Slider`: `label`, `min`, `max`, `step`, `value`, `onChange` (live), `onCommit` (pointer up / keyup); native `<input type="range">` styled, `aria-valuetext`.
- `Tabs`: `items: {id,label}[]`, `value`, `onChange`; roving `aria-selected`, arrow-key navigation; animated underline via `layoutId`.
- `Dialog`: native `<dialog>` wrapper with `open`, `onClose`, `title`, focus trap via `showModal()`.
- `Toast`: a tiny store `useToastStore` (`push({kind, message})`) and a `<Toaster/>` mounted in layout; auto-dismiss 4s; animated enter/exit with `AnimatePresence`.
- `Field`: label + input + inline error text.
- `Badge`: `tone: "neutral" | "accent" | "success" | "warning"`.
- `Skeleton`: shimmering placeholder block.

- [ ] **Step 1: Build each primitive** with the tokens; no hard-coded colours.
- [ ] **Step 2: Commit** — `feat: UI primitives`

### Task 17: `/dev/tokens` style sheet page

**Files:** Create `app/dev/tokens/page.tsx`.

- [ ] **Step 1:** Render: colour swatches with hex and contrast ratio against `bg-0` (compute in-page with a small WCAG luminance function), type scale specimens, all primitives in every state (default / hover hint / focused / disabled / loading), motion demo buttons that replay `fadeRise`, `panelSlide`, `staggerList`.
- [ ] **Step 2:** Verify in browser; every body-text swatch must show ≥ 4.5:1.
- [ ] **Step 3: Commit** — `feat: token style sheet page`

**CHECKPOINT: stop here. Show `/dev/tokens` to the owner and get explicit approval before Chunk 3.** Record approval (or requested changes) in the plan's commit message.

---

## Chunk 3: Viewer and upload

### Task 18: sceneStats from a three.js Object3D

**Files:** Create `components/viewer/sceneStats.ts`, `components/viewer/sceneStats.test.ts`.

- [ ] **Step 1: Failing test**

```ts
import { describe, it, expect } from "vitest";
import * as THREE from "three";
import { computeSceneStats } from "./sceneStats";

describe("computeSceneStats", () => {
  it("counts triangles, meshes, materials and names; measures extents", () => {
    const root = new THREE.Group();
    const m1 = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 4), new THREE.MeshStandardMaterial({ name: "Paint" }));
    m1.name = "Body";
    const m2 = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.5), m1.material);
    m2.name = "Wheel_FL"; m2.position.set(1, 0, 2);
    root.add(m1, m2);
    const s = computeSceneStats(root);
    expect(s.meshCount).toBe(2);
    expect(s.triangleCount).toBe(24);
    expect(s.materialCount).toBe(1);
    expect(s.objectNames).toEqual(["Body", "Wheel_FL"]);
    expect(s.materialNames).toEqual(["Paint"]);
    expect(s.extents[0]).toBeCloseTo(2.25);
    expect(s.hasSkeleton).toBe(false);
  });
  it("throws on empty or degenerate geometry", () => {
    expect(() => computeSceneStats(new THREE.Group())).toThrow(/no usable geometry/);
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

```ts
import * as THREE from "three";
import type { SceneStats } from "@/lib/schema";

export function computeSceneStats(root: THREE.Object3D): SceneStats {
  let triangleCount = 0, meshCount = 0, hasSkeleton = false;
  const materials = new Set<THREE.Material>();
  const objectNames: string[] = [];
  root.updateMatrixWorld(true);
  root.traverse((o) => {
    if ((o as THREE.SkinnedMesh).isSkinnedMesh) hasSkeleton = true;
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    meshCount++;
    if (mesh.name) objectNames.push(mesh.name);
    const g = mesh.geometry;
    const count = g.index ? g.index.count : g.attributes.position?.count ?? 0;
    triangleCount += Math.floor(count / 3);
    for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) materials.add(m);
  });
  if (meshCount === 0) throw new Error("no usable geometry");
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const extents: [number, number, number] = [size.x, size.y, size.z];
  if (extents.some((e) => !Number.isFinite(e) || e <= 0)) throw new Error("no usable geometry");
  return {
    triangleCount, meshCount, materialCount: materials.size, objectNames,
    materialNames: [...materials].map((m) => m.name).filter(Boolean),
    extents, hasSkeleton, animationClipCount: (root as unknown as { animations?: unknown[] }).animations?.length ?? 0,
  };
}
```

- [ ] **Step 4: Run, expect PASS.** **Step 5: Commit** — `feat: scene statistics from loaded models`

### Task 19: Model loading hook

**Files:** Create `components/viewer/loadModel.ts`, `components/viewer/loadModel.test.ts`.

- [ ] **Step 1: Failing test** (format detection and validation only; loaders are exercised in e2e)

```ts
import { describe, it, expect } from "vitest";
import { validateFile } from "./loadModel";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";

const f = (name: string, size = 10) => new File([new Uint8Array(size)], name);

describe("validateFile", () => {
  it("accepts supported formats", () => {
    expect(validateFile(f("a.glb"))).toEqual({ ok: true, value: "glb" });
    expect(validateFile(f("a.FBX"))).toEqual({ ok: true, value: "fbx" });
  });
  it("rejects unsupported", () => {
    expect(validateFile(f("a.stl")).ok).toBe(false);
  });
  it("rejects oversize", () => {
    const big = { name: "a.glb", size: MAX_UPLOAD_BYTES + 1 } as File;
    const r = validateFile(big);
    expect(!r.ok && r.error.code).toBe("too_large");
  });
});
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**

```ts
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { fail, ok, type Result } from "@/lib/services";
import type { Asset } from "@/lib/schema";

export type Format = Asset["format"];

export function validateFile(file: File): Result<Format> {
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (ext !== "glb" && ext !== "gltf" && ext !== "fbx" && ext !== "obj")
    return fail("unsupported_format", "Unsupported file type. Use GLB, GLTF, FBX or OBJ.");
  if (file.size > MAX_UPLOAD_BYTES) return fail("too_large", `File is over ${Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB.`);
  return ok(ext);
}

export type Loaded = { root: THREE.Object3D; notices: string[] };

export async function loadModel(source: Blob | string, format: Format): Promise<Result<Loaded>> {
  const url = typeof source === "string" ? source : URL.createObjectURL(source);
  const notices: string[] = [];
  try {
    if (format === "glb" || format === "gltf") {
      if (format === "gltf" && typeof source !== "string") {
        const text = await source.text();
        if (/"uri"\s*:\s*"(?!data:)/.test(text)) return fail("external_files", "This .gltf references external files. Export as a single .glb instead.");
      }
      const gltf = await new GLTFLoader().loadAsync(url);
      (gltf.scene as unknown as { animations: unknown[] }).animations = gltf.animations;
      return ok({ root: gltf.scene, notices });
    }
    if (format === "fbx") return ok({ root: await new FBXLoader().loadAsync(url), notices });
    const obj = await new OBJLoader().loadAsync(url);
    obj.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) m.material = new THREE.MeshStandardMaterial({ color: 0x9a9a9a, roughness: 0.6 }); });
    notices.push("OBJ loaded without materials; a neutral material was applied.");
    return ok({ root: obj, notices });
  } catch {
    return fail("parse_failed", "Couldn't read this model. Try re-exporting it as GLB.");
  } finally {
    if (typeof source !== "string") URL.revokeObjectURL(url);
  }
}

/** Centre on origin, rest on ground (y = 0), scale by analysis factor later. */
export function normalize(root: THREE.Object3D): void {
  const box = new THREE.Box3().setFromObject(root);
  const c = box.getCenter(new THREE.Vector3());
  root.position.sub(c);
  root.position.y += c.y - box.min.y;
}
```

- [ ] **Step 4: Run, expect PASS.** **Step 5: Commit** — `feat: model file validation, loading and normalization`

### Task 20: Viewer canvas, environment presets, camera path, scrubber, thumbnail

**Files:** Create `components/viewer/Viewer.tsx`, `Environment.tsx`, `CameraPath.tsx`, `PreviewCamera.tsx`, `Scrubber.tsx`, `RainLayer.tsx`, `thumbnail.ts`, `cameraPath.ts`, `cameraPath.test.ts`.

- [ ] **Step 1: Failing test for path maths** (`cameraPath.test.ts`)

```ts
import { describe, it, expect } from "vitest";
import { shotPathPoint } from "./cameraPath";
import { defaultPlan } from "@/lib/scene/defaultPlan";

describe("shotPathPoint", () => {
  const plan = defaultPlan("car");
  const bounds = { radius: 2.5, height: 1.4 };
  it("orbit keeps constant distance", () => {
    const a = shotPathPoint(plan, plan.shots[0], 0, bounds);
    const b = shotPathPoint(plan, plan.shots[0], 0.5, bounds);
    const d = (p: { x: number; z: number }) => Math.hypot(p.x, p.z);
    expect(d(a)).toBeCloseTo(d(b));
  });
  it("push in gets closer over time", () => {
    const shot = { ...plan.shots[0], action: "hero_push_in" as const };
    const a = shotPathPoint(plan, shot, 0, bounds);
    const b = shotPathPoint(plan, shot, 1, bounds);
    expect(Math.hypot(b.x, b.z)).toBeLessThan(Math.hypot(a.x, a.z));
  });
  it("respects camera height", () => {
    expect(shotPathPoint(plan, plan.shots[0], 0.3, bounds).y).toBeCloseTo(plan.camera.heightM);
  });
});
```

- [ ] **Step 2: Implement `cameraPath.ts`**

```ts
import type { ScenePlan, Shot } from "@/lib/schema";
export type Bounds = { radius: number; height: number };

/** t in [0,1] within the shot. Returns camera position; target is always the subject centre at bounds.height/2. */
export function shotPathPoint(plan: ScenePlan, shot: Shot, t: number, b: Bounds): { x: number; y: number; z: number } {
  const base = b.radius * 2.2 * shot.distanceMultiplier * (50 / plan.camera.lensMm) ** 0.5;
  const y = plan.camera.heightM;
  switch (shot.action) {
    case "slow_orbit": { const a = -Math.PI * 0.25 + t * Math.PI * 0.9; return { x: Math.sin(a) * base, y, z: Math.cos(a) * base }; }
    case "hero_push_in": { const r = base * (1.6 - 0.8 * t); const a = -Math.PI * 0.2; return { x: Math.sin(a) * r, y, z: Math.cos(a) * r }; }
    case "low_tracking": { return { x: -base * 0.8 + t * base * 1.6, y: Math.min(y, 0.6), z: base * 0.9 }; }
    case "handheld_walk_toward": { const r = base * (1.8 - 1.0 * t); const a = -Math.PI * 0.3 + t * 0.2; return { x: Math.sin(a) * r, y, z: Math.cos(a) * r }; }
  }
}

export function handheldOffset(t: number, strength: number) {
  return { x: Math.sin(t * 7.3) * 0.02 * strength, y: Math.abs(Math.sin(t * 5.1)) * 0.03 * strength, roll: Math.sin(t * 2.1) * 0.01 * strength };
}
```

- [ ] **Step 3: Viewer component** (`Viewer.tsx`, client component). Props: `{ root: THREE.Object3D | null; plan: ScenePlan | null; scaleFactor: number; onStats?: (s: SceneStats) => void; onThumbnail?: (b: Blob) => void; previewT: number | null; }`.
  - `<Canvas dpr={[1, 2]} gl={{ antialias: true }} camera={{ fov: 35 }}>`; `<Suspense>`; `<OrbitControls makeDefault enabled={previewT === null} />`; drei `<Grid>` ground; `<Bounds fit clip observe>` around the model on first mount for auto-framing.
  - Scale model by `scaleFactor`; call `normalize`.
  - `<Environment plan={plan} />` maps `plan.scene.environment` to background colour, ambient + key + rim lights, fog (`scene.fog = FogExp2(colour, plan.scene.fogDensity * 4)`), ground material (wet = lower roughness + `metalness 0.2`, `envMapIntensity` up). Use drei `<Environment preset>` only for `studio_*` (preset "studio"), otherwise "night" / "sunset" presets; keep it cheap.
  - `<RainLayer intensity={plan.effects.rain} />`: `Points` with ~1500 vertices falling on `useFrame`; under reduced motion (`useReducedMotion`) render static streaks (no `useFrame` update).
  - `<CameraPath plan bounds />`: for each shot, sample `shotPathPoint` at 64 points into a `Line` (drei), accent colour, second shot slightly dimmer.
  - `<PreviewCamera plan bounds t={previewT} />`: when `previewT !== null`, position a `PerspectiveCamera makeDefault` at `shotPathPoint` for the shot containing `t` plus `handheldOffset` if handheld; `lookAt` subject centre; fov from lens: `fov = 2*atan(12/lensMm)` (35mm sensor half-height 12mm) in degrees.
  - Thumbnail: a small `<ThumbnailCapture onCapture />` component inside Canvas that, when `captureKey` prop changes, does `gl.render(scene, camera)` then `gl.domElement.toBlob(cb, "image/jpeg", 0.8)` in the same `useFrame` callback; parent downscales via an offscreen canvas to 480px wide in `thumbnail.ts`.
  - `data-model-loaded="true"` attribute set on the wrapper div once the model has mounted (used by e2e).
  - Wrap Canvas in an error boundary (`components/viewer/ViewerBoundary.tsx`) showing "3D preview failed to start" and a Reload button.
- [ ] **Step 4: Scrubber** (`Scrubber.tsx`): range input 0..durationS with `onChange` → `previewT`; `onPointerUp`/`Escape` → `null`. Shows current shot label and time. Exiting preview restores orbit.
- [ ] **Step 5: Manual verify**: temporary page `app/dev/viewer/page.tsx` that loads `/samples/car.glb` with `defaultPlan("car")` and a scrubber. Confirm: auto-framed, grid, path line, scrubbing moves camera, Escape exits. Delete this page before commit or keep under `/dev` — keep it; it is useful.
- [ ] **Step 6: Commit** — `feat: 3D viewer with environments, camera path preview and thumbnail capture`

### Task 21: Sample assets

**Files:** Add `public/samples/car.glb`, `public/samples/product.glb`, `public/samples/LICENSES.md`.

- [ ] **Step 1:** Source two CC0 GLB files (e.g. from Poly Haven models or Khronos glTF sample assets with CC0 licence; a car ≤ 15 MB, a product such as a sneaker/headphones/watch ≤ 10 MB). Record source URL, author, licence in `LICENSES.md`. If no CC0 car is readily available, generate a stylised low-poly car in Blender 5.0 (installed locally: `C:\Program Files\Blender Foundation\Blender 5.0`) with named parts `Body`, `Wheel_FL/FR/RL/RR`, `Windshield`, `Headlight_L/R`, export GLB, note "generated in-house" in `LICENSES.md`.
- [ ] **Step 2:** Verify both load in `/dev/viewer` and the car classifies as `car` with four wheels (check names in stats). Rename nodes in Blender if needed.
- [ ] **Step 3: Commit** — `chore: add CC0 sample models`

---

## Chunk 4: Studio

### Task 22: Studio route, shell and step indicator

**Files:** Create `app/projects/[id]/page.tsx`, `components/studio/StudioShell.tsx`, `components/studio/StepIndicator.tsx`, `components/studio/useStudioModel.ts`.

- [ ] **Step 1: page** — client component; `useEffect` → `useStudioStore.getState().open(id)`; if `notFound` → `router.replace("/projects?notice=not_found")`. Renders `<StudioShell/>`.
- [ ] **Step 2: useStudioModel** — hook that, given `asset`, loads the model: `sampleUrl` via `loadModel(url, format)`, upload via `getAssetBlob` then `loadModel(blob, format)`; returns `{ root, notices, error }`. On `blobMissing` returns `null` and the shell shows the re-upload state.
- [ ] **Step 3: StudioShell layout** — CSS grid: top bar (project name editable inline, `StepIndicator`), left rail (`VersionRail`, 240px, collapsible), centre (`Viewer` + `Scrubber`), right panel (`Tabs`: Analysis / Controls / Render, 360px), bottom dock (`PromptDock`). Panels use `panelSlide` on mount. Under 1100px the right panel becomes a bottom sheet toggle; under 768px nothing may overflow horizontally.
- [ ] **Step 4: StepIndicator** — steps `Upload → Understand → Direct → Render`; derived: Upload done when `asset`; Understand done when `analysis`; Direct done when `versions.length > 0`; Render always "next" with a small "not connected" tag. Filled segments animate width with `SPRING.gentle`.
- [ ] **Step 5: Verify** route renders with an empty project. **Step 6: Commit** — `feat: studio shell and step indicator`

### Task 23: Upload empty state and labour sequence

**Files:** Create `components/studio/UploadDropzone.tsx`, `components/studio/LabourSequence.tsx`, `components/studio/labour.ts`, `components/studio/labour.test.ts`.

- [ ] **Step 1: Failing test** (`labour.test.ts`)

```ts
import { describe, it, expect } from "vitest";
import { scheduleSteps } from "./labour";

describe("scheduleSteps", () => {
  it("spreads steps across at least the minimum duration", () => {
    const s = scheduleSteps(["a", "b", "c"], 1200);
    expect(s.map((x) => x.at)).toEqual([0, 400, 800]);
    expect(s[2].label).toBe("c");
  });
});
```

- [ ] **Step 2: Implement `labour.ts`**

```ts
export const LABOUR_MIN_MS = 1200;
export const ANALYSIS_STEPS = ["Reading geometry", "Measuring dimensions", "Identifying parts", "Checking capabilities"];
export const PLANNING_STEPS = ["Reading your prompt", "Choosing environment", "Choosing lens and camera path", "Setting lights and effects"];
export function scheduleSteps(labels: string[], minMs = LABOUR_MIN_MS) {
  const gap = minMs / labels.length;
  return labels.map((label, i) => ({ label, at: Math.round(i * gap) }));
}
```

- [ ] **Step 3: LabourSequence component** — props `{ steps: string[]; active: boolean; onDone: () => void }`. When `active` turns true, reveals steps on the schedule (check icon animates in per step); calls `onDone` at `LABOUR_MIN_MS` or when the underlying async work finishes, whichever is later (parent passes `active=false` when work is done; component keeps showing until min elapsed). Reduced motion: list all steps immediately, still hold the minimum.
- [ ] **Step 4: UploadDropzone** — full-viewer overlay when no asset: drag target + "Choose file" + two sample cards (car, product) with thumbnails (static PNGs in `public/samples/*.jpg`, captured from `/dev/viewer`). On file: `validateFile` → `loadModel` → `computeSceneStats` (catch → "no usable geometry") → `useStudioStore.modelLoaded(...)`. Wrap analysis in `LabourSequence` with `ANALYSIS_STEPS`. Errors from the store (`quota_exceeded`, etc.) shown inline with the spec's copy. Prompt input disabled while busy.
- [ ] **Step 5: Verify** in browser with sample car: model lands, analysis steps play, step indicator fills two segments. **Step 6: Commit** — `feat: upload dropzone with labour sequence`

### Task 24: Analysis panel

**Files:** Create `components/studio/AnalysisPanel.tsx`.

- [ ] **Step 1:** Renders `analysis`: category badge + confidence (as "97% sure"), dimensions in metres with unit guess ("read as millimetres"), parts list (role → name), capabilities as chips, rig status. Fields reveal one by one (`staggerList`). Empty state when no analysis: "Load a model to see what it is."
- [ ] **Step 2: Commit** — `feat: analysis panel`

### Task 25: Prompt dock, presets, warning banner

**Files:** Create `components/studio/PromptDock.tsx`, `components/studio/PresetChips.tsx`, `components/studio/presets.ts`, `components/studio/WarningBanner.tsx`, `components/studio/OutputSettings.tsx`.

- [ ] **Step 1: presets.ts**

```ts
export const PRESETS = [
  { id: "auto_commercial", label: "Automotive Commercial", prompt: "Cinematic car commercial on a mountain road at sunset, slow orbit then push in, 10 seconds" },
  { id: "rainy_night", label: "Rainy Night", prompt: "Rainy night city street, wet asphalt, handheld camera walking toward the car" },
  { id: "luxury_studio", label: "Luxury Studio", prompt: "Black studio, dramatic lighting, slow orbit, close up" },
  { id: "product_white", label: "Clean Product", prompt: "White studio, soft lighting, slow orbit, 5 seconds" },
  { id: "tracking", label: "Low Tracking", prompt: "Low tracking shot alongside the car on a highway at dusk" },
] as const;
```

- [ ] **Step 2: PromptDock** — textarea (Enter submits, Shift+Enter newline), submit button (label "Generate scene · 2 credits" before first version, "Apply edit · 1 credit" after), "Start over" ghost button after first version (calls `startOver`), `PresetChips` above input (chip fills textarea, does not submit), example-prompt placeholder rotating from `PRESETS`. While `busy` is `planning`/`editing`, textarea disabled and `LabourSequence` with `PLANNING_STEPS` shows in the dock. Errors (`edit_not_understood` with hints as clickable chips, `at_limit`, `insufficient_credits` with link to `/pricing`) render inline under the input.
- [ ] **Step 3: WarningBanner** — shows `pendingWarning.message` with buttons "Use this scene" (`acceptPending`) and "Rewrite prompt" (`dismissPending`, refocus textarea). Slides in from bottom of viewer.
- [ ] **Step 4: OutputSettings** — segmented controls for duration (5/10/15/30), resolution, fps, quality; visible only when `currentPlan`; each change → `commitOutput`. Collapsed by default behind a "10s · 1080p · 30fps · High" summary chip (progressive disclosure).
- [ ] **Step 5: Verify** flow: preset → generate → viewer environment changes, version appears (rail built next task; check store in React devtools or console). **Step 6: Commit** — `feat: prompt dock, presets, warning banner, output settings`

### Task 26: Version rail and controls panel

**Files:** Create `components/studio/VersionRail.tsx`, `components/studio/ControlsPanel.tsx`.

- [ ] **Step 1: VersionRail** — list of versions (index, prompt text truncated, relative time); selected highlighted; keyboard: arrow up/down + Enter; click → `selectVersion`. New items `fadeRise`. Empty state: "Your scene history appears here."
- [ ] **Step 2: ControlsPanel** — five `Slider`s: Handheld (0–1, from `camera.motionStrength`), Depth of field (0–1), Motion blur (0–1), Fog (0–0.1, step 0.005), Light (−3–3 EV, from `lighting.exposure`). `onChange` → `previewSlider`; `onCommit` → `commitSlider`. Disabled with hint when no plan. Labels show human words at ends ("Smooth … Raw", "Dark … Bright").
- [ ] **Step 3: Verify** slider commit adds `manual:` version; selecting old version updates viewer. **Step 4: Commit** — `feat: version rail and manual controls`

### Task 27: Render panel, JobProgress, RenderResult, `/dev/render-states`

**Files:** Create `components/studio/RenderPanel.tsx`, `components/studio/JobProgress.tsx`, `components/studio/RenderResult.tsx`, `app/dev/render-states/page.tsx`.

- [ ] **Step 1: JobProgress** — props `{ job: RenderJob }`; shows status label, progress bar (`frame/totalFrames`), frame counter "Frame 204 / 300", state-specific copy for all seven statuses; FAILED shows `job.error` and a Retry button (prop `onRetry?`). Pure presentational.
- [ ] **Step 2: RenderResult** — props `{ job: RenderJob; onRegenerate: () => void }`; 16:9 player frame (`<video>` if `resultUrl` else an empty framed surface), Download button (disabled without url), Regenerate. Designed as the product's peak moment: generous spacing, subtle reveal animation.
- [ ] **Step 3: RenderPanel** — "Generate preview · 3 credits" button; then two choice cards: Local GPU ("Your GPU · RTX 5080 detected" placeholder text, "5 credits", "Cheapest") and Cloud GPU ("Fastest, no setup", "30 credits" from `CREDIT_COSTS.cloud_final[plan.output.quality]` where ultra→90, "4k" resolution→160); output summary line; primary "Render" button. Any action → `services.render.requestPreview/requestFinal` → on `not_connected` show a designed empty state inside the panel: "Renderer not connected yet — this is where your render will appear." No credits charged.
- [ ] **Step 4: `/dev/render-states`** — grid rendering `JobProgress` for each of the seven statuses with fixtures, `RenderResult` with and without `resultUrl`, and the RenderPanel not-connected state. No timers.
- [ ] **Step 5: Verify** visually. **Step 6: Commit** — `feat: render surfaces with intentionally blank process`

---

## Chunk 5: Dashboard, pricing, landing

These three tasks are independent; run in parallel subagents if available.

### Task 28: Dashboard

**Files:** Create `app/projects/page.tsx`, `components/dashboard/ProjectGrid.tsx`, `ProjectCard.tsx`, `NewProjectDialog.tsx`, `useThumbnail.ts`.

- [ ] **Step 1: page** — on mount `useProjectsStore.refresh()`; if `?notice=not_found` push toast "That project no longer exists." If IndexedDB unavailable (`!("indexedDB" in window)`) render blocking notice per spec. If repository `corruptDetected`, toast once.
- [ ] **Step 2: ProjectCard** — thumbnail (from `useThumbnail(assetId)` → object URL of IndexedDB blob, else gradient placeholder), name, category badge from `project.analysis?.category`, version count, state label via `deriveProjectState`, relative time, overflow menu: Rename (inline `Field`), Delete (Dialog confirm "Delete project and its model?"). Whole card is a link to `/projects/[id]`; hover lift.
- [ ] **Step 3: ProjectGrid** — `staggerList` entrance; "New project" card first; empty state with a big "Create your first project" CTA and a one-line pitch.
- [ ] **Step 4: NewProjectDialog** — name field (default "Untitled project"), Create → store.create → `router.push` to studio.
- [ ] **Step 5: Verify** create/rename/delete; thumbnail appears after a model is loaded in the studio. **Step 6: Commit** — `feat: projects dashboard`

### Task 29: Pricing

**Files:** Create `app/pricing/page.tsx`, `components/pricing/PlanCards.tsx`, `CreditPacks.tsx`, `ActionCostTable.tsx`.

- [ ] **Step 1: PlanCards** — three cards from `PLANS`; middle card raised, accent border, "Most popular" badge; "Choose plan" → `useCreditsStore.add(credits, "plan_grant")` + toast "Added N credits (prototype)". Repeatable.
- [ ] **Step 2: CreditPacks** — three packs; per-credit price shown small so the larger pack reads as better value; "Buy" → `add(credits, "pack_purchase")`.
- [ ] **Step 3: ActionCostTable** — rows from `CREDIT_COSTS`; local render row and cloud rows adjacent with a "Local is 6× cheaper" callout computed from the constants.
- [ ] **Step 4: Verify** balance in header ticks up on buy. **Step 5: Commit** — `feat: pricing page`

### Task 30: Landing

**Files:** Create `app/page.tsx`, `components/landing/{Hero,Steps,LocalVsCloud,PricingTeaser,FinalCta,Footer}.tsx`.

- [ ] **Step 1: Hero** — headline `BRAND.tagline`, sub-line ("Upload a 3D model, describe the shot, get a cinematic render."), the ONLY canvas on the page: `<Viewer>` with `/samples/car.glb` and a plan from `planFromPrompt(chip.prompt, "car")`; three example chips (Rainy Night, Sunset Road, Studio) morph the viewer environment (cross-fade via `AnimatePresence` on the Environment). Primary CTA "Start a project" → `/projects`. Hero content `fadeRise` on load.
- [ ] **Step 2: Steps** — three cards (Upload, Describe, Render) with icons, scroll-triggered `staggerList` (`whileInView`, once).
- [ ] **Step 3: LocalVsCloud** — two columns comparing (uses `CREDIT_COSTS`). **Step 4: PricingTeaser** — three plan names/prices → `/pricing`. **Step 5: FinalCta + Footer** (footer: brand, "Prototype — no renders are produced yet").
- [ ] **Step 6: Verify** no horizontal scroll at 375px width; one WebGL context (check `document.querySelectorAll("canvas").length === 1`). **Step 7: Commit** — `feat: landing page`

---

## Chunk 6: Polish, accessibility, e2e

### Task 31: Motion and psychology pass

- [ ] **Step 1:** Walk every screen against spec sections 9 and 10; fix gaps. Checklist to tick in the commit message: hero reveal; steps stagger; dashboard stagger + hover lift; model drop-in + camera settle; analysis stagger; environment cross-fade; path easing; rail slide-in; slider/chip micro-interactions; credit tick; step indicator advance; route fades; reduced-motion parity; prompt disabled during labour; low-credit warning before failing action (show when balance < cost of next action).
- [ ] **Step 2:** Use @web-design-guidelines to audit; fix findings.
- [ ] **Step 3: Commit** — `polish: motion and psychology pass`

### Task 32: Accessibility pass

- [ ] **Step 1:** Keyboard-only walkthrough of the full flow; every interactive element reachable, focus visible, tabs arrow-navigable, dialogs trap focus, `aria-label` on icon buttons, `aria-live="polite"` on labour sequence and toasts.
- [ ] **Step 2:** Contrast check on `/dev/tokens` all ≥ 4.5:1 for text.
- [ ] **Step 3: Commit** — `polish: accessibility pass`

### Task 33: Playwright e2e

**Files:** Create `playwright.config.ts`, `e2e/studio.spec.ts`.

- [ ] **Step 1: config**

```ts
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e",
  webServer: { command: "npm run dev", url: "http://localhost:3000", reuseExistingServer: true, timeout: 120_000 },
  use: { baseURL: "http://localhost:3000", launchOptions: { args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] } },
});
```

- [ ] **Step 2: spec**

```ts
import { test, expect } from "@playwright/test";

test("create project, load sample, plan, edit, render not connected", async ({ page }) => {
  await page.goto("/projects");
  await page.getByRole("button", { name: /new project/i }).click();
  await page.getByRole("button", { name: /^create$/i }).click();
  await expect(page).toHaveURL(/\/projects\/[^/]+$/);
  await page.getByRole("button", { name: /sample car/i }).click();
  await expect(page.locator("[data-model-loaded='true']")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/car/i).first()).toBeVisible();
  await page.getByRole("textbox", { name: /describe/i }).fill("rainy night, handheld walking toward the car");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("listitem", { name: /version 1/i })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("textbox", { name: /describe/i }).fill("darker");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("listitem", { name: /version 2/i })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("tab", { name: /render/i }).click();
  await page.getByRole("button", { name: /generate preview/i }).click();
  await expect(page.getByText(/renderer not connected/i)).toBeVisible();
});
```

Give the version rail items `role="listitem"` with `aria-label="Version N: <prompt>"`, and the textarea `aria-label="Describe your render"` so the selectors above hold.

- [ ] **Step 3:** `npx playwright install chromium`, then `npm run e2e`. Expected: 1 passed.
- [ ] **Step 4: Commit** — `test: end-to-end studio flow`

### Task 34: Final verification

- [ ] `npm run typecheck && npm run test && npm run e2e && npm run build` all pass. Fix anything that fails.
- [ ] Update `README.md` in `apps/web` with: what this is, what is intentionally missing (render process), how to run, where to swap services for a real backend (`lib/services/index.ts`).
- [ ] Commit — `docs: prototype README`
