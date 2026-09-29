import type { RenderJobStatus } from "@/lib/schema";

/**
 * The RunPod side of the render contract, as pure functions: what `GET /v2/<endpoint>/status/<id>` (and the
 * identical webhook body) says, and how that becomes a job row. Source of truth: Rendering-worker
 * `worker/README.md` section 1 and `worker/contract.py`.
 */

export const RUNPOD_STATUSES = ["IN_QUEUE", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"] as const;
export type RunpodStatus = (typeof RUNPOD_STATUSES)[number];
export const RUNPOD_TERMINAL: readonly RunpodStatus[] = ["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"];

/** `GET /status/<id>` / webhook body. Everything is untrusted until re-fetched with the API key. */
export type RunpodStatusResponse = {
  id?: unknown;
  status?: unknown;
  output?: unknown;
  error?: unknown;
  delayTime?: unknown;
  executionTime?: unknown;
};

/** Worker progress stages (`handler.py`), in order. */
export const WORKER_STAGES = ["downloading", "ingest", "direct", "render", "encoding", "uploading", "done"] as const;
export type WorkerStage = (typeof WORKER_STAGES)[number];

/** Worker error codes -> [retryable, user-safe message]. Mirrors contract.py ERRORS. */
export const WORKER_ERRORS = {
  INVALID_INPUT: [false, "The render request was malformed."],
  GLB_DOWNLOAD_FAILED: [true, "The model could not be downloaded."],
  GLB_TOO_LARGE: [false, "The model is larger than the 200 MB limit."],
  GLB_INVALID: [false, "The file is not a valid binary glTF (.glb) model."],
  INPUT_REJECTED: [false, "The model or request was rejected by the renderer."],
  RENDER_FAILED: [true, "The render failed."],
  RENDER_TIMEOUT: [true, "The render took too long and was stopped."],
  FRAMES_MISSING: [true, "The render finished without producing every frame."],
  ENCODE_FAILED: [true, "The video could not be encoded."],
  UPLOAD_FAILED: [true, "The result could not be uploaded."],
  WORKER_MISCONFIGURED: [true, "The render worker is misconfigured."],
  INTERNAL: [true, "The render worker hit an unexpected error."],
} as const satisfies Record<string, readonly [boolean, string]>;
export type WorkerErrorCode = keyof typeof WORKER_ERRORS;

/** Failures the site itself declares (no worker output behind them). */
export const SITE_ERRORS = {
  SUBMIT_FAILED: [false, "The render could not be started. Your credits were refunded."],
  RUNPOD_TIMED_OUT: [false, "The render ran past its time limit and was stopped."],
  RUNPOD_CANCELLED: [false, "The render was cancelled."],
  RENDER_LOST: [false, "The render service lost track of this job. Your credits were refunded."],
} as const satisfies Record<string, readonly [boolean, string]>;
export type SiteErrorCode = keyof typeof SITE_ERRORS;

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
const int = (v: unknown): number | null => {
  const n = num(v);
  return n === null ? null : Math.max(0, Math.round(n));
};

export function runpodStatus(v: unknown): RunpodStatus | null {
  return typeof v === "string" && (RUNPOD_STATUSES as readonly string[]).includes(v) ? (v as RunpodStatus) : null;
}

export type OutputMeta = { bytes: number | null; content_type: string | null };

export type SucceededResult = {
  outputs: Record<string, OutputMeta>;
  video: Record<string, unknown> | null;
  frames: number | null;
  fps: number | null;
  renderSeconds: number | null;
  gpuSeconds: number | null;
  timings: Record<string, unknown> | null;
  warnings: string[];
  pin: Record<string, unknown> | null;
  direct: Record<string, unknown> | null;
  /** True only when the worker actually drew the watermark (a missing font => false + a warning). Null: not reported. */
  watermarked: boolean | null;
  /** The clip length the site asked for, echoed by the worker (null when the director chose). */
  requestedDurationS: number | null;
};

export type FailedResult = {
  errorCode: string;
  errorMessage: string;
  retryable: boolean;
  /** Operators only: never sent to the browser. */
  errorDetail: string | null;
  logTail: string[] | null;
  stage: string | null;
  timings: Record<string, unknown> | null;
  pin: Record<string, unknown> | null;
  warnings: string[];
};

export type Interpretation =
  | { kind: "queued" }
  | { kind: "running"; stage: WorkerStage | null; frame: number | null; totalFrames: number | null }
  | { kind: "succeeded"; result: SucceededResult }
  | { kind: "failed"; cancelled: boolean; result: FailedResult }
  /** The payload names another site job, or is not a status we know: act on nothing. */
  | { kind: "ignore"; reason: string };

function warningsOf(o: Record<string, unknown>): string[] {
  return Array.isArray(o.warnings) ? o.warnings.filter((w): w is string => typeof w === "string").slice(0, 20) : [];
}

export function siteFailure(code: SiteErrorCode, detail: string | null = null): FailedResult {
  const [retryable, errorMessage] = SITE_ERRORS[code];
  return { errorCode: code, errorMessage, retryable, errorDetail: detail, logTail: null, stage: null, timings: null, pin: null, warnings: [] };
}

/** `"<CODE>: <message>"` (RunPod `error`) -> the code, when it is one the worker defines. */
export function workerCodeFromError(error: unknown): WorkerErrorCode | null {
  const s = str(error);
  const code = s?.split(":")[0]?.trim();
  return code && code in WORKER_ERRORS ? (code as WorkerErrorCode) : null;
}

function workerFailure(output: unknown, error: unknown): FailedResult {
  const o = isObj(output) ? output : {};
  const declared = str(o.error_code);
  const code: WorkerErrorCode =
    declared && declared in WORKER_ERRORS ? (declared as WorkerErrorCode) : (workerCodeFromError(error) ?? "INTERNAL");
  const known = WORKER_ERRORS[code];
  const retryable = typeof o.retryable === "boolean" ? o.retryable : known[0];
  const logTail = Array.isArray(o.log_tail) ? o.log_tail.filter((l): l is string => typeof l === "string").slice(-20) : null;
  return {
    errorCode: code,
    // The worker's own message is user-safe by contract; fall back to our copy of it.
    errorMessage: (str(o.error_message) ?? known[1]).slice(0, 300),
    retryable,
    errorDetail: (str(o.error_detail) ?? str(error))?.slice(0, 2000) ?? null,
    logTail,
    stage: str(o.stage),
    timings: isObj(o.timings) ? o.timings : null,
    pin: isObj(o.pin) ? o.pin : null,
    warnings: warningsOf(o),
  };
}

function succeeded(o: Record<string, unknown>): SucceededResult {
  const outputs: SucceededResult["outputs"] = {};
  if (isObj(o.outputs)) {
    for (const [name, meta] of Object.entries(o.outputs)) {
      if (!["video", "poster", "frames_zip"].includes(name) || !isObj(meta)) continue;
      outputs[name] = { bytes: int(meta.bytes), content_type: str(meta.content_type) };
    }
  }
  return {
    outputs,
    video: isObj(o.video) ? o.video : null,
    frames: int(o.frames),
    fps: num(o.fps),
    renderSeconds: num(o.render_seconds),
    gpuSeconds: num(o.gpu_seconds),
    timings: isObj(o.timings) ? o.timings : null,
    warnings: warningsOf(o),
    pin: isObj(o.pin) ? o.pin : null,
    direct: isObj(o.direct) ? o.direct : null,
    watermarked: typeof o.watermarked === "boolean" ? o.watermarked : null,
    requestedDurationS: num(o.requested_duration_s),
  };
}

/**
 * Reads one RunPod status payload for site job `jobId`. The worker echoes `job_id` in every output and
 * progress payload; one naming another job is ignored (a crossed wire must never finalize the wrong row).
 */
export function interpretStatus(res: RunpodStatusResponse, jobId: string): Interpretation {
  const status = runpodStatus(res.status);
  if (!status) return { kind: "ignore", reason: `unknown status ${String(res.status)}` };
  const output = res.output;
  if (isObj(output) && typeof output.job_id === "string" && output.job_id !== jobId) {
    return { kind: "ignore", reason: "output names another job" };
  }
  switch (status) {
    case "IN_QUEUE":
      return { kind: "queued" };
    case "IN_PROGRESS": {
      const o = isObj(output) ? output : {};
      const stage = (WORKER_STAGES as readonly string[]).includes(String(o.stage)) ? (o.stage as WorkerStage) : null;
      return { kind: "running", stage, frame: int(o.frame), totalFrames: int(o.total_frames) };
    }
    case "COMPLETED": {
      // A handler that returned a failure dict still completes from RunPod's point of view.
      if (isObj(output) && output.status === "succeeded") return { kind: "succeeded", result: succeeded(output) };
      if (isObj(output) && output.status === "failed") return { kind: "failed", cancelled: false, result: workerFailure(output, res.error) };
      return { kind: "failed", cancelled: false, result: workerFailure(null, "INTERNAL: completed without a result") };
    }
    case "FAILED":
      return { kind: "failed", cancelled: false, result: workerFailure(output, res.error) };
    case "CANCELLED":
      return { kind: "failed", cancelled: true, result: siteFailure("RUNPOD_CANCELLED") };
    case "TIMED_OUT":
      return { kind: "failed", cancelled: false, result: siteFailure("RUNPOD_TIMED_OUT") };
  }
}

/** Worker stage -> the studio's status (README "Progress" table). */
export function stageToStatus(stage: string | null | undefined): RenderJobStatus {
  switch (stage) {
    case "render":
      return "RENDERING";
    case "encoding":
      return "ENCODING";
    case "uploading":
    case "done": // the handler is returning; COMPLETE arrives with the terminal status
      return "UPLOADING";
    default: // downloading, ingest, direct, or no progress payload yet
      return "PREPARING";
  }
}

export type DbJobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

/** Job row status + stage -> the studio's status. */
export function rowStatus(status: DbJobStatus, stage: string | null): RenderJobStatus {
  switch (status) {
    case "queued":
      return "QUEUED";
    case "running":
      return stageToStatus(stage);
    case "succeeded":
      return "COMPLETE";
    case "failed":
      return "FAILED";
    case "cancelled":
      return "CANCELLED";
  }
}

/**
 * The most GPU time one job may use, per tier. A failed job is refunded (lib/render/failurePolicy.ts), so this cap
 * is what bounds a model built to make the worker grind: RunPod stops the job at it (TIMED_OUT, charged the
 * input-failure fee once the GPU had started). Realistic caps for 8-12 s clips, NOT measured yet: raise them after
 * measuring the p99 of executionTime per tier (worker README section 5). The worker's own limits (README
 * "Timeouts": 60 min preview, 4 h final) are longer, so RunPod's cap is the one that bites.
 */
export const PREVIEW_EXECUTION_TIMEOUT_MS = 20 * 60 * 1000;
export const FINAL_EXECUTION_TIMEOUT_MS = 120 * 60 * 1000;
/** How long a job may wait in RunPod's queue before it expires unstarted (refunded in full). */
export const QUEUE_TTL_MS = 24 * 3600 * 1000;

/** Per-tier RunPod `policy` (sent with every /run). */
export const TIER_POLICY = {
  preview: { executionTimeout: PREVIEW_EXECUTION_TIMEOUT_MS, ttl: QUEUE_TTL_MS },
  final: { executionTimeout: FINAL_EXECUTION_TIMEOUT_MS, ttl: QUEUE_TTL_MS },
} as const;

/**
 * How long the presigned URLs live: the glb GET must survive the queue wait (ttl), the output PUTs the queue
 * wait plus the run. R2 caps a presigned URL at 7 days.
 */
export function presignLifetimes(tier: keyof typeof TIER_POLICY): { getSeconds: number; putSeconds: number } {
  const p = TIER_POLICY[tier];
  const cap = 7 * 24 * 3600;
  const margin = 30 * 60;
  return {
    getSeconds: Math.min(cap, Math.ceil(p.ttl / 1000) + margin),
    putSeconds: Math.min(cap, Math.ceil((p.ttl + p.executionTimeout) / 1000) + margin),
  };
}

/** The latest moment a job can still legitimately be alive at RunPod (ttl + execution + margin). */
export function jobDeadlineMs(tier: keyof typeof TIER_POLICY, submittedAt: number): number {
  const p = TIER_POLICY[tier];
  return submittedAt + p.ttl + p.executionTimeout + 30 * 60 * 1000;
}

/** Keys of a job's outputs. Every result lives under its owner's prefix. */
export function outputKey(userId: string, jobId: string, name: "video" | "poster"): string {
  return `r/${userId}/${jobId}/${name === "video" ? "video.mp4" : "poster.jpg"}`;
}

export const OUTPUT_CONTENT_TYPES = { video: "video/mp4", poster: "image/jpeg" } as const;
