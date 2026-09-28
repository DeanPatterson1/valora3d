import {
  OUTPUT_CONTENT_TYPES,
  TIER_POLICY,
  interpretStatus,
  jobDeadlineMs,
  outputKey,
  presignLifetimes,
  siteFailure,
  type FailedResult,
  type RunpodStatusResponse,
  type SucceededResult,
} from "@/lib/render/contract";
import { renderCost } from "@/lib/render/cost";
import { isTerminalRow, type RenderJobRow } from "@/lib/render/jobRow";
import type { RenderParams, WorkerParams } from "@/lib/render/params";
import type { PlanId, RenderPlanLimits } from "@/lib/render/planLimits";
import type { RenderNotifier } from "./notify";
import type { RunpodApi } from "./runpod";
import { hashWebhookToken, newWebhookToken, verifyWebhookToken } from "./webhookToken";

/**
 * The render job lifecycle, server-side: create (debit) -> submit to RunPod -> progress (webhook, poll,
 * sweeper) -> one terminal transition (finish_render_job: outputs, or failure + refund). Every dependency is
 * injected so the whole state machine is unit-tested without Supabase, R2 or RunPod.
 */

export type UploadForRender = {
  id: string;
  user_id: string;
  status: "pending" | "ready" | "rejected";
  source: "upload" | "sample";
  r2_key: string | null;
  sample_url: string | null;
};

export type PrivatePatch = {
  webhook_token_hash?: string;
  error_detail?: string | null;
  log_tail?: string[] | null;
  pin?: Record<string, unknown> | null;
  direct?: Record<string, unknown> | null;
};

export type LivePatch = Partial<
  Pick<RenderJobRow, "status" | "stage" | "frame" | "total_frames" | "runpod_status" | "started_at" | "last_polled_at">
>;

export type FinishArgs = {
  jobId: string;
  runpodId: string | null;
  status: "succeeded" | "failed" | "cancelled";
  error: string | null;
  errorCode: string | null;
  retryable: boolean | null;
  result: Record<string, unknown>;
  refund: boolean;
};

export type CreateJobArgs = {
  userId: string;
  projectId: string;
  versionId: string | null;
  uploadId: string;
  kind: "preview" | "final";
  params: RenderParams;
  cost: number;
  idempotencyKey: string;
};

export type StoreError = { code?: string; message: string };

/** Persistence, implemented over the service-role Supabase client (renderStore.ts) and faked in tests. */
export interface RenderStore {
  getJob(id: string): Promise<RenderJobRow | null>;
  findByIdempotencyKey(userId: string, key: string): Promise<RenderJobRow | null>;
  getWebhookHash(jobId: string): Promise<string | null>;
  /** `create_render_job`: the row and the debit in one transaction. */
  createJob(args: CreateJobArgs): Promise<{ row: RenderJobRow } | { error: StoreError }>;
  putPrivate(jobId: string, patch: PrivatePatch): Promise<void>;
  /** Sets runpod_id on a job that has none yet. False when another submitter got there first. */
  markSubmitted(jobId: string, runpodId: string, runpodStatus: string): Promise<boolean>;
  /** Progress on a live job, only while it is still on `runpodId`. */
  updateLive(jobId: string, runpodId: string, patch: LivePatch): Promise<void>;
  /** `finish_render_job`: -1 when nothing moved, else credits refunded by this call. */
  finish(args: FinishArgs): Promise<number>;
  /** Claims the one automatic retry: clears runpod_id (from `oldRunpodId`) and bumps attempts. */
  claimRetry(jobId: string, oldRunpodId: string, attempts: number): Promise<boolean>;
  listStale(updatedBefore: string, limit: number): Promise<RenderJobRow[]>;
  markNotified(jobId: string): Promise<void>;
  getUpload(uploadId: string, userId: string): Promise<UploadForRender | null>;
  /** The caller's live entitlement (`user_plan_limits`, service role). create_render_job enforces it again. */
  getPlanLimits(userId: string): Promise<{ plan: PlanId; limits: RenderPlanLimits }>;
  countActive(userId: string): Promise<number>;
  countSince(userId: string, sinceIso: string): Promise<number>;
}

export interface R2Signer {
  presignGet(key: string, expiresSeconds: number, response: { contentType: string; disposition: string } | null): Promise<string>;
  presignOutputPut(key: string, contentType: string, expiresSeconds: number): Promise<string>;
}

