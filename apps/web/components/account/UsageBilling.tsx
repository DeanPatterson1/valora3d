"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, cx } from "@/components/ui";
import { keptUntil } from "@/components/studio/RenderResult";
import { useCheckout } from "@/components/pricing/useCheckout";
import type { AccountRender, CreditHistoryEntry, Page, SubscriptionSummary } from "@/lib/account/history";
import { services, type Result } from "@/lib/services";
import { useAuthStore } from "@/lib/stores/auth";
import { useCreditsStore } from "@/lib/stores/credits";
import { CancelPlanDialog } from "./CancelPlanDialog";
import { PLAN_LABEL } from "./planLabel";

const DATE: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", year: "numeric" };
const fmtDate = (ms: number) => new Date(ms).toLocaleDateString("en-US", DATE);
const fmtNum = (n: number) => n.toLocaleString("en-US");

type Paged<T> = { data: Page<T> | null; error: string | null; loading: boolean; page: number; go: (page: number) => void };

/** One zero-based page at a time from an account read; keeps the last page on screen while the next loads. */
function usePaged<T>(load: (page: number) => Promise<Result<Page<T>>>): Paged<T> {
  const [page, setPage] = useState(0);
  const [state, setState] = useState<{ data: Page<T> | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true });
  useEffect(() => {
    let live = true;
    void load(page).then((r) => {
      if (!live) return;
      setState((s) => (r.ok ? { data: r.value, error: null, loading: false } : { data: s.data, error: r.error.message, loading: false }));
    });
    return () => {
      live = false;
    };
  }, [load, page]);
  const go = useCallback((p: number) => {
    setState((s) => ({ ...s, loading: true }));
    setPage(Math.max(0, p));
  }, []);
  return { ...state, page, go };
}

function Pager({ label, paged }: { label: string; paged: Paged<unknown> }) {
  const { data, page, loading, go } = paged;
  if (!data || (page === 0 && !data.hasMore)) return null;
  return (
    <nav aria-label={`${label} pages`} className="flex items-center justify-between gap-3 pt-3">
      <Button size="sm" variant="secondary" disabled={page === 0 || loading} onClick={() => go(page - 1)}>
        Newer
      </Button>
      <span className="text-xs text-fg-muted tabular">Page {page + 1}</span>
      <Button size="sm" variant="secondary" disabled={!data.hasMore || loading} onClick={() => go(page + 1)}>
        Older
      </Button>
    </nav>
  );
}

