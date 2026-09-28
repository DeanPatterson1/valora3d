import { RenderJobParamsSchema, type RenderJob } from "@/lib/schema";
import { rowStatus, type DbJobStatus } from "./contract";

/** `public.render_jobs` as stored (init migration + 20260928140000_render_pipeline.sql). */
export type RenderJobRow = {
  id: string;
  user_id: string;
  project_id: string;
  version_id: string | null;
  upload_id: string | null;
  kind: "preview" | "final";
  status: DbJobStatus;
  params: unknown;
  runpod_id: string | null;
  output_keys: string[];
  cost_credits: number;
  error: string | null;
  error_code: string | null;
  retryable: boolean | null;
  stage: string | null;
  frame: number;
  total_frames: number | null;
  runpod_status: string | null;
  outputs: unknown;
  video: unknown;
  timings: unknown;
  warnings: unknown;
  render_seconds: number | null;
  gpu_seconds: number | null;
  delay_ms: number | null;
  execution_ms: number | null;
  attempts: number;
  refunded_credits: number;
  idempotency_key: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
  submitted_at: string | null;
  last_polled_at: string | null;
  notified_at: string | null;
  /** Asked of the worker, from the plan at creation (20260928150000_plan_limits_v2.sql). */
  watermark?: boolean;
  /** What the worker reports it drew; null until it succeeds. */
  watermarked?: boolean | null;
  /** Days the outputs are kept after the job finishes, from the plan at creation. */
  retention_days?: number;
  /** Set once the outputs were deleted by the retention sweep. */
  expired_at?: string | null;
};

const DAY_MS = 24 * 3600 * 1000;

/** When a finished job's outputs expire (finished_at + retention_days), or null for a live job. */
export function expiresAtMs(row: Pick<RenderJobRow, "status" | "finished_at" | "retention_days">): number | null {
  if (!isTerminalRow(row) || !row.finished_at || !row.retention_days) return null;
  return Date.parse(row.finished_at) + row.retention_days * DAY_MS;
}

export const TERMINAL_DB: readonly DbJobStatus[] = ["succeeded", "failed", "cancelled"];
export const isTerminalRow = (row: Pick<RenderJobRow, "status">) => TERMINAL_DB.includes(row.status);

const ms = (iso: string | null) => (iso ? Date.parse(iso) : null);

/**
 * Row -> the studio's RenderJob. Only user-safe fields cross: the error message (never the operator detail),
 * progress, params, prices. `urls` are short-lived presigned GETs minted by the caller for a finished job.
 */
export function rowToRenderJob(row: RenderJobRow, urls: { video?: string | null; poster?: string | null } = {}): RenderJob {
  const params = RenderJobParamsSchema.safeParse(row.params);
  const status = rowStatus(row.status, row.stage);
  const expired = Boolean(row.expired_at);
  const total = row.total_frames && row.total_frames > 0 ? row.total_frames : 1;
  return {
    id: row.id,
    projectId: row.project_id,
    versionId: row.version_id,
    kind: row.kind,
    target: "cloud",
    status,
    frame: Math.min(row.frame ?? 0, total),
    totalFrames: total,
    error: status === "FAILED" || status === "CANCELLED" ? (row.error ?? null) : null,
    errorCode: row.error_code,
    resultUrl: status === "COMPLETE" && !expired ? (urls.video ?? null) : null,
    posterUrl: status === "COMPLETE" && !expired ? (urls.poster ?? null) : null,
    expired,
    expiresAt: expiresAtMs(row),
    ...(params.success ? { params: params.data } : {}),
    costCredits: row.cost_credits,
    refundedCredits: row.refunded_credits ?? 0,
    createdAt: ms(row.created_at) ?? 0,
    finishedAt: ms(row.finished_at),
  };
}