export type PipelineDeps = {
  store: RenderStore;
  runpod: RunpodApi | null;
  r2: R2Signer | null;
  notifier: RenderNotifier;
  now?: () => number;
  newToken?: () => string;
  log?: (message: string, extra?: Record<string, unknown>) => void;
};

export type PipelineError = { status: number; code: string; message: string; job?: RenderJobRow };
export type PipelineResult<T> = { ok: true; value: T } | ({ ok: false } & PipelineError);

const err = <T>(status: number, code: string, message: string, job?: RenderJobRow): PipelineResult<T> => ({
  ok: false,
  status,
  code,
  message,
  ...(job ? { job } : {}),
});

/** Poll RunPod from GET /api/renders/:id at most this often per job. */
export const POLL_MIN_INTERVAL_MS = 10_000;
/** A job not heard from for this long is re-polled by the sweeper. */
export const STALE_AFTER_MS = 5 * 60_000;
/** A job whose RunPod submission never recorded an id is given up (and refunded) after this long. */
export const ORPHAN_AFTER_MS = 5 * 60_000;
/** Renders per user per day, whatever their outcome (abuse ceiling, not a plan limit). */
export const DAILY_RENDER_CAP = 50;
/** Retryable failures are resubmitted this many times (worker README: "Auto-retry once"). */
export const MAX_AUTO_RETRIES = 1;

/** Where the worker downloads the model from. Samples ship in /public and are mirrored in R2 under samples/. */
export function glbKeyFor(upload: UploadForRender): string | null {
  if (upload.source === "upload") return upload.r2_key;
  const m = upload.sample_url?.match(/^\/samples\/([A-Za-z0-9_-]+\.glb)$/);
  return m ? `samples/${m[1]}` : null;
}

export class RenderPipeline {
  private readonly now: () => number;
  private readonly newToken: () => string;
  private readonly log: (message: string, extra?: Record<string, unknown>) => void;

  constructor(private readonly deps: PipelineDeps) {
    this.now = deps.now ?? Date.now;
    this.newToken = deps.newToken ?? newWebhookToken;
    this.log = deps.log ?? ((message, extra) => console.warn(`[render] ${message}`, extra ?? ""));
  }

  private get store() {
    return this.deps.store;
  }

  // ------------------------------------------------------------------ create

  async create(
    input: {
      userId: string;
      projectId: string;
      uploadId: string;
      versionId: string | null;
      params: RenderParams;
      idempotencyKey: string;
    },
    origin: string,
  ): Promise<PipelineResult<{ row: RenderJobRow; replay: boolean }>> {
    const { runpod, r2 } = this.deps;
    if (!runpod) return err(503, "not_connected", "Rendering is currently unavailable. Please try again later.");
    if (!r2) return err(503, "not_configured", "File storage is not configured.");

    // A retried click returns the job it already made (and charged), before any limit is counted again.
    const existing = await this.store.findByIdempotencyKey(input.userId, input.idempotencyKey);
    if (existing) {
      if (existing.project_id !== input.projectId) return err(409, "conflict", "That request was already made with different details.");
      return { ok: true, value: { row: existing, replay: true } };
    }

    const upload = await this.store.getUpload(input.uploadId, input.userId);
    if (!upload || upload.status !== "ready") return err(404, "not_found", "The model for this render was not found. Upload it again.");
    const glbKey = glbKeyFor(upload);
    if (!glbKey) return err(400, "invalid_request", "This model cannot be rendered.");

    // Early, friendly answers from the live plan. The authoritative check is create_render_job's, under the
    // credit lock (a concurrent request cannot slip past the concurrency limit); both read user_plan_limits.
    const tier = input.params.tier;
    const { limits } = await this.store.getPlanLimits(input.userId);
    if (!limits.tiers.includes(tier)) return err(403, "plan_required", PLAN_REQUIRED_MESSAGE);
    if ((await this.store.countActive(input.userId)) >= limits.maxActiveJobs) {
      return err(429, "too_many_active", tooManyActiveMessage(limits.maxActiveJobs));
    }
    const since = new Date(this.now() - 24 * 3600_000).toISOString();
    if ((await this.store.countSince(input.userId, since)) >= DAILY_RENDER_CAP) {
      return err(429, "rate_limited", "You've reached today's render limit. Try again tomorrow.");
    }

    const created = await this.store.createJob({
      userId: input.userId,
      projectId: input.projectId,
      versionId: input.versionId,
      uploadId: input.uploadId,
      kind: tier,
      params: input.params,
      cost: renderCost(tier),
      idempotencyKey: input.idempotencyKey,
    });
    if ("error" in created) return { ok: false, ...sqlError(created.error) };
    const row = created.row;
    // A concurrent duplicate of the same key: the other request is submitting it.
    if (row.runpod_id || isTerminalRow(row)) return { ok: true, value: { row, replay: true } };

    const submitted = await this.submit(row, glbKey, origin);
    if (!submitted.ok) {
      await this.finishFailed(row, null, siteFailure("SUBMIT_FAILED", submitted.detail));
      const after = (await this.store.getJob(row.id)) ?? row;
      return err(502, "render_unavailable", "The render could not be started. Your credits were refunded. Try again in a minute.", after);
    }
    return { ok: true, value: { row: (await this.store.getJob(row.id)) ?? row, replay: false } };
  }

