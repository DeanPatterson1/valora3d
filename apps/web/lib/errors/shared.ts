import { z } from "zod";
import { routeTemplate } from "@/lib/analytics/events";

/**
 * Client error reports (POST /api/client-errors): what a browser may say about an error, and nothing more. No message,
 * stack or URL (they can carry personal data): the error class name, Next's digest, the page as a route template, the
 * build it ran and where it was caught. The server adds the browser family from the User-Agent header.
 */

export const ERROR_KINDS = ["global", "segment", "window", "promise"] as const;
export type ErrorKind = (typeof ERROR_KINDS)[number];

const NAME = /^[A-Za-z][A-Za-z0-9_]{0,59}$/;
const CODE = /^[A-Za-z0-9_:-]{1,40}$/;
const RELEASE = /^[A-Za-z0-9._-]{1,40}$/;

export const ClientErrorReport = z
  .object({
    kind: z.enum(ERROR_KINDS),
    path: z.string().max(300),
    name: z.string().max(100),
    digest: z.string().max(100).optional(),
    release: z.string().max(60),
  })
  .strict();

export type CleanReport = { kind: ErrorKind; path: string; name: string; code: string | null; release: string };

/** Normalises a parsed report: a route template, a class-like name (else "Error"), a digest-like code (else none). */
export function cleanReport(r: z.infer<typeof ClientErrorReport>): CleanReport {
  return {
    kind: r.kind,
    path: routeTemplate(r.path),
    name: NAME.test(r.name) ? r.name : "Error",
    code: r.digest && CODE.test(r.digest) ? r.digest : null,
    release: RELEASE.test(r.release) ? r.release : "unknown",
  };
}

/** Browser family from a User-Agent header: a coarse bucket, never the header itself. Order matters (Edge says Chrome). */
export function uaFamily(ua: string | null | undefined): string {
  if (!ua) return "unknown";
  const mobile = /Mobile|Android|iPhone|iPad/i.test(ua);
  let family = "other";
  if (/bot|crawler|spider|headless/i.test(ua)) family = "bot";
  else if (/Edg\//.test(ua)) family = "edge";
  else if (/OPR\/|Opera/.test(ua)) family = "opera";
  else if (/SamsungBrowser/.test(ua)) family = "samsung";
  else if (/Firefox\/|FxiOS/.test(ua)) family = "firefox";
  else if (/Chrome\/|CriOS/.test(ua)) family = "chrome";
  else if (/Safari\//.test(ua)) family = "safari";
  return mobile && family !== "bot" ? `${family}_mobile` : family;
}

/** The build this bundle came from (next.config.ts sets NEXT_PUBLIC_RELEASE_ID from the git hash at build time). */
export const RELEASE_ID = (process.env.NEXT_PUBLIC_RELEASE_ID ?? "dev").trim() || "dev";
