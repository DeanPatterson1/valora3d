"use client";

import Link from "next/link";
import { fmtCredits, fmtDate, shortId } from "@/lib/admin/format";
import type { AuditRow } from "@/lib/admin/types";
import { Table, Td, Tr } from "./ui";

const ACTION_LABEL: Record<string, string> = {
  credits_adjust: "Credits",
  render_refund: "Refund",
  render_retry: "Retry",
  flag_update: "Flag",
};

type FlagState = { enabled?: unknown; rollout_percent?: unknown; allowlist?: unknown; value?: unknown };

const onOff = (v: unknown) => (v === true ? "on" : v === false ? "off" : "?");
const limit = (v: unknown) => (v === null || v === undefined ? "—" : String(v));
const count = (v: unknown) => (Array.isArray(v) ? v.length : 0);

/** A flag_update row: only what changed, e.g. "renders_enabled: on → off". */
function flagSummary(row: AuditRow): string {
  const d = row.detail ?? {};
  const before = (d.before ?? {}) as FlagState;
  const after = (d.after ?? {}) as FlagState;
  const key = typeof d.key === "string" ? d.key : row.target_id;
  const parts: string[] = [];
  if ("enabled" in after && before.enabled !== after.enabled) parts.push(`${onOff(before.enabled)} → ${onOff(after.enabled)}`);
  if ("rollout_percent" in after && before.rollout_percent !== after.rollout_percent) parts.push(`rollout ${limit(before.rollout_percent)}% → ${limit(after.rollout_percent)}%`);
  if ("allowlist" in after && JSON.stringify(before.allowlist ?? []) !== JSON.stringify(after.allowlist ?? [])) {
    parts.push(`allowlist ${count(before.allowlist)} → ${count(after.allowlist)}`);
  }
  if ("value" in after && before.value !== after.value) parts.push(`value ${limit(before.value)} → ${limit(after.value)}`);
  return `${key}: ${parts.length ? parts.join(", ") : "no change"}`;
}

/** Where a row's target lives in the console. */
function targetLink(row: AuditRow, base: string): { href: string; label: string } {
  const type: string = row.target_type;
  if (type === "user") return { href: `${base}/users/${row.target_id}`, label: `user ${shortId(row.target_id)}` };
  if (type === "feature_flag") return { href: `${base}/flags`, label: `flag ${row.target_id}` };
  return { href: `${base}/renders/${row.target_id}`, label: `job ${shortId(row.target_id)}` };
}

/** What the action did, in a few words. */
export function auditSummary(row: AuditRow): string {
  const d = row.detail ?? {};
  if (row.action === "credits_adjust") return `${fmtCredits(Number(d.amount ?? 0))} → balance ${d.balance_after ?? "?"}`;
  if (row.action === "render_refund") return Number(d.refunded ?? 0) > 0 ? `refunded ${d.refunded}` : "nothing left to refund";
  if (row.action === "render_retry") {
    // Audited before the resubmit (fail closed), so newer rows name the retry's key, not the job it created.
    return typeof d.new_job_id === "string" ? `new job ${shortId(d.new_job_id)}` : "retry requested";
  }
  if ((row.action as string) === "flag_update") return flagSummary(row);
  return "";
}

export function AuditTable({ rows, base = "/admin", showTarget = true }: { rows: AuditRow[]; base?: string; showTarget?: boolean }) {
  const head = ["When (UTC)", "Action", ...(showTarget ? ["Target"] : []), "Result", "Reason", "Admin"];
  return (
    <Table label="Admin audit log" head={head} empty="No admin actions yet.">
      {rows.map((r) => (
        <Tr key={r.id}>
          <Td className="text-fg-muted">{fmtDate(r.created_at)}</Td>
          <Td>{ACTION_LABEL[r.action] ?? r.action}</Td>
          {showTarget && (
            <Td>
              <Link
                href={targetLink(r, base).href}
                className="font-code text-xs underline decoration-line underline-offset-4 hover:decoration-fg focus-visible:focus-ring"
                title={r.target_id}
              >
                {targetLink(r, base).label}
              </Link>
            </Td>
          )}
          <Td>{auditSummary(r)}</Td>
          <Td className="max-w-80 truncate text-fg-muted" title={r.reason ?? undefined}>
            {r.reason ?? ""}
          </Td>
          <Td className="max-w-48 truncate text-fg-muted" title={r.admin_id}>
            {r.admin_email ?? shortId(r.admin_id)}
          </Td>
        </Tr>
      ))}
    </Table>
  );
}
