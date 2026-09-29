import type { SupabaseClient } from "@supabase/supabase-js";
import {
  canRefund,
  canRetry,
  type AdjustmentRow,
  type AdminJob,
  type AdminJobDetail,
  type AdminUserRow,
  type AuditRow,
  type BillingEventRow,
  type BillingResponse,
  type JobDetailResponse,
  type JobPrivate,
  type JobStatus,
  type LedgerRow,
  type SubscriptionRow,
  type TransactionRow,
  type UploadRow,
  type UserDetailResponse,
  type WebhookErrorRow,
} from "@/lib/admin/types";

/**
 * Read queries for the admin console, over the SERVICE-ROLE client. Only called by /api/admin routes after
 * requireAdmin(). Each list is bounded; columns are named so a secret column (e.g. webhook_token_hash) can never
 * leak by a `select *`.
 */

export const JOB_COLUMNS =
  "id, user_id, project_id, upload_id, kind, status, stage, error, error_code, retryable, cost_credits, refunded_credits, attempts, render_seconds, gpu_seconds, execution_ms, delay_ms, runpod_id, runpod_status, created_at, started_at, finished_at";
const JOB_DETAIL_COLUMNS = `${JOB_COLUMNS}, params, timings, warnings, outputs, watermark, watermarked, expired_at, frame, total_frames`;
const LEDGER_COLUMNS = "id, user_id, amount, reason, ref, job_id, created_at";
const AUDIT_COLUMNS = "id, admin_id, action, target_type, target_id, reason, detail, created_at";
const TXN_COLUMNS = "id, user_id, kind, plan, credits_granted, credits_reversed, total_minor, currency_code, created_at";
const EVENT_COLUMNS = "event_id, event_type, occurred_at, received_at, outcome, detail";

export class QueryError extends Error {}

function rows<T>(result: { data: unknown; error: { message: string } | null }, what: string): T[] {
  if (result.error) throw new QueryError(`${what}: ${result.error.message}`);
  return (result.data ?? []) as T[];
}

/** user id -> email, for labelling rows. */
export async function emailsFor(admin: SupabaseClient, ids: string[]): Promise<Map<string, string>> {
  const unique = [...new Set(ids.filter(Boolean))];
  if (!unique.length) return new Map();
  const data = rows<{ id: string; email: string }>(
    await admin.from("profiles").select("id, email").in("id", unique),
    "profiles",
  );
  return new Map(data.map((p) => [p.id, p.email]));
}

async function withEmails<T extends { user_id: string }>(admin: SupabaseClient, list: T[]): Promise<(T & { email: string | null })[]> {
  const emails = await emailsFor(admin, list.map((r) => r.user_id));
  return list.map((r) => ({ ...r, email: emails.get(r.user_id) ?? null }));
}

async function auditWithEmails(admin: SupabaseClient, list: Omit<AuditRow, "admin_email">[]): Promise<AuditRow[]> {
  const emails = await emailsFor(admin, list.map((r) => r.admin_id));
  return list.map((r) => ({ ...r, admin_email: emails.get(r.admin_id) ?? null }));
}

export async function listJobs(
  admin: SupabaseClient,
  filter: { status?: JobStatus; userId?: string; before?: string; limit: number },
): Promise<AdminJob[]> {
  let q = admin.from("render_jobs").select(JOB_COLUMNS).order("created_at", { ascending: false }).limit(filter.limit);
  if (filter.status) q = q.eq("status", filter.status);
  if (filter.userId) q = q.eq("user_id", filter.userId);
  if (filter.before) q = q.lt("created_at", filter.before);
  const list = rows<Omit<AdminJob, "email">>(await q, "render_jobs");
  return withEmails(admin, list);
}

export async function jobDetail(admin: SupabaseClient, id: string): Promise<JobDetailResponse | null> {
  const { data, error } = await admin.from("render_jobs").select(JOB_DETAIL_COLUMNS).eq("id", id).maybeSingle();
  if (error) throw new QueryError(`render_jobs: ${error.message}`);
  if (!data) return null;
  const base = data as unknown as Omit<AdminJobDetail, "email">;
  const [emails, priv, ledger, audit] = await Promise.all([
    emailsFor(admin, [base.user_id]),
    admin.from("render_job_private").select("error_detail, log_tail, pin, direct").eq("job_id", id).maybeSingle(),
    admin.from("credit_ledger").select(LEDGER_COLUMNS).eq("job_id", id).order("created_at", { ascending: true }).limit(20),
    admin
      .from("admin_audit_log")
      .select(AUDIT_COLUMNS)
      .eq("target_type", "render_job")
      .eq("target_id", id)
      .order("created_at", { ascending: false })
      .limit(20),
  ]);
  if (priv.error) throw new QueryError(`render_job_private: ${priv.error.message}`);
  const job: AdminJobDetail = { ...base, email: emails.get(base.user_id) ?? null };
  return {
    job,
    private: (priv.data as JobPrivate) ?? null,
    ledger: rows<LedgerRow>(ledger, "credit_ledger"),
    audit: await auditWithEmails(admin, rows(audit, "admin_audit_log")),
    can: { retry: canRetry(job), refund: canRefund(job) },
  };
}

