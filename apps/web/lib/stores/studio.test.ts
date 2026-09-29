import { STARTING_BALANCE } from "@/lib/pricing";
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
    await useStudioStore.getState().modelLoaded({ fileName: "toycar.glb", format: "glb", sizeBytes: 1, source: "sample", sampleUrl: "/samples/toycar.glb", blob: null }, carStats);
  }

  it("runs the full flow: open, model loaded, analyze, plan, edit, select", async () => {
    const p = await services.projects.createProject("Car");
    if (!p.ok) throw new Error();
    const s = useStudioStore.getState();
    await s.open(p.value.id);
    await s.modelLoaded({ fileName: "toycar.glb", format: "glb", sizeBytes: 1, source: "sample", sampleUrl: "/samples/toycar.glb", blob: null }, carStats);
    expect(useStudioStore.getState().analysis?.category).toBe("car");

    const r1 = await useStudioStore.getState().submitPrompt("rainy night, handheld walking toward the car");
    expect(r1.ok).toBe(true);
    expect(useStudioStore.getState().versions.length).toBe(1);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(STARTING_BALANCE - 2);

    const r2 = await useStudioStore.getState().submitPrompt("darker and add fog");
    expect(r2.ok).toBe(true);
    const st = useStudioStore.getState();
    expect(st.versions.length).toBe(2);
    expect(st.versions[1].parentId).toBe(st.versions[0].id);
    expect(st.currentPlan?.lighting.exposure).toBeCloseTo(-0.7);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(STARTING_BALANCE - 3);

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
    expect(useCreditsStore.getState().balance).toBe(STARTING_BALANCE);
    await useStudioStore.getState().acceptPending();
    expect(useStudioStore.getState().versions.length).toBe(1);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(STARTING_BALANCE - 2);
  });

  it("slider changes are free and append a manual version", async () => {
    const p = await services.projects.createProject("Car");
    if (!p.ok) throw new Error();
    await useStudioStore.getState().open(p.value.id);
    await useStudioStore.getState().modelLoaded({ fileName: "toycar.glb", format: "glb", sizeBytes: 1, source: "sample", sampleUrl: "/samples/toycar.glb", blob: null }, carStats);
    await useStudioStore.getState().submitPrompt("studio");
    await useStudioStore.getState().commitSlider("fog", 0.05);
    const st = useStudioStore.getState();
    expect(st.versions[1].prompt).toBe("manual: fog");
    expect(st.currentPlan?.scene.fogDensity).toBe(0.05);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(STARTING_BALANCE - 2);
  });

  it("does not charge credits when appending the version fails", async () => {
    await openCar();
    vi.spyOn(services.projects, "appendVersion").mockResolvedValueOnce({ ok: false, error: { code: "quota_exceeded", message: "full" } });
    const r = await useStudioStore.getState().submitPrompt("rainy night");
    expect(r.ok).toBe(false);
    expect(useStudioStore.getState().error?.code).toBe("quota_exceeded");
    expect(useStudioStore.getState().versions.length).toBe(0);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(STARTING_BALANCE);
  });

  it("refuses with insufficient_credits before appending when the balance is too low", async () => {
    await openCar();
    const tx = await services.credits.post({ amount: -(STARTING_BALANCE - 1), reason: "pack_purchase", projectId: null });
    expect(tx.ok).toBe(true);
    const r = await useStudioStore.getState().submitPrompt("rainy night");
    expect(!r.ok && r.error.code).toBe("insufficient_credits");
    expect(!r.ok && r.error.message).toBe("You need 2 credits but have 1.");
    expect(useStudioStore.getState().error?.code).toBe("insufficient_credits");
    expect(useStudioStore.getState().versions.length).toBe(0);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(1);
  });

  it("rejects a second submit while the first is still running (one version, one charge)", async () => {
    await openCar();
    const s = useStudioStore.getState();
    const first = s.submitPrompt("rainy night");
    expect(useStudioStore.getState().busy).not.toBeNull();
    const second = await s.submitPrompt("rainy night");
    expect(!second.ok && second.error.code).toBe("busy");
    expect(!second.ok && second.error.message).toBe("Hold on, still working on the last change.");
    const r1 = await first;
    expect(r1.ok).toBe(true);
    expect(useStudioStore.getState().busy).toBeNull();
    expect(useStudioStore.getState().versions.length).toBe(1);
    await useCreditsStore.getState().refresh();
    expect(useCreditsStore.getState().balance).toBe(STARTING_BALANCE - 2);
  });

  it("keeps busy set through the append and charge, and guards manual commits too", async () => {
    await openCar();
    const s = useStudioStore.getState();
    let busyDuringAppend: unknown = "unset";
    const orig = services.projects.appendVersion.bind(services.projects);
    vi.spyOn(services.projects, "appendVersion").mockImplementation(async (v, a) => { busyDuringAppend = useStudioStore.getState().busy; return orig(v, a); });
    await s.submitPrompt("studio");
    expect(busyDuringAppend).not.toBeNull();
    expect(useStudioStore.getState().busy).toBeNull();

    const a = s.commitSlider("fog", 0.05);
    const b = await s.commitOutput({ tier: "final" });
    expect(!b.ok && b.error.code).toBe("busy");
    await a;
    expect(useStudioStore.getState().versions.length).toBe(2);
  });

  it("modelLoaded surfaces an updateProject failure", async () => {
    const p = await services.projects.createProject("Car");
    if (!p.ok) throw new Error();
    await useStudioStore.getState().open(p.value.id);
    vi.spyOn(services.projects, "updateProject").mockResolvedValueOnce({ ok: false, error: { code: "quota_exceeded", message: "full" } });
    const r = await useStudioStore.getState().modelLoaded({ fileName: "toycar.glb", format: "glb", sizeBytes: 1, source: "sample", sampleUrl: "/samples/toycar.glb", blob: null }, carStats);
    expect(!r.ok && r.error.code).toBe("quota_exceeded");
    expect(useStudioStore.getState().error?.code).toBe("quota_exceeded");
    expect(useStudioStore.getState().busy).toBeNull();
  });

  it("rename trims and persists; an empty name leaves the project unchanged", async () => {
    await openCar("Car");
    await useStudioStore.getState().rename("  Night drive  ");
    expect(useStudioStore.getState().project?.name).toBe("Night drive");
    const stored = await services.projects.getProject(useStudioStore.getState().project!.id);
    expect(stored.ok && stored.value.name).toBe("Night drive");

    await useStudioStore.getState().rename("   ");
    expect(useStudioStore.getState().project?.name).toBe("Night drive");
  });

  it("has no livePlan field; previewSlider updates currentPlan only", async () => {
    await openCar();
    await useStudioStore.getState().submitPrompt("studio");
    useStudioStore.getState().previewSlider("fog", 0.05);
    const st = useStudioStore.getState() as Record<string, unknown>;
    expect("livePlan" in st).toBe(false);
    expect((st.currentPlan as { scene: { fogDensity: number } }).scene.fogDensity).toBe(0.05);
    expect(useStudioStore.getState().versions.length).toBe(1);
  });
});
