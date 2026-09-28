import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import type { RenderJobRow } from "@/lib/render/jobRow";
import { renderCost } from "@/lib/render/cost";
import { normalizeParams, type RenderParams } from "@/lib/render/params";
import type { PlanId } from "@/lib/render/planLimits";
import { WorkerParamsSchema } from "@/lib/render/params";
import { PLAN_LIMITS } from "@/lib/pricing";
import type { RunpodStatusResponse } from "@/lib/render/contract";
import {
  RenderPipeline,
  glbKeyFor,
  workerParams,
  type CreateJobArgs,
  type FinishArgs,
  type LivePatch,
  type PrivatePatch,
  type R2Signer,
  type RenderStore,
  type StoreError,
  type UploadForRender,
} from "./renderPipeline";
import type { RunpodApi, RunpodRunBody } from "./runpod";
import { hashWebhookToken } from "./webhookToken";

const USER = "11111111-1111-1111-1111-111111111111";
const PROJECT = "aaaaaaaa-0000-0000-0000-000000000001";
const UPLOAD = "cccccccc-0000-0000-0000-000000000001";
const ORIGIN = "https://valora3d.com";
const T0 = Date.parse("2026-09-28T12:00:00Z");

/** In-memory RenderStore with the same guarantees as the SQL (create_render_job, finish_render_job). */
class FakeStore implements RenderStore {
  jobs = new Map<string, RenderJobRow>();
  priv = new Map<string, PrivatePatch>();
  ledger: { ref: string; amount: number; reason: string }[] = [];
  balance = 100;
  plan: PlanId = "creator";
  /** The plan create_render_job sees, when it differs from the pre-check's (a plan change between the two). */
  sqlPlan: PlanId | null = null;
  uploads = new Map<string, UploadForRender>([
    [UPLOAD, { id: UPLOAD, user_id: USER, status: "ready", source: "upload", r2_key: `u/${USER}/${UPLOAD}.glb`, sample_url: null }],
  ]);
  seq = 0;
  constructor(private readonly clock: () => number) {}

  private iso = () => new Date(this.clock()).toISOString();
  private touch(row: RenderJobRow, patch: Partial<RenderJobRow>) {
    const next = { ...row, ...patch, updated_at: this.iso() };
    this.jobs.set(row.id, next);
    return next;
  }
  private live(row: RenderJobRow | undefined): row is RenderJobRow {
    return !!row && (row.status === "queued" || row.status === "running");
  }

