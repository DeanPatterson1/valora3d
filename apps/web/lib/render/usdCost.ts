/**
 * Per-job cost estimate in USD, stored once on render_jobs.cost_usd_estimate when the job finishes (admin only):
 * GPU seconds (measured by the worker, else RunPod's billed execution time) x GPU_USD_PER_SECOND, plus the director's
 * tokens x DIRECTOR_USD_PER_MTOK_INPUT / _OUTPUT when the worker reports them. Unknown parts are left out, never
 * guessed; with no GPU rate configured nothing is stored.
 */

export type CostRates = {
  gpuUsdPerSecond: number;
  directorUsdPerMtokInput: number | null;
  directorUsdPerMtokOutput: number | null;
};

export type DirectorUsage = { input: number; output: number };

const count = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) && v >= 0 ? Math.round(v) : 0);

function usageOf(u: unknown): DirectorUsage | null {
  if (!u || typeof u !== "object" || Array.isArray(u)) return null;
  const o = u as Record<string, unknown>;
  // Anthropic usage fields. Cache writes and reads are counted as input (a slight over-estimate, never an under-).
  const input = count(o.input_tokens) + count(o.cache_creation_input_tokens) + count(o.cache_read_input_tokens);
  const output = count(o.output_tokens);
  return input || output ? { input, output } : null;
}

/**
 * The director's token usage from the worker's `direct` payload, if it reports one: `direct.usage` as one object or a
 * list (one per director call), or a list of calls each with `usage`. Null-safe: anything else is null.
 */
export function directorUsage(direct: unknown): DirectorUsage | null {
  if (!direct || typeof direct !== "object") return null;
  const raw = (direct as Record<string, unknown>).usage ?? (direct as Record<string, unknown>).calls;
  const list = Array.isArray(raw) ? raw.map((x) => (x && typeof x === "object" && "usage" in x ? (x as { usage: unknown }).usage : x)) : [raw];
  let input = 0;
  let output = 0;
  let found = false;
  for (const item of list) {
    const u = usageOf(item);
    if (!u) continue;
    found = true;
    input += u.input;
    output += u.output;
  }
  return found ? { input, output } : null;
}

export function estimateJobCost(
  job: { gpuSeconds: number | null; executionMs: number | null; direct: unknown },
  rates: CostRates,
): { usd: number | null; inputTokens: number | null; outputTokens: number | null } {
  const seconds =
    typeof job.gpuSeconds === "number" && Number.isFinite(job.gpuSeconds) && job.gpuSeconds >= 0
      ? job.gpuSeconds
      : typeof job.executionMs === "number" && Number.isFinite(job.executionMs) && job.executionMs >= 0
        ? job.executionMs / 1000
        : null;
  const usage = directorUsage(job.direct);
  let usd: number | null = seconds === null ? null : seconds * rates.gpuUsdPerSecond;
  if (usage && rates.directorUsdPerMtokInput !== null && rates.directorUsdPerMtokOutput !== null) {
    usd = (usd ?? 0) + (usage.input / 1e6) * rates.directorUsdPerMtokInput + (usage.output / 1e6) * rates.directorUsdPerMtokOutput;
  }
  return {
    usd: usd === null ? null : Math.round(usd * 10_000) / 10_000,
    inputTokens: usage?.input ?? null,
    outputTokens: usage?.output ?? null,
  };
}

/** Pure: rates from env. No (valid) GPU rate => null (no cost is stored). */
export function readCostRates(env: Record<string, string | undefined>): CostRates | null {
  const num = (v: string | undefined) => {
    const n = Number(v?.trim());
    return v?.trim() && Number.isFinite(n) && n >= 0 ? n : null;
  };
  const gpu = num(env.GPU_USD_PER_SECOND);
  if (gpu === null) return null;
  return {
    gpuUsdPerSecond: gpu,
    directorUsdPerMtokInput: num(env.DIRECTOR_USD_PER_MTOK_INPUT),
    directorUsdPerMtokOutput: num(env.DIRECTOR_USD_PER_MTOK_OUTPUT),
  };
}
