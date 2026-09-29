"use client";

import { Tabs } from "@/components/ui/Tabs";
import { cx } from "@/components/ui/cx";
import { fmtDate, fmtInt, fmtMoney, fmtPct, fmtSeconds } from "@/lib/admin/format";
import type { FunnelEvent, Growth } from "@/lib/admin/types";
import { Section, Table, Td, Tr } from "./ui";

/** Funnel windows the API accepts (?days=). */
export const FUNNEL_WINDOWS = [7, 30, 90] as const;
export type FunnelDays = (typeof FUNNEL_WINDOWS)[number];

const STEP_LABEL: Record<FunnelEvent, string> = {
  landing_view: "Visited landing",
  signup_start: "Started signup",
  signup_complete: "Confirmed account",
  upload_ready: "Model ready",
  render_requested: "Requested a render",
  render_succeeded: "Render delivered",
  checkout_complete: "Paid",
};

/** n / d, or null when there is no denominator (renders as "—"). */
export const ratio = (n: number, d: number): number | null => (Number(d) > 0 ? Number(n) / Number(d) : null);

/** GPU cost per render: 3 decimals under 10 cents, so $0.041 does not read as $0.04. */
export function fmtUsd(v: number | string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return `$${n.toFixed(n < 0.1 ? 3 : 2)}`;
}

/** Whole-percent, for tight spots. */
const pct0 = (r: number | null) => (r === null ? "—" : `${Math.round(r * 100)}%`);

const shortDay = (iso: string) => {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
};

/** Vertical bars, white/grey only. `highlight` marks the last bar (a partial period) as lighter. */
function Bars({
  values,
  label,
  describe,
  height = "h-24",
  partialLast = false,
}: {
  values: number[];
  label: string;
  describe: (i: number) => string;
  height?: string;
  partialLast?: boolean;
}) {
  const max = Math.max(0, ...values.map(Number));
  return (
    <figure className="flex flex-col gap-1">
      <div role="img" aria-label={label} className={cx("flex items-end gap-[3px]", height)}>
        {values.map((v, i) => {
          const pct = max > 0 ? Math.max(Number(v) > 0 ? 3 : 0, (Number(v) / max) * 100) : 0;
          const partial = partialLast && i === values.length - 1;
          return (
            <div key={i} className="flex h-full min-w-0 flex-1 items-end" title={describe(i)}>
              <div
                className={cx("w-full rounded-t-[2px]", partial ? "bg-fg/35" : "bg-fg/80", pct === 0 && "h-px bg-line")}
                style={pct > 0 ? { height: `${pct}%` } : undefined}
              />
            </div>
          );
        })}
      </div>
      <ul className="sr-only">
        {values.map((_, i) => (
          <li key={i}>{describe(i)}</li>
        ))}
      </ul>
    </figure>
  );
}

function Kpi({ label, value, sub, children }: { label: string; value: React.ReactNode; sub?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-md border border-line bg-bg-1 px-3.5 py-3">
      <span className="text-xs text-fg-muted">{label}</span>
      <span className="truncate text-xl font-semibold tabular-nums text-fg">{value}</span>
      {sub && <span className="text-xs leading-snug text-fg-muted tabular-nums">{sub}</span>}
      {children}
    </div>
  );
}

