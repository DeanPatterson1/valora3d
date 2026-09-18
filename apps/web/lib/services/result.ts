export type ServiceError = { code: string; message: string; hints?: string[] };
export type Warning = { code: string; message: string };
export type Result<T> = { ok: true; value: T; warnings?: Warning[] } | { ok: false; error: ServiceError };

export const ok = <T>(value: T, warnings?: Warning[]): Result<T> =>
  warnings?.length ? { ok: true, value, warnings } : { ok: true, value };
export const fail = <T = never>(code: string, message: string, hints?: string[]): Result<T> => ({
  ok: false,
  error: { code, message, ...(hints ? { hints } : {}) },
});
/** Re-wrap an existing ServiceError under a new Result type, preserving hints. */
export const failFrom = <T = never>(error: ServiceError): Result<T> => ({ ok: false, error });
