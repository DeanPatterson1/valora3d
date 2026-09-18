import type { Services } from "./types";
import { LocalProjectRepository } from "./local/projectRepository";
import { LocalAnalysisService } from "./local/analysis";
import { LocalDirectorService } from "./local/director";
import { LocalCreditService } from "./local/credits";
import { LocalRenderService } from "./local/render";

export const services: Services = {
  projects: new LocalProjectRepository(),
  analysis: new LocalAnalysisService(),
  director: new LocalDirectorService(),
  credits: new LocalCreditService(),
  render: new LocalRenderService(),
};
export type { Services } from "./types";
export * from "./result";
