import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { CREDIT_COSTS, PLANS, PLAN_LIMITS, CREDIT_PACKS, FREE_PLAN_CREDITS, MAX_UPLOAD_BYTES, STARTING_BALANCE, limitFeatures } from "./pricing";


describe("pricing", () => {
  it("matches the spec numbers", () => {
    expect(CREDIT_COSTS.scene_generation).toBe(2);
    expect(CREDIT_COSTS.prompt_edit).toBe(1);
    expect(CREDIT_COSTS.preview_render).toBe(3);
    expect(CREDIT_COSTS.local_final).toBe(5);
    expect(CREDIT_COSTS.final_render).toBe(60);
    expect(STARTING_BALANCE).toBe(FREE_PLAN_CREDITS);
    expect(FREE_PLAN_CREDITS).toBe(50);
    expect(PLANS[0].credits).toBe(FREE_PLAN_CREDITS);
    expect(PLANS.map((p) => p.name)).toEqual(["Free", "Creator", "Pro"]);
    expect(PLANS[1].highlighted).toBe(true);
    expect(CREDIT_PACKS).toEqual([
      { credits: 100, priceUsd: 5 },
      { credits: 500, priceUsd: 20 },
      { credits: 2000, priceUsd: 70 },
    ]);
  });
});

describe("plan claims (what the system can actually do)", () => {
  const all = PLANS.flatMap((p) => p.features).join(" | ");
  it("never promises 4K or a GPU priority (the worker renders 540p / 1080p; RunPod has no per-job priority)", () => {
    expect(all).not.toMatch(/4k|2160|1440|priority/i);
  });
  it("derives each card's render lines from PLAN_LIMITS", () => {
    for (const plan of ["free", "creator", "pro"] as const) {
      const card = PLANS.find((p) => p.name.toLowerCase() === plan)!;
      for (const line of limitFeatures(plan)) expect(card.features).toContain(line);
    }
    expect(PLANS[0].features).toEqual(["50 credits", "540p preview renders", "Watermark on renders", "1 render at a time", "7-day retention"]);
    expect(PLANS[2].features).toContain("3 renders at once");
  });
  it("keeps the plan table to the two tiers the worker renders", () => {
    expect(PLAN_LIMITS.free).toMatchObject({ maxResolution: "540p", tiers: ["preview"], watermark: true, retentionDays: 7, maxActiveJobs: 1 });
    expect(PLAN_LIMITS.creator).toMatchObject({ maxResolution: "1080p", tiers: ["preview", "final"], watermark: false, retentionDays: 30, maxActiveJobs: 1 });
    expect(PLAN_LIMITS.pro).toMatchObject({ maxResolution: "1080p", tiers: ["preview", "final"], watermark: false, retentionDays: 90, maxActiveJobs: 3 });
    expect(PLAN_LIMITS.free.rank < PLAN_LIMITS.creator.rank && PLAN_LIMITS.creator.rank < PLAN_LIMITS.pro.rank).toBe(true);
  });
});

describe("pricing constants mirrored in the database", () => {
  const dir = join(__dirname, "..", "supabase", "migrations");
  const sql = readdirSync(dir).filter((f) => f.endsWith(".sql")).map((f) => readFileSync(join(dir, f), "utf8")).join("\n");
  it("grants the Free plan credits to new users", () => {
    const m = sql.match(/function public\.free_plan_credits\(\)[\s\S]*?select (\d+) \$\$/);
    expect(Number(m?.[1])).toBe(FREE_PLAN_CREDITS);
  });
  it("caps uploads at the same size", () => {
    const m = sql.match(/function public\.max_upload_bytes\(\)[\s\S]*?select (\d+)::bigint/);
    expect(Number(m?.[1])).toBe(MAX_UPLOAD_BYTES);
  });
});
