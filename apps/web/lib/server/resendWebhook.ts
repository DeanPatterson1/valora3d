import { z } from "zod";

/**
 * Resend webhooks are signed by Svix (https://resend.com/docs/webhooks/verify-webhooks-requests,
 * https://docs.svix.com/receiving/verifying-payloads/how-manual):
 *   signed content  `${svix-id}.${svix-timestamp}.${raw body}`
 *   key             the base64 part of the signing secret after `whsec_`
 *   signature       base64 HMAC-SHA256, in `svix-signature` as space-separated `v1,<sig>` entries (any may match)
 *   timestamp       seconds; refused outside +-5 minutes (replay window)
 * Web Crypto only, constant-time comparison.
 */

export const TOLERANCE_SECONDS = 5 * 60;

function fromBase64(s: string): Uint8Array<ArrayBuffer> {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function toBase64(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

function equal(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function svixSignature(secret: string, id: string, timestamp: string, body: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", fromBase64(secret.replace(/^whsec_/, "")), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return toBase64(new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${id}.${timestamp}.${body}`))));
}

export type SvixHeaders = { id: string | null; timestamp: string | null; signature: string | null };

export async function verifySvix(secret: string, h: SvixHeaders, body: string, nowMs = Date.now()): Promise<boolean> {
  if (!h.id || !h.timestamp || !h.signature) return false;
  if (!/^[A-Za-z0-9_.:-]{1,100}$/.test(h.id) || !/^\d{1,12}$/.test(h.timestamp)) return false;
  if (Math.abs(nowMs / 1000 - Number(h.timestamp)) > TOLERANCE_SECONDS) return false;
  let want: string;
  try {
    want = await svixSignature(secret, h.id, h.timestamp, body);
  } catch {
    return false;
  }
  return h.signature
    .split(" ")
    .map((part) => part.split(","))
    .some(([version, sig]) => version === "v1" && typeof sig === "string" && equal(sig, want));
}

const Event = z.object({
  type: z.string().max(64),
  data: z
    .object({
      to: z.union([z.array(z.string().max(320)).max(50), z.string().max(320)]).optional(),
      bounce: z.object({ type: z.string().max(40).optional() }).passthrough().optional(),
    })
    .passthrough(),
});

export type Suppression = { email: string; reason: "bounce" | "complaint" };

/**
 * The addresses one event suppresses: every recipient of a hard bounce (`email.bounced`, which Resend sends for
 * permanent rejections; a bounce explicitly typed Transient is ignored), a spam complaint (`email.complained`), or an
 * address Resend itself suppressed (`email.suppressed`). Anything else suppresses nothing.
 */
export function suppressionsFrom(body: unknown): Suppression[] {
  const parsed = Event.safeParse(body);
  if (!parsed.success) return [];
  const { type, data } = parsed.data;
  let reason: Suppression["reason"] | null = null;
  if (type === "email.complained") reason = "complaint";
  else if (type === "email.suppressed") reason = "bounce";
  else if (type === "email.bounced" && data.bounce?.type?.toLowerCase() !== "transient") reason = "bounce";
  if (!reason) return [];
  const to = Array.isArray(data.to) ? data.to : data.to ? [data.to] : [];
  return to
    .map((raw) => (raw.match(/<([^<>\s]+@[^<>\s]+)>/)?.[1] ?? raw).trim().toLowerCase())
    .filter((email, i, all) => /^[^\s@]+@[^\s@]+$/.test(email) && email.length <= 254 && all.indexOf(email) === i)
    .map((email) => ({ email, reason: reason as Suppression["reason"] }));
}
