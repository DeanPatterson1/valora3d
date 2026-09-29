/** Formatting for the admin console: compact, stable, UTC (the owner compares against logs, which are UTC). */

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toISOString().slice(0, 16).replace("T", " ");
}

/** "3 min ago" style, for scanning recent rows. */
export function fmtAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(Number(n))) return "—";
  return Math.round(Number(n)).toLocaleString("en-US");
}

/** Signed credits: +25 / −100. */
export function fmtCredits(n: number): string {
  if (n > 0) return `+${fmtInt(n)}`;
  if (n < 0) return `−${fmtInt(-n)}`;
  return "0";
}

export function fmtSeconds(s: number | null | undefined): string {
  if (s === null || s === undefined || !Number.isFinite(Number(s))) return "—";
  const v = Number(s);
  if (v < 60) return `${v.toFixed(v < 10 ? 1 : 0)}s`;
  if (v < 3600) return `${Math.floor(v / 60)}m ${Math.round(v % 60)}s`;
  return `${(v / 3600).toFixed(1)}h`;
}

export function fmtPct(r: number | null | undefined): string {
  if (r === null || r === undefined || !Number.isFinite(Number(r))) return "—";
  return `${(Number(r) * 100).toFixed(1)}%`;
}

/** Minor units -> "USD 12.34". Paddle amounts are in the currency's minor unit (2 decimals for USD/EUR/GBP). */
export function fmtMoney(minor: number, currency: string): string {
  const major = Number(minor) / 100;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency, currencyDisplay: "code" }).format(major);
  } catch {
    return `${currency} ${major.toFixed(2)}`;
  }
}

export function fmtBytes(n: number): string {
  if (!Number.isFinite(n)) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 ** 2).toFixed(1)} MB`;
}

/** First 8 characters of an id, for dense tables (the full id is in the title/link). */
export const shortId = (id: string | null | undefined) => (id ? id.slice(0, 8) : "—");

/** A random request id for one admin action: the same id is sent again on a retried click. */
export function newRequestId(): string {
  return crypto.randomUUID().replace(/-/g, "");
}
