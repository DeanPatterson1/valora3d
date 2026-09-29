import type { SupabaseClient } from "@supabase/supabase-js";
import type { ServerConfig } from "@/lib/env";
import { kindCategory, type LifecycleKind } from "@/lib/email/categories";
import {
  activationNudgeEmail,
  expiryWarningEmail,
  pastDueEmail,
  planCanceledEmail,
  tipsEmail,
  welcomeEmail,
  winbackEmail,
  type Mail,
} from "@/lib/email/lifecycle";
import { sendEmail, type OutgoingEmail } from "@/lib/email/send";
import { unsubscribeLinks, type UnsubscribeLinks } from "@/lib/email/unsubscribe";
import type { PlanId } from "@/lib/pricing";

/**
 * Lifecycle mail, run by the cron sweep (POST /api/renders/sweep, every 5 minutes) and, for billing notices, right
 * after a Paddle subscription event. The database decides who is due (`due_*` functions, 20260930130000_lifecycle.sql);
 * every send is claimed first with `claim_email()` (idempotent on user + kind + ref, applies the preferences, the
 * suppression list and the per-user daily cap) and released if Resend fails, so the next run retries it.
 */

type Rpc = Pick<SupabaseClient, "rpc">;
export type Sender = (mail: OutgoingEmail) => Promise<void>;

export type ClaimResult = "claimed" | "duplicate" | "no_profile" | "suppressed" | "opted_out" | "rate_limited";

export type LifecycleDeps = {
  db: Rpc;
  send: Sender;
  unsubscribeSecret: string;
  siteUrl?: string;
  /** Sends per run, across every kind (one run must stay inside the Worker's subrequest budget). */
  budget?: number;
  now?: Date;
};

export type LifecycleResult = { sent: Partial<Record<LifecycleKind, number>>; skipped: number; failed: number; held: number };

type Recipient = { user_id: string; email: string; name: string };

const PLANS = new Set<PlanId>(["free", "creator", "pro"]);
const planOf = (p: unknown): PlanId => (PLANS.has(p as PlanId) ? (p as PlanId) : "free");

async function rpc<T>(db: Rpc, fn: string, args: Record<string, unknown>): Promise<T> {
  const { data, error } = await db.rpc(fn, args);
  if (error) throw new Error(`${fn} failed: ${error.message}`);
  return data as T;
}

/**
 * Claims, builds and sends one mail. Returns the claim result; a failed send is released and rethrown.
 * `build` gets the unsubscribe links for opt-out kinds (none for account mail).
 */
export async function sendClaimed(
  deps: Pick<LifecycleDeps, "db" | "send" | "unsubscribeSecret" | "siteUrl">,
  to: Recipient,
  kind: LifecycleKind,
  ref: string,
  build: (unsubscribe: UnsubscribeLinks | undefined) => Mail,
): Promise<ClaimResult> {
  const claim = await rpc<ClaimResult>(deps.db, "claim_email", { p_user_id: to.user_id, p_kind: kind, p_ref: ref });
  if (claim !== "claimed") return claim;
  const category = kindCategory(kind);
  try {
    const unsubscribe =
      category === "account" ? undefined : await unsubscribeLinks(deps.unsubscribeSecret, to.user_id, category, deps.siteUrl);
    const mail = build(unsubscribe);
    await deps.send({ to: to.email, ...mail, category, unsubscribe, idempotencyKey: `${kind}:${to.user_id}:${ref}` });
    return "claimed";
  } catch (error) {
    await deps.db.rpc("release_email", { p_user_id: to.user_id, p_kind: kind, p_ref: ref });
    throw error;
  }
}

type BillingRow = Recipient & { kind: "past_due" | "plan_canceled"; ref: string; plan: string; at: string | null };
type ExpiryRow = Recipient & { plan: string; job_ids: string[]; first_expiry: string; render_count: number; retention_days: number };

