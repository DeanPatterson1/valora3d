import type { Services } from "./types";
import { publicSupabaseConfig, type PublicSupabaseConfig } from "@/lib/env";
import { getBrowserSupabase } from "@/lib/supabase/browser";
import { LocalProjectRepository } from "./local/projectRepository";
import { LocalAnalysisService } from "./local/analysis";
import { LocalDirectorService } from "./local/director";
import { LocalCreditService } from "./local/credits";
import { LocalRenderService } from "./local/render";
import { LocalAuthService } from "./local/auth";
import { LocalAccountService } from "./local/account";
import { SupabaseAccountService } from "./supabase/account";
import { SupabaseAuthService } from "./supabase/auth";
import { SupabaseCreditService } from "./supabase/credits";
import { SupabaseProjectRepository } from "./supabase/projectRepository";
import { HttpRenderService } from "./supabase/render";

/**
 * The one seam. With NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY set at build time
 * the app talks to Supabase (auth, projects, credits) and R2 (models, via /api/uploads).
 * Without them it runs on the in-browser fakes, so local dev and the tests need no backend.
 * Analysis and the director stay client-side in both. Render: Local mode is `not_connected`; with Supabase
 * the studio talks to /api/renders, which answers `not_connected` itself until RUNPOD_API_KEY and
 * RUNPOD_ENDPOINT_ID are set on the server (they are secrets, so the browser cannot see them).
 */
export function createServices(supabase: PublicSupabaseConfig | null): Services {
  if (!supabase) {
    const credits = new LocalCreditService();
    return {
      backend: "local",
      auth: new LocalAuthService(),
      projects: new LocalProjectRepository(),
      analysis: new LocalAnalysisService(),
      director: new LocalDirectorService(),
      credits,
      render: new LocalRenderService(),
      account: new LocalAccountService(credits),
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
    render: new HttpRenderService(),
    account: new SupabaseAccountService(db),
  };
}

export const services: Services = createServices(publicSupabaseConfig());
export type { AccountService, AuthFeatures, AuthProvider, AuthService, ProfilePatch, RenderRequest, RenderRequestInput, RenderService, Services } from "./types";
export * from "./result";
