/**
 * Only same-origin paths survive as a post-login destination. The URL parser strips tabs and
 * newlines and treats `\` as `/`, so `/%09/evil.com` or `/\evil.com` would otherwise become
 * `//evil.com`: refuse control characters and backslashes, then resolve against a sentinel origin
 * and keep only a result that stayed on it.
 */
export function safeNextPath(raw: string | null | undefined, fallback = "/projects"): string {
  if (!raw || !raw.startsWith("/") || /[\u0000-\u001f\u007f\\]/.test(raw)) return fallback;
  let url: URL;
  try {
    url = new URL(raw, "http://sentinel.invalid");
  } catch {
    return fallback;
  }
  if (url.origin !== "http://sentinel.invalid") return fallback;
  return url.pathname + url.search + url.hash;
}
