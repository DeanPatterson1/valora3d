import { describe, it, expect } from "vitest";
import { ScenePlanSchema } from "./scene-plan";
import { UserPrefsSchema } from "./user";

const valid = {
  scene: { environment: "urban_night", time: "night", ground: "wet_asphalt", fogDensity: 0.025 },
  subject: { category: "car", position: [0, 0, 0], motion: "stationary" },
  camera: { style: "handheld", lensMm: 45, heightM: 1.45, motionStrength: 0.18 },
  shots: [
    { id: "s1", start: 0, end: 4, action: "handheld_walk_toward", distanceMultiplier: 1 },
    { id: "s2", start: 4, end: 10, action: "slow_orbit", distanceMultiplier: 1 },
  ],
  lighting: { style: "night_city", exposure: 0, rim: true, practicals: true },
  effects: { rain: 0.4, wetGround: 0.75, motionBlur: 0.18, depthOfField: 0.5 },
  output: { durationS: 10, tier: "final", aspect: "9:16" },
};

/** A plan as stored before output was limited to what the worker renders. */
const legacy = { ...valid, output: { fps: 30, durationS: 10, resolution: "1080p", quality: "high" } };

describe("ScenePlanSchema", () => {
  it("accepts a valid plan", () => {
    expect(ScenePlanSchema.safeParse(valid).success).toBe(true);
  });
  it("drops an unknown tier / format instead of failing the plan", () => {
    const r = ScenePlanSchema.safeParse({ ...valid, output: { durationS: 10, tier: "4k", aspect: "4:3" } });
    expect(r.success && r.data.output).toEqual({ durationS: 10 });
  });
  it("rejects shots that do not end at durationS", () => {
    expect(ScenePlanSchema.safeParse({ ...valid, output: { ...valid.output, durationS: 12 } }).success).toBe(false);
  });
  it("rejects a non-numeric duration", () => {
    expect(ScenePlanSchema.safeParse({ ...valid, output: { durationS: "10" } }).success).toBe(false);
  });
  it("rejects non-contiguous shots", () => {
    expect(ScenePlanSchema.safeParse({ ...valid, shots: [{ ...valid.shots[0], end: 3 }, valid.shots[1]] }).success).toBe(false);
  });
  it("rejects more than two shots", () => {
    const bad = { ...valid, shots: [{ ...valid.shots[0], end: 2 }, { ...valid.shots[0], id: "x", start: 2, end: 4 }, valid.shots[1]] };
    expect(ScenePlanSchema.safeParse(bad).success).toBe(false);
  });
});

describe("stored plans from before tiers (backward compatible)", () => {
  it.each([
    ["4k", "final"],
    ["1440p", "final"],
    ["1080p", "final"],
    ["720p", "preview"],
  ])("resolution %s parses as the %s tier; fps / resolution / quality are dropped", (resolution, tier) => {
    const r = ScenePlanSchema.safeParse({ ...legacy, output: { ...legacy.output, resolution } });
    expect(r.success).toBe(true);
    expect(r.success && r.data.output).toEqual({ durationS: 10, tier });
  });
  it("a 30 s plan moves to 12 s with its shots rescaled and still contiguous", () => {
    const long = {
      ...legacy,
      shots: [{ ...valid.shots[0], start: 0, end: 12 }, { ...valid.shots[1], start: 12, end: 30 }],
      output: { fps: 60, durationS: 30, resolution: "4k", quality: "ultra" },
    };
    const r = ScenePlanSchema.safeParse(long);
    expect(r.success).toBe(true);
    if (!r.success) return;
    expect(r.data.output).toEqual({ durationS: 12, tier: "final" });
    expect(r.data.shots.map((s) => [s.start, s.end].map((t) => Math.round(t * 1e6) / 1e6))).toEqual([[0, 4.8], [4.8, 12]]);
  });
  it("5 s and 15 s plans move to the nearest offered length (8 s / 12 s)", () => {
    const five = { ...legacy, shots: [{ ...valid.shots[0], start: 0, end: 5 }], output: { ...legacy.output, durationS: 5, quality: "draft", resolution: undefined } };
    const r5 = ScenePlanSchema.safeParse(five);
    expect(r5.success && r5.data.output).toEqual({ durationS: 8, tier: "preview" });
    expect(r5.success && r5.data.shots[0].end).toBe(8);
    const fifteen = { ...legacy, shots: [{ ...valid.shots[0], start: 0, end: 15 }], output: { ...legacy.output, durationS: 15 } };
    const r15 = ScenePlanSchema.safeParse(fifteen);
    expect(r15.success && r15.data.output.durationS).toBe(12);
  });
});

describe("stored preferences from before tiers (backward compatible)", () => {
  const prefs = (defaultOutput: unknown) => UserPrefsSchema.safeParse({ defaultOutput, localAgent: "not_connected" });
  it("maps 4K / 1440p / 1080p defaults to Final and 720p to Preview, format defaulting to 9:16", () => {
    for (const [resolution, tier] of [["4k", "final"], ["1440p", "final"], ["1080p", "final"], ["720p", "preview"]]) {
      const r = prefs({ fps: 60, durationS: 30, resolution, quality: "ultra" });
      expect(r.success && r.data.defaultOutput).toEqual({ tier, aspect: "9:16" });
    }
  });
  it("replaces an unknown stored tier / format with the default instead of losing the prefs", () => {
    const r = prefs({ tier: "ultra", aspect: "4:3" });
    expect(r.success && r.data.defaultOutput).toEqual({ tier: "preview", aspect: "9:16" });
  });
  it("keeps current prefs as they are", () => {
    expect(prefs({ tier: "final", aspect: "16:9" })).toMatchObject({ success: true, data: { defaultOutput: { tier: "final", aspect: "16:9" } } });
  });
});
