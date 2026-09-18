import { describe, it, expect, beforeEach } from "vitest";
import { z } from "zod";
import { readJson, writeJson, newId } from "./storage";

describe("storage", () => {
  beforeEach(() => localStorage.clear());
  it("round-trips valid json", () => {
    const r = writeJson("k", { a: 1 });
    expect(r.ok).toBe(true);
    expect(readJson("k", z.object({ a: z.number() }), { a: 0 })).toEqual({ value: { a: 1 }, corrupt: false });
  });
  it("treats corrupt data as empty and flags it", () => {
    localStorage.setItem("k", "{not json");
    expect(readJson("k", z.object({ a: z.number() }), { a: 0 })).toEqual({ value: { a: 0 }, corrupt: true });
  });
  it("generates unique ids", () => {
    expect(newId()).not.toBe(newId());
  });
});