function NorthStar({ growth }: { growth: Growth }) {
  const weeks = growth.north_star.weeks ?? [];
  const current = weeks.length ? weeks[weeks.length - 1] : null;
  const last = weeks.length > 1 ? weeks[weeks.length - 2] : null;
  const prev = weeks.length > 2 ? weeks[weeks.length - 3] : null;
  const change = last && prev ? ratio(last.renders - prev.renders, prev.renders) : null;
  return (
    <section aria-labelledby="north-star" className="flex flex-col gap-4 rounded-md border border-line bg-bg-1 p-4 sm:flex-row sm:items-end sm:gap-8">
      <div className="flex min-w-0 flex-col gap-1 sm:w-64 sm:shrink-0">
        <h2 id="north-star" className="text-sm text-fg-muted">
          {growth.north_star.label || "Weekly delivered renders"}
        </h2>
        <p className="text-5xl font-semibold tracking-tight tabular-nums text-fg" data-testid="north-star-value">
          {fmtInt(last?.renders ?? 0)}
        </p>
        <p className="text-xs text-fg-muted">
          Last full week{last ? ` (from ${shortDay(last.week)})` : ""}
          {change !== null && ` · ${change >= 0 ? "+" : "−"}${fmtPct(Math.abs(change))} vs the week before`}
        </p>
        <p className="text-xs text-fg-muted tabular-nums">
          {fmtInt(last?.users ?? 0)} users · {fmtInt(last?.finals ?? 0)} finals · this week so far {fmtInt(current?.renders ?? 0)}
        </p>
      </div>
      <div className="min-w-0 flex-1">
        {weeks.length === 0 ? (
          <p className="text-sm text-fg-muted">No renders delivered yet.</p>
        ) : (
          <>
            <Bars
              values={weeks.map((w) => w.renders)}
              label={`Delivered renders per week, last ${weeks.length} weeks, oldest first`}
              describe={(i) => `Week of ${shortDay(weeks[i].week)}: ${fmtInt(weeks[i].renders)} renders, ${fmtInt(weeks[i].finals)} finals, ${fmtInt(weeks[i].users)} users${i === weeks.length - 1 ? " (so far)" : ""}`}
              height="h-28"
              partialLast
            />
            <div className="mt-1 flex justify-between text-[11px] text-fg-muted" aria-hidden>
              <span>{shortDay(weeks[0].week)}</span>
              <span>This week</span>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function Funnel({ growth, days, onDaysChange, loading }: { growth: Growth; days: FunnelDays; onDaysChange: (d: FunnelDays) => void; loading?: boolean }) {
  const steps = growth.funnel.steps ?? [];
  const base = steps.find((s) => Number(s.count) > 0)?.count ?? 0;
  return (
    <Section
      title="Funnel"
      description="Distinct visitors (landing, signup start) or accounts (later steps) in the window; not a strict cohort."
      actions={
        <Tabs
          items={FUNNEL_WINDOWS.map((d) => ({ id: String(d), label: `${d} days` }))}
          value={String(days)}
          onChange={(id) => onDaysChange(Number(id) as FunnelDays)}
          label="Funnel window"
        />
      }
    >
      <ol aria-label={`Funnel, last ${growth.funnel.days} days`} aria-busy={loading || undefined} className={cx("flex flex-col gap-2.5 rounded-md border border-line bg-bg-1 p-3.5", loading && "opacity-60")}>
        {steps.map((s, i) => {
          const prev = i > 0 ? steps[i - 1].count : null;
          const conv = prev === null ? null : ratio(s.count, prev);
          const width = base > 0 ? (Number(s.count) / base) * 100 : 0;
          return (
            <li key={s.event} className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 truncate text-fg">{STEP_LABEL[s.event] ?? s.event}</span>
                <span className="shrink-0 tabular-nums">
                  <span className="text-fg">{fmtInt(s.count)}</span>
                  {i > 0 && (
                    <span className="ml-2 inline-block w-28 text-right text-xs text-fg-muted" title="Conversion from the previous step">
                      {conv === null ? "—" : `${fmtPct(conv)} of previous`}
                    </span>
                  )}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-bg-3" aria-hidden>
                <div className="h-full rounded-full bg-fg/75" style={{ width: `${Math.min(100, width)}%` }} />
              </div>
            </li>
          );
        })}
        {steps.length === 0 && <li className="text-sm text-fg-muted">No funnel events in this window.</li>}
      </ol>
    </Section>
  );
}

/** Grey cell fill that scales with the rate; capped so white text stays above 4.5:1 (#ececec on ~#4f4f4f). */
function cellStyle(r: number | null): React.CSSProperties | undefined {
  if (r === null) return undefined;
  return { backgroundColor: `rgba(255,255,255,${(0.03 + Math.min(1, Math.max(0, r)) * 0.25).toFixed(3)})` };
}

function Cohorts({ cohorts }: { cohorts: Growth["cohorts"] }) {
  const cols = Math.max(8, ...cohorts.map((c) => c.active.length));
  return (
    <Section title="Weekly cohorts" description="Signups by week; each cell is the share active (any product event) in week n after signup.">
      <Table label="Weekly signup cohorts" head={["Cohort week", "Size", ...Array.from({ length: cols }, (_, n) => `Wk ${n}`)]} empty="No cohorts yet.">
        {cohorts.map((c) => (
          <Tr key={c.week}>
            <Td className="text-fg-muted">{c.week.slice(0, 10)}</Td>
            <Td>{fmtInt(c.size)}</Td>
            {Array.from({ length: cols }, (_, n) => {
              const reached = n < c.active.length;
              const r = reached ? ratio(c.active[n], c.size) : null;
              return (
                <Td
                  key={n}
                  className="min-w-14 text-right"
                  title={reached ? `${fmtInt(c.active[n])} of ${fmtInt(c.size)} active in week ${n}` : "Not reached yet"}
                >
                  {reached ? (
                    <span className="-mx-1.5 -my-0.5 block rounded-[3px] px-1.5 py-0.5" style={cellStyle(r)}>
                      {pct0(r)}
                    </span>
                  ) : (
                    <span className="sr-only">not reached</span>
                  )}
                </Td>
              );
            })}
          </Tr>
        ))}
      </Table>
    </Section>
  );
}

export function GrowthView({
  growth,
  days,
  onDaysChange,
  funnelLoading = false,
}: {
  growth: Growth;
  days: FunnelDays;
  onDaysChange: (d: FunnelDays) => void;
  funnelLoading?: boolean;
}) {
  const s = growth.signups;
  const byDay = s.by_day ?? [];
  const act = growth.activation;
  const conv = growth.conversion;
  const cost = growth.cost;
  const rs = growth.render_success;
  const ret = growth.retention;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Growth</h1>
        <p className="text-xs text-fg-muted">Updated {fmtDate(growth.generated_at)} UTC · admin accounts excluded</p>
      </div>

      <NorthStar growth={growth} />

      <Section title="Key numbers">
        <div className="grid grid-cols-1 gap-2 min-[380px]:grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
          <Kpi label="Signups per day" value={fmtInt(s.today)} sub={`Today (UTC) · 7-day avg ${(Number(s.d7) / 7).toFixed(1)} · ${fmtInt(s.d30)} in 30 days`}>
            {byDay.length > 0 && (
              <div className="mt-1">
                <Bars
                  values={byDay.map((d) => d.n)}
                  label={`Signups per day, last ${byDay.length} days`}
                  describe={(i) => `${shortDay(byDay[i].day)}: ${fmtInt(byDay[i].n)} signups`}
                  height="h-8"
                  partialLast
                />
              </div>
            )}
          </Kpi>
          <Kpi label="Activation rate" value={fmtPct(act.rate ?? ratio(act.activated, act.cohort))} sub={`Delivered a render within 7 days · ${fmtInt(act.activated)} of ${fmtInt(act.cohort)}`} />
          <Kpi
            label="Time to first render"
            value={fmtSeconds(growth.time_to_first_render.median_seconds)}
            sub={`Median, signup to first delivered render · ${fmtInt(growth.time_to_first_render.users)} users`}
          />
          <Kpi label="Free → paid" value={fmtPct(conv.rate ?? ratio(conv.paid, conv.cohort))} sub={`Paid within 30 days · ${fmtInt(conv.paid)} of ${fmtInt(conv.cohort)} · ${fmtInt(conv.paying_now)} paying now`} />
          <Kpi
            label="MRR"
            value={fmtMoney(growth.mrr.minor, growth.mrr.currency || "USD")}
            sub={`${fmtInt(growth.mrr.subscriptions)} renewing ${growth.mrr.subscriptions === 1 ? "subscription" : "subscriptions"}, at list price`}
          />
          <Kpi label="Render success" value={fmtPct(rs.rate ?? ratio(rs.succeeded, rs.finished))} sub={`Last 7 days · ${fmtInt(rs.succeeded)} of ${fmtInt(rs.finished)} finished`} />
          <Kpi
            label="GPU cost per render"
            value={cost.priced > 0 ? fmtUsd(cost.avg_usd) : "—"}
            sub={
              cost.priced > 0
                ? `${fmtInt(cost.priced)} of ${fmtInt(cost.renders)} priced · avg ${fmtSeconds(cost.avg_gpu_seconds)} GPU · $${Number(cost.total_usd).toFixed(2)} in 30 days`
                : `Set GPU_USD_PER_SECOND · ${fmtInt(cost.renders)} renders in 30 days`
            }
          />
          <div className="flex min-w-0 flex-col gap-1 rounded-md border border-line bg-bg-1 px-3.5 py-3">
            <span className="text-xs text-fg-muted">Retention</span>
            <dl className="grid grid-cols-3 gap-2">
              {(["d1", "d7", "d30"] as const).map((k) => (
                <div key={k} className="flex min-w-0 flex-col" title={`${fmtInt(ret[k].retained)} of ${fmtInt(ret[k].cohort)} came back`}>
                  <dt className="text-[11px] text-fg-muted">{k.toUpperCase()}</dt>
                  <dd className="text-lg font-semibold tabular-nums text-fg">{pct0(ratio(ret[k].retained, ret[k].cohort))}</dd>
                </div>
              ))}
            </dl>
            <span className="text-xs leading-snug text-fg-muted tabular-nums">
              Came back: {(["d1", "d7", "d30"] as const).map((k) => `${fmtInt(ret[k].retained)}/${fmtInt(ret[k].cohort)}`).join(" · ")}
            </span>
          </div>
        </div>
      </Section>

      <Funnel growth={growth} days={days} onDaysChange={onDaysChange} loading={funnelLoading} />

      <Section title="Top sources" description="Where accounts came from (the source saved at signup).">
        <Table label="Top signup sources" head={["Source", "Signups", "Paid", "Paid %"]} empty="No signups with a source yet.">
          {growth.sources.map((r) => (
            <Tr key={r.source}>
              <Td>{r.source || "(direct)"}</Td>
              <Td>{fmtInt(r.signups)}</Td>
              <Td>{fmtInt(r.paid)}</Td>
              <Td>{fmtPct(ratio(r.paid, r.signups))}</Td>
            </Tr>
          ))}
        </Table>
      </Section>

      <Cohorts cohorts={growth.cohorts ?? []} />
    </div>
  );
}
