import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { VERSION_ACTION_COST, VERSION_HOURLY_CAP } from "@/lib/scene/versionAction";
import { INPUT_FAILURE_FEE } from "@/lib/render/failurePolicy";
import {
  CHECKOUT_ITEMS, CREDIT_COSTS, CREDIT_PACKS, FREE_PLAN_CREDITS, MAX_UPLOAD_BYTES, PLANS, PLAN_CREDIT_ROLLOVER_PERIODS, PLAN_LIMITS,
  REFERRAL_BONUS_CREDITS, REFERRAL_MONTHLY_CAP, RENDER_FAILURE_FEE, STARTING_BALANCE, creditValue, limitFeatures, priceEnvName,
} from "./pricing";


describe("pricing (placeholder prices, owner decision 2026-09-28)", () => {
  it("matches the approved numbers", () => {
    expect(CREDIT_COSTS.scene_generation).toBe(2);
    expect(CREDIT_COSTS.prompt_edit).toBe(1);
    expect(CREDIT_COSTS.preview_render).toBe(10);
    expect(CREDIT_COSTS.local_final).toBe(5);
    expect(CREDIT_COSTS.final_render).toBe(200);
    expect(RENDER_FAILURE_FEE).toBe(CREDIT_COSTS.preview_render);
    expect(INPUT_FAILURE_FEE).toBe(RENDER_FAILURE_FEE);
    expect(STARTING_BALANCE).toBe(FREE_PLAN_CREDITS);
    expect(FREE_PLAN_CREDITS).toBe(30);
    expect(PLANS.map((p) => [p.name, p.priceUsd, p.credits])).toEqual([["Free", 0, 30], ["Creator", 19, 400], ["Pro", 49, 1100]]);
    expect(PLANS[1].highlighted).toBe(true);
    expect(CREDIT_PACKS).toEqual([
      { credits: 250, priceUsd: 12 },
      { credits: 600, priceUsd: 25 },
      { credits: 1500, priceUsd: 55 },
    ]);
    expect(PLAN_CREDIT_ROLLOVER_PERIODS).toBe(1);
    expect(REFERRAL_BONUS_CREDITS).toBe(100);
    expect(REFERRAL_MONTHLY_CAP).toBe(20);
  });
  it("sells no pack below Paddle's minimum charge ($10)", () => {
    for (const pack of CREDIT_PACKS) expect(pack.priceUsd).toBeGreaterThanOrEqual(10);
  });
  it("derives checkout keys and Paddle env names from the packs", () => {
    expect(CHECKOUT_ITEMS).toEqual(["plan:creator", "plan:pro", "pack:250", "pack:600", "pack:1500"]);
    expect(CHECKOUT_ITEMS.map(priceEnvName)).toEqual([
      "PADDLE_PRICE_CREATOR_MONTHLY", "PADDLE_PRICE_PRO_MONTHLY", "PADDLE_PRICE_PACK_250", "PADDLE_PRICE_PACK_600", "PADDLE_PRICE_PACK_1500",
    ]);
  });
  it("states what credits buy honestly per plan (Free is never promised a Final)", () => {
    expect(creditValue(FREE_PLAN_CREDITS, "free")).toBe("3 Previews");
    expect(creditValue(400, "creator")).toBe("40 Previews or 2 Finals");
    expect(creditValue(1100, "pro")).toBe("110 Previews or 5 Finals");
    expect(creditValue(10_000, "free")).not.toMatch(/final/i);
    expect(PLANS.map((p) => p.value)).toEqual(["3 Previews", "40 Previews or 2 Finals", "110 Previews or 5 Finals"]);
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
    expect(PLANS[0].features).toEqual(["30 credits, once", "540p preview renders", "Watermark on renders", "1 render at a time", "7-day retention"]);
    expect(PLANS[1].features).toContain("Unused plan credits roll over one month");
    expect(PLANS[0].features.join(" ")).not.toMatch(/roll over/);
    expect(PLANS[2].features).toContain("3 renders at once");
  });
  it("keeps the plan table to the two tiers the worker renders", () => {
    expect(PLAN_LIMITS.free).toMatchObject({ maxResolution: "540p", tiers: ["preview"], watermark: true, retentionDays: 7, maxActiveJobs: 1 });
    expect(PLAN_LIMITS.creator).toMatchObject({ maxResolution: "1080p", tiers: ["preview", "final"], watermark: false, retentionDays: 30, maxActiveJobs: 1 });
    expect(PLAN_LIMITS.pro).toMatchObject({ maxResolution: "1080p", tiers: ["preview", "final"], watermark: false, retentionDays: 90, maxActiveJobs: 3 });
    expect(PLAN_LIMITS.free.rank < PLAN_LIMITS.creator.rank && PLAN_LIMITS.creator.rank < PLAN_LIMITS.pro.rank).toBe(true);
  });
});

