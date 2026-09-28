import type { Services } from "./types";
import { publicSupabaseConfig, type PublicSupabaseConfig } from "@/lib/env";
import { getBrowserSupabase } from "@/lib/supabase/browser";
import { LocalProjectRepository } from "./local/projectRepository";
import { LocalAnalysisService } from "./local/analysis";
import { LocalDirectorService } from "./local/director";
import { LocalCreditService } from "./local/credits";
import { LocalRenderService } from "./local/render";
import { LocalAuthService } from "./local/auth";
import { SupabaseAuthService } from "./supabase/auth";
import { SupabaseCreditService } from "./supabase/credits";
import { SupabaseProjectRepository } from "./supabase/projectRepository";

/**
 * The one seam. With NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY set at build time
 * the app talks to Supabase (auth, projects, credits) and R2 (models, via /api/uploads).
 * Without them it runs on the in-browser fakes, so local dev and the tests need no backend.
 * Analysis and the director stay client-side in both; render is wired by Lane D2.
 */
export function createServices(supabase: PublicSupabaseConfig | null): Services {
  if (!supabase) {
    return {
      backend: "local",
      auth: new LocalAuthService(),
      projects: new LocalProjectRepository(),
      analysis: new LocalAnalysisService(),
      director: new LocalDirectorService(),
      credits: new LocalCreditService(),
      render: new LocalRenderService(),
    };
  }
  // Lazy: the client is created on first use, in the browser.
  const db = () => getBrowserSupabase(supabase);
  return {
    backend: "supabase",
    auth: new SupabaseAuthService(db),
    projects: new SupabaseProjectRepository(db),
    analysis: new LocalAnalysisService(),
    director: new LocalDirectorService(),
    credits: new SupabaseCreditService(db),
    render: new LocalRenderService(),
  };
}

export const services: Services = createServices(publicSupabaseConfig());
export type { AuthFeatures, AuthProvider, AuthService, ProfilePatch, Services } from "./types";
export * from "./result";
