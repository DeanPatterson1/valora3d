import type { SceneStats } from "@/lib/schema";
import { analyzeStats } from "@/lib/scene/analyze";
import { ok } from "../result";
import type { AnalysisService } from "../types";

export class LocalAnalysisService implements AnalysisService {
  async analyze(stats: SceneStats) {
    return ok(analyzeStats(stats));
  }
}
