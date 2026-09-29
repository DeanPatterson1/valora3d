import { loadAdminFeedback } from "@/lib/admin/lifecycle";
import { FEEDBACK_STATUSES, type FeedbackStatus } from "@/lib/feedback/shared";
import { json, requireAdmin } from "@/lib/server/admin";
import { apiError } from "@/lib/supabase/server";

/** GET /api/admin/feedback?status=new — feedback, cancellation reasons, email suppressions, lifecycle mail counts. */
export async function GET(request: Request) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const raw = new URL(request.url).searchParams.get("status");
  const status = (FEEDBACK_STATUSES as readonly string[]).includes(raw ?? "") ? (raw as FeedbackStatus) : null;
  try {
    return json(await loadAdminFeedback(ctx.admin, status));
  } catch {
    return apiError(500, "server", "Could not load feedback.");
  }
}