  /** Mints the presigned URLs and a fresh webhook token, and hands the job to RunPod. */
  private async submit(row: RenderJobRow, glbKey: string, origin: string): Promise<{ ok: true; runpodId: string } | { ok: false; detail: string }> {
    const { runpod, r2 } = this.deps;
    if (!runpod || !r2) return { ok: false, detail: "renderer not configured" };
    try {
      const token = this.newToken();
      // The hash is stored before RunPod can possibly call back with the token.
      await this.store.putPrivate(row.id, { webhook_token_hash: await hashWebhookToken(token) });
      const life = presignLifetimes(row.kind);
      const [glbUrl, videoUrl, posterUrl] = await Promise.all([
        r2.presignGet(glbKey, life.getSeconds, null),
        r2.presignOutputPut(outputKey(row.user_id, row.id, "video"), OUTPUT_CONTENT_TYPES.video, life.putSeconds),
        r2.presignOutputPut(outputKey(row.user_id, row.id, "poster"), OUTPUT_CONTENT_TYPES.poster, life.putSeconds),
      ]);
      const webhook = new URL("/api/runpod/webhook", origin);
      webhook.searchParams.set("job", row.id);
      webhook.searchParams.set("t", token);
      const res = await runpod.run({
        input: { job_id: row.id, glb_url: glbUrl, output_put_urls: { video: videoUrl, poster: posterUrl }, params: workerParams(row) },
        webhook: webhook.toString(),
        policy: { ...TIER_POLICY[row.kind] },
      });
      const recorded = await this.store.markSubmitted(row.id, res.id, res.status);
      if (!recorded) {
        // A concurrent request with the same idempotency key submitted this job first; drop our duplicate.
        // (Its webhook token may now be ours and fail the check: the sweeper's poll still finishes it.)
        await runpod.cancel(res.id).catch(() => null);
        return { ok: true, runpodId: res.id };
      }
      return { ok: true, runpodId: res.id };
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      this.log("submit failed", { job: row.id, detail });
      return { ok: false, detail };
    }
  }

  // ------------------------------------------------------------------ status

  /**
   * Applies one RunPod status payload (already fetched with the API key, never the webhook body) to the job.
   * Returns the row as it stands afterwards.
   */
  async apply(row: RenderJobRow, res: RunpodStatusResponse | null, origin: string): Promise<RenderJobRow> {
    if (isTerminalRow(row) || !row.runpod_id) return row;
    const runpodId = row.runpod_id;
    const now = new Date(this.now()).toISOString();

    if (res === null) {
      // RunPod no longer knows the id. Only give up once the job cannot be alive anywhere.
      const submitted = Date.parse(row.submitted_at ?? row.created_at);
      if (this.now() > jobDeadlineMs(row.kind, submitted)) {
        await this.finishFailed(row, runpodId, siteFailure("RENDER_LOST", "RunPod status 404 past the job deadline"));
      } else {
        await this.store.updateLive(row.id, runpodId, { last_polled_at: now });
      }
      return (await this.store.getJob(row.id)) ?? row;
    }
    if (typeof res.id === "string" && res.id !== runpodId) {
      this.log("status for another attempt ignored", { job: row.id });
      return row;
    }

    const it = interpretStatus(res, row.id);
    switch (it.kind) {
      case "ignore":
        this.log("status ignored", { job: row.id, reason: it.reason });
        return row;
      case "queued":
        await this.store.updateLive(row.id, runpodId, { runpod_status: "IN_QUEUE", last_polled_at: now });
        break;
      case "running":
        await this.store.updateLive(row.id, runpodId, {
          status: "running",
          runpod_status: "IN_PROGRESS",
          ...(row.started_at ? {} : { started_at: now }),
          ...(it.stage ? { stage: it.stage } : {}),
          ...(it.frame !== null ? { frame: it.frame } : {}),
          ...(it.totalFrames ? { total_frames: it.totalFrames } : {}),
          last_polled_at: now,
        });
        break;
      case "succeeded":
        await this.finishSucceeded(row, runpodId, it.result, res);
        break;
      case "failed": {
        const retried = !it.cancelled && it.result.retryable && (await this.retry(row, runpodId, it.result, origin));
        if (!retried) await this.finishFailed(row, runpodId, it.result, res, it.cancelled ? "cancelled" : "failed");
        break;
      }
    }
    return (await this.store.getJob(row.id)) ?? row;
  }

