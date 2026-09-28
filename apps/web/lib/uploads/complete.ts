import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { checkGlbHeader } from "./validate";

/** The storage calls completion needs (R2Storage implements them). */
export type CompletionStorage = {
  headSize(key: string): Promise<number | null>;
  getRange(key: string, start: number, end: number): Promise<Uint8Array>;
  delete(key: string): Promise<void>;
};

export type CompletionOutcome =
  | { status: "ready"; sizeBytes: number }
  | { status: "missing" }
  | { status: "rejected"; reason: string };

/**
 * Decides whether an uploaded object is acceptable: it exists, its stored size is within the cap
 * and equals what was declared, and its first 12 bytes are a glTF 2 binary header whose length
 * matches. A rejected object is deleted so nothing unvalidated stays in the bucket.
 */
export async function verifyUploadedObject(
  storage: CompletionStorage,
  key: string,
  declaredSize: number,
): Promise<CompletionOutcome> {
  const size = await storage.headSize(key);
  if (size === null) return { status: "missing" };

  let reason: string | null = null;
  if (!Number.isFinite(size) || size <= 0) reason = "The uploaded file is empty.";
  else if (size > MAX_UPLOAD_BYTES) reason = "The uploaded file is larger than the limit.";
  else if (size !== declaredSize) reason = "The uploaded file size does not match what was declared.";
  else reason = checkGlbHeader(await storage.getRange(key, 0, 11), size);

  if (reason) {
    await storage.delete(key);
    return { status: "rejected", reason };
  }
  return { status: "ready", sizeBytes: size };
}