  async getJob(id: string) {
    return this.jobs.get(id) ?? null;
  }
  async findByIdempotencyKey(userId: string, key: string) {
    return [...this.jobs.values()].find((j) => j.user_id === userId && j.idempotency_key === key) ?? null;
  }
  async getWebhookHash(jobId: string) {
    return this.priv.get(jobId)?.webhook_token_hash ?? null;
  }
  async createJob(args: CreateJobArgs): Promise<{ row: RenderJobRow } | { error: StoreError }> {
    // create_render_job v2: the plan is enforced again under the lock, and stamped on the job.
    const limits = PLAN_LIMITS[this.sqlPlan ?? this.plan];
    if (!limits.tiers.includes(args.kind)) return { error: { code: "P0001", message: `plan_required: ${args.kind}` } };
    const active = [...this.jobs.values()].filter((j) => j.user_id === args.userId && this.live(j)).length;
    if (active >= limits.maxActiveJobs) return { error: { code: "P0001", message: `too_many_active: max ${limits.maxActiveJobs}` } };
    if (this.balance < args.cost) return { error: { code: "P0001", message: `insufficient_credits: need ${args.cost}, have ${this.balance}` } };
    const id = `00000000-0000-4000-8000-${String(++this.seq).padStart(12, "0")}`;
    const now = this.iso();
    const row: RenderJobRow = {
      id, user_id: args.userId, project_id: args.projectId, version_id: args.versionId, upload_id: args.uploadId,
      kind: args.kind, status: "queued", params: args.params, runpod_id: null, output_keys: [], cost_credits: args.cost,
      error: null, error_code: null, retryable: null, stage: null, frame: 0, total_frames: null, runpod_status: null,
      outputs: null, video: null, timings: null, warnings: [], render_seconds: null, gpu_seconds: null, delay_ms: null,
      execution_ms: null, attempts: 0, refunded_credits: 0, idempotency_key: args.idempotencyKey, created_at: now,
      started_at: null, finished_at: null, updated_at: now, submitted_at: null, last_polled_at: null, notified_at: null,
      watermark: limits.watermark, watermarked: null, retention_days: limits.retentionDays, expired_at: null,
    };
    this.jobs.set(id, row);
    this.balance -= args.cost;
    this.ledger.push({ ref: `render:${id}`, amount: -args.cost, reason: args.kind === "preview" ? "render_preview" : "render_final" });
    return { row };
  }
  async putPrivate(jobId: string, patch: PrivatePatch) {
    this.priv.set(jobId, { ...this.priv.get(jobId), ...patch });
  }
  async markSubmitted(jobId: string, runpodId: string, runpodStatus: string) {
    const row = this.jobs.get(jobId);
    if (!this.live(row) || row.runpod_id) return false;
    this.touch(row, { runpod_id: runpodId, runpod_status: runpodStatus, submitted_at: this.iso(), last_polled_at: this.iso() });
    return true;
  }
  async updateLive(jobId: string, runpodId: string, patch: LivePatch) {
    const row = this.jobs.get(jobId);
    if (!this.live(row) || row.runpod_id !== runpodId) return;
    this.touch(row, patch);
  }
  async finish(a: FinishArgs) {
    const row = this.jobs.get(a.jobId);
    if (!this.live(row) || row.runpod_id !== a.runpodId) return -1;
    const r = a.result as Record<string, unknown>;
    let next = this.touch(row, {
      status: a.status, error: a.error, error_code: a.errorCode, retryable: a.retryable, finished_at: this.iso(),
      ...(r.outputs ? { outputs: r.outputs } : {}),
      ...(r.output_keys ? { output_keys: r.output_keys as string[] } : {}),
      ...(typeof r.gpu_seconds === "number" ? { gpu_seconds: r.gpu_seconds } : {}),
      ...(typeof r.frame === "number" ? { frame: r.frame, total_frames: r.total_frames as number } : {}),
      ...(typeof r.execution_ms === "number" ? { execution_ms: r.execution_ms } : {}),
      ...(Array.isArray(r.warnings) ? { warnings: r.warnings } : {}),
      ...(typeof r.watermarked === "boolean" ? { watermarked: r.watermarked } : {}),
    });
    let refunded = 0;
    if (a.refund && !this.ledger.some((l) => l.ref === `refund:${a.jobId}`)) {
      refunded = next.cost_credits;
      this.balance += refunded;
      this.ledger.push({ ref: `refund:${a.jobId}`, amount: refunded, reason: "render_refund" });
      next = this.touch(next, { refunded_credits: refunded });
    }
    return refunded;
  }
  async claimRetry(jobId: string, oldRunpodId: string, attempts: number) {
    const row = this.jobs.get(jobId);
    if (!this.live(row) || row.runpod_id !== oldRunpodId || row.attempts !== attempts) return false;
    this.touch(row, { runpod_id: null, attempts: attempts + 1, status: "queued", stage: null, frame: 0, submitted_at: null });
    return true;
  }
  async listStale(before: string, limit: number) {
    return [...this.jobs.values()].filter((j) => this.live(j) && j.updated_at < before).slice(0, limit);
  }
  async markNotified(jobId: string) {
    const row = this.jobs.get(jobId)!;
    this.touch(row, { notified_at: this.iso() });
  }
  async getUpload(uploadId: string, userId: string) {
    const u = this.uploads.get(uploadId);
    return u && u.user_id === userId ? u : null;
  }
  async getPlanLimits() {
    return { plan: this.plan, limits: PLAN_LIMITS[this.plan] };
  }
  async countActive(userId: string) {
    return [...this.jobs.values()].filter((j) => j.user_id === userId && this.live(j)).length;
  }
  async countSince(userId: string, since: string) {
    return [...this.jobs.values()].filter((j) => j.user_id === userId && j.created_at >= since).length;
  }
}

