import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { z } from "zod";
import { classifyStorageError, readJson, writeJson, newId } from "./storage";

describe("storage", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

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

  describe("classifyStorageError", () => {
    it("recognises QuotaExceededError by name", () => {
      expect(classifyStorageError(new DOMException("", "QuotaExceededError"))).toBe("quota_exceeded");
    });
    it("recognises legacy quota code 22", () => {
      const e = new DOMException("", "SomethingElse");
      Object.defineProperty(e, "code", { value: 22 });
      expect(classifyStorageError(e)).toBe("quota_exceeded");
    });
    it("treats any other error as storage_unavailable", () => {
      expect(classifyStorageError(new DOMException("", "SecurityError"))).toBe("storage_unavailable");
      expect(classifyStorageError(new Error("boom"))).toBe("storage_unavailable");
      expect(classifyStorageError(undefined)).toBe("storage_unavailable");
    });
  });

  describe("writeJson failures", () => {
    it("reports quota_exceeded when setItem throws QuotaExceededError", () => {
      vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
        throw new DOMException("", "QuotaExceededError");
      });
      const r = writeJson("k", { a: 1 });
      expect(!r.ok && r.error.code).toBe("quota_exceeded");
      expect(!r.ok && r.error.message).toBe("Storage is full. Delete an old project to free space.");
    });
    it("reports storage_unavailable when setItem throws SecurityError", () => {
      vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
        throw new DOMException("", "SecurityError");
      });
      const r = writeJson("k", { a: 1 });
      expect(!r.ok && r.error.code).toBe("storage_unavailable");
      expect(!r.ok && r.error.message).toBe("Browser storage is unavailable. Use a normal, non-private browser window.");
    });
  });
});
