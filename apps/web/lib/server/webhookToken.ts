/**
 * Per-job webhook tokens. RunPod does not sign webhooks, so the webhook URL carries an unguessable random
 * token; only its SHA-256 is stored, and the check is constant-time. Web Crypto only (runs on Workers).
 */

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function base64url(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** 32 random bytes, base64url (43 chars). */
export function newWebhookToken(): string {
  return base64url(crypto.getRandomValues(new Uint8Array(32)));
}

export async function hashWebhookToken(token: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token));
  return toHex(new Uint8Array(digest));
}

/** Constant-time string equality (for equal-length hex digests; unequal lengths fail without early exit on content). */
export function timingSafeEqualStr(a: string, b: string): boolean {
  const len = Math.max(a.length, b.length);
  let diff = a.length ^ b.length;
  for (let i = 0; i < len; i++) diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return diff === 0;
}

/** Hashes the presented token and compares it with the stored hash in constant time. */
export async function verifyWebhookToken(presented: string | null | undefined, storedHash: string | null | undefined): Promise<boolean> {
  if (!presented || !storedHash || presented.length > 256) return false;
  return timingSafeEqualStr(await hashWebhookToken(presented), storedHash);
}
