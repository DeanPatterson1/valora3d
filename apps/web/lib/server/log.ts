/** Only developer-authored event names and route templates belong in logs. Never pass Error objects. */
type LogMessage = "global_error" | "request_failed" | "files_delete_failed" | "signout_failed" | "auth_failed" | "turnstile_unavailable";
type LogRoute = "/api/client-errors" | "/api/auth/signup" | "/api/auth/forgot-password" | "/api/account/delete" | "/api/projects/[id]";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function log(level: "info" | "warn" | "error", route: LogRoute, message: LogMessage, context: { requestId?: string; userId?: string } = {}) {
  const entry = {
    level, route, message,
    requestId: context.requestId && uuid.test(context.requestId) ? context.requestId : crypto.randomUUID(),
    ...(context.userId && uuid.test(context.userId) ? { userId: context.userId } : {}),
  };
  console[level](JSON.stringify(entry));
}
