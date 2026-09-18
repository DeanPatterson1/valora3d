// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ModelAnalysis, Project, SceneVersion } from "@/lib/schema";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { useStudioStore } from "@/lib/stores/studio";
import { ProjectStatus, statusLine } from "./StudioOverlay";
import { useLabourStore } from "./useLabour";

const analysis: ModelAnalysis = {
  category: "car", confidence: 0.9, unitGuess: "m", scaleFactor: 1, dimensionsMeters: [1.4, 4.72, 1.8],
  parts: {}, capabilities: ["drive"], rigged: false,
};
const v = (index: number, prompt: string): SceneVersion => ({ id: `v${index}`, projectId: "p", index, prompt, parentId: null, plan: defaultPlan("car"), createdAt: 0 });
const project: Project = { id: "p", name: "Night drive", createdAt: 0, updatedAt: 0, assetId: null, analysis: null, selectedVersionId: null };

describe("statusLine", () => {
  it("advances from no model, to what it looks like, to the selected scene", () => {
    expect(statusLine({ hasModel: false, analysis: null, versions: [], selectedVersionId: null })).toBe("No model yet");
    expect(statusLine({ hasModel: true, analysis: null, versions: [], selectedVersionId: null })).toBe("Reading the model");
    expect(statusLine({ hasModel: true, analysis, versions: [], selectedVersionId: null })).toBe("Looks like a car · 4.7 m long");
    const versions = [v(0, "Rainy night"), v(1, "manual: fog"), v(2, "Make it brighter")];
    expect(statusLine({ hasModel: true, analysis, versions, selectedVersionId: "v1" })).toBe("Scene v2 · Fog adjusted");
    // An unknown selection falls back to the newest version.
    expect(statusLine({ hasModel: true, analysis, versions, selectedVersionId: "zzz" })).toBe("Scene v3 · Make it brighter");
  });
});

describe("ProjectStatus", () => {
  beforeEach(() => {
    useStudioStore.getState().reset();
    useLabourStore.getState().end();
  });
  afterEach(cleanup);

  it("renames inline through the store action", () => {
    const rename = vi.fn(async () => {});
    useStudioStore.setState({ project, rename });
    render(<ProjectStatus />);
    fireEvent.click(screen.getByRole("button", { name: "Project name: Night drive. Rename" }));
    const input = screen.getByRole("textbox", { name: "Project name" });
    fireEvent.change(input, { target: { value: "Rainy night" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(rename).toHaveBeenCalledWith("Rainy night");
  });

  it("holds the previous status while the labour sequence runs", () => {
    useStudioStore.setState({ project, analysis, asset: { id: "a", projectId: "p", fileName: "car.glb", format: "glb", sizeBytes: 1, source: "sample", blobKey: null, sampleUrl: "/samples/car.glb", thumbnailKey: null } });
    useLabourStore.getState().beginPlanning();
    useStudioStore.setState({ versions: [v(0, "Rainy night")], selectedVersionId: "v0" });
    const { rerender } = render(<ProjectStatus />);
    expect(screen.getByTestId("studio-status").textContent).toBe("Looks like a car · 4.7 m long");
    useLabourStore.getState().end();
    rerender(<ProjectStatus />);
    expect(screen.getByTestId("studio-status").textContent).toBe("Scene v1 · Rainy night");
  });
});
