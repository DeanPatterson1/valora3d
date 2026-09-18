import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { clear } from "idb-keyval";
import { useStudioStore } from "./studio";
import { useCreditsStore } from "./credits";
import { services } from "@/lib/services";

const carStats = { triangleCount: 10, meshCount: 5, materialCount: 1, objectNames: ["Body","Wheel_FL","Wheel_FR","Wheel_RL","Wheel_RR"],
  materialNames: [], extents: [4.5, 1.9, 1.4] as [number, number, number], hasSkeleton: false, animationClipCount: 0 };

describe("useStudioStore", () => {
  beforeEach(async () => { localStorage.clear(); await clear(); useStudioStore.getState().reset(); });
  afterEach(() => { vi.restoreAllMocks(); });

  async function openCar(name = "Car") {
    const p = await services.projects.createProject(name);
    if (!p.ok) throw new Error();
    await useStudioStore.getState().open(p.value.id);
    await useStudioStore.getState().modelLoaded({ fileName: "car.glb", format: "glb", sizeBytes: 1, source: "sample", sampleUrl: "/samples/car.glb", blob: null }, carStats);
  }

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

  it("does not charge credits when appending the version fails", async () => {
    await openCar();
    vi.spyOn(services.projects, "appendVersion").mockResolvedValueOnce({ ok: false, error: { code: "quota_exceeded", message: "full" } });
    const r = await useStudioStore.getState().submitPrompt("rainy night");
    expect(r.ok).toBe(false);
    expect(useStudioStore.getState().error?.code).toBe("quota_exceeded");
    expect(useStudioStore.getState().versions.length).toBe(0);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(100);
  });

  it("refuses with insufficient_credits before appending when the balance is too low", async () => {
    await openCar();
    const tx = await services.credits.post({ amount: -99, reason: "pack_purchase", projectId: null });
    expect(tx.ok).toBe(true);
    const r = await useStudioStore.getState().submitPrompt("rainy night");
    expect(!r.ok && r.error.code).toBe("insufficient_credits");
    expect(!r.ok && r.error.message).toBe("You need 2 credits but have 1.");
    expect(useStudioStore.getState().error?.code).toBe("insufficient_credits");
    expect(useStudioStore.getState().versions.length).toBe(0);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(1);
  });
});
