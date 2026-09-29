/**
 * Share-link slugs: random, unguessable, URL-safe. 18 bytes of Web Crypto randomness (144 bits) as
 * base64url = 24 characters. The database accepts 22-64 (render_shares.slug check), so every slug has
 * at least 128 bits of entropy even if the length changes later.
 */
export const SHARE_SLUG_BYTES = 18;
export const SHARE_SLUG_RE = /^[A-Za-z0-9_-]{22,64}$/;

export function isShareSlug(value: unknown): value is string {
  return typeof value === "string" && SHARE_SLUG_RE.test(value);
}

export function newShareSlug(random: (bytes: Uint8Array) => Uint8Array = (b) => crypto.getRandomValues(b)): string {
  const bytes = random(new Uint8Array(SHARE_SLUG_BYTES));
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