describe("pricing constants mirrored in the database (one migration per layer)", () => {
  const dir = join(__dirname, "..", "supabase", "migrations");
  const files = readdirSync(dir).filter((f) => f.endsWith(".sql")).sort();
  const all = files.map((f) => readFileSync(join(dir, f), "utf8")).join("\n");
  /** The LAST definition of a SQL function wins (migrations run in order). */
  const last = (fn: string, re: RegExp) => {
    const hits = [...all.matchAll(new RegExp(String.raw`create (?:or replace )?function public\.${fn}\([\s\S]*?\$\$[\s\S]*?\$\$`, "g"))].map((m) => m[0]);
    const m = hits.at(-1)?.match(re);
    expect(m, fn).not.toBeNull();
    return m!.slice(1);
  };
  it("grants the Free plan credits to new users", () => {
    expect(Number(last("free_plan_credits", /select (\d+) \$\$/)[0])).toBe(FREE_PLAN_CREDITS);
  });
  it("charges the same render prices and caps the failure fee at a Preview", () => {
    expect(last("render_cost", /when 'preview' then (\d+) when 'final' then (\d+) end/).map(Number)).toEqual([
      CREDIT_COSTS.preview_render, CREDIT_COSTS.final_render,
    ]);
    expect(last("render_failure_fee", /select public\.render_cost\('(\w+)'\)/)[0]).toBe("preview");
  });
  it("rolls plan credits over for the same number of months", () => {
    expect(Number(last("plan_credit_rollover", /interval '1 month' \* (\d+)/)[0])).toBe(PLAN_CREDIT_ROLLOVER_PERIODS);
  });
  it("pays the same referral bonus under the same monthly cap", () => {
    expect(Number(last("referral_bonus_credits", /select (\d+) \$\$/)[0])).toBe(REFERRAL_BONUS_CREDITS);
    expect(Number(last("referral_monthly_cap", /select (\d+) \$\$/)[0])).toBe(REFERRAL_MONTHLY_CAP);
  });
  it("prices scene-version actions the same (save_scene_version never takes a price from the browser)", () => {
    const m = last("scene_action_cost", /when 'generate' then (\d+) when 'edit' then (\d+) when 'adjust' then (\d+) end/);
    expect(m.map(Number)).toEqual([VERSION_ACTION_COST.generate, VERSION_ACTION_COST.edit, VERSION_ACTION_COST.adjust]);
    expect(VERSION_ACTION_COST).toEqual({ generate: CREDIT_COSTS.scene_generation, edit: CREDIT_COSTS.prompt_edit, adjust: CREDIT_COSTS.slider_change });
    expect(Number(last("scene_version_hourly_cap", /select (\d+) \$\$/)[0])).toBe(VERSION_HOURLY_CAP);
  });
  it("caps uploads at the same size", () => {
    expect(Number(last("max_upload_bytes", /select (\d+)::bigint/)[0])).toBe(MAX_UPLOAD_BYTES);
  });
});