class FakeRunpod implements RunpodApi {
  runs: RunpodRunBody[] = [];
  statuses = new Map<string, RunpodStatusResponse | null>();
  cancelled: string[] = [];
  failRun = false;
  n = 0;
  async run(body: RunpodRunBody) {
    if (this.failRun) throw new Error("RunPod /run failed: 500");
    this.runs.push(body);
    const id = `rp-${++this.n}`;
    this.statuses.set(id, { id, status: "IN_QUEUE" });
    return { id, status: "IN_QUEUE" };
  }
  async status(id: string) {
    return this.statuses.has(id) ? (this.statuses.get(id) ?? null) : null;
  }
  async cancel(id: string) {
    this.cancelled.push(id);
    this.statuses.set(id, { id, status: "CANCELLED" });
    return { id, status: "CANCELLED" };
  }
}

const signer: R2Signer = {
  presignGet: async (key, exp) => `https://acct.r2.cloudflarestorage.com/b/${key}?get&exp=${exp}`,
  presignOutputPut: async (key, ct, exp) => `https://acct.r2.cloudflarestorage.com/b/${key}?put&ct=${encodeURIComponent(ct)}&exp=${exp}`,
};

let now = T0;
let store: FakeStore;
let runpod: FakeRunpod;
let notifier: { notifyRenderReady: Mock<(userId: string, jobId: string) => Promise<void>> };
let pipeline: RenderPipeline;
let tokens: string[];

const params = (p: Partial<RenderParams> = {}): RenderParams => normalizeParams({ prompt: "slow orbit", tier: "preview", ...p });
let keySeq = 0;
const create = (p: Partial<RenderParams> = {}, key = `key-${++keySeq}-abcdef`) =>
  pipeline.create({ userId: USER, projectId: PROJECT, uploadId: UPLOAD, versionId: null, params: params(p), idempotencyKey: key }, ORIGIN);

async function created(p: Partial<RenderParams> = {}) {
  const r = await create(p);
  if (!r.ok) throw new Error(`create failed: ${r.code}`);
  return r.value.row;
}

beforeEach(() => {
  now = T0;
  keySeq = 0;
  store = new FakeStore(() => now);
  runpod = new FakeRunpod();
  notifier = { notifyRenderReady: vi.fn(async (_u: string, _j: string) => {}) };
  tokens = [];
  let t = 0;
  pipeline = new RenderPipeline({
    store,
    runpod,
    r2: signer,
    notifier,
    now: () => now,
    newToken: () => {
      const tok = `token-${++t}-${"x".repeat(32)}`;
      tokens.push(tok);
      return tok;
    },
    log: () => {},
  });
});

const SUCCESS = (id: string, jobId: string): RunpodStatusResponse => ({
  id,
  status: "COMPLETED",
  delayTime: 4200,
  executionTime: 580700,
  output: {
    status: "succeeded",
    job_id: jobId,
    outputs: { video: { bytes: 4812345, content_type: "video/mp4" }, poster: { bytes: 81234, content_type: "image/jpeg" } },
    video: { width: 540, height: 960, fps: 30, frames: 300, duration_s: 10 },
    frames: 300,
    fps: 30,
    tier: "preview",
    render_seconds: 512.3,
    gpu_seconds: 571.9,
    timings: { total_s: 580.7 },
    direct: { source: "llm", world: "rain_courtyard" },
    pin: { worker: "1", blender: "5.0.1" },
    warnings: [],
  },
});