function PlanCard({ subscription, onChanged }: { subscription: SubscriptionSummary | null | undefined; onChanged?: () => void }) {
  const plan = useAuthStore((s) => s.user?.plan ?? "free");
  const balance = useCreditsStore((s) => s.balance);
  const loaded = useCreditsStore((s) => s.loaded);
  const purchased = useCreditsStore((s) => s.ledger.some((t) => t.reason === "pack_purchase" || t.reason === "plan_grant"));
  const billing = useCheckout();
  const server = services.backend === "supabase";
  const showPortal = server && (plan !== "free" || Boolean(subscription) || purchased);
  // In-app cancel: a plan that will renew (a scheduled cancel shows "Ends on" instead).
  const canCancel = server && subscription && subscription.status !== "canceled" && subscription.status !== "paused" && subscription.next?.kind === "renews";
  const [cancelOpen, setCancelOpen] = useState(false);
  const [changed, setChanged] = useState(false);
  // Re-read the plan only once the dialog closes, so its "done" step stays on screen.
  const closeCancel = () => {
    setCancelOpen(false);
    if (changed) {
      setChanged(false);
      onChanged?.();
    }
  };

  let renewal = "One-time credits, no renewal.";
  if (subscription?.next) {
    renewal = `${subscription.next.kind === "renews" ? "Renews" : "Ends"} on ${fmtDate(subscription.next.at)}`;
  } else if (subscription === undefined && plan !== "free") {
    renewal = "Loading renewal date…";
  } else if (plan !== "free") {
    renewal = "Monthly plan";
  }
  if (subscription?.status === "past_due") renewal = `${renewal} · payment overdue`;

  return (
    <section aria-labelledby="plan-heading" className="flex flex-col gap-5 rounded-lg border border-line bg-bg-1 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <h3 id="plan-heading" className="flex items-center gap-2 text-sm text-fg-muted">
          Current plan <Badge>{PLAN_LABEL[subscription?.plan ?? plan]}</Badge>
        </h3>
        <p className="text-sm text-fg">{renewal}</p>
        <p className="text-sm text-fg-muted">
          Balance <span className="tabular text-fg">{loaded ? `${fmtNum(balance)} credits` : "—"}</span>
        </p>
      </div>
      <div className="flex flex-col items-start gap-2 sm:items-end">
        <div className="flex flex-wrap gap-2">
          <Link href="/pricing" className="inline-flex h-9 items-center rounded-full border border-line px-4 text-sm text-fg transition-colors hover:bg-bg-3 focus-visible:focus-ring">
            Get credits
          </Link>
          {showPortal && (
            <Button variant="secondary" loading={billing.pending === "portal"} onClick={() => void billing.manage()}>
              Manage billing / invoices
            </Button>
          )}
        </div>
        {showPortal && <p className="max-w-xs text-xs text-fg-muted sm:text-right">Paddle emails a receipt for every payment. Invoices live in the billing portal.</p>}
        {canCancel && (
          <button
            type="button"
            onClick={() => setCancelOpen(true)}
            className="cursor-pointer rounded-sm text-xs text-fg-muted underline underline-offset-2 transition-colors hover:text-fg focus-visible:focus-ring"
          >
            Cancel plan
          </button>
        )}
      </div>
      {(canCancel || cancelOpen) && subscription && (
        <CancelPlanDialog open={cancelOpen} onClose={closeCancel} onChanged={() => setChanged(true)} subscription={subscription} />
      )}
    </section>
  );
}

