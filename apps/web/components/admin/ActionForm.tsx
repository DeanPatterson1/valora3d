"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { newRequestId } from "@/lib/admin/format";
import { Notice } from "./ui";

export type ActionResult = { ok: true; message: string } | { ok: false; error: string };

/**
 * One admin action behind a disclosure: the trigger opens a small form (reason, extra fields), the confirm
 * button sends it. The request id is minted when the form opens and reused if the same submission is retried
 * (a double click, a network blip), so the server applies it once; it is replaced only after a success.
 */
export function ActionForm({
  label,
  confirmLabel,
  description,
  reasonRequired = true,
  danger = false,
  disabled = false,
  children,
  valid = true,
  onSubmit,
}: {
  label: string;
  confirmLabel: string;
  description: string;
  reasonRequired?: boolean;
  danger?: boolean;
  disabled?: boolean;
  children?: React.ReactNode;
  valid?: boolean;
  onSubmit: (input: { reason: string; requestId: string }) => Promise<ActionResult>;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [requestId, setRequestId] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ActionResult | null>(null);
  const reasonOk = !reasonRequired || reason.trim().length >= 3;

  if (!open) {
    return (
      <div className="flex flex-col gap-2">
        <Button
          variant={danger ? "danger" : "secondary"}
          size="sm"
          disabled={disabled}
          onClick={() => {
            setOpen(true);
            setRequestId(newRequestId());
            setResult(null);
          }}
          className="w-fit"
        >
          {label}
        </Button>
        {result && <Notice tone={result.ok ? "success" : "danger"}>{result.ok ? result.message : result.error}</Notice>}
      </div>
    );
  }

  return (
    <form
      className="flex max-w-lg flex-col gap-3 rounded-md border border-line bg-bg-1 p-3.5"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!reasonOk || !valid || busy) return;
        setBusy(true);
        const r = await onSubmit({ reason: reason.trim(), requestId });
        setBusy(false);
        setResult(r);
        if (r.ok) {
          setOpen(false);
          setReason("");
        }
      }}
    >
      <p className="text-sm text-fg-muted">{description}</p>
      {children}
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-reason`} className="text-sm text-fg">
          Reason{reasonRequired ? "" : " (optional)"}
        </label>
        <textarea
          id={`${id}-reason`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
          rows={2}
          required={reasonRequired}
          placeholder="Shown in the audit log"
          className="w-full rounded-sm border border-line bg-bg-2 px-3 py-2 text-sm text-fg placeholder:text-fg-muted/70 outline-none focus-visible:focus-ring"
        />
      </div>
      {result && !result.ok && <Notice tone="danger">{result.error}</Notice>}
      <div className="flex gap-2">
        <Button type="submit" variant={danger ? "danger" : "primary"} size="sm" loading={busy} disabled={!reasonOk || !valid}>
          {confirmLabel}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)} disabled={busy}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