const FAILURE = (id: string, jobId: string, code: string, retryable: boolean): RunpodStatusResponse => ({
  id,
  status: "FAILED",
  error: `${code}: user-safe message`,
  output: {
    status: "failed", job_id: jobId, error_code: code, error_message: "The model or request was rejected by the renderer.",
    error_detail: "input rejected: night_street cannot frame this model at 16:9", retryable, stage: "direct",
    timings: { total_s: 20.6 }, pin: { worker: "1" }, warnings: [], log_tail: ["line a", "line b"],
  },
});

describe("create", () => {
  it("debits, signs the model GET and both output PUTs under the owner prefix, and submits with a hashed per-job token", async () => {
    const row = await created({ world: "rain_courtyard", aspect: "16:9", seed: 7, duration: 10, paint: "#AABBCC", finish: "satin" });
    expect(store.balance).toBe(100 - renderCost("preview"));
    expect(row.runpod_id).toBe("rp-1");
    expect(row.submitted_at).not.toBeNull();

    const body = runpod.runs[0];
    expect(body.input.job_id).toBe(row.id);
    expect(body.input.glb_url).toContain(`u/${USER}/${UPLOAD}.glb`);
    expect(body.input.output_put_urls.video).toContain(`r/${USER}/${row.id}/video.mp4`);
    expect(body.input.output_put_urls.video).toContain("ct=video%2Fmp4");
    expect(body.input.output_put_urls.poster).toContain(`r/${USER}/${row.id}/poster.jpg`);
    expect(body.input.output_put_urls.poster).toContain("ct=image%2Fjpeg");
    expect(body.input.params).toEqual({
      prompt: "slow orbit", tier: "preview", world: "rain_courtyard", aspect: "16:9", seed: 7, duration: 10, paint: "#aabbcc", finish: "satin",
    });
    expect(body.policy).toEqual({ executionTimeout: 90 * 60 * 1000, ttl: 24 * 3600 * 1000 });

    const hook = new URL(body.webhook);
    expect(hook.origin + hook.pathname).toBe(`${ORIGIN}/api/runpod/webhook`);
    expect(hook.searchParams.get("job")).toBe(row.id);
    // Only the hash is stored.
    expect(store.priv.get(row.id)?.webhook_token_hash).toBe(await hashWebhookToken(tokens[0]));
    expect(JSON.stringify([...store.jobs.values()])).not.toContain(tokens[0]);
  });

  it("uses the final tier's longer execution timeout", async () => {
    await created({ tier: "final" });
    expect(runpod.runs[0].policy.executionTimeout).toBe(270 * 60 * 1000);
    expect(store.balance).toBe(100 - renderCost("final"));
  });

  it("refunds at once when RunPod refuses the submission", async () => {
    runpod.failRun = true;
    const r = await create();
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.status).toBe(502);
    expect(r.code).toBe("render_unavailable");
    expect(r.job?.status).toBe("failed");
    expect(r.job?.error_code).toBe("SUBMIT_FAILED");
    expect(r.job?.refunded_credits).toBe(renderCost("preview"));
    expect(store.balance).toBe(100);
  });

  it("returns the same job for a retried idempotency key, charged once", async () => {
    const a = await create({}, "same-key-123");
    const b = await create({}, "same-key-123");
    expect(a.ok && b.ok).toBe(true);
    if (!a.ok || !b.ok) return;
    expect(b.value.row.id).toBe(a.value.row.id);
    expect(b.value.replay).toBe(true);
    expect(runpod.runs).toHaveLength(1);
    expect(store.balance).toBe(100 - renderCost("preview"));
  });

  it("gates the final tier by plan (Free renders previews only) and caps concurrent jobs", async () => {
    store.plan = "free";
    const f = await create({ tier: "final" });
    expect(!f.ok && f.code).toBe("plan_required");
    await created();
    const second = await create();
    expect(!second.ok && second.code).toBe("too_many_active");
    expect(runpod.runs).toHaveLength(1);
  });

  it("lets Pro run three renders at once", async () => {
    store.plan = "pro";
    await created();
    await created({ tier: "final" });
    await created();
    const fourth = await create();
    expect(!fourth.ok && fourth.code).toBe("too_many_active");
    expect(!fourth.ok && fourth.message).toContain("3 renders");
  });

  it("maps create_render_job's own plan refusals (the plan changed after the pre-check), charging nothing", async () => {
    store.plan = "pro";
    store.sqlPlan = "free";
    const f = await create({ tier: "final" });
    expect(!f.ok && [f.status, f.code]).toEqual([403, "plan_required"]);
    await created();
    const second = await create();
    expect(!second.ok && [second.status, second.code]).toEqual([429, "too_many_active"]);
    expect(store.balance).toBe(100 - renderCost("preview"));
    expect(runpod.runs).toHaveLength(1);
  });

  it("stamps the watermark from the plan and sends it to the worker; the browser has no say", async () => {
    store.plan = "free";
    const free = await created();
    expect(free.watermark).toBe(true);
    expect(free.retention_days).toBe(7);
    expect(runpod.runs[0].input.params).toMatchObject({ watermark: true });
    expect(WorkerParamsSchema.safeParse(runpod.runs[0].input.params).success).toBe(true);
    expect(store.ledger[0]).toMatchObject({ reason: "render_preview" });

    store.plan = "creator";
    store.jobs.clear();
    const paid = await created({ tier: "final" });
    expect(paid.watermark).toBe(false);
    expect(paid.retention_days).toBe(30);
    expect(runpod.runs[1].input.params).not.toHaveProperty("watermark");
    expect(store.ledger.at(-1)).toMatchObject({ reason: "render_final" });
  });

  it("refuses a model that is not the caller's or not ready, and an overdraft", async () => {
    store.uploads.set(UPLOAD, { ...store.uploads.get(UPLOAD)!, status: "pending" });
    expect((await create()).ok).toBe(false);
    store.uploads.set(UPLOAD, { ...store.uploads.get(UPLOAD)!, status: "ready", user_id: "someone-else" });
    const r = await create();
    expect(!r.ok && r.code).toBe("not_found");
    store.uploads.set(UPLOAD, { ...store.uploads.get(UPLOAD)!, user_id: USER });
    store.balance = 1;
    const broke = await create();
    expect(!broke.ok && broke.status).toBe(402);
    expect(runpod.runs).toHaveLength(0);
  });

  it("answers not_connected without RunPod configured, charging nothing", async () => {
    pipeline = new RenderPipeline({ store, runpod: null, r2: signer, notifier, now: () => now, log: () => {} });
    const r = await create();
    expect(!r.ok && r.code).toBe("not_connected");
    expect(store.balance).toBe(100);
  });
});

