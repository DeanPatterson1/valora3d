"use client";

import Link from "next/link";
import { fmtCredits, fmtDate, shortId } from "@/lib/admin/format";
import type { AuditRow } from "@/lib/admin/types";
import { Table, Td, Tr } from "./ui";

const ACTION_LABEL: Record<AuditRow["action"], string> = {
  credits_adjust: "Credits",
  render_refund: "Refund",
  render_retry: "Retry",
};

/** What the action did, in a few words. */
export function auditSummary(row: AuditRow): string {
  const d = row.detail ?? {};
  if (row.action === "credits_adjust") return `${fmtCredits(Number(d.amount ?? 0))} → balance ${d.balance_after ?? "?"}`;
  if (row.action === "render_refund") return Number(d.refunded ?? 0) > 0 ? `refunded ${d.refunded}` : "nothing left to refund";
  if (row.action === "render_retry") {
    // Audited before the resubmit (fail closed), so newer rows name the retry's key, not the job it created.
    return typeof d.new_job_id === "string" ? `new job ${shortId(d.new_job_id)}` : "retry requested";
  }
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
                href={r.target_type === "user" ? `${base}/users/${r.target_id}` : `${base}/renders/${r.target_id}`}
                className="font-code text-xs underline decoration-line underline-offset-4 hover:decoration-fg focus-visible:focus-ring"
                title={r.target_id}
              >
                {r.target_type === "user" ? "user" : "job"} {shortId(r.target_id)}
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
