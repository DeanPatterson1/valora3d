/**
 * Per-user abuse ceilings (not plan limits). Enforced in SQL under the per-user lock from the append-only
 * `usage_events` counter (20260929200000_storage_security.sql: upload_daily_cap / render_daily_cap /
 * input_failure_daily_cap), so deleting a project resets nothing and concurrent requests cannot exceed them.
 * These copies are for messages and tests; lib/server/storagePurge.test.ts pins them to the SQL.
 */
export const UPLOAD_DAILY_CAP = 30;
export const RENDER_DAILY_CAP = 50;
/** Renders that failed because of their model or request (lib/render/failurePolicy.ts), per rolling day. */
export const INPUT_FAILURE_DAILY_CAP = 5;