  private async finishSucceeded(row: RenderJobRow, runpodId: string, r: SucceededResult, res: RunpodStatusResponse) {
    // The job asked for a watermark (the plan's decision) but the worker says it did not draw one (e.g. its font
    // is missing): keep the render, but record it on the job and in the log so an operator sees it.
    const unmarked = row.watermark === true && r.watermarked !== true;
    const warnings = unmarked ? [...r.warnings, "watermark requested but not applied by the worker"].slice(-20) : r.warnings;
    if (unmarked) this.log("watermark missing on a watermarked job", { job: row.id, reported: r.watermarked });
    const moved = await this.store.finish({
      jobId: row.id,
      runpodId,
      status: "succeeded",
      error: null,
      errorCode: null,
      retryable: null,
      refund: false,
      result: {
        runpod_status: "COMPLETED",
        stage: "done",
        ...(r.frames ? { frame: r.frames, total_frames: r.frames } : {}),
        outputs: r.outputs,
        video: r.video,
        timings: r.timings,
        warnings,
        ...(r.watermarked !== null ? { watermarked: r.watermarked } : {}),
        render_seconds: r.renderSeconds,
        gpu_seconds: r.gpuSeconds,
        ...runpodTimes(res),
        output_keys: [outputKey(row.user_id, row.id, "video"), outputKey(row.user_id, row.id, "poster")],
      },
    });
    if (moved < 0) return; // a duplicate webhook or a late poll: the first one already did this
    await this.store.putPrivate(row.id, { pin: r.pin, direct: r.direct }).catch(() => {});
    try {
      await this.deps.notifier.notifyRenderReady(row.user_id, row.id);
      await this.store.markNotified(row.id);
    } catch (error) {
      this.log("render-ready mail failed", { job: row.id, detail: error instanceof Error ? error.message : String(error) });
    }
  }

  private async finishFailed(
    row: RenderJobRow,
    runpodId: string | null,
    r: FailedResult,
    res?: RunpodStatusResponse,
    status: "failed" | "cancelled" = "failed",
  ): Promise<number> {
    const refunded = await this.store.finish({
      jobId: row.id,
      runpodId,
      status,
      error: r.errorMessage,
      errorCode: r.errorCode,
      retryable: r.retryable,
      refund: true,
      result: {
        runpod_status: res ? String(res.status ?? "") || null : null,
        timings: r.timings,
        warnings: r.warnings,
        ...(res ? runpodTimes(res) : {}),
      },
    });
    if (refunded >= 0 && (r.errorDetail || r.logTail || r.pin)) {
      await this.store.putPrivate(row.id, { error_detail: r.errorDetail, log_tail: r.logTail, pin: r.pin }).catch(() => {});
    }
    return refunded;
  }

  /** One automatic resubmission of a retryable failure, on the same debit. False => finish as failed. */
  private async retry(row: RenderJobRow, runpodId: string, r: FailedResult, origin: string): Promise<boolean> {
    if ((row.attempts ?? 0) >= MAX_AUTO_RETRIES || !row.upload_id) return false;
    const upload = await this.store.getUpload(row.upload_id, row.user_id);
    const glbKey = upload && upload.status === "ready" ? glbKeyFor(upload) : null;
    if (!glbKey) return false;
    // Only one caller (webhook, poll or sweeper) may claim the retry for this attempt.
    if (!(await this.store.claimRetry(row.id, runpodId, row.attempts ?? 0))) return true;
    await this.store.putPrivate(row.id, { error_detail: r.errorDetail, log_tail: r.logTail, pin: r.pin }).catch(() => {});
    const claimed: RenderJobRow = { ...row, runpod_id: null, attempts: (row.attempts ?? 0) + 1, status: "queued" };
    const submitted = await this.submit(claimed, glbKey, origin);
    if (!submitted.ok) await this.finishFailed(claimed, null, r);
    this.log("auto-retry", { job: row.id, code: r.errorCode, resubmitted: submitted.ok });
    return true;
  }

