import { describe, it, expect } from "vitest";
import type { ScenePlan } from "@/lib/schema";
import { CREDIT_COSTS, PLANS, CREDIT_PACKS, STARTING_BALANCE, cloudPrice } from "./pricing";

const output = (o: Partial<ScenePlan["output"]>): ScenePlan["output"] => ({ fps: 30, durationS: 10, resolution: "1080p", quality: "standard", ...o });

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

describe("cloudPrice", () => {
  it("prices each quality below 4k", () => {
    expect(cloudPrice(output({ quality: "draft" }))).toBe(30);
    expect(cloudPrice(output({ quality: "standard" }))).toBe(30);
    expect(cloudPrice(output({ quality: "high" }))).toBe(60);
    expect(cloudPrice(output({ quality: "ultra" }))).toBe(90);
  });

  it("charges the 4k rate regardless of quality", () => {
    for (const quality of ["draft", "standard", "high", "ultra"] as const) {
      expect(cloudPrice(output({ resolution: "4k", quality }))).toBe(160);
    }
  });

  it("does not treat 1440p as 4k", () => {
    expect(cloudPrice(output({ resolution: "1440p", quality: "ultra" }))).toBe(90);
  });
});
