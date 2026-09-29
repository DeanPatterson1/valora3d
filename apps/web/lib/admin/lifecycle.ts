import type { SupabaseClient } from "@supabase/supabase-js";
import type { FeedbackKind, FeedbackStatus } from "@/lib/feedback/shared";

/** /admin/feedback: user feedback, cancellation reasons, the email suppression list and what lifecycle mail went out. */

export type AdminFeedbackRow = {
  id: string;
  user_id: string | null;
  email: string | null;
  kind: FeedbackKind;
  message: string;
  page: string | null;
  release: string | null;
  ua_family: string | null;
  status: FeedbackStatus;
  created_at: string;
};

export type AdminCancellationRow = {
  id: string;
  user_id: string | null;
  email: string | null;
  plan: string | null;
  reason: string;
  detail: string | null;
  outcome: "canceled" | "paused" | "downgraded";
  created_at: string;
};

export type AdminSuppressionRow = { email: string; reason: "bounce" | "complaint" | "manual"; created_at: string; updated_at: string };

export type AdminFeedbackResponse = {
  feedback: AdminFeedbackRow[];
  cancellations: AdminCancellationRow[];
  suppressions: AdminSuppressionRow[];
  /** Lifecycle mail sent in the last 30 days, per kind. */
  emailsSent: Record<string, number>;
};

const LIMIT = 200;

export async function loadAdminFeedback(admin: SupabaseClient, status: FeedbackStatus | null): Promise<AdminFeedbackResponse> {
  let fb = admin
    .from("feedback")
    .select("id, user_id, kind, message, page, release, ua_family, status, created_at")
    .order("created_at", { ascending: false })
    .limit(LIMIT);
  if (status) fb = fb.eq("status", status);
  const since = new Date(Date.now() - 30 * 86_400_000).toISOString();
  const [feedback, cancellations, suppressions, sent] = await Promise.all([
    fb,
    admin.from("cancellation_feedback").select("id, user_id, plan, reason, detail, outcome, created_at").order("created_at", { ascending: false }).limit(LIMIT),
    admin.from("email_suppressions").select("email, reason, created_at, updated_at").order("updated_at", { ascending: false }).limit(LIMIT),
    admin.from("email_log").select("kind").gte("sent_at", since).limit(10_000),
  ]);
  for (const r of [feedback, cancellations, suppressions, sent]) if (r.error) throw new Error(r.error.message);

  const fbRows = (feedback.data ?? []) as Omit<AdminFeedbackRow, "email">[];
  const cxRows = (cancellations.data ?? []) as Omit<AdminCancellationRow, "email">[];
  const ids = [...new Set([...fbRows, ...cxRows].map((r) => r.user_id).filter((id): id is string => Boolean(id)))];
  const emails = new Map<string, string>();
  if (ids.length) {
    const { data, error } = await admin.from("profiles").select("id, email").in("id", ids);
    if (error) throw new Error(error.message);
    for (const p of (data ?? []) as { id: string; email: string }[]) emails.set(p.id, p.email);
  }
  const emailsSent: Record<string, number> = {};
  for (const r of (sent.data ?? []) as { kind: string }[]) emailsSent[r.kind] = (emailsSent[r.kind] ?? 0) + 1;

  return {
    feedback: fbRows.map((r) => ({ ...r, email: r.user_id ? (emails.get(r.user_id) ?? null) : null })),
    cancellations: cxRows.map((r) => ({ ...r, email: r.user_id ? (emails.get(r.user_id) ?? null) : null })),
    suppressions: (suppressions.data ?? []) as AdminSuppressionRow[],
    emailsSent,
  };
}
