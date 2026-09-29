"use client";

import { useState } from "react";
import { Tabs } from "@/components/ui/Tabs";
import { fmtCredits, fmtDate, fmtInt, fmtMoney, fmtPct, fmtSeconds } from "@/lib/admin/format";
import { JOB_STATUSES, type Overview, type WindowKey } from "@/lib/admin/types";
import { Section, Stat, StatGrid, StatusPill, Table, Td, Tr } from "./ui";

const WINDOWS: { id: WindowKey; label: string }[] = [
  { id: "d1", label: "24 hours" },
  { id: "d7", label: "7 days" },
  { id: "d30", label: "30 days" },
];

export function OverviewView({ overview }: { overview: Overview }) {
  const [win, setWin] = useState<WindowKey>("d7");
  const w = overview.windows[win];
  const paying = Object.values(overview.paying).reduce((a, b) => a + Number(b), 0);
  const failures = Number(w.renders.by_status.failed ?? 0);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-xs text-fg-muted">Updated {fmtDate(overview.generated_at)} UTC</p>
      </div>

      <Section title="People">
        <StatGrid>
          <Stat label="Signups today (UTC)" value={fmtInt(overview.signups.today)} sub={`${fmtInt(overview.signups.d7)} in 7 days`} />
          <Stat label="Signups, 30 days" value={fmtInt(overview.signups.d30)} sub={`${fmtInt(overview.signups.total)} accounts in total`} />
          <Stat
            label="Paying users"
            value={fmtInt(paying)}
            sub={`Creator ${fmtInt(overview.paying.creator ?? 0)} · Pro ${fmtInt(overview.paying.pro ?? 0)}`}
          />
          <Stat label="Renders in flight" value={fmtInt(overview.live_renders)} sub="Queued or running now" />
        </StatGrid>
      </Section>

      <div className="flex flex-col gap-6">
        <Tabs items={WINDOWS} value={win} onChange={(id) => setWin(id as WindowKey)} label="Time window" />

        <Section title="Renders" description="Jobs created in the window. Failure rate counts finished jobs only (cancels excluded).">
          <StatGrid>
            <Stat label="Renders" value={fmtInt(w.renders.total)} sub={`${fmtInt(w.renders.finished)} finished`} />
            <Stat label="Failure rate" value={fmtPct(w.renders.failure_rate)} sub={`${fmtInt(failures)} failed`} />
            <Stat label="Avg render time" value={fmtSeconds(w.renders.avg_render_seconds)} sub={`${fmtSeconds(w.renders.avg_wall_seconds)} request to result`} />
            <Stat label="GPU time" value={fmtSeconds(w.renders.gpu_seconds)} sub={`${fmtSeconds(w.renders.execution_seconds)} billed execution`} />
          </StatGrid>
          <div className="flex flex-wrap gap-2 text-xs text-fg-muted">
            {JOB_STATUSES.map((s) => (
              <span key={s} className="inline-flex items-center gap-1.5">
                <StatusPill status={s} /> {fmtInt(w.renders.by_status[s] ?? 0)}
              </span>
            ))}
          </div>
        </Section>

        <Section title="Credits" description="Ledger movement in the window.">
          <StatGrid>
            <Stat label="Granted" value={fmtInt(w.credits.granted)} sub="Signups, plans, packs, admin grants" />
            <Stat label="Spent" value={fmtInt(w.credits.spent)} sub={`${fmtInt(w.credits.refunded)} refunded`} />
            <Stat label="Reversed by billing" value={fmtInt(w.credits.reversed)} sub="Refunds and chargebacks" />
            <Stat label="Deducted by admins" value={fmtInt(w.credits.admin_deducted)} />
          </StatGrid>
          <details className="rounded-md border border-line bg-bg-1">
            <summary className="cursor-pointer px-3 py-2 text-sm focus-visible:focus-ring">By ledger reason</summary>
            <div className="p-2">
              <Table label="Credits by reason" head={["Reason", "Net credits"]} empty="No ledger movement.">
                {Object.entries(w.credits.by_reason).map(([reason, total]) => (
                  <Tr key={reason}>
                    <Td>{reason}</Td>
                    <Td>{fmtCredits(Number(total))}</Td>
                  </Tr>
                ))}
              </Table>
            </div>
          </details>
        </Section>

        <Section title="Revenue" description="Gross from completed Paddle transactions (before Paddle's fees and tax).">
          <StatGrid>
            {w.revenue.length === 0 ? (
              <Stat label="Gross" value="—" sub="No transactions" />
            ) : (
              w.revenue.map((r) => (
                <Stat key={r.currency} label={`Gross, ${r.currency}`} value={fmtMoney(r.gross_minor, r.currency)} sub={`${fmtInt(r.transactions)} transactions`} />
              ))
            )}
            <Stat label="Refunds and chargebacks" value={fmtInt(w.adjustments)} />
            <Stat label="Webhook errors" value={fmtInt(w.webhook_errors)} sub="See Billing" />
          </StatGrid>
        </Section>

        <Section title="Plans" description="Plan shown on each profile (kept in sync with billing).">
          <div className="flex flex-wrap gap-4 text-sm text-fg-muted">
            {["free", "creator", "pro"].map((p) => (
              <span key={p}>
                <span className="capitalize">{p}</span> <span className="tabular-nums text-fg">{fmtInt(overview.plans[p] ?? 0)}</span>
              </span>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}
