import type { Category, ScenePlan } from "@/lib/schema";

export function defaultPlan(category: Category): ScenePlan {
  const car = category === "car";
  return {
    scene: {
      environment: car ? "outdoor_road" : "studio_black",
      time: car ? "dusk" : "day",
      ground: car ? "dry_asphalt" : "studio_floor",
      fogDensity: 0,
    },
    subject: { category, position: [0, 0, 0], motion: "stationary" },
    camera: { style: "smooth", lensMm: car ? 50 : 85, heightM: car ? 1.0 : 0.6, motionStrength: 0 },
    shots: [{ id: "shot-1", start: 0, end: 10, action: "slow_orbit", distanceMultiplier: 1 }],
    lighting: { style: car ? "sunset" : "soft_studio", exposure: 0, rim: true, practicals: false },
    effects: { rain: 0, wetGround: 0, motionBlur: 0.2, depthOfField: 0.3 },
    output: { fps: 30, durationS: 10, resolution: "1080p", quality: "high" },
  };
}
