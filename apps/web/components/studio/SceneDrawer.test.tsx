// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { ModelAnalysis, SceneVersion } from "@/lib/schema";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { useStudioStore } from "@/lib/stores/studio";
import { SceneDrawer } from "./SceneDrawer";
import { SceneDetailsButton } from "./StudioOverlay";
import { useLabourStore } from "./useLabour";
import { useStudioUi } from "./useStudioUi";

const analysis: ModelAnalysis = {
  category: "car", confidence: 0.9, unitGuess: "m", scaleFactor: 1, dimensionsMeters: [4.5, 1.8, 1.4],
  parts: {}, capabilities: ["drive"], rigged: false,
};
const version: SceneVersion = { id: "v1", projectId: "p", index: 0, prompt: "Rainy night", parentId: null, plan: defaultPlan("car"), createdAt: Date.now() };

describe("SceneDrawer", () => {
  beforeEach(() => {
    useStudioStore.getState().reset();
    useLabourStore.getState().end();
    useStudioUi.getState().reset();
    useStudioStore.setState({ analysis });
  });
  afterEach(cleanup);

  it("is closed by default and opens from the one icon button", () => {
    render(<><SceneDetailsButton /><SceneDrawer wide /></>);
    expect(screen.queryByTestId("scene-drawer")).toBeNull();
    const button = screen.getByRole("button", { name: "Scene details" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(button);
    expect(screen.getByTestId("scene-drawer")).toBeTruthy();
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByTestId("analysis-category").textContent).toBe("car");
  });

  it("shows only Analysis and a hint until a scene exists", () => {
    useStudioUi.getState().openDrawer();
    const { rerender } = render(<SceneDrawer wide />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Analysis"]);
    expect(screen.getByText("Generate a scene to unlock controls and rendering.")).toBeTruthy();

    useStudioStore.setState({ versions: [version], selectedVersionId: "v1", currentPlan: version.plan });
    rerender(<SceneDrawer wide />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Analysis", "Controls", "Render"]);
    expect(screen.queryByText("Generate a scene to unlock controls and rendering.")).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Render" }));
    expect(screen.getByRole("tabpanel").getAttribute("aria-labelledby")).toMatch(/-tab-render$/);
  });

  it("keeps Controls locked while the first version is still behind the labour sequence", () => {
    useLabourStore.getState().beginPlanning();
    useStudioStore.setState({ versions: [version], selectedVersionId: "v1", currentPlan: version.plan });
    useStudioUi.getState().openDrawer();
    render(<SceneDrawer wide />);
    expect(screen.getAllByRole("tab")).toHaveLength(1);
  });

  it("opens on the tab the composer asked for and closes on Escape, handing focus back to the icon button", () => {
    useStudioStore.setState({ versions: [version], selectedVersionId: "v1", currentPlan: version.plan });
    useStudioUi.getState().openDrawer("controls");
    render(<><SceneDetailsButton /><SceneDrawer wide /></>);
    expect(screen.getByRole("tab", { name: "Controls" }).getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(useStudioUi.getState().drawerOpen).toBe(false);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Scene details" }));
    expect(useStudioUi.getState().focusRequest).toBeNull();
  });

  it("closes on a pointerdown in the viewer, not in the composer or sidebar", () => {
    useStudioUi.getState().openDrawer();
    render(
      <>
        <section data-viewer-area><span data-testid="viewer" /></section>
        <div data-composer><span data-testid="composer" /></div>
        <SceneDrawer wide />
      </>,
    );
    fireEvent.pointerDown(screen.getByTestId("composer"));
    expect(useStudioUi.getState().drawerOpen).toBe(true);
    fireEvent.pointerDown(screen.getByTestId("scene-drawer"));
    expect(useStudioUi.getState().drawerOpen).toBe(true);
    fireEvent.pointerDown(screen.getByTestId("viewer"));
    expect(useStudioUi.getState().drawerOpen).toBe(false);
  });
});
