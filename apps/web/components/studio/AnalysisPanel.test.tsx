// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { ModelAnalysis, SceneStats } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";
import { AnalysisPanel, humanise } from "./AnalysisPanel";

const car: ModelAnalysis = {
  category: "car",
  confidence: 0.97,
  unitGuess: "mm",
  scaleFactor: 0.001,
  dimensionsMeters: [1.42, 4.5, 1.85],
  parts: { front_left_wheel: "Wheel_FL", body: "Body_Shell" },
  capabilities: ["drive", "wheel_rotation"],
  rigged: false,
};

const stats: SceneStats = {
  triangleCount: 124800,
  meshCount: 12,
  materialCount: 4,
  objectNames: ["Wheel_FL", "Body_Shell"],
  materialNames: ["Paint"],
  extents: [4500, 1850, 1420],
  hasSkeleton: false,
  animationClipCount: 0,
};

describe("AnalysisPanel", () => {
  beforeEach(() => useStudioStore.getState().reset());
  afterEach(cleanup);

  it("shows the empty state without an analysis", () => {
    render(<AnalysisPanel />);
    expect(screen.getByText("Load a model to see what it is.")).toBeTruthy();
    expect(screen.queryByTestId("analysis-category")).toBeNull();
  });

  it("shows skeleton rows while analysing", () => {
    useStudioStore.setState({ busy: "analyzing" });
    render(<AnalysisPanel />);
    expect(screen.getByRole("status", { name: "Analysing model" })).toBeTruthy();
    expect(screen.queryByText("Load a model to see what it is.")).toBeNull();
  });

  it("renders category, confidence, dimensions, counts, parts and rig for a car", () => {
    useStudioStore.setState({ analysis: car, stats });
    render(<AnalysisPanel />);

    expect(screen.getByTestId("analysis-category").textContent).toBe("car");
    expect(screen.getByText("97% sure")).toBeTruthy();

    // Dimensions sorted descending, in metres, with the unit guess phrased humanly.
    const size = screen.getByText("Size").nextElementSibling!.textContent!;
    expect(size).toContain("4.50");
    expect(size.indexOf("4.50")).toBeLessThan(size.indexOf("1.85"));
    expect(size.indexOf("1.85")).toBeLessThan(size.indexOf("1.42"));
    expect(size).toContain("read as millimetres");

    const geometry = screen.getByText("Geometry").nextElementSibling!.textContent!;
    expect(geometry).toContain("124,800");
    expect(geometry).toContain("12");
    expect(geometry).toContain("meshes");

    expect(screen.getByText("Front left wheel")).toBeTruthy();
    expect(screen.getByText("Wheel_FL")).toBeTruthy();
    expect(screen.getByText("Wheel rotation")).toBeTruthy();
    expect(screen.getByText("No skeleton — static only")).toBeTruthy();
  });

  it("phrases unknown units honestly", () => {
    useStudioStore.setState({ analysis: { ...car, unitGuess: "unknown", category: "product", rigged: true } });
    render(<AnalysisPanel />);
    expect(screen.getByText(/units unknown — assumed metres/)).toBeTruthy();
    expect(screen.getByTestId("analysis-category").textContent).toBe("product");
    expect(screen.getByText("Rigged")).toBeTruthy();
  });

  it("humanises snake_case ids", () => {
    expect(humanise("front_left_wheel")).toBe("Front left wheel");
    expect(humanise("wheel_rotation")).toBe("Wheel rotation");
    expect(humanise("body")).toBe("Body");
  });
});
