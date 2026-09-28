import type { RenderJob } from "@/lib/schema";
import { apiFetch } from "../http";
import { fail, ok, type Result } from "../result";
import type { RenderRequest, RenderService } from "../types";

const TERMINAL = new Set<RenderJob["status"]>(["COMPLETE", "FAILED", "CANCELLED"]);
export const isTerminalJob = (job: RenderJob) => TERMINAL.has(job.status);

/** Poll cadence: quick while a job moves, slower while it waits in the queue, backing off on errors. */
export const POLL = { activeMs: 3_000, queuedMs: 6_000, maxMs: 30_000 } as const;

export function nextDelay(job: RenderJob | null, failures: number): number {
  if (failures > 0) return Math.min(POLL.maxMs, POLL.activeMs * 2 ** failures);
  return job?.status === "QUEUED" ? POLL.queuedMs : POLL.activeMs;
}

type Timer = { set: (fn: () => void, ms: number) => unknown; clear: (handle: unknown) => void };
const realTimer: Timer = {
  set: (fn, ms) => setTimeout(fn, ms),
  clear: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
};

/**
 * Renders through the site's API (/api/renders*), which talks to RunPod server-side. Job state lives on the
 * server, so a closed drawer or a reload loses nothing: `list` finds the jobs again and `subscribe` resumes.
 * Progress comes from polling (RunPod only calls back at the end; the API polls RunPod when a row is stale).
 */
export class HttpRenderService implements RenderService {
  constructor(
    private readonly fetchImpl: typeof fetch = (...args) => fetch(...args),
    private readonly timer: Timer = realTimer,
  ) {}

  async request(input: RenderRequest): Promise<Result<RenderJob>> {
    const r = await apiFetch<{ job: RenderJob }>(
      "/api/renders",
      {
        method: "POST",
        body: JSON.stringify({
          project_id: input.projectId,
          upload_id: input.uploadId,
          version_id: input.versionId,
          params: input.params,
          idempotency_key: input.idempotencyKey,
        }),
      },
      this.fetchImpl,
    );
    if (!r.ok) {
      // The server has no renderer wired (RunPod env absent): same recovery state as Local mode.
      if (r.error.code === "not_connected") return fail("not_connected", r.error.message);
      return r;
    }
    return ok(r.value.job);
  }

  async get(jobId: string): Promise<Result<RenderJob>> {
    const r = await apiFetch<{ job: RenderJob }>(`/api/renders/${encodeURIComponent(jobId)}`, {}, this.fetchImpl);
    return r.ok ? ok(r.value.job) : r;
  }

  async list(projectId: string): Promise<Result<RenderJob[]>> {
    const r = await apiFetch<{ jobs: RenderJob[] }>(`/api/renders?project_id=${encodeURIComponent(projectId)}`, {}, this.fetchImpl);
    return r.ok ? ok(r.value.jobs) : r;
  }

  async cancel(jobId: string): Promise<Result<RenderJob>> {
    const r = await apiFetch<{ job: RenderJob }>(`/api/renders/${encodeURIComponent(jobId)}/cancel`, { method: "POST", body: "{}" }, this.fetchImpl);
    return r.ok ? ok(r.value.job) : r;
  }

  async downloadUrl(jobId: string, file: "video" | "poster"): Promise<Result<string>> {
    const r = await apiFetch<{ url: string }>(`/api/renders/${encodeURIComponent(jobId)}/download?file=${file}`, {}, this.fetchImpl);
    return r.ok ? ok(r.value.url) : r;
  }

  subscribe(jobId: string, onUpdate: (job: RenderJob) => void): () => void {
    let stopped = false;
    let handle: unknown = null;
    let failures = 0;
    let last: RenderJob | null = null;

    const tick = async () => {
      if (stopped) return;
      const r = await this.get(jobId);
      if (stopped) return;
      if (r.ok) {
        failures = 0;
        last = r.value;
        onUpdate(r.value);
        if (isTerminalJob(r.value)) return stop();
      } else if (r.error.code === "not_found" || r.error.code === "unauthorized") {
        // Gone, or the session ended: nothing more to follow.
        return stop();
      } else {
        // Keep the last known state showing; try again later.
        failures = Math.min(failures + 1, 6);
      }
      handle = this.timer.set(() => void tick(), nextDelay(last, failures));
    };

    const stop = () => {
      stopped = true;
      if (handle !== null) this.timer.clear(handle);
      handle = null;
    };

    handle = this.timer.set(() => void tick(), 0);
    return stop;
  }
}