describe("webhook", () => {
  it("rejects a wrong or missing token without touching the job", async () => {
    const row = await created();
    runpod.statuses.set("rp-1", SUCCESS("rp-1", row.id));
    expect((await pipeline.webhook(row.id, "nope", null, ORIGIN)).status).toBe(401);
    expect((await pipeline.webhook(row.id, null, null, ORIGIN)).status).toBe(401);
    expect((await pipeline.webhook("not-a-uuid", tokens[0], null, ORIGIN)).status).toBe(401);
    expect(store.jobs.get(row.id)?.status).toBe("queued");
  });

  it("acts on RunPod's own status, never the body, and is idempotent: one transition, one mail", async () => {
    const row = await created();
    runpod.statuses.set("rp-1", SUCCESS("rp-1", row.id));
    // A forged body claiming failure is ignored: the status is re-read with the API key.
    const forged = { id: "rp-1", status: "FAILED", error: "INTERNAL: x" };
    expect((await pipeline.webhook(row.id, tokens[0], forged, ORIGIN)).status).toBe(200);
    const done = store.jobs.get(row.id)!;
    expect(done.status).toBe("succeeded");
    expect(done.output_keys).toEqual([`r/${USER}/${row.id}/video.mp4`, `r/${USER}/${row.id}/poster.jpg`]);
    expect(done.gpu_seconds).toBe(571.9);
    expect(done.execution_ms).toBe(580700);
    expect(done.frame).toBe(300);
    expect(store.priv.get(row.id)?.pin).toEqual({ worker: "1", blender: "5.0.1" });
    expect(notifier.notifyRenderReady).toHaveBeenCalledWith(USER, row.id);

    // RunPod delivers again: nothing changes, no second mail, no refund.
    expect((await pipeline.webhook(row.id, tokens[0], SUCCESS("rp-1", row.id), ORIGIN)).note).toBe("already final");
    expect(notifier.notifyRenderReady).toHaveBeenCalledTimes(1);
    expect(store.balance).toBe(100 - renderCost("preview"));
  });

  it("keeps a watermarked job the worker could not mark, recording watermarked=false and a warning", async () => {
    store.plan = "free";
    const logs: string[] = [];
    pipeline = new RenderPipeline({ store, runpod, r2: signer, notifier, now: () => now, newToken: () => `t-${"y".repeat(40)}`, log: (m) => logs.push(m) });
    const row = await created();
    const res = SUCCESS("rp-1", row.id);
    runpod.statuses.set("rp-1", { ...res, output: { ...(res.output as object), watermarked: false, warnings: ["watermark skipped: font missing"] } });
    await pipeline.refresh(store.jobs.get(row.id)!, ORIGIN, true);
    const done = store.jobs.get(row.id)!;
    expect(done.status).toBe("succeeded");
    expect(done.watermarked).toBe(false);
    expect(done.warnings).toEqual(["watermark skipped: font missing", "watermark requested but not applied by the worker"]);
    expect(logs).toContain("watermark missing on a watermarked job");
  });

  it("records watermarked=true without a warning when the worker drew it", async () => {
    store.plan = "free";
    const row = await created();
    const res = SUCCESS("rp-1", row.id);
    runpod.statuses.set("rp-1", { ...res, output: { ...(res.output as object), watermarked: true } });
    await pipeline.refresh(store.jobs.get(row.id)!, ORIGIN, true);
    expect(store.jobs.get(row.id)).toMatchObject({ status: "succeeded", watermarked: true, warnings: [] });
  });

  it("records a non-retryable failure with the user message, keeps operator detail private, and refunds once", async () => {
    const row = await created();
    runpod.statuses.set("rp-1", FAILURE("rp-1", row.id, "INPUT_REJECTED", false));
    await pipeline.webhook(row.id, tokens[0], null, ORIGIN);
    await pipeline.webhook(row.id, tokens[0], null, ORIGIN);
    const failed = store.jobs.get(row.id)!;
    expect(failed.status).toBe("failed");
    expect(failed.error_code).toBe("INPUT_REJECTED");
    expect(failed.error).toBe("The model or request was rejected by the renderer.");
    expect(failed.retryable).toBe(false);
    expect(failed.refunded_credits).toBe(renderCost("preview"));
    expect(store.ledger.filter((l) => l.ref.startsWith("refund:"))).toHaveLength(1);
    expect(store.balance).toBe(100);
    expect(store.priv.get(row.id)?.error_detail).toContain("night_street");
    expect(store.priv.get(row.id)?.log_tail).toEqual(["line a", "line b"]);
    expect(notifier.notifyRenderReady).not.toHaveBeenCalled();
  });

  it("retries a retryable failure once on the same debit, then refunds if it fails again", async () => {
    const row = await created();
    runpod.statuses.set("rp-1", FAILURE("rp-1", row.id, "GLB_DOWNLOAD_FAILED", true));
    await pipeline.webhook(row.id, tokens[0], null, ORIGIN);
    let now1 = store.jobs.get(row.id)!;
    expect(now1.status).toBe("queued");
    expect(now1.attempts).toBe(1);
    expect(now1.runpod_id).toBe("rp-2");
    expect(runpod.runs).toHaveLength(2);
    expect(store.balance).toBe(100 - renderCost("preview"));

    // The old attempt's token no longer opens the webhook; the new one does.
    expect((await pipeline.webhook(row.id, tokens[0], null, ORIGIN)).status).toBe(401);
    runpod.statuses.set("rp-2", FAILURE("rp-2", row.id, "RENDER_FAILED", true));
    await pipeline.webhook(row.id, tokens[1], null, ORIGIN);
    now1 = store.jobs.get(row.id)!;
    expect(now1.status).toBe("failed");
    expect(now1.error_code).toBe("RENDER_FAILED");
    expect(runpod.runs).toHaveLength(2);
    expect(store.balance).toBe(100);
  });

  it("ignores a report from a superseded attempt and a payload naming another job", async () => {
    const row = await created();
    expect((await pipeline.webhook(row.id, tokens[0], { id: "rp-old", status: "COMPLETED" }, ORIGIN)).note).toBe("stale attempt");
    runpod.statuses.set("rp-1", SUCCESS("rp-1", "another-job"));
    await pipeline.webhook(row.id, tokens[0], null, ORIGIN);
    expect(store.jobs.get(row.id)?.status).toBe("queued");
  });

  it("refunds RunPod's own CANCELLED and TIMED_OUT", async () => {
    const a = await created();
    runpod.statuses.set("rp-1", { id: "rp-1", status: "TIMED_OUT" });
    await pipeline.webhook(a.id, tokens[0], null, ORIGIN);
    expect(store.jobs.get(a.id)).toMatchObject({ status: "failed", error_code: "RUNPOD_TIMED_OUT", refunded_credits: renderCost("preview") });

    const b = await created();
    runpod.statuses.set("rp-2", { id: "rp-2", status: "CANCELLED" });
    await pipeline.webhook(b.id, tokens[1], null, ORIGIN);
    expect(store.jobs.get(b.id)).toMatchObject({ status: "cancelled", error_code: "RUNPOD_CANCELLED", refunded_credits: renderCost("preview") });
    expect(store.balance).toBe(100);
  });

  it("asks RunPod to retry (503) while the status call fails", async () => {
    const row = await created();
    runpod.status = async () => {
      throw new Error("down");
    };
    expect((await pipeline.webhook(row.id, tokens[0], null, ORIGIN)).status).toBe(503);
  });
});

