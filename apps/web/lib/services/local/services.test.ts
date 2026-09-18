import { describe, it, expect, beforeEach } from "vitest";
import { LocalCreditService } from "./credits";
import { LocalDirectorService } from "./director";
import { LocalRenderService } from "./render";
import { analyzeStats } from "@/lib/scene/analyze";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { STARTING_BALANCE } from "@/lib/pricing";

describe("LocalCreditService", () => {
  beforeEach(() => localStorage.clear());
  it("seeds the starting balance once", async () => {
    const c = new LocalCreditService();
    const first = await c.balance();
    expect(first.ok && first.value).toBe(STARTING_BALANCE);
    const again = await new LocalCreditService().balance();
    expect(again.ok && again.value).toBe(STARTING_BALANCE);
  });
  it("posts a charge and reduces the balance", async () => {
    const c = new LocalCreditService();
    const r = await c.post({ amount: -10, reason: "scene_generation", projectId: "p1" });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value).toMatchObject({ amount: -10, reason: "scene_generation", projectId: "p1" });
    expect(r.value.id).toBeTruthy();
    expect(r.value.createdAt).toBeGreaterThan(0);
    const bal = await c.balance();
    expect(bal.ok && bal.value).toBe(STARTING_BALANCE - 10);
    const ledger = await c.ledger();
    expect(ledger.ok && ledger.value.length).toBe(2);
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
  it("passes edit hints through when the prompt is not understood", async () => {
    const r = await new LocalDirectorService().edit("xyzzy plugh", defaultPlan("car"));
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.error.code).toBe("edit_not_understood");
    expect(r.error.hints?.length).toBeGreaterThan(0);
  });
});

describe("LocalRenderService", () => {
  it("is not connected", async () => {
    const r = await new LocalRenderService().requestPreview("p", "v");
    expect(!r.ok && r.error.code).toBe("not_connected");
  });
});
