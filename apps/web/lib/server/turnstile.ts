import { apiError } from "@/lib/supabase/server";
import { log } from "./log";

export type AuthAction = "signup" | "forgot-password";

export async function verifyTurnstile(request: Request, token: string | undefined, action: AuthAction, requestId: string): Promise<Response | null> {
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY?.trim();
  const secret = process.env.TURNSTILE_SECRET_KEY?.trim();
  if (!siteKey && !secret) return null;
  if (!siteKey || !secret) {
    log("error", `/api/auth/${action}`, "turnstile_unavailable", { requestId });
    return apiError(503, "unavailable", "Verification is unavailable. Please try again later.");
  }
  const rejected = () => apiError(400, "verification_failed", "Complete the security check and try again.");
  if (!token || token.length > 2048) return rejected();
  try {
    const response = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ secret, response: token }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) throw new Error("Verification unavailable");
    const result = await response.json() as { success?: boolean; hostname?: string; action?: string };
    return result.success === true && result.hostname === new URL(request.url).hostname && result.action === action ? null : rejected();
  } catch {
    log("error", `/api/auth/${action}`, "turnstile_unavailable", { requestId });
    return apiError(503, "unavailable", "Verification is unavailable. Please try again later.");
  }
}
