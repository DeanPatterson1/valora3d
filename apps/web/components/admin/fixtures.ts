import type { AdminJob, AuditRow, BillingResponse, JobDetailResponse, Overview, UserDetailResponse, AdminUserRow, WindowStats } from "@/lib/admin/types";

/**
 * Hand-written sample data for /dev/admin (design review and screenshots in Local mode). Never used by /admin.
 * Timestamps are relative to a fixed instant so the page renders the same every time.
 */
const NOW = Date.parse("2026-09-29T12:00:00Z");
const ago = (minutes: number) => new Date(NOW - minutes * 60_000).toISOString();

const U1 = "3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f";
const U2 = "7a1d2e3f-4b5c-4d6e-8f90-a1b2c3d4e5f6";
const U3 = "c0ffee00-1234-4abc-8def-0123456789ab";
const ADMIN = "0d0d0d0d-aaaa-4bbb-8ccc-dddddddddddd";

const win = (scale: number): WindowStats => ({
  since: ago(scale * 1440),
  credits: {
    granted: 1250 * scale,
    spent: 610 * scale,
    refunded: 18 * scale,
    reversed: scale > 1 ? 100 : 0,
    admin_deducted: 0,
    by_reason: { signup_grant: 400 * scale, plan_grant: 700 * scale, pack_purchase: 150 * scale, render_preview: -250 * scale, render_final: -360 * scale, render_refund: 18 * scale },
  },
  renders: {
    total: 64 * scale,
    by_status: { queued: 1, running: 2, succeeded: 55 * scale, failed: 4 * scale, cancelled: 2 * scale },
    finished: 59 * scale,
    failure_rate: 4 / 59,
    avg_render_seconds: 212.4,
    avg_wall_seconds: 301.7,
    gpu_seconds: 12_830 * scale,
    execution_seconds: 13_900 * scale,
  },
  revenue: [{ currency: "USD", gross_minor: 48_300 * scale, transactions: 21 * scale, credits_reversed: scale > 1 ? 100 : 0 }],
  adjustments: scale > 1 ? 1 : 0,
  webhook_errors: scale > 1 ? 1 : 0,
});

export const FIXTURE_OVERVIEW: Overview = {
  generated_at: new Date(NOW).toISOString(),
  signups: { today: 14, d7: 96, d30: 388, total: 1204 },
  plans: { free: 1121, creator: 64, pro: 19 },
  paying: { creator: 61, pro: 19 },
  live_renders: 3,
  windows: { d1: win(1), d7: win(7), d30: win(30) },
};

const job = (over: Partial<AdminJob> & Pick<AdminJob, "id" | "status">): AdminJob => ({
  user_id: U1,
  email: "maya@studio.example",
  project_id: "11111111-2222-4333-8444-555555555555",
  upload_id: "99999999-8888-4777-8666-555555555555",
  kind: "preview",
  stage: over.status === "succeeded" ? "done" : null,
  error: null,
  error_code: null,
  retryable: null,
  cost_credits: 3,
  refunded_credits: 0,
  attempts: 0,
  render_seconds: 198.2,
  gpu_seconds: 201.9,
  execution_ms: 214_000,
  delay_ms: 8_400,
  runpod_id: `rp-${over.id.slice(0, 6)}`,
  runpod_status: "COMPLETED",
  created_at: ago(12),
  started_at: ago(11),
  finished_at: ago(7),
  ...over,
});

