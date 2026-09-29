import { serverConfig } from "@/lib/env";
import { CATEGORY_COLUMN } from "@/lib/email/categories";
import { isOptOutCategory, verifyUnsubscribeToken } from "@/lib/email/unsubscribe";
import { limitHygieneRequest } from "@/lib/server/hygieneRequest";
import { createServiceSupabase } from "@/lib/supabase/server";

/**
 * One-click unsubscribe (RFC 8058), no login: the List-Unsubscribe header of every product-tips and render mail points
 * here. Mail providers POST `List-Unsubscribe=One-Click` to the header URL (u, c, t in the query); the /unsubscribe page
 * posts the same three fields as a form and gets redirected back to its "done" state. The token is an HMAC of
 * (user id, category) (lib/email/unsubscribe.ts), so a link can only ever turn one category off for one account.
 * Cross-site by design (no same-origin check); it is rate-limited per IP. GET never changes anything: it forwards to
 * the confirmation page, so link scanners that prefetch URLs cannot unsubscribe anyone.
 */

const HEADERS = { "Cache-Control": "no-store", "X-Robots-Tag": "noindex" } as const;

function fields(url: URL, form: URLSearchParams | null) {
  const pick = (k: string) => form?.get(k) ?? url.searchParams.get(k) ?? "";
  return { u: pick("u"), c: pick("c"), t: pick("t"), fromPage: form?.get("from") === "page" };
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const page = new URL("/unsubscribe", url);
  for (const k of ["u", "c", "t"]) {
    const v = url.searchParams.get(k);
    if (v) page.searchParams.set(k, v.slice(0, 100));
  }
  return Response.redirect(page, 303);
}

export async function POST(request: Request) {
  const limited = await limitHygieneRequest(request);
  if (limited) return limited;
  const url = new URL(request.url);
  let form: URLSearchParams | null = null;
  const type = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (type.startsWith("application/x-www-form-urlencoded") || type.startsWith("multipart/form-data")) {
    try {
      const body = await request.formData();
      form = new URLSearchParams();
      for (const k of ["u", "c", "t", "from"]) {
        const v = body.get(k);
        if (typeof v === "string") form.set(k, v.slice(0, 200));
      }
    } catch {
      form = null;
    }
  }
  const { u, c, t, fromPage } = fields(url, form);
  const back = (state: string) => Response.redirect(new URL(`/unsubscribe?${state}`, url), 303);

  const config = serverConfig();
  if (!config) return fromPage ? back("error=unavailable") : new Response("Unavailable", { status: 503, headers: HEADERS });
  if (!isOptOutCategory(c) || !(await verifyUnsubscribeToken(config.unsubscribeSecret, u, c, t))) {
    return fromPage ? back("error=invalid") : new Response("Invalid link", { status: 400, headers: HEADERS });
  }
  const { error } = await createServiceSupabase(config)
    .from("profiles")
    .update({ [CATEGORY_COLUMN[c]]: false })
    .eq("id", u);
  if (error) return fromPage ? back("error=unavailable") : new Response("Try again later", { status: 500, headers: HEADERS });
  // A deleted account has nothing left to unsubscribe: the answer is the same, so a link reveals nothing.
  return fromPage ? back(`done=${c}`) : new Response("Unsubscribed", { status: 200, headers: HEADERS });
}
