/** Preset prompts (spec 10, blank-page avoidance). Every prompt uses words the fake director understands. */
export const PRESETS = [
  { id: "auto_commercial", label: "Automotive commercial", prompt: "Cinematic car commercial on a mountain road at sunset, slow orbit then push in, 10 seconds" },
  { id: "rainy_night", label: "Rainy night", prompt: "Rainy night city street, wet asphalt, handheld camera walking toward the car" },
  { id: "luxury_studio", label: "Luxury studio", prompt: "Black studio, dramatic lighting, slow orbit, close up" },
  { id: "product_white", label: "Clean product", prompt: "White studio, soft lighting, slow orbit, 8 seconds" },
  { id: "tracking", label: "Low tracking", prompt: "Low tracking shot alongside the car on a highway at dusk" },
] as const;

export type Preset = (typeof PRESETS)[number];

/** The three shown as empty-state suggestions above the composer; the rest live under `+`. */
export const SUGGESTED_PRESETS: readonly Preset[] = [PRESETS[1], PRESETS[2], PRESETS[0]];
