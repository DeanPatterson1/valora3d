"use client";

import Link from "next/link";
import { fmtCredits, fmtDate, fmtInt, fmtSeconds, shortId } from "@/lib/admin/format";
import type { JobDetailResponse } from "@/lib/admin/types";
import { ActionForm, type ActionResult } from "./ActionForm";
import { AuditTable } from "./AuditTable";
import { JsonDisclosure, KeyValues, Section, StatusPill, Table, Td, Tr } from "./ui";

export type RenderActions = {
  retry: (input: { reason: string }) => Promise<ActionResult>;
  refund: (input: { reason: string; requestId: string }) => Promise<ActionResult>;
};

/** numeric may arrive as a string from Postgres. */
function costText(v: number | string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  return Number.isFinite(n) ? `$${n.toFixed(4)}` : "—";
}

function logText(tail: unknown): string | null {
  if (Array.isArray(tail)) return tail.map(String).join("\n");
  if (typeof tail === "string") return tail;
  return null;
}

export function RenderDetailView({ detail, actions, base = "/admin" }: { detail: JobDetailResponse; actions: RenderActions; base?: string }) {
  const { job } = detail;
  const log = logText(detail.private?.log_tail);
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <Link href={`${base}/renders`} className="w-fit text-sm text-fg-muted hover:text-fg focus-visible:focus-ring">
          ← Renders
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-code text-xl font-semibold tracking-tight" title={job.id}>
            Job {shortId(job.id)}
          </h1>
          <StatusPill status={job.status} />
          {job.error_code && <span className="font-code text-sm text-danger">{job.error_code}</span>}
        </div>
        {job.error && <p className="text-sm text-fg-muted">{job.error}</p>}
      </div>

      <Section title="Actions" description="Each action is recorded in the audit log with your account.">
        <div className="flex flex-col gap-3">
          {detail.can.retry ? (
            <ActionForm
              label="Retry render"
              confirmLabel="Retry now"
              reasonRequired={false}
              description="Starts a new render with the same model and settings through the normal pipeline. The user is charged the normal cost (the failed attempt was refunded). A job can be retried once."
              onSubmit={({ reason }) => actions.retry({ reason })}
            />
          ) : (
            <p className="text-xs text-fg-muted">Retry: only for a failed render the worker marked retryable.</p>
          )}
          {detail.can.refund ? (
            <ActionForm
              label="Refund credits"
              confirmLabel={`Refund ${job.cost_credits - job.refunded_credits} credits`}
              description="Returns this render's credits to the user. A render is refunded at most once."
              onSubmit={actions.refund}
            />
          ) : (
            <p className="text-xs text-fg-muted">Refund: only for a failed or cancelled render that still holds its credits.</p>
          )}
        </div>
      </Section>

      <Section title="Job">
        <KeyValues
          items={[
            ["User", <Link key="u" href={`${base}/users/${job.user_id}`} className="underline decoration-line underline-offset-4 hover:decoration-fg">{job.email ?? job.user_id}</Link>],
            ["Tier", job.kind],
            ["Credits", `${fmtCredits(-job.cost_credits)}${job.refunded_credits ? ` · refunded ${job.refunded_credits}` : ""}`],
            ["Cost estimate", costText(job.cost_usd_estimate)],
            ...(job.director_input_tokens != null || job.director_output_tokens != null
              ? ([["Director tokens", `${fmtInt(job.director_input_tokens ?? 0)} in / ${fmtInt(job.director_output_tokens ?? 0)} out`]] as [string, string][])
              : []),
            ["Attempts", String(job.attempts)],
            ["Retryable", job.retryable === null ? "—" : job.retryable ? "yes" : "no"],
            ["Stage", job.stage ? `${job.stage} (${job.frame}/${job.total_frames ?? "?"})` : "—"],
            ["Watermark", job.watermark ? (job.watermarked === false ? "asked, not drawn" : "yes") : "no"],
            ["RunPod", job.runpod_id ? `${job.runpod_id} · ${job.runpod_status ?? "?"}` : "—"],
            ["Outputs", job.expired_at ? `expired ${fmtDate(job.expired_at)}` : job.status === "succeeded" ? "stored" : "—"],
          ]}
        />
      </Section>

      <Section title="Timing" description="UTC. Render and GPU time come from the worker; queue and execution from RunPod.">
        <KeyValues
          items={[
            ["Created", fmtDate(job.created_at)],
            ["Started", fmtDate(job.started_at)],
            ["Finished", fmtDate(job.finished_at)],
            ["Queue delay", fmtSeconds(job.delay_ms === null ? null : job.delay_ms / 1000)],
            ["Execution", fmtSeconds(job.execution_ms === null ? null : job.execution_ms / 1000)],
            ["Render", fmtSeconds(job.render_seconds)],
            ["GPU", fmtSeconds(job.gpu_seconds)],
          ]}
        />
        <JsonDisclosure label="Stage timings" value={job.timings} />
      </Section>

      <Section title="Operator detail" description="Never shown to the user.">
        {detail.private?.error_detail ? (
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md border border-line bg-bg-1 px-3 py-2 text-xs text-fg">
            {detail.private.error_detail}
          </pre>
        ) : (
          <p className="text-sm text-fg-muted">No operator error detail.</p>
        )}
        <JsonDisclosure label="Log tail" value={log} open={Boolean(log) && job.status === "failed"} />
        <JsonDisclosure label="Pin (versions and hashes)" value={detail.private?.pin ?? null} />
        <JsonDisclosure label="Settings (params)" value={job.params} />
        <JsonDisclosure label="Warnings" value={Array.isArray(job.warnings) && job.warnings.length ? job.warnings : null} />
        <JsonDisclosure label="Outputs" value={job.outputs} />
      </Section>

      <Section title="Ledger" description="Credit rows for this job.">
        <Table label="Job ledger" head={["When (UTC)", "Reason", "Credits", "Ref"]} empty="No ledger rows.">
          {detail.ledger.map((l) => (
            <Tr key={l.id}>
              <Td className="text-fg-muted">{fmtDate(l.created_at)}</Td>
              <Td>{l.reason}</Td>
              <Td>{fmtCredits(l.amount)}</Td>
              <Td className="font-code text-xs text-fg-muted">{l.ref}</Td>
            </Tr>
          ))}
        </Table>
      </Section>

      <Section title="Admin actions on this job">
        <AuditTable rows={detail.audit} base={base} showTarget={false} />
      </Section>
    </div>
  );
}
