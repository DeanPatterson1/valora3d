/** Only developer-authored event names and route templates belong in logs. Never pass Error objects. */
type LogMessage = "global_error" | "files_delete_failed" | "files_delete_deferred" | "render_cancel_failed" | "signout_failed" | "share_gate_failed" | "share_view_count_failed";
type LogRoute = "/api/client-errors" | "/api/account/delete" | "/api/projects/[id]" | "/r/[slug]";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function log(level: "info" | "warn" | "error", route: LogRoute, message: LogMessage, context: { requestId?: string; userId?: string } = {}) {
  const entry = {
    level, route, message,
    requestId: context.requestId && uuid.test(context.requestId) ? context.requestId : crypto.randomUUID(),
    ...(context.userId && uuid.test(context.userId) ? { userId: context.userId } : {}),
  };
  console[level](JSON.stringify(entry));
}

const TEMPLATE = /^\/[A-Za-z0-9/_.[\]()@-]{0,160}$/;
const TOKEN = /^[A-Za-z0-9._:-]{1,60}$/;
const safe = (v: unknown, re: RegExp): string | undefined => (typeof v === "string" && re.test(v) ? v : undefined);

/** One line per client error report (already reduced to fixed fields by lib/errors/shared.ts). */
export function logClientError(
  report: { kind: string; path: string; name: string; code: string | null; release: string },
  browser: string,
) {
  console.error(
    JSON.stringify({
      level: "error",
      route: "/api/client-errors",
      message: "client_error",
      requestId: crypto.randomUUID(),
      kind: safe(report.kind, TOKEN),
      path: safe(report.path, TEMPLATE),
      name: safe(report.name, TOKEN),
      code: safe(report.code, TOKEN),
      release: safe(report.release, TOKEN),
      browser: safe(browser, TOKEN),
    }),
  );
}

/**
 * One line per unhandled server error (instrumentation.ts onRequestError): the route FILE template (never the request
 * URL), the method, the error class name and Next's digest, a request id and Cloudflare's ray id to find the request in
 * Workers Logs. Never the message or the stack: they can carry user data.
 */
export function logRouteError(error: unknown, context: { routePath?: string; routeType?: string; method?: string; ray?: string | null }) {
  const e = error as { name?: unknown; digest?: unknown } | null;
  console.error(
    JSON.stringify({
      level: "error",
      message: "unhandled_route_error",
      requestId: crypto.randomUUID(),
      route: safe(context.routePath, TEMPLATE) ?? "unknown",
      routeType: safe(context.routeType, TOKEN),
      method: safe(context.method, /^[A-Z]{3,7}$/),
      name: safe(e?.name, /^[A-Za-z][A-Za-z0-9_]{0,59}$/) ?? "Error",
      digest: safe(e?.digest, TOKEN),
      ray: safe(context.ray ?? undefined, /^[0-9a-f]{16}(-[A-Z]{3})?$/),
      release: safe(process.env.NEXT_PUBLIC_RELEASE_ID, TOKEN),
    }),
  );
}
