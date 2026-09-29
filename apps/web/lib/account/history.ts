import type { CreditTransaction, Plan, RenderJob } from "@/lib/schema";

/** Rows per page on the Profile page's credit history and renders lists. */
export const HISTORY_PAGE_SIZE = 20;

export type Page<T> = { items: T[]; page: number; hasMore: boolean };

/** One row of the credit history as the Profile page shows it. */
export type CreditHistoryEntry = {
  id: string;
  createdAt: number;
  /** Signed: grants positive, spends negative. */
  amount: number;
  /** The balance right after this row. */
  balanceAfter: number;
  /** Plain words: "Final render", "Refund: render failed", "Credit pack 500"… */
  label: string;
  projectId: string | null;
};

/** A render in the account-wide list, with the name of the project it belongs to. */
export type AccountRender = { job: RenderJob; projectName: string };

/** The live subscription as the Profile page summarises it. Null on Free with no subscription. */
export type SubscriptionSummary = {
  plan: Exclude<Plan, "free">;
  status: "active" | "trialing" | "past_due" | "paused" | "canceled";
  /** "renews" while it will bill again; "ends" when it is set to stop (canceled or a scheduled cancel). */
  next: { kind: "renews" | "ends"; at: number } | null;
};

const PLAN_NAMES: Record<string, string> = { free: "Free", creator: "Creator", pro: "Pro" };

export type LedgerLabelInput = {
  /** A credit_ledger reason, or the Local fakes' "starting_balance". */
  reason: CreditTransaction["reason"] | "signup_grant" | (string & {});
  amount: number;
  /** For a monthly plan grant: the plan it was for. */
  plan?: string | null;
  /** For a refund: the status of the render it refunded. */
  jobStatus?: string | null;
};

/** A ledger reason in plain words. Unknown reasons read as "Adjustment", never as a raw code. */
export function ledgerLabel({ reason, amount, plan, jobStatus }: LedgerLabelInput): string {
  switch (reason) {
    case "signup_grant":
      return "Free plan credits";
    case "starting_balance":
      return "Starting credits";
    case "plan_grant":
      return plan && PLAN_NAMES[plan] ? `Monthly ${PLAN_NAMES[plan]} credits` : "Monthly plan credits";
    case "pack_purchase":
      return `Credit pack ${Math.abs(amount).toLocaleString("en-US")}`;
    case "scene_generation":
      return "Scene generation";
    case "prompt_edit":
      return "Prompt edit";
    case "preview_render":
    case "render_preview":
      return "Preview render";
    case "render_final":
      return "Final render";
    case "render_refund":
      return jobStatus === "cancelled" ? "Refund: render cancelled" : "Refund: render failed";
    case "billing_reversal":
      return amount < 0 ? "Payment refunded" : "Adjustment";
    case "admin_adjustment":
    default:
      return "Adjustment";
  }
}

/** Zero-based page -> inclusive PostgREST range. A page asks for one extra row to learn whether more exist. */
export function pageRange(page: number, size = HISTORY_PAGE_SIZE): { from: number; to: number } {
  const p = Number.isFinite(page) && page > 0 ? Math.floor(page) : 0;
  return { from: p * size, to: p * size + size };
}

/** Cuts the look-ahead row off a fetched `pageRange` window. */
export function toPage<T>(rows: T[], page: number, size = HISTORY_PAGE_SIZE): Page<T> {
  return { items: rows.slice(0, size), page: Math.max(0, Math.floor(page) || 0), hasMore: rows.length > size };
}

/** A zero-based page of an already-loaded list (Local mode). */
export function paginate<T>(all: T[], page: number, size = HISTORY_PAGE_SIZE): Page<T> {
  const { from, to } = pageRange(page, size);
  return toPage(all.slice(from, to + 1), page, size);
}

/**
 * Local mode: the whole ledger (oldest first) -> history entries, newest first, each with the balance
 * right after it.
 */
export function localHistory(ledger: CreditTransaction[]): CreditHistoryEntry[] {
  let running = 0;
  const out: CreditHistoryEntry[] = [];
  for (const t of [...ledger].sort((a, b) => a.createdAt - b.createdAt)) {
    running += t.amount;
    out.push({
      id: t.id,
      createdAt: t.createdAt,
      amount: t.amount,
      balanceAfter: running,
      label: ledgerLabel({ reason: t.reason, amount: t.amount }),
      projectId: t.projectId,
    });
  }
  return out.reverse();
}

/** `public.credit_history` as read by the signed-in user (migration 20260929120000_account.sql). */
export type CreditHistoryRow = {
  id: number;
  amount: number;
  reason: string;
  project_id: string | null;
  created_at: string;
  balance_after: number;
  plan: string | null;
  job_status: string | null;
};

export function historyRowToEntry(row: CreditHistoryRow): CreditHistoryEntry {
  return {
    id: String(row.id),
    createdAt: Date.parse(row.created_at),
    amount: row.amount,
    balanceAfter: row.balance_after,
    label: ledgerLabel({ reason: row.reason, amount: row.amount, plan: row.plan, jobStatus: row.job_status }),
    projectId: row.project_id,
  };
}

/** `public.billing_subscriptions` columns the Profile page reads (own rows only, RLS). */
export type SubscriptionRow = {
  plan: string;
  status: string;
  current_period_end: string | null;
  paid_through: string | null;
  canceled_at: string | null;
  scheduled_change: unknown;
};

const STATUSES = new Set(["active", "trialing", "past_due", "paused", "canceled"]);

/** The subscription that decides what the Profile page says, and the renewal / end date to show. */
export function summariseSubscription(rows: SubscriptionRow[], now = Date.now()): SubscriptionSummary | null {
  const time = (iso: string | null | undefined) => (iso ? Date.parse(iso) : NaN);
  // A live one first; else a stopped one still inside its paid period.
  const live = rows.filter((r) => r.status === "active" || r.status === "trialing");
  const lapsing = rows.filter((r) => !live.includes(r) && time(r.paid_through) > now);
  const pick = [...live, ...lapsing].sort((a, b) => (time(b.current_period_end) || 0) - (time(a.current_period_end) || 0))[0];
  if (!pick || (pick.plan !== "creator" && pick.plan !== "pro") || !STATUSES.has(pick.status)) return null;

  const change = pick.scheduled_change as { action?: unknown; effective_at?: unknown } | null;
  const scheduledCancel = change && change.action === "cancel" && typeof change.effective_at === "string" ? time(change.effective_at) : NaN;
  let next: SubscriptionSummary["next"] = null;
  if (Number.isFinite(scheduledCancel)) next = { kind: "ends", at: scheduledCancel };
  else if (pick.status === "active" || pick.status === "trialing") {
    const at = time(pick.current_period_end);
    if (Number.isFinite(at)) next = { kind: "renews", at };
  } else {
    const at = time(pick.paid_through) || time(pick.current_period_end);
    if (Number.isFinite(at)) next = { kind: "ends", at };
  }
  return { plan: pick.plan, status: pick.status as SubscriptionSummary["status"], next };
}