  /**
   * Fresh state for GET /api/renders/:id: polls RunPod when the row has not been refreshed recently, so the
   * studio sees progress even without webhooks (RunPod only calls back at the end).
   */
  async refresh(row: RenderJobRow, origin: string, force = false): Promise<RenderJobRow> {
    if (isTerminalRow(row)) return row;
    if (!row.runpod_id) {
      // updated_at, not created_at: a claimed auto-retry is legitimately unsubmitted for a moment.
      if (this.now() - Date.parse(row.updated_at) > ORPHAN_AFTER_MS) {
        await this.finishFailed(row, null, siteFailure("SUBMIT_FAILED", "no RunPod id recorded"));
        return (await this.store.getJob(row.id)) ?? row;
      }
      return row;
    }
    const last = row.last_polled_at ? Date.parse(row.last_polled_at) : 0;
    if (!force && this.now() - last < POLL_MIN_INTERVAL_MS) return row;
    if (!this.deps.runpod) return row;
    let res: RunpodStatusResponse | null;
    try {
      res = await this.deps.runpod.status(row.runpod_id);
    } catch (error) {
      this.log("status poll failed", { job: row.id, detail: error instanceof Error ? error.message : String(error) });
      return row;
    }
    return this.apply(row, res, origin);
  }

  // ------------------------------------------------------------------ cancel

  /** Cancels at RunPod. Credits come back only if the GPU had not started on it. */
  async cancel(row: RenderJobRow, origin: string): Promise<PipelineResult<RenderJobRow>> {
    if (isTerminalRow(row)) return err(409, "already_finished", "This render has already finished.", row);
    const runpod = this.deps.runpod;
    if (!row.runpod_id || !runpod) {
      await this.finishFailed(row, row.runpod_id, { ...siteFailure("RUNPOD_CANCELLED"), errorMessage: "Cancelled. Your credits were refunded." }, undefined, "cancelled");
      return { ok: true, value: (await this.store.getJob(row.id)) ?? row };
    }
    let before: RunpodStatusResponse | null = null;
    try {
      before = await runpod.status(row.runpod_id);
    } catch {
      return err(503, "render_unavailable", "Couldn't reach the render service. Try again in a moment.", row);
    }
    const it = before ? interpretStatus(before, row.id) : null;
    if (it && (it.kind === "succeeded" || it.kind === "failed")) {
      // Finished at RunPod already: record that instead of cancelling.
      const after = await this.apply(row, before, origin);
      return err(409, "already_finished", "This render has already finished.", after);
    }
    try {
      await runpod.cancel(row.runpod_id);
    } catch {
      return err(503, "render_unavailable", "Couldn't reach the render service. Try again in a moment.", row);
    }
    const started = it?.kind === "running" || row.status === "running";
    await this.store.finish({
      jobId: row.id,
      runpodId: row.runpod_id,
      status: "cancelled",
      error: started ? "Cancelled while rendering. Credits aren't refunded once the GPU has started." : "Cancelled. Your credits were refunded.",
      errorCode: "CANCELLED_BY_USER",
      retryable: false,
      refund: !started,
      result: { runpod_status: "CANCELLED" },
    });
    return { ok: true, value: (await this.store.getJob(row.id)) ?? row };
  }

  // ------------------------------------------------------------------ webhook

