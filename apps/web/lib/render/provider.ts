import type { RenderJobStatus } from "@/lib/schema";
import type { RenderJobRequest } from "./job";

/**
 * Client for the local render server (`tools/render-studio/server.py`).
 *
 * The server binds loopback only and pins the Host header, so this talks to it
 * directly from the browser during local development — the same arrangement the
 * pipeline was built with. It is not reachable from a deployed origin, which is why
 * "Cloud GPU" stays a separate, unimplemented target.
 */

export const RENDER_SERVER = "http://127.0.0.1:8765";

const SUBMIT_TIMEOUT_MS = 180_000;
const GET_TIMEOUT_MS = 5_000;
/** How long to wait before retrying after the event stream drops. */
const POLL_INTERVAL_MS = 2_000;

/** The pipeline's own job states, from `jobs.py`. */
export type PipelineStatus = "queued" | "preparing" | "rendering" | "encoding" | "done" | "failed" | "cancelled";

export type PipelineJob = {
  jobId: string;
  status: PipelineStatus;
  progress: number;
  frame: number;
  totalFrames: number;
  position: number;
  output: { latest?: string; video?: string; poster?: string };
  error?: string;
};

/**
 * `UPLOADING` has no local equivalent: nothing leaves the machine. A cancelled render
 * is reported as failed because the studio's job type has no cancelled state.
 */
export const STATUS_MAP: Record<PipelineStatus, RenderJobStatus> = {
  queued: "QUEUED",
  preparing: "PREPARING",
  rendering: "RENDERING",
  encoding: "ENCODING",
  done: "COMPLETE",
  failed: "FAILED",
  cancelled: "FAILED",
};

export class RenderServerError extends Error {
  constructor(
    message: string,
    readonly code: "offline" | "refused" | "server",
    readonly status?: number,
  ) {
    super(message);
    this.name = "RenderServerError";
  }
}

const OFFLINE =
  "The local render server is not running. Start it with `py tools/render-studio/server.py`.";

async function request<T>(path: string, init: RequestInit, timeoutMs: number): Promise<T> {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(RENDER_SERVER + path, { ...init, signal: abort.signal });
  } catch {
    // A refused connection and a DNS-less loopback both land here; from the UI's point
    // of view the server is simply not there.
    throw new RenderServerError(OFFLINE, "offline");
  } finally {
    clearTimeout(timer);
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const message = (body as { error?: string } | null)?.error;
    throw new RenderServerError(
      message || `The render server refused the job (${response.status}).`,
      response.status >= 500 ? "server" : "refused",
      response.status,
    );
  }
  return body as T;
}

export async function health(): Promise<{ ready: boolean; gpu?: string; queueLength?: number; error?: string }> {
  return request("/api/health", { method: "GET" }, GET_TIMEOUT_MS);
}

export async function submit(job: RenderJobRequest, snapshot: string): Promise<PipelineJob> {
  return request(
    "/api/jobs",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job, snapshot }),
    },
    SUBMIT_TIMEOUT_MS,
  );
}

export async function getJob(jobId: string): Promise<PipelineJob> {
  return request(`/api/jobs/${jobId}`, { method: "GET" }, GET_TIMEOUT_MS);
}

export async function cancel(jobId: string): Promise<void> {
  await request(`/api/jobs/${jobId}/cancel`, { method: "POST", body: "{}" }, GET_TIMEOUT_MS);
}

/** Absolute URL of one of a finished job's files. */
export function fileUrl(jobId: string, name: "video.mp4" | "poster.jpg" | "latest.jpg"): string {
  return `${RENDER_SERVER}/files/${jobId}/${name}`;
}

/**
 * Follows a job to a terminal state. Server-sent events carry progress; if the stream
 * drops the poll below keeps the UI truthful rather than leaving it stuck mid-render.
 */
export function subscribe(jobId: string, onUpdate: (job: PipelineJob) => void): () => void {
  let stopped = false;
  let source: EventSource | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const settle = (job: PipelineJob) => {
    onUpdate(job);
    if (job.status === "done" || job.status === "failed" || job.status === "cancelled") stop();
  };

  const poll = async () => {
    if (stopped) return;
    try {
      settle(await getJob(jobId));
    } catch {
      // Leave the last known state showing; the next tick tries again.
    }
    if (!stopped) timer = setTimeout(poll, POLL_INTERVAL_MS);
  };

  const stop = () => {
    stopped = true;
    source?.close();
    source = null;
    if (timer) clearTimeout(timer);
    timer = null;
  };

  try {
    source = new EventSource(`${RENDER_SERVER}/api/jobs/${jobId}/events`);
    source.addEventListener("progress", (event) => {
      try {
        settle(JSON.parse((event as MessageEvent).data) as PipelineJob);
      } catch {
        // A malformed frame is not worth tearing the stream down for.
      }
    });
    source.onerror = () => {
      source?.close();
      source = null;
      if (!stopped && !timer) timer = setTimeout(poll, POLL_INTERVAL_MS);
    };
  } catch {
    void poll();
  }

  return stop;
}
