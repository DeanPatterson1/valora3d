import { describe, it, expect } from "vitest";
import { ANALYSIS_STEPS, LABOUR_MIN_MS, PLANNING_STEPS, scheduleSteps } from "./labour";

describe("scheduleSteps", () => {
  it("spreads steps across at least the minimum duration", () => {
    const s = scheduleSteps(["a", "b", "c"], 1200);
    expect(s.map((x) => x.at)).toEqual([0, 400, 800]);
    expect(s[2].label).toBe("c");
  });

  it("defaults to LABOUR_MIN_MS and starts at 0", () => {
    const s = scheduleSteps(ANALYSIS_STEPS);
    expect(LABOUR_MIN_MS).toBe(1200);
    expect(s[0].at).toBe(0);
    expect(s).toHaveLength(ANALYSIS_STEPS.length);
    expect(s.map((x) => x.at)).toEqual([0, 300, 600, 900]);
  });

  it("keeps every step strictly before the minimum", () => {
    for (const labels of [ANALYSIS_STEPS, PLANNING_STEPS]) {
      for (const step of scheduleSteps(labels)) expect(step.at).toBeLessThan(LABOUR_MIN_MS);
    }
  });

  it("returns an empty schedule for no labels", () => {
    expect(scheduleSteps([])).toEqual([]);
  });
});
