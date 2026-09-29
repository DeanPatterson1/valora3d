// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { _setFlagLoader, bucket, evaluateFlag, flag, invalidateFlags, publicFlags, setting, type FlagRow } from "./flags";

const row = (p: Partial<FlagRow>): FlagRow => ({
  key: "renders_enabled",
  kind: "flag",
  enabled: true,
  rollout_percent: 100,
  allowlist: [],
  value: null,
  ...p,
});

afterEach(() => {
  _setFlagLoader(null);
  vi.useRealTimers();
});

describe("flags", () => {
  it("buckets deterministically and roughly evenly", () => {
    expect(bucket("k", "user-1")).toBe(bucket("k", "user-1"));
    const counts = Array(10).fill(0);
    for (let i = 0; i < 5000; i++) counts[Math.floor(bucket("k", `u${i}`) / 10)]++;
    for (const c of counts) expect(c).toBeGreaterThan(380);
  });

  it("evaluates off, allowlist and rollout in that order; a missing flag is on", () => {
    expect(evaluateFlag(undefined, "u")).toBe(true);
    expect(evaluateFlag(row({ enabled: false, allowlist: ["u"] }), "u")).toBe(false);
    expect(evaluateFlag(row({ rollout_percent: 0, allowlist: ["u"] }), "u")).toBe(true);
    expect(evaluateFlag(row({ rollout_percent: 0 }), "u")).toBe(false);
    expect(evaluateFlag(row({ rollout_percent: 50 }), null)).toBe(false);
    const on = Array.from({ length: 1000 }, (_, i) => evaluateFlag(row({ rollout_percent: 30 }), `s${i}`)).filter(Boolean).length;
    expect(on).toBeGreaterThan(240);
    expect(on).toBeLessThan(360);
  });

  it("reads the table once per 30 s, keeps the last good copy on errors, and fails open with none", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
    const loader = vi.fn(async (): Promise<FlagRow[] | null> => [
      row({ enabled: false }),
      row({ key: "global_max_active_renders", kind: "setting", value: "12" }),
    ]);
    _setFlagLoader(loader);
    expect(await flag("renders_enabled")).toBe(false);
    expect(await setting("global_max_active_renders")).toBe(12);
    expect(await setting("daily_gpu_budget_seconds")).toBeNull();
    expect(loader).toHaveBeenCalledTimes(1);
    vi.setSystemTime(31_000);
    loader.mockRejectedValueOnce(new Error("db down"));
    expect(await flag("renders_enabled")).toBe(false);
    expect(loader).toHaveBeenCalledTimes(2);
    invalidateFlags();
    loader.mockResolvedValueOnce([row({ enabled: true })]);
    expect(await flag("renders_enabled")).toBe(true);

    _setFlagLoader(async () => null);
    expect(await publicFlags("u")).toEqual({
      renders_enabled: true,
      finals_enabled: true,
      signups_enabled: true,
      sharing_enabled: true,
      checkout_enabled: true,
    });
  });
});
