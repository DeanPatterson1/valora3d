import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { VERSION_ACTION_COST, VERSION_HOURLY_CAP } from "@/lib/scene/versionAction";
import { INPUT_FAILURE_FEE } from "@/lib/render/failurePolicy";
import {
  CHECKOUT_ITEMS, CREDIT_COSTS, CREDIT_PACKS, FIRST_CLIP_PACK_ID, FREE_PLAN_CREDITS, MAX_UPLOAD_BYTES, PLANS, PLAN_CREDIT_ROLLOVER_PERIODS, PLAN_LIMITS,
  REFERRAL_BONUS_CREDITS, REFERRAL_MONTHLY_CAP, RENDER_FAILURE_FEE, STARTING_BALANCE, creditValue, limitFeatures, priceEnvName,
} from "./pricing";


describe("pricing v3 (placeholder prices; 100 credits = one 1080p final clip)", () => {
  it("matches the approved numbers", () => {
    expect(CREDIT_COSTS.scene_generation).toBe(5);
    expect(CREDIT_COSTS.prompt_edit).toBe(2);
    expect(CREDIT_COSTS.preview_render).toBe(5);
    expect(CREDIT_COSTS.local_final).toBe(3);
    expect(CREDIT_COSTS.final_render).toBe(100);
    expect(CREDIT_COSTS.model_analysis).toBe(0);
    expect(CREDIT_COSTS.slider_change).toBe(0);
    expect(RENDER_FAILURE_FEE).toBe(CREDIT_COSTS.preview_render);
    expect(INPUT_FAILURE_FEE).toBe(RENDER_FAILURE_FEE);
    expect(STARTING_BALANCE).toBe(FREE_PLAN_CREDITS);
    expect(FREE_PLAN_CREDITS).toBe(10);
    // Exactly one AI scene plan and one watermarked preview, nothing more.
    expect(FREE_PLAN_CREDITS).toBe(CREDIT_COSTS.scene_generation + CREDIT_COSTS.preview_render);
    expect(PLANS.map((p) => [p.name, p.priceUsd, p.credits])).toEqual([["Free", 0, 10], ["Creator", 24, 800], ["Pro", 49, 2500]]);
    expect(PLANS[1].highlighted).toBe(true);
    expect(CREDIT_PACKS).toEqual([
      { id: "first", clips: 1, credits: 100, priceUsd: 2, oncePerAccount: true },
      { id: "1", clips: 1, credits: 100, priceUsd: 6, oncePerAccount: false },
      { id: "5", clips: 5, credits: 500, priceUsd: 20, oncePerAccount: false },
      { id: "15", clips: 15, credits: 1500, priceUsd: 55, oncePerAccount: false },
    ]);
    // One clip is 100 credits everywhere: a pack of N clips is N * final_render.
    for (const pack of CREDIT_PACKS) expect(pack.credits).toBe(pack.clips * CREDIT_COSTS.final_render);
    expect(CREDIT_PACKS.filter((p) => p.oncePerAccount).map((p) => p.id)).toEqual([FIRST_CLIP_PACK_ID]);
    expect(PLANS.filter((p) => p.period === "month").map((p) => p.credits / CREDIT_COSTS.final_render)).toEqual([8, 25]);
    expect(PLAN_LIMITS.pro.maxActiveJobs).toBe(3);
    expect(PLAN_CREDIT_ROLLOVER_PERIODS).toBe(1);
    expect(REFERRAL_BONUS_CREDITS).toBe(100);
    expect(REFERRAL_MONTHLY_CAP).toBe(20);
  });
  it("keeps the price per credit falling as the pack grows, the intro clip aside", () => {
    const per = CREDIT_PACKS.filter((p) => !p.oncePerAccount).map((p) => p.priceUsd / p.credits);
    expect([...per].sort((a, b) => b - a)).toEqual(per);
    // The intro clip is the cheapest clip on sale, and a subscriber's clip is cheaper than a one-off pack clip.
    expect(CREDIT_PACKS[0].priceUsd).toBeLessThan(CREDIT_PACKS[1].priceUsd);
    expect(PLANS[1].priceUsd / (PLANS[1].credits / 100)).toBeLessThan(CREDIT_PACKS[1].priceUsd);
  });
  it("derives checkout keys and Paddle env names from the packs", () => {
    expect(CHECKOUT_ITEMS).toEqual(["plan:creator", "plan:pro", "pack:first", "pack:1", "pack:5", "pack:15"]);
    expect(CHECKOUT_ITEMS.map(priceEnvName)).toEqual([
      "PADDLE_PRICE_CREATOR_MONTHLY", "PADDLE_PRICE_PRO_MONTHLY", "PADDLE_PRICE_PACK_FIRST", "PADDLE_PRICE_PACK_1", "PADDLE_PRICE_PACK_5", "PADDLE_PRICE_PACK_15",
    ]);
  });
  it("states what credits buy honestly per plan (Free is never promised a Final)", () => {
    expect(creditValue(FREE_PLAN_CREDITS, "free")).toBe("2 Previews");
    expect(creditValue(800, "creator")).toBe("160 Previews or 8 Finals");
    expect(creditValue(2500, "pro")).toBe("500 Previews or 25 Finals");
    expect(creditValue(10_000, "free")).not.toMatch(/final/i);
    expect(PLANS.map((p) => p.value)).toEqual(["2 Previews", "160 Previews or 8 Finals", "500 Previews or 25 Finals"]);
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
    expect(PLANS[0].features).toEqual(["10 credits, once", "540p preview renders", "Watermark on renders", "1 render at a time", "7-day retention"]);
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
  it("enforces the once-per-account first clip in the database too (unique pack_id index, grant that never drops a paid order)", () => {
    expect(all).toMatch(/create unique index billing_transactions_first_clip_once on public\.billing_transactions \(user_id\) where pack_id = '/);
    expect(all).toContain(`where pack_id = '${FIRST_CLIP_PACK_ID}'`);
    expect(last("billing_grant_pack", /v_pack = '(\w+)'/)[0]).toBe(FIRST_CLIP_PACK_ID);
    // The grant function stores the transaction (and its credits) even when the pack repeats: no charge without credits.
    expect(last("billing_grant_pack", /(first_clip_repeat)/)[0]).toBe("first_clip_repeat");
  });
  it("caps uploads at the same size", () => {
    expect(Number(last("max_upload_bytes", /select (\d+)::bigint/)[0])).toBe(MAX_UPLOAD_BYTES);
  });
});
