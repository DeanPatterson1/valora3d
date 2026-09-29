/**
 * Shapes the /api/admin routes return and the /admin screens render. Rows are the database's own column
 * names (snake_case), trimmed to what the console shows. Never includes webhook tokens or secrets.
 */

export type WindowKey = "d1" | "d7" | "d30";

export type WindowStats = {
  since: string;
  credits: {
    granted: number;
    spent: number;
    refunded: number;
    reversed: number;
    admin_deducted: number;
    by_reason: Record<string, number>;
  };
  renders: {
    total: number;
    by_status: Record<string, number>;
    finished: number;
    failure_rate: number | null;
    avg_render_seconds: number | null;
    avg_wall_seconds: number | null;
    gpu_seconds: number;
    execution_seconds: number;
  };
  revenue: { currency: string; gross_minor: number; transactions: number; credits_reversed: number }[];
  adjustments: number;
  webhook_errors: number;
};

export type Overview = {
  generated_at: string;
  signups: { today: number; d7: number; d30: number; total: number };
  plans: Record<string, number>;
  paying: Record<string, number>;
  live_renders: number;
  windows: Record<WindowKey, WindowStats>;
};

export const JOB_STATUSES = ["queued", "running", "succeeded", "failed", "cancelled"] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export type AdminJob = {
  id: string;
  user_id: string;
  email: string | null;
  project_id: string;
  upload_id: string | null;
  kind: "preview" | "final";
  status: JobStatus;
  stage: string | null;
  error: string | null;
  error_code: string | null;
  retryable: boolean | null;
  cost_credits: number;
  refunded_credits: number;
  attempts: number;
  render_seconds: number | null;
  gpu_seconds: number | null;
  execution_ms: number | null;
  delay_ms: number | null;
  runpod_id: string | null;
  runpod_status: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type AdminJobDetail = AdminJob & {
  params: unknown;
  timings: unknown;
  warnings: unknown;
  outputs: unknown;
  watermark: boolean | null;
  watermarked: boolean | null;
  expired_at: string | null;
  frame: number;
  total_frames: number | null;
};

export type JobPrivate = { error_detail: string | null; log_tail: unknown; pin: unknown; direct: unknown } | null;

export type LedgerRow = {
  id: number;
  user_id: string;
  amount: number;
  reason: string;
  ref: string;
  job_id: string | null;
  created_at: string;
};

export type AuditRow = {
  id: number;
  admin_id: string;
  admin_email: string | null;
  action: "credits_adjust" | "render_refund" | "render_retry";
  target_type: "user" | "render_job";
  target_id: string;
  reason: string | null;
  detail: Record<string, unknown>;
  created_at: string;
};

export type JobDetailResponse = {
  job: AdminJobDetail;
  private: JobPrivate;
  ledger: LedgerRow[];
  audit: AuditRow[];
  /** What the console may offer, decided server-side with the same rules the actions enforce. */
  can: { retry: boolean; refund: boolean };
};

export type AdminUserRow = {
  id: string;
  email: string;
  name: string;
  plan: string;
  created_at: string;
  balance: number;
};

export type UploadRow = {
  id: string;
  file_name: string;
  source: string;
  status: string;
  size_bytes: number;
  reject_reason: string | null;
  created_at: string;
  expired_at: string | null;
};

export type SubscriptionRow = {
  id: string;
  plan: string;
  status: string;
  current_period_end: string | null;
  paid_through: string | null;
  canceled_at: string | null;
};

export type TransactionRow = {
  id: string;
  /** Null once the account was deleted (the payment record is kept, detached). */
  user_id: string | null;
  email?: string | null;
  kind: string;
  plan: string | null;
  credits_granted: number;
  credits_reversed: number;
  total_minor: number;
  currency_code: string | null;
  created_at: string;
};

export type UserDetailResponse = {
  user: AdminUserRow & { live_plan: string; is_admin: boolean };
  ledger: LedgerRow[];
  jobs: AdminJob[];
  uploads: UploadRow[];
  subscriptions: SubscriptionRow[];
  transactions: TransactionRow[];
  audit: AuditRow[];
};

export type BillingEventRow = {
  event_id: string;
  event_type: string;
  occurred_at: string | null;
  received_at: string;
  outcome: string;
  detail: string | null;
};

export type WebhookErrorRow = {
  id: number;
  received_at: string;
  event_id: string | null;
  event_type: string | null;
  stage: string;
  code: string | null;
  message: string | null;
};

export type AdjustmentRow = {
  id: string;
  transaction_id: string;
  user_id: string | null;
  action: string;
  credits: number;
  created_at: string;
};

/** A refund / chargeback that had nothing to take back (billing_unapplied_adjustments). */
export type UnappliedAdjustmentRow = {
  adjustment_id: string;
  transaction_id: string;
  action: string;
  /** no_transaction: that payment never granted anything (yet). account_deleted: its account is gone. */
  reason: "no_transaction" | "account_deleted";
  received_at: string;
  resolved_at: string | null;
  resolved_outcome: string | null;
};

export type BillingResponse = {
  events: BillingEventRow[];
  problems: BillingEventRow[];
  errors: WebhookErrorRow[];
  transactions: TransactionRow[];
  adjustments: AdjustmentRow[];
  unapplied: UnappliedAdjustmentRow[];
};

/** Only a failed job the worker marked retryable is offered a retry. */
export function canRetry(job: Pick<AdminJob, "status" | "retryable" | "upload_id">): boolean {
  return job.status === "failed" && job.retryable === true && job.upload_id !== null;
}

/** refund_render_job refunds only failed / cancelled jobs, and only what is still charged. */
export function canRefund(job: Pick<AdminJob, "status" | "cost_credits" | "refunded_credits">): boolean {
  return (job.status === "failed" || job.status === "cancelled") && job.cost_credits > (job.refunded_credits ?? 0);
}

/**
 * The idempotency key an admin retry of `jobId` is created under: one retry job per failed job, ever. It lives
 * in the `admin:` namespace: the `:` is outside the alphabet POST /api/renders accepts from users
 * (`^[A-Za-z0-9_-]{8,128}$`), so no user can pre-create a job under this key to block or hijack the retry.
 */
export const retryKey = (jobId: string) => `admin:retry:${jobId}`;

/** The audit request id of that retry (admin_audit_log.request_id, unique). */
export const retryRequestId = (jobId: string) => `retry:${jobId}`;
