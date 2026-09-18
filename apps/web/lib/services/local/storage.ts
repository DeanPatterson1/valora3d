import type { ZodType } from "zod";
import { fail, ok, type Result } from "../result";

export const KEYS = {
  projects: "rs.projects",
  assets: "rs.assets",
  versions: "rs.versions",
  ledger: "rs.ledger",
} as const;

export function readJson<T>(key: string, schema: ZodType<T>, fallback: T): { value: T; corrupt: boolean } {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return { value: fallback, corrupt: false };
    const parsed = schema.safeParse(JSON.parse(raw));
    return parsed.success ? { value: parsed.data, corrupt: false } : { value: fallback, corrupt: true };
  } catch {
    return { value: fallback, corrupt: true };
  }
}

export function writeJson(key: string, value: unknown): Result<void> {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return ok(undefined);
  } catch {
    return fail("quota_exceeded", "Storage is full. Delete an old project to free space.");
  }
}

export function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36);
}