function CreditHistory() {
  const load = useCallback((p: number) => services.account.creditHistory(p), []);
  const paged = usePaged<CreditHistoryEntry>(load);
  const rows = paged.data?.items ?? [];
  return (
    <section aria-labelledby="credit-history" className="flex flex-col gap-3">
      <h3 id="credit-history" className="text-lg font-semibold tracking-tight text-fg">
        Credit history
      </h3>
      {paged.error && !paged.data ? (
        <p role="alert" className="text-sm text-fg-muted">{paged.error}</p>
      ) : !paged.data ? (
        <p role="status" className="text-sm text-fg-muted">Loading credit history…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-fg-muted">No credit activity yet.</p>
      ) : (
        <div className={cx("rounded-lg border border-line bg-bg-1", paged.loading && "opacity-60")} aria-busy={paged.loading}>
          <table className="w-full table-fixed text-sm">
            <caption className="sr-only">Credit history, newest first</caption>
            <thead className="text-xs text-fg-muted">
              <tr className="border-b border-line">
                <th scope="col" className="px-4 py-2.5 text-left font-normal">Activity</th>
                <th scope="col" className="hidden w-32 px-4 py-2.5 text-left font-normal sm:table-cell">Date</th>
                <th scope="col" className="w-20 px-4 py-2.5 text-right font-normal sm:w-24">Amount</th>
                <th scope="col" className="w-20 px-4 py-2.5 text-right font-normal sm:w-24">Balance</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-b-0">
                  <td className="px-4 py-3 align-top">
                    <span className="block truncate text-fg">{r.label}</span>
                    <span className="block text-xs text-fg-muted sm:hidden">{fmtDate(r.createdAt)}</span>
                  </td>
                  <td className="hidden px-4 py-3 align-top text-fg-muted sm:table-cell">{fmtDate(r.createdAt)}</td>
                  <td className={cx("px-4 py-3 text-right align-top tabular", r.amount > 0 ? "text-fg" : "text-fg-muted")}>
                    {r.amount > 0 ? `+${fmtNum(r.amount)}` : `−${fmtNum(-r.amount)}`}
                  </td>
                  <td className="px-4 py-3 text-right align-top tabular text-fg-muted">{fmtNum(r.balanceAfter)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {paged.error && paged.data && <p role="alert" className="text-xs text-fg-muted">{paged.error}</p>}
      <Pager label="Credit history" paged={paged as Paged<unknown>} />
    </section>
  );
}

function renderStatus(r: AccountRender): string {
  const j = r.job;
  if (j.status === "COMPLETE") return j.expired ? "Expired" : (keptUntil(j) ?? "Ready");
  if (j.status === "FAILED") return j.refundedCredits ? "Failed · refunded" : "Failed";
  if (j.status === "CANCELLED") return "Cancelled";
  return "Rendering…";
}

function RenderCard({ r }: { r: AccountRender }) {
  const [busy, setBusy] = useState(false);
  const { job } = r;
  const vertical = job.params?.aspect !== "16:9";
  const canDownload = job.status === "COMPLETE" && !job.expired;
  const download = async () => {
    setBusy(true);
    const u = await services.render.downloadUrl(job.id, "video");
    setBusy(false);
    if (u.ok) window.location.assign(u.value);
  };
  return (
    <li className="flex gap-3 rounded-lg border border-line bg-bg-1 p-3">
      <Link
        href={`/projects/${job.projectId}`}
        aria-label={`Open ${r.projectName}`}
        className={cx("relative shrink-0 overflow-hidden rounded-md bg-bg-3 focus-visible:focus-ring", vertical ? "h-24 w-[54px]" : "h-[54px] w-24")}
      >
        {job.posterUrl && (
          // eslint-disable-next-line @next/next/no-img-element -- short-lived presigned URL; next/image cannot cache it
          <img src={job.posterUrl} alt="" loading="lazy" className="size-full object-cover" />
        )}
      </Link>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="truncate text-sm text-fg">{r.projectName}</span>
        <span className="text-xs text-fg-muted">
          {job.kind === "preview" ? "Preview" : "Final"}
          {job.createdAt ? ` · ${fmtDate(job.createdAt)}` : ""}
        </span>
        <span className="text-xs text-fg-muted">{renderStatus(r)}</span>
      </div>
      {canDownload && (
        <Button size="sm" variant="ghost" className="self-center" loading={busy} onClick={() => void download()} aria-label={`Download ${r.projectName}`}>
          Download
        </Button>
      )}
    </li>
  );
}

function RendersList() {
  const load = useCallback((p: number) => services.account.renders(p), []);
  const paged = usePaged<AccountRender>(load);
  const rows = paged.data?.items ?? [];
  return (
    <section aria-labelledby="account-renders" className="flex flex-col gap-3">
      <h3 id="account-renders" className="text-lg font-semibold tracking-tight text-fg">
        Renders
      </h3>
      {paged.error && !paged.data ? (
        <p role="alert" className="text-sm text-fg-muted">{paged.error}</p>
      ) : !paged.data ? (
        <p role="status" className="text-sm text-fg-muted">Loading renders…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-fg-muted">No renders yet. Finished renders from every project show up here.</p>
      ) : (
        <ul aria-label="Renders" aria-busy={paged.loading} className={cx("grid gap-2 md:grid-cols-2", paged.loading && "opacity-60")}>
          {rows.map((r) => (
            <RenderCard key={r.job.id} r={r} />
          ))}
        </ul>
      )}
      <Pager label="Renders" paged={paged as Paged<unknown>} />
    </section>
  );
}

/** Profile -> "Usage & billing": plan, balance, the credit ledger and every render, a page at a time. */
export function UsageBilling() {
  const [subscription, setSubscription] = useState<SubscriptionSummary | null | undefined>(undefined);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let live = true;
    void services.account.subscription().then((r) => live && setSubscription(r.ok ? r.value : null));
    return () => {
      live = false;
    };
  }, [version]);
  return (
    <div className="flex flex-col gap-10">
      <PlanCard subscription={subscription} onChanged={() => setVersion((v) => v + 1)} />
      <CreditHistory />
      <RendersList />
    </div>
  );
}
