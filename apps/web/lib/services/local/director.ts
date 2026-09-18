import type { ModelAnalysis, ScenePlan } from "@/lib/schema";
import { planFromPrompt } from "@/lib/scene/director/planFromPrompt";
import { editFromPrompt } from "@/lib/scene/director/editFromPrompt";
import { fail, ok } from "../result";
import type { DirectorService } from "../types";

const VEHICLE_VERBS = /\b(drive|driving|drives|accelerat\w*|drift\w*|speed(ing)? (down|along)|race|racing)\b/i;

export class LocalDirectorService implements DirectorService {
  async plan(prompt: string, analysis: ModelAnalysis) {
    const plan = planFromPrompt(prompt, analysis.category);
    const warnings =
      VEHICLE_VERBS.test(prompt) && !analysis.capabilities.includes("drive")
        ? [
            {
              code: "capability_mismatch",
              message:
                "This model doesn't appear to be drivable. I can place it in the scene and move the camera as asked, but driving animation isn't available.",
            },
          ]
        : [];
    return ok(plan, warnings);
  }
  async edit(prompt: string, plan: ScenePlan) {
    const r = editFromPrompt(prompt, plan);
    return r.ok ? ok(r.patches) : fail(r.error.code, r.error.message, r.error.hints);
  }
}
