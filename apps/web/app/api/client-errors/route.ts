import { serverConfig } from "@/lib/env";
import { ClientErrorReport, cleanReport, uaFamily } from "@/lib/errors/shared";
import { apiError, createServiceSupabase } from "@/lib/supabase/server";
import { sameOrigin } from "@/lib/server/api";
import { limitHygieneRequest, readLimitedJson } from "@/lib/server/hygieneRequest";
import { logClientError } from "@/lib/server/log";

/**
 * POST /api/client-errors {kind, path, name, digest?, release} — a browser error report (lib/errors/report.ts).
 * Same-origin JSON, 1 KiB, rate-limited per IP. No free text is accepted: messages, stacks and URLs can contain
 * personal data. The path is stored as a route template, the browser as a family from the User-Agent header. One log
 * line, plus a row in client_errors (30 days; /admin -> Errors) when the backend is configured.
 */
export async function POST(request: Request) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const limited = await limitHygieneRequest(request);
  if (limited) return limited;
  const raw = await readLimitedJson(request, 1024);
  if (raw instanceof Response) return raw;
  const parsed = ClientErrorReport.safeParse(raw);
  if (!parsed.success) return apiError(400, "invalid_request", "Invalid report.");
  const report = cleanReport(parsed.data);
  const browser = uaFamily(request.headers.get("user-agent"));
  logClientError(report, browser);
  const config = serverConfig();
  if (config) {
    try {
      await createServiceSupabase(config).rpc("record_client_error", {
        p_release: report.release,
        p_path: report.path,
        p_name: report.name,
        p_code: report.code,
        p_kind: report.kind,
        p_ua_family: browser,
      });
    } catch {
      // The log line above still carries it.
    }
  }
  return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
}
