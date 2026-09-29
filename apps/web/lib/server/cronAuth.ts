import type { ServerConfig } from "@/lib/env";
import { timingSafeEqualStr } from "./webhookToken";

/** Bearer CRON_SECRET, constant-time (the Worker's cron handler, custom-worker.mjs). Closed when no secret is set. */
export function cronAuthorized(request: Request, config: ServerConfig | null): config is ServerConfig {
  if (!config?.cronSecret) return false;
  const presented = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ?? "";
  return timingSafeEqualStr(presented, config.cronSecret);
}
