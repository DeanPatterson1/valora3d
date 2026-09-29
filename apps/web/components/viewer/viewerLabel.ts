import type { ScenePlan } from "@/lib/schema";

const words = (id: string) => id.replace(/_/g, " ");

/**
 * The 3D preview's text alternative (the canvas is `role="img"`): what is loaded and, once a scene is planned,
 * where and how it is shot. Changes with the scene, so a screen reader hears the same thing a sighted user sees.
 */
export function viewerLabel({ fileName, category, plan }: { fileName?: string | null; category?: string | null; plan?: ScenePlan | null }): string {
  if (!fileName) return "3D preview. No model loaded.";
  const subject = category ? `${fileName}, a ${category} model` : fileName;
  if (!plan) return `3D preview of ${subject}.`;
  const moves = [...new Set(plan.shots.map((s) => words(s.action)))].join(" then ");
  const rain = plan.effects.rain > 0 ? ", with rain" : "";
  return `3D preview of ${subject}. Scene: ${words(plan.scene.environment)} at ${plan.scene.time}${rain}; camera: ${moves}.`;
}
