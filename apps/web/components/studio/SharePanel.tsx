"use client";

import { useEffect, useId, useState } from "react";
import { Button, Skeleton, useToastStore } from "@/components/ui";
import type { RenderShareService } from "@/lib/services/types";
import type { RenderShare } from "@/lib/share/types";

export type SharePanelProps = {
  jobId: string;
  service: RenderShareService;
};

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * Opt-in public link for a finished render, opened from RenderResult's "Share". Nothing is public until the
 * owner presses "Create link"; the prompt stays private unless they tick the box.
 */
export function SharePanel({ jobId, service }: SharePanelProps) {
  const push = useToastStore((s) => s.push);
  const [share, setShare] = useState<RenderShare | null | undefined>(undefined);
  const [showPrompt, setShowPrompt] = useState(false);
  const [busy, setBusy] = useState<"create" | "prompt" | "stop" | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const checkboxId = useId();
  const linkId = useId();

  useEffect(() => {
    let live = true;
    void service.getShare(jobId).then((r) => {
      if (!live) return;
      if (r.ok) {
        setShare(r.value);
        setShowPrompt(r.value?.showPrompt ?? false);
      } else {
        setLoadError(r.error.message);
      }
    });
    return () => {
      live = false;
    };
  }, [jobId, service]);

  const url = share ? `${window.location.origin}${share.path}` : "";

  async function create() {
    setBusy("create");
    const r = await service.share(jobId, { showPrompt });
    setBusy(null);
    if (!r.ok) {
      push({ kind: "danger", message: r.error.message });
      return;
    }
    setShare(r.value);
    const copied = await copyText(`${window.location.origin}${r.value.path}`);
    push({ kind: "success", message: copied ? "Link created and copied." : "Link created." });
  }

  async function togglePrompt(next: boolean) {
    setShowPrompt(next);
    if (!share) return;
    setBusy("prompt");
    const r = await service.share(jobId, { showPrompt: next });
    setBusy(null);
    if (!r.ok) {
      setShowPrompt(!next);
      push({ kind: "danger", message: r.error.message });
      return;
    }
    setShare(r.value);
    push({ kind: "info", message: next ? "Your prompt now shows on the page." : "Your prompt is hidden." });
  }

  async function copy() {
    const copied = await copyText(url);
    push(copied ? { kind: "success", message: "Link copied." } : { kind: "danger", message: "Couldn't copy. Select the link and copy it." });
  }

  async function stop() {
    setBusy("stop");
    const r = await service.unshare(jobId);
    setBusy(null);
    if (!r.ok) {
      push({ kind: "danger", message: r.error.message });
      return;
    }
    setShare(null);
    push({ kind: "info", message: "Sharing stopped. The old link no longer works." });
  }

  return (
    <section aria-label="Share" className="flex flex-col gap-4 rounded-lg border border-line bg-bg-1 p-4">
      <div className="flex flex-col gap-1">
        <h4 className="text-sm font-medium text-fg">{share ? "Shared with a public link" : "Share a public link"}</h4>
        <p className="text-sm text-fg-muted">
          {share
            ? "Anyone with the link can watch this video. It stops working when the render expires."
            : "Anyone with the link can watch this video. You can stop sharing at any time."}
        </p>
      </div>

      {share === undefined && !loadError ? (
        <Skeleton className="h-9 w-full" />
      ) : loadError ? (
        <p role="alert" className="text-sm text-danger">
          {loadError}
        </p>
      ) : (
        <>
          {share && (
            <div className="flex flex-col gap-2 sm:flex-row">
              <label htmlFor={linkId} className="sr-only">
                Share link
              </label>
              <input
                id={linkId}
                readOnly
                value={url}
                onFocus={(e) => e.currentTarget.select()}
                className="h-9 w-full min-w-0 shrink-0 rounded-sm border border-line bg-bg-2 sm:w-auto sm:flex-1 px-3 text-sm text-fg outline-none focus-visible:focus-ring"
              />
              <Button variant="secondary" icon={<LinkIcon />} onClick={copy}>
                Copy link
              </Button>
            </div>
          )}

          <label htmlFor={checkboxId} className="flex cursor-pointer items-center gap-2 text-sm text-fg">
            <input
              id={checkboxId}
              type="checkbox"
              checked={showPrompt}
              disabled={busy !== null}
              onChange={(e) => void togglePrompt(e.currentTarget.checked)}
              className="size-4 cursor-pointer"
            />
            Show my prompt on the page
          </label>

          {share ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-fg-muted">
                {share.viewCount === 1 ? "1 view" : `${share.viewCount.toLocaleString("en-US")} views`}
              </span>
              <Button variant="danger" size="sm" loading={busy === "stop"} disabled={busy !== null} onClick={stop}>
                Stop sharing
              </Button>
            </div>
          ) : (
            <div>
              <Button variant="secondary" icon={<LinkIcon />} loading={busy === "create"} disabled={busy !== null} onClick={create}>
                Create link
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

export function ShareIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 10V2.5M5 5.5l3-3 3 3M3.5 8.5v4.5h9V8.5" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6.5 9.5l3-3M7 4.5l1-1a2.8 2.8 0 0 1 4 4l-1 1M9 11.5l-1 1a2.8 2.8 0 0 1-4-4l1-1" />
    </svg>
  );
}
