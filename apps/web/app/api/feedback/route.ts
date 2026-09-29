import { uaFamily } from "@/lib/errors/shared";
import { FeedbackRequest, feedbackRow } from "@/lib/feedback/shared";
import { ownerMail } from "@/lib/ops/run";
import { sendOwnerMail } from "@/lib/ops/alerts";
import { sameOrigin } from "@/lib/server/api";
import { limitHygieneRequest, readLimitedJson } from "@/lib/server/hygieneRequest";
import { SITE_URL } from "@/lib/site";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

/** At most one owner mail about new bug reports per this many seconds (the rest wait in /admin/feedback). */
const BUG_ALERT_INTERVAL_SECONDS = 15 * 60;

/**
 * POST /api/feedback {kind, message, page?, release?} — a signed-in user's bug report, idea or question. Inserted with
 * the user's own session (RLS: insert own rows, no reads), so the database also enforces the per-account cap (5 an
 * hour, 20 a day); the hygiene limiter caps each IP. The browser family comes from the User-Agent header, the page is a
 * route template. A new bug mails the owner (OWNER_ALERT_EMAIL), at most once per 15 minutes.
 */
export async function POST(request: Request) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const limited = await limitHygieneRequest(request);
  if (limited) return limited;
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const raw = await readLimitedJson(request, 8 * 1024);
  if (raw instanceof Response) return raw;
  const parsed = FeedbackRequest.safeParse(raw);
  if (!parsed.success) return apiError(400, "invalid_request", "Write at least a few words.");

  const row = feedbackRow(parsed.data, uaFamily(request.headers.get("user-agent")));
  const { error } = await ctx.userClient.from("feedback").insert(row);
  if (error) {
    if (error.code === "P0001" && error.message.startsWith("rate_limited")) {
      return apiError(429, "rate_limited", "Thanks, we've got several messages from you in the last hour. Try again a bit later.");
    }
    return apiError(500, "server", "Couldn't send your feedback. Try again, or email support@valora3d.com.");
  }

  if (row.kind === "bug") {
    const mail = ownerMail(ctx.config);
    if (mail) {
      try {
        const admin = createServiceSupabase(ctx.config);
        const claimed = await admin.rpc("claim_owner_alert", { p_kind: "feedback_bug", p_min_interval_seconds: BUG_ALERT_INTERVAL_SECONDS });
        if (claimed.data === true) {
          await sendOwnerMail(
            mail,
            {
              subject: "[Valora3D] New bug report",
              text: [
                "A user reported a bug.",
                "",
                `Page: ${row.page ?? "unknown"}`,
                `Release: ${row.release ?? "unknown"}`,
                `Browser: ${row.ua_family ?? "unknown"}`,
                `User: ${ctx.user.id}`,
                "",
                row.message.slice(0, 1500),
                "",
                `Triage: ${SITE_URL}/admin/feedback`,
                `(At most one of these mails per ${BUG_ALERT_INTERVAL_SECONDS / 60} minutes; later reports wait in the admin list.)`,
              ].join("\n"),
            },
            `feedback-bug-${Date.now()}`,
          );
        }
      } catch {
        // The report is saved; the alert is a convenience.
      }
    }
  }
  return Response.json({ ok: true }, { status: 201, headers: { "Cache-Control": "no-store" } });
}
