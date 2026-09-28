/**
 * Paddle webhook signatures and the signed user id we put in checkout custom data.
 * Web Crypto only (runs on Cloudflare Workers; no node:crypto).
 *
 * Paddle sends `Paddle-Signature: ts=<unix seconds>;h1=<hex HMAC-SHA256>` where the HMAC key is the
 * notification destination's secret and the message is `<ts>:<raw body>`. Several h1 values may be
 * present while a secret is being rotated; any match passes.
 */

const encoder = new TextEncoder();

/** Default window either side of now. Replays inside it are stopped by the event-id table. */
export const SIGNATURE_TOLERANCE_S = 300;

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

function toHex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
}

function fromHex(hex: string): Uint8Array<ArrayBuffer> | null {
  if (!/^[0-9a-f]{64}$/i.test(hex)) return null;
  const out = new Uint8Array(32);
  for (let i = 0; i < 32; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export async function hmacHex(secret: string, message: string): Promise<string> {
  const key = await hmacKey(secret);
  return toHex(await crypto.subtle.sign("HMAC", key, encoder.encode(message)));
}

export type ParsedSignature = { ts: number; h1: string[] };

export function parseSignatureHeader(header: string | null): ParsedSignature | null {
  if (!header) return null;
  let ts: number | null = null;
  const h1: string[] = [];
  for (const part of header.split(";")) {
    const eq = part.indexOf("=");
    if (eq < 0) continue;
    const k = part.slice(0, eq).trim();
    const v = part.slice(eq + 1).trim();
    if (k === "ts" && /^\d{1,12}$/.test(v)) ts = Number(v);
    else if (k === "h1" && v) h1.push(v);
  }
  if (ts === null || h1.length === 0) return null;
  return { ts, h1 };
}

export type VerifyResult = { ok: true } | { ok: false; reason: "missing" | "malformed" | "stale" | "mismatch" };

/**
 * Verifies a webhook on its RAW body (never a re-serialised JSON). `crypto.subtle.verify` compares
 * in constant time.
 */
export async function verifyPaddleSignature(
  rawBody: string,
  header: string | null,
  secret: string,
  nowMs: number = Date.now(),
  toleranceS: number = SIGNATURE_TOLERANCE_S,
): Promise<VerifyResult> {
  if (!header) return { ok: false, reason: "missing" };
  const parsed = parseSignatureHeader(header);
  if (!parsed) return { ok: false, reason: "malformed" };
  if (Math.abs(nowMs / 1000 - parsed.ts) > toleranceS) return { ok: false, reason: "stale" };
  const key = await hmacKey(secret);
  const message = encoder.encode(`${parsed.ts}:${rawBody}`);
  for (const candidate of parsed.h1) {
    const sig = fromHex(candidate);
    if (sig && (await crypto.subtle.verify("HMAC", key, sig, message))) return { ok: true };
  }
  return { ok: false, reason: "mismatch" };
}

/** Builds a valid header, for tests and local simulation. */
export async function signPaddlePayload(rawBody: string, secret: string, ts: number): Promise<string> {
  return `ts=${ts};h1=${await hmacHex(secret, `${ts}:${rawBody}`)}`;
}

// ---------------------------------------------------------------------------------------------
// Checkout custom data: { user_id, user_sig }. The browser passes it to Paddle.js, so it could be
// edited; the signature stops anyone crediting (or, with a chargeback, debiting) another account.
// Derived from the webhook secret with a label so the two uses never share a message space.
// ---------------------------------------------------------------------------------------------

const USER_LABEL = "valora3d:checkout-user:v1:";

export async function signUserId(userId: string, secret: string): Promise<string> {
  return hmacHex(secret, USER_LABEL + userId);
}

export async function verifyUserSig(userId: string, sig: string, secret: string): Promise<boolean> {
  const bytes = fromHex(sig);
  if (!bytes) return false;
  const key = await hmacKey(secret);
  return crypto.subtle.verify("HMAC", key, bytes, encoder.encode(USER_LABEL + userId));
}
