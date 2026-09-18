/** Preset prompts (spec 10, blank-page avoidance). Every prompt uses words the fake director understands. */
export const PRESETS = [
  { id: "auto_commercial", label: "Automotive Commercial", prompt: "Cinematic car commercial on a mountain road at sunset, slow orbit then push in, 10 seconds" },
  { id: "rainy_night", label: "Rainy Night", prompt: "Rainy night city street, wet asphalt, handheld camera walking toward the car" },
  { id: "luxury_studio", label: "Luxury Studio", prompt: "Black studio, dramatic lighting, slow orbit, close up" },
  { id: "product_white", label: "Clean Product", prompt: "White studio, soft lighting, slow orbit, 5 seconds" },
  { id: "tracking", label: "Low Tracking", prompt: "Low tracking shot alongside the car on a highway at dusk" },
] as const;

export type Preset = (typeof PRESETS)[number];
