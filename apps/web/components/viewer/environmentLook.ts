import type { ScenePlan } from "@/lib/schema";

export type EnvironmentName = ScenePlan["scene"]["environment"];
export type LightingStyle = ScenePlan["lighting"]["style"];
export type TimeOfDay = ScenePlan["scene"]["time"];
export type EnvMap = "studio" | "sunset" | "dawn" | "night";

/** Local copies of the Poly Haven 1k HDRs drei ships as presets (see `public/hdri/LICENSES.md`). */
export const ENV_MAP_FILES: Record<EnvMap, string> = {
  studio: "/hdri/studio_small_03_1k.hdr",
  sunset: "/hdri/venice_sunset_1k.hdr",
  dawn: "/hdri/kiara_1_dawn_1k.hdr",
  night: "/hdri/dikhololo_night_1k.hdr",
};

/** Everything a preset decides about the world around the model. */
export type EnvironmentLook = {
  /** Sky at the horizon (also the fog colour and, for studios, the whole backdrop). */
  horizon: string;
  /** Sky overhead. Equal to `horizon` for flat studio backdrops. */
  zenith: string;
  ground: string;
  gridCell: string;
  gridSection: string;
  /** Extra fog so studio floors dissolve into their backdrop. */
  baseFog: number;
  /** Reflection map, and how strongly it lights the model. */
  envMap: EnvMap;
  envIntensity: number;
  /** Reflection strength on the floor; kept low for the black studio so the void stays black. */
  groundEnv: number;
  practicals: boolean;
};

export function environmentLook(environment: EnvironmentName, time: TimeOfDay): EnvironmentLook {
  switch (environment) {
    case "studio_black":
      // Backdrop and floor sit within a few levels of each other and the fog is dense, so the
      // lit floor dissolves into the dark cyc with no visible horizon.
      return {
        horizon: "#0d0d0e",
        zenith: "#060607",
        ground: "#090909",
        gridCell: "#161514",
        gridSection: "#1c1a18",
        baseFog: 0.02,
        envMap: "studio",
        envIntensity: 0.55,
        groundEnv: 0.08,
        practicals: false,
      };
    case "studio_white":
      return {
        horizon: "#e6e2db",
        zenith: "#f1eee8",
        ground: "#bdb7ae",
        gridCell: "#ada79e",
        gridSection: "#a09a90",
        baseFog: 0.02,
        envMap: "studio",
        envIntensity: 0.9,
        groundEnv: 0.45,
        practicals: false,
      };
    case "outdoor_road": {
      if (time === "night")
        return {
          horizon: "#1c1e2c",
          zenith: "#05060c",
          ground: "#1a1a1c",
          gridCell: "#212023",
          gridSection: "#27262a",
          baseFog: 0.016,
          envMap: "night",
          envIntensity: 0.5,
          groundEnv: 0.35,
          practicals: false,
        };
      if (time === "day")
        return {
          horizon: "#c9d3dc",
          zenith: "#6f9bc8",
          ground: "#3a3a3c",
          gridCell: "#434346",
          gridSection: "#4c4c50",
          baseFog: 0.014,
          envMap: "dawn",
          envIntensity: 0.9,
          groundEnv: 0.35,
          practicals: false,
        };
      return {
        horizon: "#d8875a",
        zenith: "#2c2140",
        ground: "#2a2729",
        gridCell: "#34302f",
        gridSection: "#3c3735",
        baseFog: 0.018,
        envMap: "sunset",
        envIntensity: 0.8,
        groundEnv: 0.35,
        practicals: false,
      };
    }
    case "urban_night":
      return {
        horizon: "#182032",
        zenith: "#04060b",
        ground: "#101318",
        gridCell: "#161a22",
        gridSection: "#1c212b",
        baseFog: 0.016,
        envMap: "night",
        envIntensity: 0.6,
        groundEnv: 0.4,
        practicals: true,
      };
  }
}

export type Rig = {
  ambient: [color: string, intensity: number];
  key: [color: string, intensity: number, elevation: number, azimuth: number];
  fill: [color: string, intensity: number];
  rim: [color: string, intensity: number];
  /** Shadow softness in shadow-map texels. */
  softness: number;
};

export function lightingRig(style: LightingStyle): Rig {
  switch (style) {
    case "soft_studio":
      return { ambient: ["#ffffff", 0.55], key: ["#fff4e6", 2.2, 0.95, -0.7], fill: ["#e8eef8", 0.9], rim: ["#ffffff", 1.4], softness: 8 };
    case "dramatic_three_point":
      return { ambient: ["#ffffff", 0.15], key: ["#fff1dd", 3.4, 0.8, -1.1], fill: ["#c8d3e6", 0.25], rim: ["#ffffff", 2.6], softness: 2 };
    case "night_city":
      return { ambient: ["#5c6f9e", 0.35], key: ["#a9bce6", 1.0, 1.1, -0.4], fill: ["#3b4d78", 0.45], rim: ["#f2a83b", 2.2], softness: 4 };
    case "sunset":
      return { ambient: ["#ffd2a8", 0.35], key: ["#ffb26b", 2.8, 0.28, -0.9], fill: ["#6e7fb0", 0.55], rim: ["#ffd9b0", 1.6], softness: 3 };
    case "overcast":
      return { ambient: ["#dfe6ee", 1.1], key: ["#f2f5f8", 1.2, 1.2, -0.5], fill: ["#d0d8e2", 0.6], rim: ["#ffffff", 0.5], softness: 10 };
  }
}