describe("progress polling", () => {
  it("maps stage and frames onto the row, at most every 10 s unless forced", async () => {
    const row = await created();
    runpod.statuses.set("rp-1", { id: "rp-1", status: "IN_PROGRESS", output: { job_id: row.id, stage: "render", status: "RENDERING", frame: 42, total_frames: 300 } });
    now += 11_000;
    const after = await pipeline.refresh(store.jobs.get(row.id)!, ORIGIN);
    expect(after).toMatchObject({ status: "running", stage: "render", frame: 42, total_frames: 300, runpod_status: "IN_PROGRESS" });
    expect(after.started_at).not.toBeNull();

    runpod.statuses.set("rp-1", { id: "rp-1", status: "IN_PROGRESS", output: { job_id: row.id, stage: "encoding" } });
    now += 2_000;
    expect((await pipeline.refresh(after, ORIGIN)).stage).toBe("render"); // too soon: no poll
    now += 10_000;
    expect((await pipeline.refresh(store.jobs.get(row.id)!, ORIGIN)).stage).toBe("encoding");
  });
});

describe("cancel", () => {
  it("refunds a job the GPU had not started", async () => {
    const row = await created();
    const r = await pipeline.cancel(store.jobs.get(row.id)!, ORIGIN);
    expect(r.ok && r.value.status).toBe("cancelled");
    expect(runpod.cancelled).toEqual(["rp-1"]);
    expect(store.balance).toBe(100);
    // The CANCELLED webhook that follows changes nothing.
    await pipeline.webhook(row.id, tokens[0], null, ORIGIN);
    expect(store.ledger.filter((l) => l.ref.startsWith("refund:"))).toHaveLength(1);
  });

  it("does not refund once rendering has started", async () => {
    const row = await created();
    runpod.statuses.set("rp-1", { id: "rp-1", status: "IN_PROGRESS", output: { job_id: row.id, stage: "render", frame: 3, total_frames: 300 } });
    const r = await pipeline.cancel(store.jobs.get(row.id)!, ORIGIN);
    expect(r.ok && r.value).toMatchObject({ status: "cancelled", refunded_credits: 0, error_code: "CANCELLED_BY_USER" });
    expect(store.balance).toBe(100 - renderCost("preview"));
  });

  it("records the finish instead when RunPod already finished it", async () => {
    const row = await created();
    runpod.statuses.set("rp-1", SUCCESS("rp-1", row.id));
    const r = await pipeline.cancel(store.jobs.get(row.id)!, ORIGIN);
    expect(!r.ok && r.code).toBe("already_finished");
    expect(store.jobs.get(row.id)?.status).toBe("succeeded");
    expect(runpod.cancelled).toEqual([]);
  });
});

