"use client";

import Link from "next/link";
import { fmtAgo, fmtCredits, fmtSeconds, shortId } from "@/lib/admin/format";
import { JOB_STATUSES, type AdminJob, type JobStatus } from "@/lib/admin/types";
import { StatusPill, Table, Td, Tr } from "./ui";

export type RenderFilter = { status: JobStatus | ""; user: string };

export function RenderFilters({ value, onChange, userLabel }: { value: RenderFilter; onChange: (f: RenderFilter) => void; userLabel?: string | null }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="flex items-center gap-2 text-sm text-fg-muted">
        Status
        <select
          value={value.status}
          onChange={(e) => onChange({ ...value, status: e.target.value as JobStatus | "" })}
          className="h-8 rounded-sm border border-line bg-bg-2 px-2 text-sm text-fg focus-visible:focus-ring"
        >
          <option value="">All</option>
          {JOB_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      {value.user && (
        <span className="inline-flex h-8 items-center gap-2 rounded-full bg-bg-2 px-3 text-sm">
          User {userLabel ?? shortId(value.user)}
          <button type="button" onClick={() => onChange({ ...value, user: "" })} className="text-fg-muted hover:text-fg focus-visible:focus-ring" aria-label="Clear user filter">
            ✕
          </button>
        </span>
      )}
    </div>
  );
}

/** Recent jobs, one line each. Error code only (the message is on the detail page). */
export function RendersTable({ jobs, base = "/admin", showUser = true }: { jobs: AdminJob[]; base?: string; showUser?: boolean }) {
  const head = ["Job", "Status", ...(showUser ? ["User"] : []), "Tier", "Credits", "Render", "Error", "Created"];
  return (
    <Table label="Render jobs" head={head} empty="No renders match.">
      {jobs.map((j) => (
        <Tr key={j.id}>
          <Td>
            <Link href={`${base}/renders/${j.id}`} className="font-code text-xs underline decoration-line underline-offset-4 hover:decoration-fg focus-visible:focus-ring" title={j.id}>
              {shortId(j.id)}
            </Link>
          </Td>
          <Td>
            <StatusPill status={j.status} />
            {j.attempts > 0 && <span className="ml-1.5 text-xs text-fg-muted">retry {j.attempts}</span>}
          </Td>
          {showUser && (
            <Td className="max-w-56 truncate">
              <Link href={`${base}/users/${j.user_id}`} className="hover:underline focus-visible:focus-ring" title={j.user_id}>
                {j.email ?? shortId(j.user_id)}
              </Link>
            </Td>
          )}
          <Td>{j.kind}</Td>
          <Td>
            {fmtCredits(-j.cost_credits)}
            {j.refunded_credits > 0 && <span className="ml-1 text-xs text-fg-muted">({fmtCredits(j.refunded_credits)})</span>}
          </Td>
          <Td>{fmtSeconds(j.render_seconds)}</Td>
          <Td className="font-code text-xs text-fg-muted">{j.error_code ?? ""}</Td>
          <Td className="text-fg-muted" title={j.created_at}>
            {fmtAgo(j.created_at)}
          </Td>
        </Tr>
      ))}
    </Table>
  );
}
