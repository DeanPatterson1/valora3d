import { fail, ok, type Result } from "./result";

/**
 * Error codes for failures that are not about the domain: every real network call maps to one of
 * these or to the `{ error: { code, message } }` the API route returned.
 */
export const TRANSPORT_ERRORS = {
  unauthorized: "Your session has ended. Sign in again.",
  offline: "You appear to be offline. Check your connection and try again.",
  server: "Something went wrong on our side. Try again in a minute.",
  rate_limited: "Too many requests. Wait a moment and try again.",
} as const;
export type TransportErrorCode = keyof typeof TRANSPORT_ERRORS;

/** Maps an HTTP response to a Result. Pure apart from reading the body. */
export async function responseToResult<T>(res: Response): Promise<Result<T>> {
  let body: unknown = null;
  if (res.status !== 204) {
    try {
      body = await res.json();
    } catch {
      body = null;
    }
  }
  if (res.ok) return ok(body as T);
  const err = (body as { error?: { code?: unknown; message?: unknown } } | null)?.error;
  const code = typeof err?.code === "string" ? err.code : null;
  const message = typeof err?.message === "string" ? err.message : null;
  if (res.status === 401) return fail("unauthorized", message ?? TRANSPORT_ERRORS.unauthorized);
  if (res.status === 429) return fail("rate_limited", message ?? TRANSPORT_ERRORS.rate_limited);
  if (code && message && res.status < 500) return fail(code, message);
  return fail("server", TRANSPORT_ERRORS.server);
}

/** Same-origin JSON call to an API route, with the transport errors mapped. */
export async function apiFetch<T>(path: string, init: RequestInit = {}, fetchImpl: typeof fetch = fetch): Promise<Result<T>> {
  let res: Response;
  try {
    res = await fetchImpl(path, {
      ...init,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
  } catch {
    return fail("offline", TRANSPORT_ERRORS.offline);
  }
  return responseToResult<T>(res);
}

/** Maps a supabase-js / PostgREST error to the taxonomy. */
export function supabaseErrorToResult<T = never>(error: { message: string; status?: number; code?: string } | null | undefined): Result<T> {
  if (!error) return fail("server", TRANSPORT_ERRORS.server);
  if (error.status === 401 || error.code === "PGRST301") return fail("unauthorized", TRANSPORT_ERRORS.unauthorized);
  if (error.status === 429) return fail("rate_limited", TRANSPORT_ERRORS.rate_limited);
  if (/fetch|network/i.test(error.message) && !error.status) return fail("offline", TRANSPORT_ERRORS.offline);
  return fail("server", TRANSPORT_ERRORS.server);
}
