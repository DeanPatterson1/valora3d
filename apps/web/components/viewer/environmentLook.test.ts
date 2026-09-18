import { describe, expect, it } from "vitest";
import { ENV_MAP_FILES, environmentLook, lightingRig, type EnvironmentName, type LightingStyle, type TimeOfDay } from "./environmentLook";

const ENVS: EnvironmentName[] = ["studio_black", "studio_white", "outdoor_road", "urban_night"];
const TIMES: TimeOfDay[] = ["day", "dusk", "night"];
const STYLES: LightingStyle[] = ["soft_studio", "dramatic_three_point", "night_city", "sunset", "overcast"];

describe("environmentLook", () => {
  it("every environment has a distinct background from every other environment at each time", () => {
    for (const time of TIMES) {
      const horizons = ENVS.map((env) => environmentLook(env, time).horizon);
      expect(new Set(horizons).size).toBe(ENVS.length);
    }
  });
  it("outdoor_road changes with time of day", () => {
    const horizons = TIMES.map((time) => environmentLook("outdoor_road", time).horizon);
    expect(new Set(horizons).size).toBe(TIMES.length);
  });
  it("points every look at a local HDR", () => {
    for (const env of ENVS)
      for (const time of TIMES) {
        const file = ENV_MAP_FILES[environmentLook(env, time).envMap];
        expect(file).toMatch(/^\/hdri\/.+\.hdr$/);
      }
  });
});

describe("lightingRig", () => {
  it("yields a rig for every style", () => {
    for (const style of STYLES) {
      const rig = lightingRig(style);
      expect(rig.key[1]).toBeGreaterThan(0);
      expect(rig.softness).toBeGreaterThan(0);
    }
  });
});
