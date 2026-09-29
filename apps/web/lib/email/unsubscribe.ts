import { SITE_URL } from "@/lib/site";
import { OPT_OUT_CATEGORIES, type OptOutCategory } from "./categories";

/**
 * One-click unsubscribe (RFC 8058) without a login: every opt-out mail carries a token that is an HMAC-SHA256 of
 * (user id, category) under a server secret (lib/env.ts `unsubscribeSecret`). The token never expires, so an old mail's
 * link still works; it can only ever turn one category off for one account. Web Crypto only (Workers + Node).
 *
 *   List-Unsubscribe:       <https://valora3d.com/api/email/unsubscribe?u=…&c=…&t=…>
 *   List-Unsubscribe-Post:  List-Unsubscribe=One-Click
 *   body footer link:       https://valora3d.com/unsubscribe?u=…&c=…&t=…   (a page with a confirm button: link
 *                           scanners that prefetch GETs never unsubscribe anyone)
 */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TOKEN = /^[A-Za-z0-9_-]{43}$/;

const enc = new TextEncoder();

function base64url(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function hmac(secret: string, message: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(message)));
}

export function isOptOutCategory(value: unknown): value is OptOutCategory {
  return typeof value === "string" && (OPT_OUT_CATEGORIES as readonly string[]).includes(value);
}

export async function unsubscribeToken(secret: string, userId: string, category: OptOutCategory): Promise<string> {
  return base64url(await hmac(secret, `valora3d:unsubscribe:v1:${userId.toLowerCase()}:${category}`));
}

/** Constant-time check of a presented token. */
export async function verifyUnsubscribeToken(secret: string, userId: string, category: string, token: string): Promise<boolean> {
  if (!UUID.test(userId) || !isOptOutCategory(category) || !TOKEN.test(token)) return false;
  const want = await unsubscribeToken(secret, userId, category);
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ token.charCodeAt(i);
  return diff === 0;
}

export type UnsubscribeLinks = { oneClick: string; page: string };

export async function unsubscribeLinks(secret: string, userId: string, category: OptOutCategory, siteUrl = SITE_URL): Promise<UnsubscribeLinks> {
  const q = new URLSearchParams({ u: userId, c: category, t: await unsubscribeToken(secret, userId, category) }).toString();
  return { oneClick: `${siteUrl}/api/email/unsubscribe?${q}`, page: `${siteUrl}/unsubscribe?${q}` };
}

/** The mail headers for an opt-out category (Gmail / Yahoo bulk-sender rules). */
export function unsubscribeHeaders(links: UnsubscribeLinks): Record<string, string> {
  return { "List-Unsubscribe": `<${links.oneClick}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" };
}
