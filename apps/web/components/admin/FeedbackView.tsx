"use client";

import { useState } from "react";
import { Tabs } from "@/components/ui/Tabs";
import { cx } from "@/components/ui/cx";
import type { AdminFeedbackResponse, AdminFeedbackRow } from "@/lib/admin/lifecycle";
import { fmtAgo, fmtDate, fmtInt } from "@/lib/admin/format";
import { CANCEL_REASONS } from "@/lib/billing/cancel";
import { FEEDBACK_STATUSES, type FeedbackStatus } from "@/lib/feedback/shared";
import { Section, Stat, StatGrid, Table, Td, Tr } from "./ui";

const REASON_LABEL: Record<string, string> = Object.fromEntries(CANCEL_REASONS.map((r) => [r.id, r.label]));
const STATUS_LABEL: Record<FeedbackStatus, string> = { new: "New", triaged: "Triaged", done: "Done" };
export type FeedbackFilter = FeedbackStatus | "all";

function StatusSelect({ row, onChange }: { row: AdminFeedbackRow; onChange: (id: string, s: FeedbackStatus) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  return (
    <select
      aria-label={`Status of ${row.kind} from ${row.email ?? "a deleted account"}`}
      value={row.status}
      disabled={busy}
      onChange={async (e) => {
        setBusy(true);
        await onChange(row.id, e.target.value as FeedbackStatus);
        setBusy(false);
      }}
      className="h-8 rounded-sm border border-line bg-bg-2 px-2 text-xs text-fg focus-visible:focus-ring disabled:opacity-50"
    >
      {FEEDBACK_STATUSES.map((s) => (
        <option key={s} value={s}>
          {STATUS_LABEL[s]}
        </option>
      ))}
    </select>
  );
}

/** /admin/feedback: what users told us (feedback, cancellation reasons) and which addresses we no longer mail. */
export function FeedbackView({
  data,
  filter,
  onFilter,
  onStatus,
  base = "/admin",
  now,
}: {
  data: AdminFeedbackResponse;
  filter: FeedbackFilter;
  onFilter: (f: FeedbackFilter) => void;
  onStatus: (id: string, status: FeedbackStatus) => Promise<void>;
  base?: string;
  now?: number;
}) {
  const reasons = Object.entries(
    data.cancellations.reduce<Record<string, number>>((acc, c) => ({ ...acc, [c.reason]: (acc[c.reason] ?? 0) + 1 }), {}),
  ).sort((a, b) => b[1] - a[1]);
  const saved = data.cancellations.filter((c) => c.outcome !== "canceled").length;
  const sentTotal = Object.values(data.emailsSent).reduce((a, n) => a + n, 0);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Feedback</h1>
        <p className="text-sm text-fg-muted">Bug reports, ideas and questions from the app, why people cancel, and the addresses we no longer email.</p>
      </div>

      <Section
        title="From users"
        description="Newest first. Page is a route template; browser is a family. No screenshots, no URLs."
        actions={
          <Tabs
            items={[{ id: "all", label: "All" }, ...FEEDBACK_STATUSES.map((s) => ({ id: s, label: STATUS_LABEL[s] }))]}
            value={filter}
            onChange={(id) => onFilter(id as FeedbackFilter)}
            label="Status"
          />
        }
      >
        {data.feedback.length === 0 ? (
          <p className="rounded-md border border-line px-3 py-6 text-center text-sm text-fg-muted">No feedback here.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.feedback.map((f) => (
              <li key={f.id} className={cx("flex flex-col gap-2 rounded-md border border-line bg-bg-1 p-3", f.status === "done" && "opacity-70")}>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-muted">
                  <span className={cx("inline-flex h-5 items-center rounded-full bg-bg-3 px-2 font-medium", f.kind === "bug" ? "text-danger" : "text-fg")}>
                    {f.kind}
                  </span>
                  {f.user_id ? (
                    <a href={`${base}/users/${f.user_id}`} className="text-fg hover:underline focus-visible:focus-ring">
                      {f.email ?? f.user_id.slice(0, 8)}
                    </a>
                  ) : (
                    <span>deleted account</span>
                  )}
                  <span className="font-code">{f.page ?? "—"}</span>
                  <span className="font-code">{f.release ?? "—"}</span>
                  <span>{f.ua_family ?? "—"}</span>
                  <span title={`${fmtDate(f.created_at)} UTC`}>{fmtAgo(f.created_at, now)}</span>
                  <span className="ml-auto">
                    <StatusSelect row={f} onChange={onStatus} />
                  </span>
                </div>
                <p className="whitespace-pre-wrap break-words text-sm text-fg">{f.message}</p>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Why people cancel" description="From the in-app cancel flow. Paused and downgraded count as saved.">
        <StatGrid>
          <Stat label="Responses" value={fmtInt(data.cancellations.length)} />
          <Stat label="Saved (pause or downgrade)" value={fmtInt(saved)} />
          {reasons.slice(0, 2).map(([r, n]) => (
            <Stat key={r} label={REASON_LABEL[r] ?? r} value={fmtInt(n)} />
          ))}
        </StatGrid>
        <Table label="Cancellation reasons" head={["When", "Account", "Plan", "Reason", "Outcome", "Note"]} empty="No cancellations yet.">
          {data.cancellations.map((c) => (
            <Tr key={c.id}>
              <Td className="text-fg-muted" title={`${fmtDate(c.created_at)} UTC`}>{fmtAgo(c.created_at, now)}</Td>
              <Td>{c.user_id ? <a href={`${base}/users/${c.user_id}`} className="hover:underline focus-visible:focus-ring">{c.email ?? c.user_id.slice(0, 8)}</a> : "deleted"}</Td>
              <Td>{c.plan ?? "—"}</Td>
              <Td>{REASON_LABEL[c.reason] ?? c.reason}</Td>
              <Td className={c.outcome === "canceled" ? "text-fg-muted" : "text-success"}>{c.outcome}</Td>
              <Td className="max-w-80 whitespace-normal text-fg-muted">{c.detail ?? "—"}</Td>
            </Tr>
          ))}
        </Table>
      </Section>

      <Section title="Email" description="Lifecycle mail sent in the last 30 days, and addresses that bounced or complained (they get no tips or render mail).">
        <StatGrid>
          <Stat label="Sent, 30 days" value={fmtInt(sentTotal)} sub={Object.entries(data.emailsSent).map(([k, n]) => `${k} ${n}`).join(" · ") || "none"} />
          <Stat label="Suppressed addresses" value={fmtInt(data.suppressions.length)} />
        </StatGrid>
        <Table label="Suppressed addresses" head={["Address", "Reason", "Since", "Last event"]} empty="No bounces or complaints.">
          {data.suppressions.map((s) => (
            <Tr key={s.email}>
              <Td>{s.email}</Td>
              <Td className={s.reason === "complaint" ? "text-danger" : "text-fg-muted"}>{s.reason}</Td>
              <Td className="text-fg-muted">{fmtDate(s.created_at)}</Td>
              <Td className="text-fg-muted">{fmtAgo(s.updated_at, now)}</Td>
            </Tr>
          ))}
        </Table>
      </Section>
    </div>
  );
}
