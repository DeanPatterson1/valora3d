import { z } from "zod";
import { apiError } from "@/lib/supabase/server";
import { sameOrigin } from "@/lib/server/api";
import { limitHygieneRequest, readLimitedJson } from "@/lib/server/hygieneRequest";
import { log } from "@/lib/server/log";

// No arbitrary strings: messages, stacks, URLs, digests and user identifiers can contain PII.
const Report = z.object({ event: z.literal("global_error") }).strict();

export async function POST(request: Request) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const limited = await limitHygieneRequest(request);
  if (limited) return limited;
  const raw = await readLimitedJson(request, 1024);
  if (raw instanceof Response) return raw;
  if (!Report.safeParse(raw).success) return apiError(400, "invalid_request", "Invalid report.");
  log("error", "/api/client-errors", "global_error");
  return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
}
