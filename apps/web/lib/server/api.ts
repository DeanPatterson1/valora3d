import type { ZodType } from "@/lib/zod";
import { apiError } from "@/lib/supabase/server";

/**
 * Cookie-authenticated routes accept only same-origin browser requests: a cross-site form or
 * fetch carries an Origin that differs from the host. Requests with no Origin (curl, server to
 * server) are refused too; every legitimate caller is the app in the browser.
 */
export function sameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    return new URL(origin).host === new URL(request.url).host;
  } catch {
    return false;
  }
}

export async function readBody<T>(request: Request, schema: ZodType<T>): Promise<T | Response> {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  let raw: unknown;
  try {
    raw = await request.json();
  } catch {
    return apiError(400, "invalid_request", "Expected a JSON body.");
  }
  const parsed = schema.safeParse(raw);
  if (!parsed.success) return apiError(400, "invalid_request", "The request body is not valid.");
  return parsed.data;
}

/** Postgres raise codes used by the SQL functions, mapped to API errors. */
export function sqlErrorResponse(error: { code?: string; message: string }): Response {
  if (error.code === "P0001" && error.message.startsWith("insufficient_credits")) {
    const m = error.message.match(/need (\d+), have (-?\d+)/);
    if (m && Number(m[2]) < 0) {
      return apiError(402, "insufficient_credits", `Your balance is ${m[2]} credits after a refund or chargeback. Add credits to continue.`);
    }
    return apiError(402, "insufficient_credits", m ? `You need ${m[1]} credits but have ${m[2]}.` : "Not enough credits.");
  }
  if (error.code === "P0001" && error.message.startsWith("rate_limited")) {
    return apiError(429, "rate_limited", "You've saved a lot of versions in the last hour. Wait a few minutes and try again.");
  }
  if (error.code === "P0002") return apiError(404, "not_found", "Not found.");
  if (error.code === "23505") return apiError(409, "conflict", "That request was already made with different details.");
  if (error.code === "22023") return apiError(400, "invalid_request", "The request is not valid.");
  return apiError(500, "server", "Something went wrong on our side.");
}
