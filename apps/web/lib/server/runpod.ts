import type { RunpodConfig } from "@/lib/env";
import type { RunpodStatusResponse } from "@/lib/render/contract";

/**
 * RunPod Serverless REST client (server-only: holds the API key).
 * `POST /v2/<endpoint>/run`, `GET /v2/<endpoint>/status/<id>`, `POST /v2/<endpoint>/cancel/<id>`.
 */
export type RunpodRunBody = {
  input: {
    job_id: string;
    glb_url: string;
    output_put_urls: { video: string; poster: string; frames_zip?: string };
    params: Record<string, unknown>;
  };
  webhook: string;
  policy: { executionTimeout: number; ttl: number };
};

export class RunpodError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "RunpodError";
  }
}

export interface RunpodApi {
  run(body: RunpodRunBody): Promise<{ id: string; status: string }>;
  /** Null when RunPod no longer knows the id (404: expired past its ttl, or never existed). */
  status(runpodId: string): Promise<RunpodStatusResponse | null>;
  cancel(runpodId: string): Promise<RunpodStatusResponse | null>;
}

const TIMEOUT_MS = 15_000;
const RUNPOD_ID = /^[A-Za-z0-9_-]{1,128}$/;

export class RunpodClient implements RunpodApi {
  private readonly base: string;

  constructor(
    private readonly config: RunpodConfig,
    private readonly fetchImpl: typeof fetch = (...args) => fetch(...args),
  ) {
    this.base = `https://api.runpod.ai/v2/${encodeURIComponent(config.endpointId)}`;
  }

  async run(body: RunpodRunBody): Promise<{ id: string; status: string }> {
    const res = await this.send(`${this.base}/run`, { method: "POST", body: JSON.stringify(body) });
    if (!res.ok) throw new RunpodError(`RunPod /run failed: ${res.status}`, res.status);
    const json = (await res.json().catch(() => null)) as { id?: unknown; status?: unknown } | null;
    if (!json || typeof json.id !== "string" || !RUNPOD_ID.test(json.id)) throw new RunpodError("RunPod /run returned no job id", res.status);
    return { id: json.id, status: typeof json.status === "string" ? json.status : "IN_QUEUE" };
  }

  async status(runpodId: string): Promise<RunpodStatusResponse | null> {
    return this.read(`${this.base}/status/${this.id(runpodId)}`, "GET");
  }

  async cancel(runpodId: string): Promise<RunpodStatusResponse | null> {
    return this.read(`${this.base}/cancel/${this.id(runpodId)}`, "POST");
  }

  private id(runpodId: string): string {
    if (!RUNPOD_ID.test(runpodId)) throw new RunpodError("bad RunPod id", null);
    return runpodId;
  }

  private async read(url: string, method: "GET" | "POST"): Promise<RunpodStatusResponse | null> {
    const res = await this.send(url, { method });
    if (res.status === 404) return null;
    if (!res.ok) throw new RunpodError(`RunPod ${method} failed: ${res.status}`, res.status);
    const json = await res.json().catch(() => null);
    if (!json || typeof json !== "object") throw new RunpodError("RunPod returned no JSON", res.status);
    return json as RunpodStatusResponse;
  }

  private async send(url: string, init: RequestInit): Promise<Response> {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), TIMEOUT_MS);
    try {
      return await this.fetchImpl(url, {
        ...init,
        signal: abort.signal,
        headers: { Authorization: `Bearer ${this.config.apiKey}`, "Content-Type": "application/json" },
      });
    } catch (error) {
      throw new RunpodError(`RunPod unreachable: ${error instanceof Error ? error.message : String(error)}`, null);
    } finally {
      clearTimeout(timer);
    }
  }
}
