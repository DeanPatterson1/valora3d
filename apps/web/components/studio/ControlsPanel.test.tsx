// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import type { SceneVersion } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";
import { ControlsPanel } from "./ControlsPanel";

const plan = { ...defaultPlan("car"), camera: { ...defaultPlan("car").camera, motionStrength: 0.2 } };
const v0: SceneVersion = { id: "v0", projectId: "p1", index: 0, prompt: "Studio", parentId: null, plan, createdAt: Date.now() };

function withPlan(extra: Partial<ReturnType<typeof useStudioStore.getState>> = {}) {
  useStudioStore.setState({ versions: [v0], selectedVersionId: "v0", currentPlan: plan, ...extra });
}

describe("ControlsPanel", () => {
  beforeEach(() => useStudioStore.getState().reset());
  afterEach(cleanup);

  it("renders five disabled sliders with a hint when there is no plan", () => {
    render(<ControlsPanel />);
    const sliders = screen.getAllByRole("slider");
    expect(sliders).toHaveLength(5);
    for (const s of sliders) expect((s as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText("Generate a scene first")).toBeTruthy();
    expect(screen.getByText(/Sliders are free/)).toBeTruthy();
  });

  it("reflects the current plan and enables the sliders", () => {
    withPlan();
    render(<ControlsPanel />);
    const handheld = screen.getByRole("slider", { name: "Handheld" }) as HTMLInputElement;
    expect(handheld.disabled).toBe(false);
    expect(Number(handheld.value)).toBeCloseTo(0.2);
    expect(screen.queryByText("Generate a scene first")).toBeNull();
    const light = screen.getByRole("slider", { name: "Light" }) as HTMLInputElement;
    expect(light.min).toBe("-3");
    expect(light.max).toBe("3");
    expect(light.getAttribute("aria-valuetext")).toBe(`${plan.lighting.exposure > 0 ? "+" : ""}${plan.lighting.exposure.toFixed(1)} EV`);
  });

  it("previews on change and commits on release", () => {
    const commitSlider = vi.fn(async () => ({ ok: true as const, value: null }));
    withPlan({ commitSlider });
    render(<ControlsPanel />);

    const fog = screen.getByRole("slider", { name: "Fog" }) as HTMLInputElement;
    fireEvent.change(fog, { target: { value: "0.05" } });
    // Live preview updates the current plan without a version.
    expect(useStudioStore.getState().currentPlan?.scene.fogDensity).toBeCloseTo(0.05);
    expect(commitSlider).not.toHaveBeenCalled();

    fireEvent.pointerUp(fog);
    expect(commitSlider).toHaveBeenCalledTimes(1);
    expect(commitSlider).toHaveBeenCalledWith("fog", 0.05);
  });

  it("does not commit when the value has not changed (blur, key-up)", () => {
    const commitSlider = vi.fn(async () => ({ ok: true as const, value: null }));
    withPlan({ commitSlider });
    render(<ControlsPanel />);
    const handheld = screen.getByRole("slider", { name: "Handheld" });
    fireEvent.blur(handheld);
    fireEvent.keyUp(handheld, { key: "Tab" });
    expect(commitSlider).not.toHaveBeenCalled();
  });

  it("moves the sliders when an older version becomes current", () => {
    withPlan();
    const { rerender } = render(<ControlsPanel />);
    const older = { ...plan, lighting: { ...plan.lighting, exposure: -1.5 } };
    useStudioStore.setState({ currentPlan: older });
    rerender(<ControlsPanel />);
    const light = screen.getByRole("slider", { name: "Light" }) as HTMLInputElement;
    expect(Number(light.value)).toBeCloseTo(-1.5);
  });
});
