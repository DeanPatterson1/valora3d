import { z } from "zod";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { fail, ok, type Result } from "@/lib/services/result";

/** Uploads are single-file binary glTF only. Checked here (declared) and on completion (bytes). */
export const UPLOAD_EXTENSION = ".glb";

/** Samples the app ships under /public/samples; the only sample URLs the server will record. */
export const SAMPLE_URL_PREFIX = "/samples/";

const SHA256 = /^[0-9a-f]{64}$/;

export const CreateUploadBody = z.discriminatedUnion("kind", [
  z.object({
    kind: z.literal("upload"),
    projectId: z.uuid(),
    fileName: z.string().min(1).max(255),
    sizeBytes: z.number().int(),
    sha256: z.string().optional(),
  }),
  z.object({
    kind: z.literal("sample"),
    projectId: z.uuid(),
    fileName: z.string().min(1).max(255),
    sizeBytes: z.number().int().nonnegative(),
    sampleUrl: z.string(),
  }),
]);
export type CreateUploadBody = z.infer<typeof CreateUploadBody>;

export type ValidUpload = { fileName: string; sizeBytes: number; sha256: string | null };

/** Validates what the browser declares before any URL is signed. */
export function validateDeclaredUpload(input: { fileName: string; sizeBytes: number; sha256?: string }): Result<ValidUpload> {
  const fileName = input.fileName.trim();
  if (!fileName.toLowerCase().endsWith(UPLOAD_EXTENSION) || fileName.length <= UPLOAD_EXTENSION.length) {
    return fail("unsupported_format", "Only .glb files can be uploaded.", ["Export the model as a single binary .glb."]);
  }
  if (/[\\/\u0000-\u001f]/.test(fileName)) return fail("invalid_name", "The file name contains characters that are not allowed.");
  if (!Number.isSafeInteger(input.sizeBytes) || input.sizeBytes <= 0) return fail("empty_file", "The file is empty.");
  if (input.sizeBytes > MAX_UPLOAD_BYTES) {
    return fail("too_large", `Files up to ${Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB can be uploaded.`);
  }
  const sha = input.sha256?.toLowerCase() ?? null;
  if (sha !== null && !SHA256.test(sha)) return fail("invalid_checksum", "The file checksum is malformed.");
  return ok({ fileName, sizeBytes: input.sizeBytes, sha256: sha });
}

/** A shipped sample: `/samples/<plain-name>.glb`, no encoding, dots or nesting. */
export function isAllowedSampleUrl(url: string): boolean {
  return url.startsWith(SAMPLE_URL_PREFIX) && /^\/samples\/[A-Za-z0-9_-]+\.glb$/.test(url);
}

/** Every user object lives under its owner's prefix. The id is generated server-side. */
export function uploadKey(userId: string, id: string): string {
  return `u/${userId}/${id}.glb`;
}

export function userPrefix(userId: string): string {
  return `u/${userId}/`;
}

/**
 * A GLB file starts with the 12-byte header: magic "glTF", uint32 LE version (2), uint32 LE total
 * length. Returns why the header is wrong, or null when it is a glTF 2 binary of the stated size.
 */
export function checkGlbHeader(header: Uint8Array, objectSize: number): string | null {
  if (header.length < 12) return "The file is too short to be a .glb.";
  const magic = String.fromCharCode(header[0], header[1], header[2], header[3]);
  if (magic !== "glTF") return "The file is not a binary glTF (.glb).";
  const view = new DataView(header.buffer, header.byteOffset, header.byteLength);
  if (view.getUint32(4, true) !== 2) return "Only glTF 2.0 .glb files are supported.";
  if (view.getUint32(8, true) !== objectSize) return "The .glb header length does not match the file size.";
  return null;
}
