// @vitest-environment node
import { describe, expect, it } from "vitest";
import { directorUsage, estimateJobCost, readCostRates } from "./usdCost";

const rates = { gpuUsdPerSecond: 0.000306, directorUsdPerMtokInput: 4, directorUsdPerMtokOutput: 20 };

describe("per-job USD cost", () => {
  it("reads rates from env; no GPU rate means no cost", () => {
    expect(readCostRates({})).toBeNull();
    expect(readCostRates({ GPU_USD_PER_SECOND: "abc" })).toBeNull();
    expect(readCostRates({ GPU_USD_PER_SECOND: "0.000306" })).toEqual({
      gpuUsdPerSecond: 0.000306,
      directorUsdPerMtokInput: null,
      directorUsdPerMtokOutput: null,
    });
    expect(readCostRates({ GPU_USD_PER_SECOND: "0.0005", DIRECTOR_USD_PER_MTOK_INPUT: "4", DIRECTOR_USD_PER_MTOK_OUTPUT: "-1" })?.directorUsdPerMtokOutput).toBeNull();
  });

  it("parses the director's usage in any of the worker's shapes, null-safe", () => {
    expect(directorUsage(null)).toBeNull();
    expect(directorUsage({ source: "llm" })).toBeNull();
    expect(directorUsage({ usage: { input_tokens: 100, output_tokens: 20 } })).toEqual({ input: 100, output: 20 });
    expect(
      directorUsage({ usage: [{ input_tokens: 100, output_tokens: 20, cache_read_input_tokens: 50 }, { input_tokens: 10, output_tokens: 1 }] }),
    ).toEqual({ input: 160, output: 21 });
    expect(directorUsage({ calls: [{ usage: { input_tokens: 5, output_tokens: 5 } }, "junk"] })).toEqual({ input: 5, output: 5 });
    expect(directorUsage({ usage: { input_tokens: -5, output_tokens: "9" } })).toBeNull();
  });

  it("prices GPU seconds (else billed execution) plus tokens when both token rates exist", () => {
    expect(estimateJobCost({ gpuSeconds: 600, executionMs: 999_000, direct: null }, rates)).toEqual({ usd: 0.1836, inputTokens: null, outputTokens: null });
    expect(estimateJobCost({ gpuSeconds: null, executionMs: 10_000, direct: null }, rates).usd).toBe(0.0031);
    expect(estimateJobCost({ gpuSeconds: null, executionMs: null, direct: null }, rates).usd).toBeNull();
    expect(estimateJobCost({ gpuSeconds: 0, executionMs: null, direct: { usage: { input_tokens: 20_000, output_tokens: 5_000 } } }, rates)).toEqual({
      usd: 0.18,
      inputTokens: 20_000,
      outputTokens: 5_000,
    });
    expect(
      estimateJobCost({ gpuSeconds: 100, executionMs: null, direct: { usage: { input_tokens: 1e6, output_tokens: 0 } } }, { ...rates, directorUsdPerMtokOutput: null }).usd,
    ).toBe(0.0306);
  });
});
