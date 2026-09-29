import type { SupabaseClient } from "@supabase/supabase-js";

/**
 * "Download my data" (Settings -> Account; GDPR art. 15/20). Everything is read with the user's OWN session, so RLS
 * returns only their rows; the three tables users cannot read (their feedback text, cancellation reasons and the
 * mail log) are read with the service role and filtered to their id. No other person's data, no storage keys, no
 * payment references beyond what the user's own billing rows already show them. Model files and videos are not
 * inside the JSON (they are downloadable from the app while retained).
 */

export const EXPORT_ROW_LIMIT = 5000;

type Query = { data: unknown[] | null; error: { message: string } | null };
export type ExportReader = (table: string, columns: string, byUser?: string) => Promise<Query>;

/** What is exported, table by table, and which columns. */
export const EXPORT_TABLES: { key: string; table: string; columns: string; service?: true }[] = [
  { key: "projects", table: "projects", columns: "id, name, created_at, updated_at, selected_version_id" },
  { key: "scene_versions", table: "scene_versions", columns: "id, project_id, index, prompt, parent_id, plan, created_at" },
  { key: "models", table: "uploads", columns: "id, project_id, source, file_name, format, size_bytes, status, reject_reason, created_at, completed_at" },
  {
    key: "render_jobs",
    table: "render_jobs",
    columns: "id, project_id, version_id, kind, status, params, cost_credits, created_at, started_at, finished_at, expired_at, retention_days",
  },
  { key: "share_links", table: "render_shares", columns: "slug, job_id, show_prompt, view_count, created_at, revoked_at" },
  { key: "credit_ledger", table: "credit_history", columns: "id, amount, reason, project_id, job_id, created_at, balance_after, plan" },
  { key: "subscriptions", table: "billing_subscriptions", columns: "plan, status, current_period_start, current_period_end, canceled_at, created_at" },
  { key: "payments", table: "billing_transactions", columns: "id, kind, plan, credits_granted, credits_reversed, total_minor, currency_code, period_start, period_end, created_at" },
  { key: "feedback", table: "feedback", columns: "kind, message, page, status, created_at", service: true },
  { key: "cancellation_feedback", table: "cancellation_feedback", columns: "plan, reason, detail, outcome, created_at", service: true },
  { key: "emails_sent", table: "email_log", columns: "kind, sent_at", service: true },
];

export async function buildExport(
  userId: string,
  profileRead: () => Promise<{ data: Record<string, unknown> | null; error: { message: string } | null }>,
  userRead: ExportReader,
  serviceRead: ExportReader,
  now = new Date(),
): Promise<Record<string, unknown>> {
  const profile = await profileRead();
  if (profile.error || !profile.data) throw new Error("profile read failed");
  const p = profile.data;
  const out: Record<string, unknown> = {
    format: "valora3d-export/v1",
    exported_at: now.toISOString(),
    account: {
      id: userId,
      email: p.email,
      name: p.name,
      plan: p.plan,
      created_at: p.created_at,
      signup_source: p.signup_source ?? null,
    },
    preferences: {
      settings: p.prefs ?? {},
      email_render_notifications: p.email_render_ready !== false,
      email_product_tips: p.email_product_tips !== false,
    },
  };
  for (const t of EXPORT_TABLES) {
    const r = t.service ? await serviceRead(t.table, t.columns, userId) : await userRead(t.table, t.columns);
    if (r.error) throw new Error(`${t.table} read failed`);
    out[t.key] = r.data ?? [];
  }
  out.not_included = [
    "Model files and rendered videos: download them from the app while they are kept.",
    "Sign-in records held by our authentication provider (Supabase Auth).",
    "Payment details held by Paddle, our merchant of record (see paddle.net).",
  ];
  return out;
}

export function supabaseReaders(userClient: SupabaseClient, admin: SupabaseClient) {
  const userRead: ExportReader = async (table, columns) =>
    (await userClient.from(table).select(columns).limit(EXPORT_ROW_LIMIT)) as unknown as Query;
  const serviceRead: ExportReader = async (table, columns, byUser) => {
    if (!byUser) return { data: [], error: null };
    return (await admin.from(table).select(columns).eq("user_id", byUser).limit(EXPORT_ROW_LIMIT)) as unknown as Query;
  };
  return { userRead, serviceRead };
}
