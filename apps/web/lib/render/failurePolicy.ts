import { CREDIT_COSTS } from "@/lib/pricing";
import type { SiteErrorCode, WorkerErrorCode } from "./contract";

/**
 * Who pays for a failed render: THE one table the pipeline, the SQL fee and the help copy follow.
 *
 * - `infra`: our side (the worker, RunPod, storage, the network, a request the site itself built wrong). Refunded
 *   in full, and resubmitted once when a second attempt can plausibly succeed (`retry`).
 * - `input`: the model or scene the user supplied (a file the renderer rejects, or a scene too heavy to finish in
 *   the tier's time limit). A small fixed fee (INPUT_FAILURE_FEE) is kept and the rest refunded, it is never
 *   resubmitted, and each one counts toward the daily INPUT_FAILURE_DAILY_CAP (lib/usageLimits.ts). Without
 *   this, a model built to grind the GPU until its time limit would get unlimited free GPU time.
 *
 * `INVALID_INPUT` is infra: the site builds and validates the whole request, so the worker refusing it is our
 * mismatch, not the user's. RunPod's own `TIMED_OUT` depends on whether the GPU started (see failureOutcome).
 */
export type FailureFault = "infra" | "input";

export const FAILURE_POLICY = {
  // Worker codes (contract.ts WORKER_ERRORS).
  INVALID_INPUT: { fault: "infra", retry: false },
  GLB_DOWNLOAD_FAILED: { fault: "infra", retry: true },
  GLB_TOO_LARGE: { fault: "input", retry: false },
  GLB_INVALID: { fault: "input", retry: false },
  INPUT_REJECTED: { fault: "input", retry: false },
  RENDER_FAILED: { fault: "infra", retry: true },
  RENDER_TIMEOUT: { fault: "input", retry: false },
  FRAMES_MISSING: { fault: "infra", retry: true },
  ENCODE_FAILED: { fault: "infra", retry: true },
  UPLOAD_FAILED: { fault: "infra", retry: true },
  // The endpoint is misconfigured for every job: a resubmission fails the same way.
  WORKER_MISCONFIGURED: { fault: "infra", retry: false },
  INTERNAL: { fault: "infra", retry: true },
  // Site codes (contract.ts SITE_ERRORS).
  SUBMIT_FAILED: { fault: "infra", retry: false },
  RUNPOD_CANCELLED: { fault: "infra", retry: false },
  RENDER_LOST: { fault: "infra", retry: false },
  // Overridden by failureOutcome: input once the GPU started (the tier's time limit ran out on the scene),
  // infra when the job never left the queue (RunPod had no capacity before its ttl).
  RUNPOD_TIMED_OUT: { fault: "input", retry: false },
} as const satisfies Record<WorkerErrorCode | SiteErrorCode, { fault: FailureFault; retry: boolean }>;

/** Credits kept on an input-caused failure: the price of one preview (never more than the job cost). */
export const INPUT_FAILURE_FEE = CREDIT_COSTS.preview_render;

export type FailureOutcome = { fault: FailureFault; retry: boolean; fee: number };

/**
 * The outcome for a failed job. `started`: the GPU had begun on it (RunPod IN_PROGRESS seen / started_at set).
 * `workerRetryable`: the worker's own flag; a retry needs both it and the table's yes. An unknown code is infra.
 */
export function failureOutcome(code: string, opts: { started: boolean; cost: number; workerRetryable: boolean }): FailureOutcome {
  const known = (FAILURE_POLICY as Record<string, { fault: FailureFault; retry: boolean }>)[code] ?? { fault: "infra", retry: false };
  const fault: FailureFault = code === "RUNPOD_TIMED_OUT" && !opts.started ? "infra" : known.fault;
  return {
    fault,
    retry: fault === "infra" && known.retry && opts.workerRetryable,
    fee: fault === "input" ? Math.max(0, Math.min(INPUT_FAILURE_FEE, opts.cost)) : 0,
  };
}

/** What the user reads about the credits of a failed job. */
export function refundNote(outcome: FailureOutcome, cost: number): string {
  if (cost <= 0) return "";
  if (outcome.fault === "infra") return "Your credits were refunded.";
  const back = cost - outcome.fee;
  return back > 0
    ? `${outcome.fee} credits were kept because the model or scene caused the failure; ${back} were refunded.`
    : "The credits were kept because the model or scene caused the failure.";
}