  /**
   * POST /api/runpod/webhook?job=<id>&t=<token>. The body is never trusted: it only names which RunPod
   * attempt called. The token is checked in constant time, then the status is re-read with the API key.
   * Returns the HTTP status to answer with (non-2xx makes RunPod retry).
   */
  async webhook(jobId: string | null, token: string | null, body: RunpodStatusResponse | null, origin: string): Promise<{ status: number; note: string }> {
    if (!jobId || !/^[0-9a-f-]{36}$/i.test(jobId)) return { status: 401, note: "unauthorized" };
    const [row, hash] = await Promise.all([this.store.getJob(jobId), this.store.getWebhookHash(jobId)]);
    // One answer for "no such job" and "wrong token": nothing to probe.
    if (!row || !(await verifyWebhookToken(token, hash))) return { status: 401, note: "unauthorized" };
    if (isTerminalRow(row)) return { status: 200, note: "already final" };
    if (!row.runpod_id) return { status: 503, note: "not yet submitted" };
    if (body && typeof body.id === "string" && body.id !== row.runpod_id) return { status: 200, note: "stale attempt" };
    if (!this.deps.runpod) return { status: 503, note: "renderer not configured" };
    let res: RunpodStatusResponse | null;
    try {
      res = await this.deps.runpod.status(row.runpod_id);
    } catch {
      return { status: 503, note: "status unavailable" };
    }
    await this.apply(row, res, origin);
    return { status: 200, note: "applied" };
  }

  // ------------------------------------------------------------------ sweeper

  /** Re-polls live jobs nobody has heard from in STALE_AFTER_MS: covers lost webhooks and dropped submits. */
  async sweep(origin: string, limit = 25): Promise<{ checked: number; finished: number }> {
    const before = new Date(this.now() - STALE_AFTER_MS).toISOString();
    const rows = await this.store.listStale(before, limit);
    let finished = 0;
    for (const row of rows) {
      try {
        const after = await this.refresh(row, origin, true);
        if (isTerminalRow(after)) finished++;
      } catch (error) {
        this.log("sweep failed for job", { job: row.id, detail: error instanceof Error ? error.message : String(error) });
      }
    }
    return { checked: rows.length, finished };
  }
}

/**
 * The stored params as the worker contract's `params` (no nulls, no site-only keys), plus `watermark` from the
 * job row: stamped from the plan by create_render_job, never read from the stored (browser) params. Sent only
 * when true; the worker's default is false.
 */
export function workerParams(row: Pick<RenderJobRow, "params" | "kind" | "watermark">): WorkerParams {
  const p = (row.params && typeof row.params === "object" ? row.params : {}) as Record<string, unknown>;
  const out: Record<string, unknown> = { prompt: typeof p.prompt === "string" ? p.prompt : "", tier: row.kind };
  for (const k of ["world", "aspect", "seed", "duration", "paint", "finish"] as const) {
    if (p[k] !== undefined && p[k] !== null) out[k] = p[k];
  }
  if (row.watermark === true) out.watermark = true;
  return out as WorkerParams;
}

const PLAN_REQUIRED_MESSAGE = "Final renders are part of the Creator and Pro plans. Render a preview, or upgrade.";

function tooManyActiveMessage(max: number): string {
  return max === 1
    ? "You already have a render in progress. Wait for it to finish, or cancel it."
    : `You already have ${max} renders in progress. Wait for one to finish.`;
}

function runpodTimes(res: RunpodStatusResponse): { delay_ms?: number; execution_ms?: number } {
  const out: { delay_ms?: number; execution_ms?: number } = {};
  if (typeof res.delayTime === "number" && Number.isFinite(res.delayTime)) out.delay_ms = Math.round(res.delayTime);
  if (typeof res.executionTime === "number" && Number.isFinite(res.executionTime)) out.execution_ms = Math.round(res.executionTime);
  return out;
}

/** SQL raise codes from create_render_job (see lib/server/api.ts sqlErrorResponse). */
function sqlError(e: StoreError): PipelineError {
  if (e.code === "P0001" && e.message.startsWith("plan_required")) return { status: 403, code: "plan_required", message: PLAN_REQUIRED_MESSAGE };
  if (e.code === "P0001" && e.message.startsWith("too_many_active")) {
    const max = Number(e.message.match(/max (\d+)/)?.[1] ?? "1");
    return { status: 429, code: "too_many_active", message: tooManyActiveMessage(max) };
  }
  if (e.code === "P0001" && e.message.startsWith("insufficient_credits")) {
    const m = e.message.match(/need (\d+), have (-?\d+)/);
    return { status: 402, code: "insufficient_credits", message: m ? `You need ${m[1]} credits but have ${m[2]}.` : "Not enough credits." };
  }
  if (e.code === "P0002") return { status: 404, code: "not_found", message: "The project or model was not found." };
  if (e.code === "23505") return { status: 409, code: "conflict", message: "That request was already made with different details." };
  if (e.code === "22023") return { status: 400, code: "invalid_request", message: "The request is not valid." };
  return { status: 500, code: "server", message: "Something went wrong on our side." };
}
