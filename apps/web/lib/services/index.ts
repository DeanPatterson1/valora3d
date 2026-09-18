import type { Services } from "./types";
import { LocalProjectRepository } from "./local/projectRepository";
import { LocalAnalysisService } from "./local/analysis";
import { LocalDirectorService } from "./local/director";
import { LocalCreditService } from "./local/credits";
import { LocalRenderService } from "./local/render";
import { LocalAuthService } from "./local/auth";

export const services: Services = {
  auth: new LocalAuthService(),
  projects: new LocalProjectRepository(),
  analysis: new LocalAnalysisService(),
  director: new LocalDirectorService(),
  credits: new LocalCreditService(),
  render: new LocalRenderService(),
};
export type { AuthProvider, AuthService, ProfilePatch, Services } from "./types";
export * from "./result";
