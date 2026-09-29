import { logRouteError } from "@/lib/server/log";

/**
 * Next's server error hook: one structured log line per unhandled error in a page, route handler, server action or the
 * proxy (Workers Logs). See lib/server/log.ts for what the line may contain: never the message, stack or URL.
 */
export function onRequestError(
  error: unknown,
  request: { path: string; method: string; headers: Record<string, string | string[] | undefined> },
  context: { routePath?: string; routeType?: string },
): void {
  const ray = request.headers["cf-ray"];
  logRouteError(error, {
    routePath: context.routePath,
    routeType: context.routeType,
    method: request.method,
    ray: typeof ray === "string" ? ray : null,
  });
}
