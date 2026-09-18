import { describe, it, expect, beforeEach } from "vitest";
import { LocalCreditService } from "./credits";
import { LocalDirectorService } from "./director";
import { LocalRenderService } from "./render";
import { analyzeStats } from "@/lib/scene/analyze";

describe("LocalCreditService", () => {
  beforeEach(() => localStorage.clear());
  it("seeds the starting balance once", async () => {
    const c = new LocalCreditService();
    const first = await c.balance();
    expect(first.ok && first.value).toBe(100);
    const again = await new LocalCreditService().balance();
    expect(again.ok && again.value).toBe(100);
  });
  it("refuses overspend", async () => {
    const c = new LocalCreditService();
    const r = await c.post({ amount: -500, reason: "scene_generation", projectId: null });
    expect(!r.ok && r.error.code).toBe("insufficient_credits");
  });
});

describe("LocalDirectorService", () => {
  const car = analyzeStats({
    triangleCount: 1,
    meshCount: 1,
    materialCount: 1,
    objectNames: ["Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR"],
    materialNames: [],
    extents: [4.5, 1.9, 1.4],
    hasSkeleton: false,
    animationClipCount: 0,
  });
  const chair = analyzeStats({
    triangleCount: 1,
    meshCount: 1,
    materialCount: 1,
    objectNames: ["Chair"],
    materialNames: [],
    extents: [0.5, 0.5, 0.9],
    hasSkeleton: false,
    animationClipCount: 0,
  });
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
