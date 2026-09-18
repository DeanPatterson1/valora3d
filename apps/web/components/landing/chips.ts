import type { ScenePlan } from "@/lib/schema";
import { planFromPrompt } from "@/lib/scene/director/planFromPrompt";

export type HeroChip = { id: string; label: string; prompt: string };

/** The three example looks under the hero viewer. Each runs through the real director. */
export const HERO_CHIPS: readonly HeroChip[] = [
  { id: "rainy-night", label: "Rainy night", prompt: "Rainy night on a city street, cinematic" },
  { id: "sunset-road", label: "Sunset road", prompt: "Sunset on an open road" },
  { id: "studio", label: "Studio", prompt: "Clean studio, dramatic lighting" },
];

export function heroPlan(chip: HeroChip): ScenePlan {
  return planFromPrompt(chip.prompt, "car");
}
