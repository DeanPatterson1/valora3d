import { z } from "zod";
import { serverConfig } from "@/lib/env";
import { apiError, createRequestSupabase } from "@/lib/supabase/server";
import { MIN_PASSWORD, normaliseEmail } from "@/lib/services/local/auth";
import { sameOrigin } from "./api";
import { limitHygieneRequest, readLimitedJson } from "./hygieneRequest";
import { verifyTurnstile, type AuthAction } from "./turnstile";
import { log } from "./log";

const Reset = z.object({ email: z.email().max(254), turnstileToken: z.string().max(2048).optional() });
const Signup = Reset.extend({ password: z.string().min(MIN_PASSWORD).max(1024), name: z.string().trim().min(1).max(200) });

export async function authEntry(request: Request, action: AuthAction): Promise<Response> {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const requestId = crypto.randomUUID();
  try {
    const limited = await limitHygieneRequest(request);
    if (limited) return limited;
    const raw = await readLimitedJson(request, 16_384);
    if (raw instanceof Response) return raw;
    const parsed = (action === "signup" ? Signup : Reset).safeParse(raw);
    if (!parsed.success) return apiError(400, "invalid_request", "Check the form fields and try again.");
    const config = serverConfig();
    if (!config) return apiError(503, "not_configured", "The account service is not configured.");
    const verification = await verifyTurnstile(request, parsed.data.turnstileToken, action, requestId);
    if (verification) return verification;
    const supabase = await createRequestSupabase(config);
    const origin = new URL(request.url).origin;
    const email = normaliseEmail(parsed.data.email);
    if (action === "signup") {
      const body = Signup.parse(parsed.data);
      const { data, error } = await supabase.auth.signUp({ email, password: body.password, options: {
        data: { name: body.name }, emailRedirectTo: `${origin}/auth/callback?next=/projects`,
      } });
      if (error) {
        if (error.status === 429) return apiError(429, "rate_limited", "Too many requests. Please wait a minute.");
        if (error.code === "weak_password") return apiError(400, "invalid_password", "Choose a stronger password.");
        if (error.code === "user_already_exists") return apiError(400, "exists", "An account with that email already exists. Log in instead.");
        log("error", "/api/auth/signup", "auth_failed", { requestId });
        return apiError(503, "unavailable", "Could not create the account. Try again later.");
      }
      return Response.json({ verificationSent: !data.session || !data.user, userId: data.session && data.user ? data.user.id : null }, { headers: { "Cache-Control": "no-store" } });
    }
    const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${origin}/auth/callback?next=/reset-password` });
    if (error?.status === 429) return apiError(429, "rate_limited", "Too many requests. Please wait a minute.");
    if (error && (!error.status || error.status >= 500)) {
      log("error", "/api/auth/forgot-password", "auth_failed", { requestId });
      return apiError(503, "unavailable", "Could not send the reset link. Try again later.");
    }
    return Response.json({ sent: true }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    log("error", `/api/auth/${action}`, "request_failed", { requestId });
    return apiError(503, "unavailable", "Please try again later.");
  }
}
