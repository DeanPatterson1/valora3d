"use client";

import { useId, useState } from "react";
import { cx } from "@/components/ui/cx";
import { fmtAgo, fmtDate, fmtInt, shortId } from "@/lib/admin/format";
import type { FeatureFlagRow, FlagUpdate } from "@/lib/admin/types";
import { ActionForm, type ActionResult } from "./ActionForm";
import { Section } from "./ui";

/** What a form sends: the changed fields, plus the reason and the form's idempotency key. */
export type FlagChange = Omit<FlagUpdate, "reason" | "request_id"> & { reason: string; requestId: string };
export type OnFlagUpdate = (key: string, change: FlagChange) => Promise<ActionResult>;

export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const MAX_ALLOWLIST = 200;

const inputClass =
  "w-full rounded-sm border border-line bg-bg-2 px-3 py-2 text-sm text-fg placeholder:text-fg-muted/70 outline-none focus-visible:focus-ring";

/** Allowlist textarea -> ids (one per line; commas and spaces also split) + what is wrong with it. */
export function parseAllowlist(text: string): { ids: string[]; bad: string[]; tooMany: boolean } {
  const parts = text
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const ids = Array.from(new Set(parts.map((s) => s.toLowerCase())));
  return { ids, bad: parts.filter((s) => !UUID_RE.test(s)), tooMany: ids.length > MAX_ALLOWLIST };
}

function Pill({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "off" | "on" }) {
  return (
    <span
      className={cx(
        "inline-flex h-5 items-center whitespace-nowrap rounded-full px-2 text-xs font-medium",
        tone === "off" ? "bg-bg-3 text-danger" : tone === "on" ? "bg-bg-3 text-fg" : "border border-line text-fg-muted",
      )}
    >
      {children}
    </span>
  );
}

function Updated({ flag, now }: { flag: FeatureFlagRow; now?: number }) {
  return (
    <p className="text-xs text-fg-muted" title={`${fmtDate(flag.updated_at)} UTC`}>
      Updated {fmtAgo(flag.updated_at, now)} by {flag.updated_by_email ?? (flag.updated_by ? shortId(flag.updated_by) : "system")}
    </p>
  );
}

function RolloutForm({ flag, onUpdate }: { flag: FeatureFlagRow; onUpdate: OnFlagUpdate }) {
  const id = useId();
  const [percent, setPercent] = useState(String(flag.rollout_percent));
  const [allow, setAllow] = useState(flag.allowlist.join("\n"));
  const p = Number(percent);
  const percentOk = percent.trim() !== "" && Number.isInteger(p) && p >= 0 && p <= 100;
  const list = parseAllowlist(allow);
  const valid = percentOk && list.bad.length === 0 && !list.tooMany;
  return (
    <ActionForm
      label="Edit rollout"
      confirmLabel="Save rollout"
      description="Rollout sends a stable share of accounts through while the switch is on. Allowlisted accounts always pass."
      valid={valid}
      onSubmit={({ reason, requestId }) => onUpdate(flag.key, { rollout_percent: p, allowlist: list.ids, reason, requestId })}
    >
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-pct`} className="text-sm text-fg">
          Rollout percent
        </label>
        <input
          id={`${id}-pct`}
          type="number"
          inputMode="numeric"
          min={0}
          max={100}
          step={1}
          value={percent}
          onChange={(e) => setPercent(e.target.value)}
          aria-invalid={!percentOk || undefined}
          className={cx(inputClass, "w-28")}
        />
        {!percentOk && <p className="text-xs text-danger">A whole number from 0 to 100.</p>}
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-allow`} className="text-sm text-fg">
          Allowlist (user ids, one per line)
        </label>
        <textarea
          id={`${id}-allow`}
          value={allow}
          onChange={(e) => setAllow(e.target.value)}
          rows={3}
          spellCheck={false}
          placeholder="3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f"
          aria-invalid={list.bad.length > 0 || list.tooMany || undefined}
          className={cx(inputClass, "font-code text-xs")}
        />
        {list.bad.length > 0 && (
          <p className="break-all text-xs text-danger">
            Not a user id: {list.bad.slice(0, 3).join(", ")}
            {list.bad.length > 3 ? ` and ${list.bad.length - 3} more` : ""}
          </p>
        )}
        {list.tooMany && <p className="text-xs text-danger">At most {MAX_ALLOWLIST} ids.</p>}
        <p className="text-xs text-fg-muted">
          {fmtInt(list.ids.length)} of {MAX_ALLOWLIST}
        </p>
      </div>
    </ActionForm>
  );
}