export async function findUsers(admin: SupabaseClient, query: string): Promise<AdminUserRow[]> {
  return rows<AdminUserRow>(await admin.rpc("admin_find_users", { p_query: query, p_limit: 50 }), "admin_find_users");
}

export async function userDetail(admin: SupabaseClient, id: string): Promise<UserDetailResponse | null> {
  const found = rows<AdminUserRow>(await admin.rpc("admin_find_users", { p_query: id, p_limit: 1 }), "admin_find_users");
  const user = found[0];
  if (!user) return null;
  const [plan, isAdmin, ledger, jobs, uploads, subs, txns, audit] = await Promise.all([
    admin.rpc("user_plan", { p_user_id: id }),
    admin.from("admins").select("user_id").eq("user_id", id).maybeSingle(),
    admin.from("credit_ledger").select(LEDGER_COLUMNS).eq("user_id", id).order("created_at", { ascending: false }).limit(100),
    admin.from("render_jobs").select(JOB_COLUMNS).eq("user_id", id).order("created_at", { ascending: false }).limit(25),
    admin
      .from("uploads")
      .select("id, file_name, source, status, size_bytes, reject_reason, created_at, expired_at")
      .eq("user_id", id)
      .order("created_at", { ascending: false })
      .limit(25),
    admin
      .from("billing_subscriptions")
      .select("id, plan, status, current_period_end, paid_through, canceled_at")
      .eq("user_id", id)
      .order("created_at", { ascending: false }),
    admin.from("billing_transactions").select(TXN_COLUMNS).eq("user_id", id).order("created_at", { ascending: false }).limit(25),
    admin
      .from("admin_audit_log")
      .select(AUDIT_COLUMNS)
      .eq("target_type", "user")
      .eq("target_id", id)
      .order("created_at", { ascending: false })
      .limit(25),
  ]);
  const jobRows = rows<Omit<AdminJob, "email">>(jobs, "render_jobs").map((j) => ({ ...j, email: user.email }));
  return {
    user: { ...user, live_plan: typeof plan.data === "string" ? plan.data : user.plan, is_admin: Boolean(isAdmin.data) },
    ledger: rows<LedgerRow>(ledger, "credit_ledger"),
    jobs: jobRows,
    uploads: rows<UploadRow>(uploads, "uploads"),
    subscriptions: rows<SubscriptionRow>(subs, "billing_subscriptions"),
    transactions: rows<TransactionRow>(txns, "billing_transactions"),
    audit: await auditWithEmails(admin, rows(audit, "admin_audit_log")),
  };
}

/** Outcomes that mean "a paid event did not do what it should" and deserve an operator's eye. */
export const PROBLEM_OUTCOMES = ["unmatched", "pending", "stale"] as const;

export async function billingOverview(admin: SupabaseClient): Promise<BillingResponse> {
  const [events, problems, errors, txns, adjustments] = await Promise.all([
    admin.from("billing_events").select(EVENT_COLUMNS).order("received_at", { ascending: false }).limit(50),
    admin
      .from("billing_events")
      .select(EVENT_COLUMNS)
      .in("outcome", [...PROBLEM_OUTCOMES])
      .order("received_at", { ascending: false })
      .limit(50),
    admin
      .from("billing_webhook_errors")
      .select("id, received_at, event_id, event_type, stage, code, message")
      .order("received_at", { ascending: false })
      .limit(50),
    admin.from("billing_transactions").select(TXN_COLUMNS).order("created_at", { ascending: false }).limit(50),
    admin
      .from("billing_adjustments")
      .select("id, transaction_id, user_id, action, credits, created_at")
      .order("created_at", { ascending: false })
      .limit(25),
  ]);
  return {
    events: rows<BillingEventRow>(events, "billing_events"),
    problems: rows<BillingEventRow>(problems, "billing_events"),
    errors: rows<WebhookErrorRow>(errors, "billing_webhook_errors"),
    transactions: await withEmails(admin, rows<TransactionRow>(txns, "billing_transactions")),
    adjustments: rows<AdjustmentRow>(adjustments, "billing_adjustments"),
  };
}

export async function auditLog(admin: SupabaseClient, limit: number): Promise<AuditRow[]> {
  const list = rows<Omit<AuditRow, "admin_email">>(
    await admin.from("admin_audit_log").select(AUDIT_COLUMNS).order("created_at", { ascending: false }).limit(limit),
    "admin_audit_log",
  );
  return auditWithEmails(admin, list);
}
