/**
 * The "this browser asked for an auth email" hint (login-CSRF defence, see lib/auth/emailLink.ts). Kept in its own
 * dependency-free module because the browser-side auth service sets it.
 */

/** Set by this site's own JS when it asks Supabase to send an email; a cross-site page cannot set it. */
export const EMAIL_FLOW_COOKIE = "v3d_email_flow";
const EMAIL_FLOW_MAX_AGE_S = 24 * 60 * 60;

/** Browser only: remember that this browser asked for an auth email (read server-side by /auth/continue). */
export function markEmailFlowStarted(
  doc: Pick<Document, "cookie"> | undefined = typeof document === "undefined" ? undefined : document,
  https: boolean = typeof location !== "undefined" && location.protocol === "https:",
): void {
  if (!doc) return;
  doc.cookie = `${EMAIL_FLOW_COOKIE}=1; Max-Age=${EMAIL_FLOW_MAX_AGE_S}; Path=/; SameSite=Lax${https ? "; Secure" : ""}`;
}