/** Billing notices due (all accounts, or one). Separate so the Paddle webhook can send them at once. */
export async function runBillingNotices(deps: LifecycleDeps, userId: string | null = null, result = emptyResult()): Promise<LifecycleResult> {
  const rows = await rpc<BillingRow[]>(deps.db, "due_billing_emails", { p_user_id: userId, p_limit: deps.budget ?? 40 });
  for (const row of rows ?? []) {
    if (spent(result) >= (deps.budget ?? 40)) break;
    const input = { name: row.name, siteUrl: deps.siteUrl, plan: planOf(row.plan), at: row.at ? new Date(row.at) : null };
    await attempt(result, row.kind, () =>
      sendClaimed(deps, row, row.kind, row.ref, () => (row.kind === "past_due" ? pastDueEmail(input) : planCanceledEmail(input))),
    );
  }
  return result;
}

const emptyResult = (): LifecycleResult => ({ sent: {}, skipped: 0, failed: 0, held: 0 });
const spent = (r: LifecycleResult) => Object.values(r.sent).reduce((a, n) => a + (n ?? 0), 0) + r.failed;

async function attempt(result: LifecycleResult, kind: LifecycleKind, fn: () => Promise<ClaimResult>): Promise<ClaimResult | "failed"> {
  try {
    const claim = await fn();
    if (claim === "claimed") result.sent[kind] = (result.sent[kind] ?? 0) + 1;
    else if (claim === "rate_limited") result.held += 1;
    else result.skipped += 1;
    return claim;
  } catch {
    result.failed += 1;
    return "failed";
  }
}

const TIPS: { kind: Extract<LifecycleKind, "welcome" | "activation_nudge" | "tips" | "winback">; build: typeof welcomeEmail }[] = [
  { kind: "welcome", build: welcomeEmail },
  { kind: "activation_nudge", build: activationNudgeEmail },
  { kind: "tips", build: tipsEmail },
  { kind: "winback", build: winbackEmail },
];

/** One sweep: billing notices, then expiry warnings, then the product-tips sequence, within one send budget. */
export async function runLifecycle(deps: LifecycleDeps): Promise<LifecycleResult> {
  const budget = deps.budget ?? 40;
  const now = deps.now ?? new Date();
  const result = emptyResult();

  await runBillingNotices(deps, null, result);

  // Expiry warnings: one mail per user per batch (the ref is the UTC day), then the jobs are marked so they are never
  // warned about twice. Opted-out / suppressed users are marked too (nothing to send later); a held one is not.
  if (spent(result) < budget) {
    const rows = await rpc<ExpiryRow[]>(deps.db, "due_expiry_warnings", { p_limit: budget });
    for (const row of rows ?? []) {
      if (spent(result) >= budget) break;
      const claim = await attempt(result, "expiry_warning", () =>
        sendClaimed(deps, row, "expiry_warning", now.toISOString().slice(0, 10), (u) =>
          expiryWarningEmail({
            name: row.name,
            siteUrl: deps.siteUrl,
            unsubscribePage: u?.page,
            count: row.render_count,
            firstExpiry: new Date(row.first_expiry),
            retentionDays: row.retention_days,
            plan: planOf(row.plan),
          }),
        ),
      );
      if (claim !== "failed" && claim !== "rate_limited") await rpc<number>(deps.db, "mark_expiry_warned", { p_job_ids: row.job_ids });
    }
  }

  for (const { kind, build } of TIPS) {
    if (spent(result) >= budget) break;
    const rows = await rpc<Recipient[]>(deps.db, "due_lifecycle_emails", { p_kind: kind, p_limit: budget - spent(result) });
    for (const row of rows ?? []) {
      if (spent(result) >= budget) break;
      await attempt(result, kind, () =>
        sendClaimed(deps, row, kind, "once", (u) => build({ name: row.name, siteUrl: deps.siteUrl, unsubscribePage: u?.page })),
      );
    }
  }
  return result;
}

/** Resend for user mail (lifecycle sender), or null when email is not configured. */
export function lifecycleSender(config: ServerConfig): Sender | null {
  const email = config.email;
  if (!email) return null;
  return (mail) => sendEmail({ resendApiKey: email.resendApiKey, from: config.lifecycleFrom }, mail);
}
