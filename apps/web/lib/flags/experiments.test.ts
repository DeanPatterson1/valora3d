// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { assignVariant, EXPERIMENTS, experiment, type ExperimentDef } from "./experiments";

describe("experiments", () => {
  it("has none configured yet", () => {
    expect(Object.keys(EXPERIMENTS)).toEqual([]);
  });

  it("assigns deterministically, honouring weights", () => {
    const def: ExperimentDef = { variants: ["control", "keyword"], weights: [90, 10] };
    expect(assignVariant("hero", def, "u1")).toBe(assignVariant("hero", def, "u1"));
    const keyword = Array.from({ length: 2000 }, (_, i) => assignVariant("hero", def, `s${i}`)).filter((v) => v === "keyword").length;
    expect(keyword).toBeGreaterThan(120);
    expect(keyword).toBeLessThan(290);
  });

  it("logs the exposure it serves; an unknown experiment or no subject is control and logs nothing", async () => {
    const rpc = vi.fn(async () => ({ data: true, error: null }));
    const registry: Record<string, ExperimentDef> = { hero_headline: { variants: ["control", "keyword"] } };
    const v = await experiment({ rpc } as never, "hero_headline", { userId: "3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f" }, registry);
    expect(["control", "keyword"]).toContain(v);
    expect(rpc).toHaveBeenCalledWith(
      "record_product_event",
      expect.objectContaining({ p_event: "experiment_exposure", p_props: { key: "hero_headline", variant: v } }),
    );
    rpc.mockClear();
    expect(await experiment({ rpc } as never, "nope", { userId: "u" }, registry)).toBe("control");
    expect(await experiment({ rpc } as never, "hero_headline", {}, registry)).toBe("control");
    expect(rpc).not.toHaveBeenCalled();
  });
});
