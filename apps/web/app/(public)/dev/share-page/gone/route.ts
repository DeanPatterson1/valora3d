import { goneResponse } from "@/lib/share/public";

/** Dev only: the 410 page a revoked (`?reason=revoked`) or expired share link gets from the proxy. */
export function GET(request: Request) {
  if (process.env.NODE_ENV === "production") return new Response(null, { status: 404 });
  return goneResponse(new URL(request.url).searchParams.get("reason") === "revoked" ? "revoked" : "expired");
}
