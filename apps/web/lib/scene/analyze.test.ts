import { describe, it, expect } from "vitest";
import { inferUnits } from "./inferUnits";
import { classify, hasCarNameSignal } from "./classify";
import { analyzeStats, detectParts } from "./analyze";
import type { SceneStats } from "@/lib/schema";

const stats = (over: Partial<SceneStats>): SceneStats => ({
  triangleCount: 1000,
  meshCount: 5,
  materialCount: 2,
  objectNames: [],
  materialNames: [],
  extents: [1, 1, 1],
  hasSkeleton: false,
  animationClipCount: 0,
  ...over,
});

describe("inferUnits", () => {
  it("keeps metres when in range", () => {
    expect(inferUnits([4.7, 1.9, 1.4], true)).toEqual({ unitGuess: "m", scaleFactor: 1 });
  });
  it("detects millimetres for a car", () => {
    expect(inferUnits([4700, 1900, 1400], true)).toEqual({ unitGuess: "mm", scaleFactor: 0.001 });
  });
  it("detects centimetres for a named car", () => {
    expect(inferUnits([450, 190, 140], true)).toEqual({ unitGuess: "cm", scaleFactor: 0.01 });
  });
  it("known limitation: unnamed cm car resolves to mm product scale", () => {
    expect(inferUnits([450, 190, 140], false)).toEqual({ unitGuess: "mm", scaleFactor: 0.001 });
  });
  it("is axis agnostic", () => {
    expect(inferUnits([1400, 4700, 1900], true).unitGuess).toBe("mm");
  });
  it("returns unknown when nothing fits", () => {
    expect(inferUnits([1e9, 1, 1], false)).toEqual({ unitGuess: "unknown", scaleFactor: 1 });
  });
});

describe("classify", () => {
  it("detects car by names", () => {
    expect(hasCarNameSignal(["Body", "Wheel_FL"], [])).toBe(true);
    expect(classify([1, 1, 1], true)).toEqual({ category: "car", confidence: 0.8 });
  });
  it("detects car by proportions", () => {
    expect(classify([4.5, 1.9, 1.4], false)).toEqual({ category: "car", confidence: 0.7 });
  });
  it("caps confidence", () => {
    expect(classify([4.5, 1.9, 1.4], true).confidence).toBe(0.97);
  });
  it("defaults to product", () => {
    expect(classify([0.3, 0.2, 0.1], false)).toEqual({ category: "product", confidence: 0.6 });
  });
});

describe("detectParts", () => {
  it("finds wheel codes when the code precedes the word or is dot-separated", () => {
    expect(detectParts(["FL_Wheel", "FR_Wheel", "RL_Wheel", "RR_Wheel"])).toEqual({
      front_left_wheel: "FL_Wheel",
      front_right_wheel: "FR_Wheel",
      rear_left_wheel: "RL_Wheel",
      rear_right_wheel: "RR_Wheel",
    });
    expect(detectParts(["wheel.FL"]).front_left_wheel).toBe("wheel.FL");
  });
  it("does not read a code out of the middle of a word", () => {
    expect(detectParts(["wheel_flap"])).toEqual({});
  });
  it("still finds spelled-out positions", () => {
    expect(detectParts(["Front_Left_Wheel"]).front_left_wheel).toBe("Front_Left_Wheel");
  });
  it("matches body with a suffix separator but not inside a longer word", () => {
    expect(detectParts(["Body"]).body).toBe("Body");
    expect(detectParts(["Body.001"]).body).toBe("Body.001");
    expect(detectParts(["Body_Main"]).body).toBe("Body_Main");
    expect(detectParts(["body-shell"]).body).toBe("body-shell");
    expect(detectParts(["Bodywork"]).body).toBeUndefined();
    expect(detectParts(["Carbody", "car_body"]).body).toBe("Carbody");
  });
});

describe("analyzeStats", () => {
  it("assembles a full analysis for a car", () => {
    const a = analyzeStats(
      stats({
        extents: [4700, 1900, 1400],
        objectNames: ["Body", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR", "Headlight_L"],
      }),
    );
    expect(a.category).toBe("car");
    expect(a.unitGuess).toBe("mm");
    expect(a.dimensionsMeters).toEqual([4.7, 1.9, 1.4]);
    expect(a.parts.front_left_wheel).toBe("Wheel_FL");
    expect(a.parts.body).toBe("Body");
    expect(a.capabilities).toContain("drive");
    expect(a.rigged).toBe(false);
  });

  it("classifies the bundled toy car sample as a car", () => {
    // Extents and the node names of public/samples/toycar.glb (see samples/tools/prepare_samples.mjs).
    // Its wheels are baked into the body mesh, so it is a car without the drive capabilities.
    const a = analyzeStats(
      stats({
        extents: [2.096, 1.302, 4.3],
        objectNames: ["ToyCar", "Car_Body", "Windshield", "Camera001", "Camera002"],
        materialNames: ["ToyCar", "Glass"],
      }),
    );
    expect(a.category).toBe("car");
    expect(a.confidence).toBe(0.97);
    expect(a.unitGuess).toBe("m");
    expect(a.scaleFactor).toBe(1);
    expect(a.parts).toEqual({ body: "Car_Body", windshield: "Windshield" });
    expect(a.capabilities).toEqual(["static", "rotate"]);
  });
});