export const FIXTURE_JOBS: AdminJob[] = [
  job({ id: "4e0b7f21-0000-4000-8000-000000000001", status: "running", stage: "render", render_seconds: null, gpu_seconds: null, finished_at: null, runpod_status: "IN_PROGRESS", created_at: ago(3) }),
  job({
    id: "9c3a5d02-0000-4000-8000-000000000002",
    status: "failed",
    kind: "final",
    cost_credits: 12,
    refunded_credits: 12,
    error: "The render failed on our side. Your credits were refunded.",
    error_code: "GPU_OOM",
    retryable: true,
    attempts: 1,
    user_id: U2,
    email: "jon@carsandcoffee.example",
    render_seconds: null,
    created_at: ago(26),
  }),
  job({ id: "1b7e6c33-0000-4000-8000-000000000003", status: "succeeded", kind: "final", cost_credits: 12, created_at: ago(44) }),
  job({ id: "d24f8a14-0000-4000-8000-000000000004", status: "cancelled", cost_credits: 3, error: "Cancelled while rendering.", error_code: "CANCELLED_BY_USER", retryable: false, user_id: U3, email: "ops@watchbrand.example", created_at: ago(90) }),
  job({ id: "70a9e2c5-0000-4000-8000-000000000005", status: "succeeded", created_at: ago(140) }),
  job({ id: "e8c1b3f6-0000-4000-8000-000000000006", status: "failed", error_code: "INVALID_INPUT", retryable: false, refunded_credits: 3, error: "This model could not be read.", created_at: ago(300) }),
];

export const FIXTURE_AUDIT: AuditRow[] = [
  { id: 3, admin_id: ADMIN, admin_email: "owner@valora3d.com", action: "render_refund", target_type: "render_job", target_id: FIXTURE_JOBS[3].id, reason: "Crash was on our side", detail: { refunded: 3 }, created_at: ago(35) },
  { id: 2, admin_id: ADMIN, admin_email: "owner@valora3d.com", action: "credits_adjust", target_type: "user", target_id: U2, reason: "Launch-week goodwill", detail: { amount: 50, ledger_id: 881, balance_after: 142 }, created_at: ago(180) },
  { id: 1, admin_id: ADMIN, admin_email: "owner@valora3d.com", action: "render_retry", target_type: "render_job", target_id: "a1b2c3d4-0000-4000-8000-0000000000ff", reason: null, detail: { new_job_id: FIXTURE_JOBS[4].id }, created_at: ago(1440) },
];

export const FIXTURE_JOB_DETAIL: JobDetailResponse = {
  job: {
    ...FIXTURE_JOBS[1],
    params: { prompt: "slow orbit at golden hour, low camera", tier: "final", world: "studio_soft", aspect: "16:9", duration: 10 },
    timings: { ingest: 4.1, direct: 12.8, render: 0, encode: 0 },
    warnings: [],
    outputs: null,
    watermark: false,
    watermarked: null,
    expired_at: null,
    frame: 57,
    total_frames: 240,
  },
  private: {
    error_detail: "CUDA out of memory. Tried to allocate 1.20 GiB (GPU 0; 23.65 GiB total capacity)",
    log_tail: ["Fra:56 Mem:9120.33M | Rendering 1 / 2 samples", "Fra:57 Mem:22110.02M | Rendering 1 / 2 samples", "Error: CUDA error: out of memory"],
    pin: { blender: "5.0.1", engine: "a9f3c21", image: "valora3d/worker:2026-09-28" },
    direct: null,
  },
  ledger: [
    { id: 870, user_id: U2, amount: -12, reason: "render_final", ref: `render:${FIXTURE_JOBS[1].id}`, job_id: FIXTURE_JOBS[1].id, created_at: ago(26) },
    { id: 874, user_id: U2, amount: 12, reason: "render_refund", ref: `refund:${FIXTURE_JOBS[1].id}`, job_id: FIXTURE_JOBS[1].id, created_at: ago(19) },
  ],
  audit: [],
  can: { retry: true, refund: false },
};

export const FIXTURE_USERS: AdminUserRow[] = [
  { id: U1, email: "maya@studio.example", name: "Maya", plan: "creator", created_at: ago(60 * 24 * 12), balance: 318 },
  { id: U2, email: "jon@carsandcoffee.example", name: "Jon", plan: "pro", created_at: ago(60 * 24 * 3), balance: 142 },
  { id: U3, email: "ops@watchbrand.example", name: "", plan: "free", created_at: ago(60 * 5), balance: -25 },
];

