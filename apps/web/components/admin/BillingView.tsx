"use client";

import Link from "next/link";
import { fmtCredits, fmtDate, fmtMoney, shortId } from "@/lib/admin/format";
import type { BillingEventRow, BillingResponse } from "@/lib/admin/types";
import { Notice, Section, StatusPill, Table, Td, Tr } from "./ui";

function EventsTable({ rows, label, empty }: { rows: BillingEventRow[]; label: string; empty: string }) {
  return (
    <Table label={label} head={["Received (UTC)", "Event", "Type", "Outcome", "Detail"]} empty={empty}>
      {rows.map((e) => (
        <Tr key={e.event_id}>
          <Td className="text-fg-muted">{fmtDate(e.received_at)}</Td>
          <Td className="font-code text-xs">{e.event_id}</Td>
          <Td>{e.event_type}</Td>
          <Td>
            <StatusPill status={e.outcome} />
          </Td>
          <Td className="max-w-80 truncate text-fg-muted" title={e.detail ?? undefined}>
            {e.detail ?? ""}
          </Td>
        </Tr>
      ))}
    </Table>
  );
}

export function BillingView({ data, base = "/admin" }: { data: BillingResponse; base?: string }) {
  const attention = data.problems.length + data.errors.length;
  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
      {attention === 0 ? (
        <Notice tone="success">No failed or unmatched webhook events.</Notice>
      ) : (
        <Notice tone="danger">
          {attention} webhook {attention === 1 ? "event needs" : "events need"} a look. Paddle retries failed deliveries for up to 3 days; an
          unmatched event granted nothing.
        </Notice>
      )}

      {data.errors.length > 0 && (
        <Section title="Failed webhook deliveries" description="Signature was valid but the event could not be applied. Paddle retries these.">
          <Table label="Webhook errors" head={["Received (UTC)", "Stage", "Event", "Type", "Code", "Message"]}>
            {data.errors.map((e) => (
              <Tr key={e.id}>
                <Td className="text-fg-muted">{fmtDate(e.received_at)}</Td>
                <Td>
                  <StatusPill status={e.stage} />
                </Td>
                <Td className="font-code text-xs">{e.event_id ?? "—"}</Td>
                <Td>{e.event_type ?? "—"}</Td>
                <Td className="font-code text-xs">{e.code ?? ""}</Td>
                <Td className="max-w-96 truncate text-fg-muted" title={e.message ?? undefined}>
                  {e.message ?? ""}
                </Td>
              </Tr>
            ))}
          </Table>
        </Section>
      )}

      {data.problems.length > 0 && (
        <Section title="Unmatched or stale events" description="Recorded, but no account or subscription matched.">
          <EventsTable rows={data.problems} label="Problem events" empty="" />
        </Section>
      )}

      <Section title="Recent transactions" description="Completed Paddle transactions that granted credits.">
        <Table label="Transactions" head={["When (UTC)", "User", "Kind", "Amount", "Credits", "Transaction"]} empty="No transactions yet.">
          {data.transactions.map((t) => (
            <Tr key={t.id}>
              <Td className="text-fg-muted">{fmtDate(t.created_at)}</Td>
              <Td className="max-w-56 truncate">
                {t.user_id ? (
                  <Link href={`${base}/users/${t.user_id}`} className="hover:underline focus-visible:focus-ring" title={t.user_id}>
                    {t.email ?? shortId(t.user_id)}
                  </Link>
                ) : (
                  <span className="text-fg-muted">Deleted account</span>
                )}
              </Td>
              <Td>{t.kind === "subscription" ? `plan ${t.plan ?? ""}` : "pack"}</Td>
              <Td>{fmtMoney(t.total_minor, t.currency_code ?? "USD")}</Td>
              <Td>
                {fmtCredits(t.credits_granted)}
                {t.credits_reversed > 0 && <span className="ml-1 text-xs text-danger">−{t.credits_reversed}</span>}
              </Td>
              <Td className="font-code text-xs text-fg-muted">{t.id}</Td>
            </Tr>
          ))}
        </Table>
      </Section>

      {data.adjustments.length > 0 && (
        <Section title="Refunds and chargebacks">
          <Table label="Adjustments" head={["When (UTC)", "Action", "Credits", "Transaction", "User"]}>
            {data.adjustments.map((a) => (
              <Tr key={a.id}>
                <Td className="text-fg-muted">{fmtDate(a.created_at)}</Td>
                <Td>{a.action}</Td>
                <Td>{fmtCredits(a.credits)}</Td>
                <Td className="font-code text-xs">{a.transaction_id}</Td>
                <Td>
                  {a.user_id ? (
                    <Link href={`${base}/users/${a.user_id}`} className="font-code text-xs hover:underline">
                      {shortId(a.user_id)}
                    </Link>
                  ) : (
                    <span className="text-fg-muted">Deleted account</span>
                  )}
                </Td>
              </Tr>
            ))}
          </Table>
        </Section>
      )}

      {data.unapplied.length > 0 && (
        <Section
          title="Refunds with nothing to take back"
          description="Paddle refunded or charged back a payment that never granted credits (a $0 or unknown transaction), or whose account was deleted. Recorded so Paddle stops retrying; if the payment arrives later, the refund is applied then."
        >
          <Table label="Unapplied refunds" head={["Received (UTC)", "Action", "Why", "Transaction", "Adjustment", "Resolved"]}>
            {data.unapplied.map((u) => (
              <Tr key={u.adjustment_id}>
                <Td className="text-fg-muted">{fmtDate(u.received_at)}</Td>
                <Td>{u.action}</Td>
                <Td>{u.reason === "account_deleted" ? "Account deleted" : "No payment applied"}</Td>
                <Td className="font-code text-xs">{u.transaction_id}</Td>
                <Td className="font-code text-xs text-fg-muted">{u.adjustment_id}</Td>
                <Td className="text-fg-muted">{u.resolved_at ? `${u.resolved_outcome ?? "applied"} ${fmtDate(u.resolved_at)}` : "—"}</Td>
              </Tr>
            ))}
          </Table>
        </Section>
      )}

      <details className="rounded-md border border-line bg-bg-1">
        <summary className="cursor-pointer px-3 py-2 text-sm focus-visible:focus-ring">All recent webhook events ({data.events.length})</summary>
        <div className="p-2">
          <EventsTable rows={data.events} label="Recent webhook events" empty="No webhook events yet." />
        </div>
      </details>
    </div>
  );
}
