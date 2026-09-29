"use client";

import Link from "next/link";
import { useState } from "react";
import { fmtBytes, fmtCredits, fmtDate, fmtInt, fmtMoney, shortId } from "@/lib/admin/format";
import type { UserDetailResponse } from "@/lib/admin/types";
import { ActionForm, type ActionResult } from "./ActionForm";
import { AuditTable } from "./AuditTable";
import { RendersTable } from "./RendersView";
import { KeyValues, Section, StatusPill, Table, Td, Tr } from "./ui";

export type CreditsAction = (input: { amount: number; reason: string; requestId: string }) => Promise<ActionResult>;

const MAX_ADJUST = 100_000;

function CreditAdjust({ balance, onSubmit }: { balance: number; onSubmit: CreditsAction }) {
  const [direction, setDirection] = useState<"grant" | "deduct">("grant");
  const [amount, setAmount] = useState("");
  const n = Number(amount);
  const valid = Number.isInteger(n) && n > 0 && n <= MAX_ADJUST;
  const signed = direction === "grant" ? n : -n;
  return (
    <ActionForm
      label="Adjust credits"
      confirmLabel={valid ? `${direction === "grant" ? "Grant" : "Deduct"} ${fmtInt(n)} credits` : "Adjust credits"}
      description={`Adds a ledger row (admin adjustment) with your account and the reason. Balance now ${fmtInt(balance)}${valid ? `, after ${fmtInt(balance + signed)}` : ""}. A deduction may take the balance below zero, which blocks renders.`}
      danger={direction === "deduct"}
      valid={valid}
      onSubmit={({ reason, requestId }) => onSubmit({ amount: signed, reason, requestId })}
    >
      <fieldset className="flex flex-wrap items-end gap-3">
        <legend className="sr-only">Adjustment</legend>
        <div className="inline-flex rounded-full bg-bg-2 p-1" role="radiogroup" aria-label="Direction">
          {(["grant", "deduct"] as const).map((d) => (
            <button
              key={d}
              type="button"
              role="radio"
              aria-checked={direction === d}
              onClick={() => setDirection(d)}
              className={`h-7 rounded-full px-3 text-sm capitalize focus-visible:focus-ring ${direction === d ? "bg-bg-3 text-fg" : "text-fg-muted hover:text-fg"}`}
            >
              {d}
            </button>
          ))}
        </div>
        <label className="flex flex-col gap-1 text-sm">
          Credits
          <input
            type="number"
            inputMode="numeric"
            min={1}
            max={MAX_ADJUST}
            step={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
            className="h-9 w-32 rounded-sm border border-line bg-bg-2 px-3 text-sm text-fg tabular-nums outline-none focus-visible:focus-ring"
          />
        </label>
      </fieldset>
    </ActionForm>
  );
}

export function UserDetailView({ detail, onAdjust, base = "/admin" }: { detail: UserDetailResponse; onAdjust: CreditsAction; base?: string }) {
  const { user } = detail;
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <Link href={`${base}/users`} className="w-fit text-sm text-fg-muted hover:text-fg focus-visible:focus-ring">
          ← Users
        </Link>
        <h1 className="break-all text-xl font-semibold tracking-tight">{user.email || user.id}</h1>
        <p className="font-code text-xs text-fg-muted">{user.id}</p>
      </div>

      <Section title="Account">
        <KeyValues
          items={[
            ["Balance", <span key="b" className={user.balance < 0 ? "text-danger" : undefined}>{fmtInt(user.balance)} credits</span>],
            ["Plan", user.live_plan === user.plan ? user.live_plan : `${user.live_plan} (profile shows ${user.plan})`],
            ["Name", user.name || "—"],
            ["Joined", `${fmtDate(user.created_at)} UTC`],
            ["Admin", user.is_admin ? "yes" : "no"],
          ]}
        />
        <CreditAdjust balance={user.balance} onSubmit={onAdjust} />
      </Section>

      <Section title="Ledger" description="Newest first, last 100 rows.">
        <Table label="Credit ledger" head={["When (UTC)", "Reason", "Credits", "Ref"]} empty="No ledger rows.">
          {detail.ledger.map((l) => (
            <Tr key={l.id}>
              <Td className="text-fg-muted">{fmtDate(l.created_at)}</Td>
              <Td>{l.reason}</Td>
              <Td className={l.amount < 0 ? "text-fg-muted" : undefined}>{fmtCredits(l.amount)}</Td>
              <Td className="font-code text-xs text-fg-muted">
                {l.job_id ? (
                  <Link href={`${base}/renders/${l.job_id}`} className="hover:underline">
                    {l.ref}
                  </Link>
                ) : (
                  l.ref
                )}
              </Td>
            </Tr>
          ))}
        </Table>
      </Section>

      <Section
        title="Renders"
        actions={
          <Link href={`${base}/renders?user=${user.id}`} className="text-sm text-fg-muted hover:text-fg focus-visible:focus-ring">
            All renders →
          </Link>
        }
      >
        <RendersTable jobs={detail.jobs} base={base} showUser={false} />
      </Section>

      <Section title="Uploads">
        <Table label="Uploads" head={["File", "Status", "Size", "Uploaded (UTC)", "Note"]} empty="No uploads.">
          {detail.uploads.map((u) => (
            <Tr key={u.id}>
              <Td className="max-w-64 truncate" title={u.id}>
                {u.file_name}
                {u.source === "sample" && <span className="ml-1.5 text-xs text-fg-muted">sample</span>}
              </Td>
              <Td>
                <StatusPill status={u.status} />
              </Td>
              <Td>{fmtBytes(u.size_bytes)}</Td>
              <Td className="text-fg-muted">{fmtDate(u.created_at)}</Td>
              <Td className="text-fg-muted">{u.expired_at ? "expired" : (u.reject_reason ?? "")}</Td>
            </Tr>
          ))}
        </Table>
      </Section>

      <Section title="Billing">
        <Table label="Subscriptions" head={["Subscription", "Plan", "Status", "Period ends", "Paid through"]} empty="No subscriptions.">
          {detail.subscriptions.map((s) => (
            <Tr key={s.id}>
              <Td className="font-code text-xs">{s.id}</Td>
              <Td className="capitalize">{s.plan}</Td>
              <Td>
                <StatusPill status={s.status} />
              </Td>
              <Td className="text-fg-muted">{fmtDate(s.current_period_end)}</Td>
              <Td className="text-fg-muted">{fmtDate(s.paid_through)}</Td>
            </Tr>
          ))}
        </Table>
        <Table label="Transactions" head={["Transaction", "Kind", "Amount", "Credits", "When (UTC)"]} empty="No transactions.">
          {detail.transactions.map((t) => (
            <Tr key={t.id}>
              <Td className="font-code text-xs" title={t.id}>
                {shortId(t.id.replace(/^txn_/, ""))}
              </Td>
              <Td>{t.kind === "subscription" ? `plan ${t.plan ?? ""}` : "pack"}</Td>
              <Td>{fmtMoney(t.total_minor, t.currency_code ?? "USD")}</Td>
              <Td>
                {fmtCredits(t.credits_granted)}
                {t.credits_reversed > 0 && <span className="ml-1 text-xs text-danger">−{t.credits_reversed} reversed</span>}
              </Td>
              <Td className="text-fg-muted">{fmtDate(t.created_at)}</Td>
            </Tr>
          ))}
        </Table>
      </Section>

      <Section title="Admin actions on this user">
        <AuditTable rows={detail.audit} base={base} showTarget={false} />
      </Section>
    </div>
  );
}
