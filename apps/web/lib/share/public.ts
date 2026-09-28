import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { SITE_URL } from "@/lib/site";
import { shareMediaPath, sharePath, type GoneReason, type PublicShare } from "./types";

export const SUPPORT_EMAIL = "support@valora3d.com";

/**
 * The video's pixel size: the worker's own report when present, else what the tier renders
 * (preview 540p, final 1080p) in the requested aspect (default 9:16).
 */
export function videoSize(
  kind: "preview" | "final",
  aspect: string | null | undefined,
  width?: number | null,
  height?: number | null,
): { width: number; height: number } {
  if (width && height && width > 0 && height > 0 && width <= 8192 && height <= 8192) return { width, height };
  const short = kind === "final" ? 1080 : 540;
  const long = kind === "final" ? 1920 : 960;
  return aspect === "16:9" ? { width: long, height: short } : { width: short, height: long };
}

const clip = (s: string, max: number) => (s.length > max ? `${s.slice(0, max - 1).trimEnd()}…` : s);

/** Mailto for the page's report link: the slug identifies the video, nothing about the viewer. */
export function reportHref(slug: string): string {
  const subject = `Report shared render ${slug}`;
  const body = `I'm reporting the shared render at ${SITE_URL}${sharePath(slug)} because: `;
  return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

/**
 * Metadata for a live share. Always noindex: a shared link is for the people it was sent to, not search.
 * og:video points at the page's own video route (a redirect to a short-lived storage link), so the tags stay
 * valid after any single signed URL expires. X's "player" card needs an embeddable iframe page, which the
 * site's frame-ancestors 'none' forbids, so X gets summary_large_image with the poster.
 */
export function shareMetadata(share: PublicShare, siteUrl: string = SITE_URL): Metadata {
  const title = `A render made with ${BRAND.name}`;
  const description = share.prompt
    ? clip(`“${share.prompt}”, rendered with ${BRAND.name}.`, 200)
    : `Watch this render, made with ${BRAND.name} from a 3D model and a few words.`;
  const url = `${siteUrl}${sharePath(share.slug)}`;
  const video = `${siteUrl}${shareMediaPath(share.slug, "video")}`;
  const poster = `${siteUrl}${shareMediaPath(share.slug, "poster")}`;
  const { width, height } = share;
  return {
    title,
    description,
    robots: { index: false, follow: false, nocache: true },
    openGraph: {
      type: "video.other",
      title,
      description,
      url,
      siteName: BRAND.name,
      images: [{ url: poster, width, height, alt: title }],
      videos: [{ url: video, secureUrl: video, type: "video/mp4", width, height }],
    },
    twitter: { card: "summary_large_image", title, description, images: [poster] },
  };
}

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const GONE_COPY: Record<GoneReason, string> = {
  revoked: "The person who shared this render has stopped sharing it.",
  expired: "This render has expired and its video was deleted.",
};

/**
 * The friendly 410 page, self-contained (the proxy answers with it before any page renders, so it cannot use
 * the app's stylesheet). Neutral near-black, white text, no accent, like the rest of the site.
 */
export function goneHtml(reason: GoneReason): string {
  const title = "This render is no longer available";
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>${esc(title)} · ${esc(BRAND.name)}</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100dvh; display: flex; flex-direction: column; background: #0d0d0d; color: #ececec;
    font: 16px/1.5 Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; -webkit-font-smoothing: antialiased; }
  header { padding: 20px; border-bottom: 1px solid #ffffff1a; }
  header a { color: #ececec; font-weight: 600; text-decoration: none; }
  main { flex: 1; display: flex; align-items: center; justify-content: center; padding: 48px 16px; }
  .card { max-width: 440px; text-align: center; display: flex; flex-direction: column; gap: 12px; align-items: center; }
  h1 { margin: 0; font-size: 24px; line-height: 1.25; font-weight: 600; letter-spacing: -0.01em; }
  p { margin: 0; color: #b4b4b4; }
  .cta { margin-top: 12px; display: inline-flex; align-items: center; height: 40px; padding: 0 20px; border-radius: 999px;
    background: #ffffff; color: #0d0d0d; font-weight: 500; font-size: 14px; text-decoration: none; }
  .home { color: #b4b4b4; font-size: 14px; }
  a:focus-visible { outline: 2px solid #ececec; outline-offset: 3px; }
</style>
</head>
<body>
<header><a href="/">${esc(BRAND.name)}</a></header>
<main>
  <div class="card">
    <h1>${esc(title)}</h1>
    <p>${esc(GONE_COPY[reason])}</p>
    <a class="cta" href="/signup">Make your own with ${esc(BRAND.name)}</a>
    <a class="home" href="/">Go to the home page</a>
  </div>
</main>
</body>
</html>`;
}

export function goneResponse(reason: GoneReason): Response {
  return new Response(goneHtml(reason), {
    status: 410,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      // A revoked or expired slug never comes back (sharing again mints a new one).
      "Cache-Control": "public, max-age=300",
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
}