describe("sweeper", () => {
  it("finalizes a job whose webhook was lost, and leaves fresh ones alone", async () => {
    const lost = await created();
    runpod.statuses.set("rp-1", SUCCESS("rp-1", lost.id));
    expect(await pipeline.sweep(ORIGIN)).toEqual({ checked: 0, finished: 0 });
    now += 6 * 60_000;
    expect(await pipeline.sweep(ORIGIN)).toEqual({ checked: 1, finished: 1 });
    expect(store.jobs.get(lost.id)?.status).toBe("succeeded");
    expect(notifier.notifyRenderReady).toHaveBeenCalledTimes(1);
  });

  it("refunds a job RunPod no longer knows once it is past its deadline", async () => {
    const row = await created();
    runpod.statuses.delete("rp-1");
    now += 6 * 60_000;
    await pipeline.sweep(ORIGIN);
    expect(store.jobs.get(row.id)?.status).toBe("queued"); // 404 but still inside ttl + execution
    now += 30 * 3600_000;
    await pipeline.sweep(ORIGIN);
    expect(store.jobs.get(row.id)).toMatchObject({ status: "failed", error_code: "RENDER_LOST" });
    expect(store.balance).toBe(100);
  });

  it("refunds a job whose submission never recorded a RunPod id", async () => {
    const r = await store.createJob({ userId: USER, projectId: PROJECT, versionId: null, uploadId: UPLOAD, kind: "preview", params: params(), cost: 3, idempotencyKey: "orphan-key-1" });
    if ("error" in r) throw new Error("setup");
    now += 6 * 60_000;
    await pipeline.sweep(ORIGIN);
    expect(store.jobs.get(r.row.id)).toMatchObject({ status: "failed", error_code: "SUBMIT_FAILED" });
    expect(store.balance).toBe(100);
  });
});

describe("helpers", () => {
  it("maps samples to their R2 mirror and refuses anything else", () => {
    const base = { id: "u", user_id: USER, status: "ready" as const, r2_key: null };
    expect(glbKeyFor({ ...base, source: "sample", sample_url: "/samples/car.glb" })).toBe("samples/car.glb");
    expect(glbKeyFor({ ...base, source: "sample", sample_url: "/samples/../x.glb" })).toBeNull();
    expect(glbKeyFor({ ...base, source: "upload", sample_url: null, r2_key: "u/x/y.glb" })).toBe("u/x/y.glb");
  });

  it("sends only contract keys to the worker, with the tier from the row", () => {
    expect(workerParams({ kind: "final", params: { prompt: "x", tier: "preview", world: null, junk: 1 } })).toEqual({ prompt: "x", tier: "final" });
  });

  it("takes watermark from the job row only, never from the stored params", () => {
    expect(workerParams({ kind: "preview", params: { prompt: "x", watermark: false }, watermark: true })).toEqual({ prompt: "x", tier: "preview", watermark: true });
    expect(workerParams({ kind: "final", params: { prompt: "x", watermark: true }, watermark: false })).toEqual({ prompt: "x", tier: "final" });
  });
});
