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