function KillSwitch({ flag, onUpdate, now }: { flag: FeatureFlagRow; onUpdate: OnFlagUpdate; now?: number }) {
  const turningOff = flag.enabled;
  return (
    <li className="flex flex-col gap-3 rounded-md border border-line bg-bg-1 p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <code className="font-code text-sm text-fg">{flag.key}</code>
        <Pill tone={flag.enabled ? "on" : "off"}>{flag.enabled ? "On" : "Off"}</Pill>
        {flag.enabled && flag.rollout_percent < 100 && <Pill>Rollout {flag.rollout_percent}%</Pill>}
        {flag.allowlist.length > 0 && <Pill>+{fmtInt(flag.allowlist.length)} allowlisted</Pill>}
      </div>
      <p className="text-sm text-fg-muted">{flag.description}</p>
      <Updated flag={flag} now={now} />
      <div className="flex flex-wrap items-start gap-3">
        <ActionForm
          label={turningOff ? "Turn off" : "Turn on"}
          confirmLabel={turningOff ? `Turn off ${flag.key}` : `Turn on ${flag.key}`}
          danger={turningOff}
          description={turningOff ? "Stops this for every user within about 30 seconds. Work already running is not interrupted." : "Opens this again for users (subject to the rollout below)."}
          onSubmit={({ reason, requestId }) => onUpdate(flag.key, { enabled: !flag.enabled, reason, requestId })}
        />
        <RolloutForm flag={flag} onUpdate={onUpdate} />
      </div>
    </li>
  );
}

function SettingForm({ flag, onUpdate }: { flag: FeatureFlagRow; onUpdate: OnFlagUpdate }) {
  const id = useId();
  const [text, setText] = useState(flag.value === null ? "" : String(flag.value));
  const n = Number(text);
  const empty = text.trim() === "";
  const valid = empty || (Number.isInteger(n) && n >= 0);
  const next = empty ? null : n;
  return (
    <ActionForm
      label="Change"
      confirmLabel={next === null ? "Save: no limit" : `Save: ${fmtInt(next)}`}
      description="Leave empty for no limit."
      valid={valid}
      onSubmit={({ reason, requestId }) => onUpdate(flag.key, { value: next, reason, requestId })}
    >
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-value`} className="text-sm text-fg">
          Value
        </label>
        <input
          id={`${id}-value`}
          type="number"
          inputMode="numeric"
          min={0}
          step={1}
          value={text}
          placeholder="No limit"
          onChange={(e) => setText(e.target.value)}
          aria-invalid={!valid || undefined}
          className={cx(inputClass, "w-40")}
        />
        {!valid && <p className="text-xs text-danger">A whole number, 0 or more, or empty.</p>}
      </div>
    </ActionForm>
  );
}

function Setting({ flag, onUpdate, now }: { flag: FeatureFlagRow; onUpdate: OnFlagUpdate; now?: number }) {
  return (
    <li className="flex flex-col gap-3 rounded-md border border-line bg-bg-1 p-3.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <code className="font-code text-sm text-fg">{flag.key}</code>
        <span className="text-xl font-semibold tabular-nums text-fg">{flag.value === null ? "No limit" : fmtInt(flag.value)}</span>
      </div>
      <p className="text-sm text-fg-muted">{flag.description}</p>
      <Updated flag={flag} now={now} />
      <SettingForm flag={flag} onUpdate={onUpdate} />
    </li>
  );
}

export function FlagsView({ flags, onUpdate, now }: { flags: FeatureFlagRow[]; onUpdate: OnFlagUpdate; /** Fixed clock for previews/tests. */ now?: number }) {
  const switches = flags.filter((f) => f.kind === "flag");
  const settings = flags.filter((f) => f.kind === "setting");
  const off = switches.filter((f) => !f.enabled);
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Flags</h1>
        <p className="text-sm text-fg-muted">Changes apply within about 30 seconds and are recorded in the audit log.</p>
        {off.length > 0 && (
          <p role="status" className="text-sm text-fg">
            {off.length === 1 ? "1 kill switch is off" : `${off.length} kill switches are off`}: <span className="font-code text-xs">{off.map((f) => f.key).join(", ")}</span>
          </p>
        )}
      </div>
      <Section title="Kill switches" description="Turn a feature off for everyone in an incident. On is the normal state.">
        {switches.length ? (
          <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">
            {switches.map((f) => (
              <KillSwitch key={f.key} flag={f} onUpdate={onUpdate} now={now} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-fg-muted">No kill switches defined.</p>
        )}
      </Section>
      <Section title="Limits" description="Capacity and budget guards for the render queue.">
        {settings.length ? (
          <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">
            {settings.map((f) => (
              <Setting key={f.key} flag={f} onUpdate={onUpdate} now={now} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-fg-muted">No limits defined.</p>
        )}
      </Section>
    </div>
  );
}
