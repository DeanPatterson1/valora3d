import { describe, it, expect } from "vitest";
import { fail, failFrom, ok } from "./result";

describe("result", () => {
  it("ok drops an empty warnings array", () => {
    expect(ok(1, [])).toEqual({ ok: true, value: 1 });
    expect(ok(1, [{ code: "w", message: "m" }])).toEqual({ ok: true, value: 1, warnings: [{ code: "w", message: "m" }] });
  });
  it("fail omits hints when none are given", () => {
    expect(fail("c", "m")).toEqual({ ok: false, error: { code: "c", message: "m" } });
    expect(fail("c", "m", ["h"])).toEqual({ ok: false, error: { code: "c", message: "m", hints: ["h"] } });
  });
  it("failFrom re-wraps a ServiceError without dropping hints", () => {
    const src = fail("c", "m", ["h1", "h2"]);
    if (src.ok) throw new Error("unreachable");
    const r = failFrom<number>(src.error);
    expect(r).toEqual({ ok: false, error: { code: "c", message: "m", hints: ["h1", "h2"] } });
  });
});
