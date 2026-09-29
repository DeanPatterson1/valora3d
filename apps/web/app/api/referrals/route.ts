import { toReferralSummary } from "@/lib/referrals";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

/**
 * GET /api/referrals — the caller's referral code (made on first ask) and counts for the Invite card. Service role:
 * the referrals table has no user policy (a row names another person's account); only counts leave the database.
 */
export async function GET() {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const admin = createServiceSupabase(ctx.config);
  const code = await admin.rpc("referral_code", { p_user_id: ctx.user.id });
  if (code.error) return apiError(500, "server", "Could not load your invite link.");
  const summary = await admin.rpc("referral_summary", { p_user_id: ctx.user.id });
  const parsed = summary.error ? null : toReferralSummary(summary.data);
  if (!parsed) return apiError(500, "server", "Could not load your invite link.");
  return Response.json(parsed, { headers: { "Cache-Control": "no-store" } });
}