export const FIXTURE_USER_DETAIL: UserDetailResponse = {
  user: { ...FIXTURE_USERS[1], live_plan: "pro", is_admin: false },
  ledger: [
    { id: 881, user_id: U2, amount: 50, reason: "admin_adjustment", ref: "admin:credits:5d1c9e", job_id: null, created_at: ago(180) },
    ...FIXTURE_JOB_DETAIL.ledger,
    { id: 700, user_id: U2, amount: 2000, reason: "plan_grant", ref: "paddle:sub:sub_01j:1790000000:pro", job_id: null, created_at: ago(60 * 24 * 3) },
    { id: 699, user_id: U2, amount: 50, reason: "signup_grant", ref: `signup:${U2}`, job_id: null, created_at: ago(60 * 24 * 3) },
  ],
  jobs: FIXTURE_JOBS.filter((j) => j.user_id === U2),
  uploads: [
    { id: "55555555-4444-4333-8222-111111111111", file_name: "gt3rs_hero.glb", source: "upload", status: "ready", size_bytes: 48_211_004, reject_reason: null, created_at: ago(60 * 24 * 2), expired_at: null },
    { id: "55555555-4444-4333-8222-111111111112", file_name: "toycar.glb", source: "sample", status: "ready", size_bytes: 1_204_100, reject_reason: null, created_at: ago(60 * 24 * 3), expired_at: null },
  ],
  subscriptions: [{ id: "sub_01j8example", plan: "pro", status: "active", current_period_end: ago(-60 * 24 * 27), paid_through: ago(-60 * 24 * 27), canceled_at: null }],
  transactions: [
    { id: "txn_01j8examplepro", user_id: U2, kind: "subscription", plan: "pro", credits_granted: 2000, credits_reversed: 0, total_minor: 4900, currency_code: "USD", created_at: ago(60 * 24 * 3) },
  ],
  audit: [FIXTURE_AUDIT[1]],
};

export const FIXTURE_BILLING: BillingResponse = {
  events: [
    { event_id: "evt_01j8aaa", event_type: "transaction.completed", occurred_at: ago(61), received_at: ago(60), outcome: "granted", detail: null },
    { event_id: "evt_01j8aab", event_type: "subscription.updated", occurred_at: ago(61), received_at: ago(60), outcome: "synced", detail: null },
    { event_id: "evt_01j8aac", event_type: "transaction.completed", occurred_at: ago(400), received_at: ago(399), outcome: "unmatched", detail: "no user for sub_01j9zzz" },
  ],
  problems: [{ event_id: "evt_01j8aac", event_type: "transaction.completed", occurred_at: ago(400), received_at: ago(399), outcome: "unmatched", detail: "no user for sub_01j9zzz" }],
  errors: [{ id: 4, received_at: ago(15), event_id: "evt_01j8zzz", event_type: "adjustment.created", stage: "apply", code: "P0001", message: "reversal for txn_01j8q before its payment was applied" }],
  transactions: [
    { id: "txn_01j8examplepro", user_id: U2, email: "jon@carsandcoffee.example", kind: "subscription", plan: "pro", credits_granted: 2000, credits_reversed: 0, total_minor: 4900, currency_code: "USD", created_at: ago(60 * 24 * 3) },
    { id: "txn_01j8examplepack", user_id: U1, email: "maya@studio.example", kind: "pack", plan: null, credits_granted: 500, credits_reversed: 100, total_minor: 1900, currency_code: "USD", created_at: ago(60 * 24 * 6) },
  ],
  adjustments: [{ id: "adj_01j8example", transaction_id: "txn_01j8examplepack", user_id: U1, action: "refund", credits: -100, created_at: ago(60 * 24 * 5) }],
};
