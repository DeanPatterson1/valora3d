"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, cx } from "@/components/ui";
import { RENDER_SERVER, health } from "@/lib/render/provider";

/**
 * Live status of the local render server (`tools/render-studio/server.py`).
 *
 * Reported rather than asserted: the server is a separate process the person starts
 * themselves, so the only truthful thing to show is the result of asking it.
 */

type State =
  | { kind: "checking" }
  | { kind: "ready"; gpu?: string; queueLength?: number }
  | { kind: "unavailable"; reason?: string }
  | { kind: "offline" };

const START_COMMAND = "py tools/render-studio/server.py";

const DOT: Record<State["kind"], string> = {
  checking: "bg-fg-muted/50",
  ready: "bg-success",
  unavailable: "bg-danger",
  offline: "bg-fg-muted/50",
};

export function LocalRendererStatus() {
  const [state, setState] = useState<State>({ kind: "checking" });

  const check = useCallback(async () => {
    setState({ kind: "checking" });
    try {
      const result = await health();
      setState(
        result.ready
          ? { kind: "ready", gpu: result.gpu, queueLength: result.queueLength }
          : { kind: "unavailable", reason: result.error },
      );
    } catch {
      setState({ kind: "offline" });
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  return (
    <div className="flex flex-col gap-3" data-testid="local-renderer-status">
      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 text-sm text-fg-muted">
          <span aria-hidden className={cx("size-1.5 rounded-full", DOT[state.kind])} />
          <span data-testid="local-renderer-label">{label(state)}</span>
        </span>
        <Button size="sm" onClick={check} loading={state.kind === "checking"}>
          Check again
        </Button>
      </div>

      {state.kind === "ready" && state.gpu && (
        <p className="text-xs text-fg-muted">
          Rendering on {state.gpu}
          {typeof state.queueLength === "number" && state.queueLength > 0
            ? ` · ${state.queueLength} job${state.queueLength === 1 ? "" : "s"} queued`
            : ""}
          .
        </p>
      )}

      {state.kind === "offline" && (
        <p className="text-xs leading-relaxed text-fg-muted">
          Start it from the repository root, then check again:
          <code className="mt-1 block rounded-md border border-line bg-bg-2 px-2 py-1 font-mono text-[11px] text-fg">
            {START_COMMAND}
          </code>
          It listens on {RENDER_SERVER} and never leaves this machine.
        </p>
      )}

      {state.kind === "unavailable" && (
        <p className="text-xs leading-relaxed text-fg-muted">
          {state.reason ?? "The render server is running but cannot render yet."} Blender and ffmpeg both need to be
          on your PATH.
        </p>
      )}
    </div>
  );
}

function label(state: State): string {
  switch (state.kind) {
    case "checking":
      return "Checking…";
    case "ready":
      return "Connected";
    case "unavailable":
      return "Running, but not ready";
    case "offline":
      return "Not running";
  }
}
