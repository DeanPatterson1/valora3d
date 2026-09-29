import type { ZodType } from "@/lib/zod";
import { fail, ok, type Result } from "../result";

export const KEYS = {
  projects: "rs.projects",
  assets: "rs.assets",
  versions: "rs.versions",
  ledger: "rs.ledger",
  users: "rs.users",
  session: "rs.session",
} as const;

/** Every localStorage key the prototype owns starts with this prefix (see `LocalAuthService.deleteAllData`). */
export const KEY_PREFIX = "rs.";

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

export type StorageErrorCode = "quota_exceeded" | "storage_unavailable";

const STORAGE_MESSAGES: Record<StorageErrorCode, string> = {
  quota_exceeded: "Storage is full. Delete an old project to free space.",
  storage_unavailable: "Browser storage is unavailable. Use a normal, non-private browser window.",
};

/** Classify a thrown localStorage/IndexedDB error as quota (recoverable by deleting data) or unavailable (private mode, blocked storage). */
export function classifyStorageError(e: unknown): StorageErrorCode {
  return e instanceof DOMException && (e.name === "QuotaExceededError" || e.code === 22) ? "quota_exceeded" : "storage_unavailable";
}

export function storageFailure<T = never>(e: unknown): Result<T> {
  const code = classifyStorageError(e);
  return fail(code, STORAGE_MESSAGES[code]);
}

export function writeJson(key: string, value: unknown): Result<void> {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return ok(undefined);
  } catch (e) {
    return storageFailure(e);
  }
}

export function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36);
}
