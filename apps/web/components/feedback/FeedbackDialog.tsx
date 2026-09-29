"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { create } from "zustand";
import { Button, Dialog, useToastStore } from "@/components/ui";
import { ChoiceList, TextArea } from "@/components/account/ChoiceList";
import { routeTemplate } from "@/lib/analytics/events";
import { sendFeedback } from "@/lib/account/lifecycleClient";
import { RELEASE_ID } from "@/lib/errors/shared";
import { FEEDBACK_KINDS, MESSAGE_MAX, MESSAGE_MIN, feedbackIntent, type FeedbackKind } from "@/lib/feedback/shared";
import { services, type Result } from "@/lib/services";

/** One dialog per app shell; the sidebar item, the help center link and error pages open it. */
type FeedbackState = { open: boolean; kind: FeedbackKind; from: string | null; show: (kind?: FeedbackKind, from?: string | null) => void; close: () => void };
export const useFeedbackStore = create<FeedbackState>((set) => ({
  open: false,
  kind: "bug",
  from: null,
  show: (kind = "bug", from = null) => set({ open: true, kind, from }),
  close: () => set({ open: false }),
}));

const PLACEHOLDER: Record<FeedbackKind, string> = {
  bug: "What happened, and what did you expect? Steps to reproduce help a lot.",
  idea: "What would you like Valora3D to do?",
  question: "What would you like to know?",
};

export function FeedbackDialog({
  open,
  onClose,
  initialKind = "bug",
  page,
  submit = sendFeedback,
  local = services.backend === "local",
}: {
  open: boolean;
  onClose: () => void;
  initialKind?: FeedbackKind;
  /** The page the report is about (a route template is derived from it). */
  page: string;
  submit?: (body: { kind: FeedbackKind; message: string; page?: string; release?: string }) => Promise<Result<{ ok: true }>>;
  /** Local mode has no backend: the dialog offers email instead. */
  local?: boolean;
}) {
  const push = useToastStore((s) => s.push);
  const [kind, setKind] = useState<FeedbackKind>(initialKind);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastOpen, setLastOpen] = useState(open);
  // Each opening starts from the kind it was opened with (derived-state reset, no effect needed).
  if (open !== lastOpen) {
    setLastOpen(open);
    if (open) {
      setKind(initialKind);
      setError(null);
    }
  }
  const template = routeTemplate(page);
  const tooShort = message.trim().length < MESSAGE_MIN;

  const send = async () => {
    setSending(true);
    setError(null);
    const r = await submit({ kind, message: message.trim(), page: template, release: RELEASE_ID });
    setSending(false);
    if (!r.ok) {
      setError(r.error.message);
      return;
    }
    setMessage("");
    onClose();
    push({ kind: "success", message: kind === "bug" ? "Thanks. We'll look into it." : "Thanks. We read every message." });
  };

  const mailto = `mailto:support@valora3d.com?subject=${encodeURIComponent(`Valora3D ${kind}`)}&body=${encodeURIComponent(`${message}\n\nPage: ${template}\nBuild: ${RELEASE_ID}`)}`;

  return (
    <Dialog open={open} onClose={() => !sending && onClose()} title="Send feedback" description="A bug, an idea or a question. It goes straight to the person who builds Valora3D.">
      <div className="flex flex-col gap-4">
        <ChoiceList legend="What kind?" options={FEEDBACK_KINDS} value={kind} onChange={setKind} columns={3} />
        <TextArea label="Message" value={message} onChange={setMessage} maxLength={MESSAGE_MAX} rows={5} placeholder={PLACEHOLDER[kind]} />
        <p className="text-xs text-fg-muted">
          We&apos;ll attach the page ({template}), the app version and your browser type, so you don&apos;t have to. No screenshot needed.
        </p>
        {local && (
          <p className="text-xs text-fg-muted">
            This preview has no account server, so feedback goes by email.
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <Button onClick={onClose} disabled={sending}>
            Cancel
          </Button>
          {local ? (
            <a
              href={mailto}
              aria-disabled={tooShort || undefined}
              onClick={(e) => tooShort && e.preventDefault()}
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-fg transition-colors hover:bg-primary/90 focus-visible:focus-ring aria-disabled:opacity-50"
            >
              Email it
            </a>
          ) : (
            <Button variant="primary" loading={sending} disabled={tooShort} onClick={() => void send()}>
              Send
            </Button>
          )}
        </div>
      </div>
    </Dialog>
  );
}

/**
 * Mounted once in the app shell: renders the dialog from the store, and opens it for `?feedback=bug|idea|question`
 * (error pages' "Report this problem" and the help center link; `&from=` names the page the problem was on).
 */
export function FeedbackHost() {
  const { open, kind, from, show, close } = useFeedbackStore();
  const params = useSearchParams();
  const pathname = usePathname() ?? "/";
  useEffect(() => {
    const intent = feedbackIntent(params);
    if (intent) show(intent.kind, intent.from);
  }, [params, show]);
  return <FeedbackDialog open={open} onClose={close} initialKind={kind} page={from ?? pathname} />;
}
