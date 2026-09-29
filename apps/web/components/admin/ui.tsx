"use client";

import { useCallback, useEffect, useState } from "react";
import { cx } from "@/components/ui/cx";

/** Dense, readable building blocks for the admin console: tables, stat tiles, sections, JSON disclosure. */

export function Section({ title, description, actions, children }: { title: string; description?: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-base font-semibold text-fg">{title}</h2>
          {description && <p className="text-xs text-fg-muted">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-md border border-line bg-bg-1 px-3.5 py-3">
      <span className="text-xs text-fg-muted">{label}</span>
      <span className="truncate text-xl font-semibold tabular-nums text-fg">{value}</span>
      {sub && <span className="truncate text-xs text-fg-muted tabular-nums">{sub}</span>}
    </div>
  );
}

export function StatGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">{children}</div>;
}

/** A horizontally scrolling table: rows stay one line on a phone instead of wrapping into noise. */
export function Table({ label, head, children, empty }: { label: string; head: React.ReactNode[]; children: React.ReactNode; empty?: string }) {
  const hasRows = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return (
    <div className="overflow-x-auto rounded-md border border-line">
      <table aria-label={label} className="w-full border-collapse text-left text-sm">
        <thead className="bg-bg-1">
          <tr>
            {head.map((h, i) => (
              <th key={i} scope="col" className="whitespace-nowrap border-b border-line px-3 py-2 text-xs font-medium text-fg-muted">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {hasRows ? (
            children
          ) : (
            <tr>
              <td colSpan={head.length} className="px-3 py-6 text-center text-sm text-fg-muted">
                {empty ?? "Nothing here yet."}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function Tr({ children, className }: { children: React.ReactNode; className?: string }) {
  return <tr className={cx("border-b border-line last:border-b-0 hover:bg-bg-1/60", className)}>{children}</tr>;
}

export function Td({ children, className, title }: { children: React.ReactNode; className?: string; title?: string }) {
  return (
    <td title={title} className={cx("whitespace-nowrap px-3 py-2 align-top text-fg tabular-nums", className)}>
      {children}
    </td>
  );
}

const STATUS_TONE: Record<string, string> = {
  succeeded: "text-success",
  granted: "text-success",
  synced: "text-fg-muted",
  failed: "text-danger",
  unmatched: "text-danger",
  apply: "text-danger",
  cancelled: "text-fg-muted",
  running: "text-fg",
  queued: "text-fg",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <span className={cx("inline-flex h-5 items-center rounded-full bg-bg-3 px-2 text-xs font-medium", STATUS_TONE[status] ?? "text-fg-muted")}>
      {status}
    </span>
  );
}

/** Progressive disclosure for raw operator data (timings, pin, log tail). */
export function JsonDisclosure({ label, value, open = false }: { label: string; value: unknown; open?: boolean }) {
  const empty = value === null || value === undefined || (typeof value === "object" && Object.keys(value as object).length === 0);
  return (
    <details open={open} className="rounded-md border border-line bg-bg-1 [&[open]>summary]:border-b [&[open]>summary]:border-line">
      <summary className="cursor-pointer select-none px-3 py-2 text-sm text-fg focus-visible:focus-ring">
        {label}
        {empty && <span className="ml-2 text-xs text-fg-muted">empty</span>}
      </summary>
      {!empty && (
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words px-3 py-2 text-xs leading-relaxed text-fg-muted">
          {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
        </pre>
      )}
    </details>
  );
}

export function KeyValues({ items }: { items: [string, React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(7rem,max-content)_1fr] gap-x-4 gap-y-1.5 rounded-md border border-line bg-bg-1 px-3.5 py-3 text-sm">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-fg-muted">{k}</dt>
          <dd className="min-w-0 break-words text-fg tabular-nums">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Notice({ tone = "neutral", children }: { tone?: "neutral" | "danger" | "success"; children: React.ReactNode }) {
  return (
    <p
      role={tone === "danger" ? "alert" : "status"}
      className={cx(
        "rounded-md border border-line bg-bg-1 px-3.5 py-2.5 text-sm",
        tone === "danger" ? "text-danger" : tone === "success" ? "text-success" : "text-fg-muted",
      )}
    >
      {children}
    </p>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="py-8 text-center text-sm text-fg-muted" role="status">{label}</p>;
}

export type Loaded<T> = { data: T | null; error: string | null; loading: boolean; reload: () => void };

/**
 * GETs an admin API route (same-origin, cookie session). Keeps the last result on screen while a reload or a
 * new filter is loading, so an action's refresh does not flash the page.
 */
export function useAdminData<T>(url: string | null): Loaded<T> {
  const [tick, setTick] = useState(0);
  const key = url ? `${url}#${tick}` : null;
  const [state, setState] = useState<{ key: string | null; data: T | null; error: string | null }>({ key: null, data: null, error: null });
  useEffect(() => {
    if (!url || !key) return;
    let live = true;
    fetch(url, { cache: "no-store", credentials: "same-origin" })
      .then(async (res) => {
        const body = await res.json().catch(() => null);
        if (!live) return;
        if (!res.ok) setState({ key, data: null, error: body?.error?.message ?? `Request failed (${res.status}).` });
        else setState({ key, data: body as T, error: null });
      })
      .catch(() => {
        if (live) setState({ key, data: null, error: "Network error." });
      });
    return () => {
      live = false;
    };
  }, [url, key]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data: state.data, error: state.error, loading: state.key !== key, reload };
}

/** POSTs an admin action. Returns the parsed body or an error message. */
export async function postAdmin<T>(url: string, body: unknown): Promise<{ ok: true; data: T } | { ok: false; error: string }> {
  try {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json().catch(() => null);
    if (!res.ok) return { ok: false, error: json?.error?.message ?? `Request failed (${res.status}).` };
    return { ok: true, data: json as T };
  } catch {
    return { ok: false, error: "Network error." };
  }
}
