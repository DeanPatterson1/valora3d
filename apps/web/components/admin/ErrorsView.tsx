"use client";

import { Tabs } from "@/components/ui/Tabs";
import { cx } from "@/components/ui/cx";
import { fmtAgo, fmtDate, fmtInt } from "@/lib/admin/format";
import type { ClientErrorGroup } from "@/lib/admin/types";
import { Section, Table, Td, Tr } from "./ui";

/** Windows the API accepts (?days=). */
export const ERROR_WINDOWS = [
  { days: 1, label: "24 hours" },
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
] as const;
export type ErrorDays = (typeof ERROR_WINDOWS)[number]["days"];

export function ErrorsView({
  errors,
  days,
  onDaysChange,
  loading = false,
  now,
}: {
  errors: ClientErrorGroup[];
  days: ErrorDays;
  onDaysChange: (d: ErrorDays) => void;
  loading?: boolean;
  /** Fixed clock for previews/tests; defaults to the real time. */
  now?: number;
}) {
  const total = errors.reduce((a, e) => a + Number(e.count), 0);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Client errors</h1>
        <p className="text-sm text-fg-muted">Reported by browsers: error type, page template and build. No messages or personal data. Kept 30 days.</p>
      </div>
      <Section
        title={errors.length ? `${fmtInt(total)} ${total === 1 ? "error" : "errors"} in ${fmtInt(errors.length)} ${errors.length === 1 ? "group" : "groups"}` : "Errors"}
        description="Grouped by build, page and error type. Most frequent first."
        actions={
          <Tabs
            items={ERROR_WINDOWS.map((w) => ({ id: String(w.days), label: w.label }))}
            value={String(days)}
            onChange={(id) => onDaysChange(Number(id) as ErrorDays)}
            label="Time window"
          />
        }
      >
        <div aria-busy={loading || undefined} className={cx(loading && "opacity-60")}>
          <Table label="Client error groups" head={["Count", "Error", "Page", "Release", "Browsers", "Codes", "Last seen"]} empty="No client errors in this window.">
            {[...errors]
              .sort((a, b) => Number(b.count) - Number(a.count))
              .map((e) => (
                <Tr key={`${e.release}|${e.path}|${e.name}`}>
                  <Td className="text-right font-semibold">{fmtInt(e.count)}</Td>
                  <Td title={e.kinds?.length ? `Kinds: ${e.kinds.join(", ")}` : undefined}>{e.name}</Td>
                  <Td className="font-code text-xs">{e.path}</Td>
                  <Td className="font-code text-xs text-fg-muted">{e.release}</Td>
                  <Td className="max-w-64 truncate text-fg-muted" title={e.browsers.join(", ")}>
                    {e.browsers.length ? e.browsers.join(", ") : "—"}
                  </Td>
                  <Td className="font-code text-xs text-fg-muted" title={e.codes?.join(", ") || undefined}>
                    {e.codes?.length ? `${e.codes.slice(0, 2).join(", ")}${e.codes.length > 2 ? ` +${e.codes.length - 2}` : ""}` : "—"}
                  </Td>
                  <Td className="text-fg-muted" title={`${fmtDate(e.last_seen)} UTC (first ${fmtDate(e.first_seen)})`}>
                    {fmtAgo(e.last_seen, now)}
                  </Td>
                </Tr>
              ))}
          </Table>
        </div>
      </Section>
    </div>
  );
}
