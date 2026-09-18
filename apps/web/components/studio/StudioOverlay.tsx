"use client";

import { useEffect, useRef, useState } from "react";
import { cx } from "@/components/ui";
import type { ModelAnalysis, SceneVersion } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";
import { useLabour } from "./useLabour";
import { useStudioUi } from "./useStudioUi";

function withArticle(category: string): string {
  return `${/^[aeiou]/i.test(category) ? "an" : "a"} ${category.replace(/_/g, " ")}`;
}

/**
 * One quiet line under the project name. Replaces the step indicator (spec 8, revised):
 * "No model yet" → "Looks like a car · 4.7 m long" → "Scene ready · 3 versions". The
 * prompt itself is not echoed: the sidebar history already carries it.
 */
export function statusLine(input: {
  hasModel: boolean;
  analysis: ModelAnalysis | null;
  versions: SceneVersion[];
}): string {
  const { hasModel, analysis, versions } = input;
  if (versions.length > 0) {
    return `Scene ready · ${versions.length} ${versions.length === 1 ? "version" : "versions"}`;
  }
  if (!hasModel) return "No model yet";
  if (!analysis) return "Reading the model";
  const longest = Math.max(...analysis.dimensionsMeters);
  return `Looks like ${withArticle(analysis.category)} · ${longest.toFixed(1)} m long`;
}

/**
 * A 120px gradient across the top of the viewer so the name, status and the details
 * button read over a bright model. Sits under the overlays and never takes pointer events.
 */
export function OverlayScrim({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      data-testid="overlay-scrim"
      className={cx("pointer-events-none absolute inset-x-0 top-0 h-[120px]", className)}
      style={{ background: "linear-gradient(to bottom, color-mix(in oklab, var(--color-bg-0) 60%, transparent), transparent)" }}
    />
  );
}

/** Top-left of the viewer: the project name (click to rename) and the status line. */
export function ProjectStatus({ className }: { className?: string }) {
  const project = useStudioStore((s) => s.project);
  const asset = useStudioStore((s) => s.asset);
  const blobMissing = useStudioStore((s) => s.blobMissing);
  const analysis = useStudioStore((s) => s.analysis);
  const versions = useStudioStore((s) => s.versions);
  const rename = useStudioStore((s) => s.rename);
  const { labouring, frozenAnalysis, frozenVersionCount } = useLabour();

  // The line advances when the labour sequence ends, not when the store resolves.
  const status = statusLine({
    hasModel: asset !== null && !blobMissing,
    analysis: labouring ? frozenAnalysis : analysis,
    versions: labouring ? versions.slice(0, frozenVersionCount) : versions,
  });

  return (
    <div className={cx("pointer-events-none flex max-w-[min(60%,26rem)] flex-col", className)}>
      <div className="pointer-events-auto -ml-2 flex">
        {project ? (
          <InlineName name={project.name} onCommit={(n) => void rename(n)} />
        ) : (
          <span className="mx-2 my-1 block h-5 w-32 animate-pulse rounded-sm bg-bg-2" />
        )}
      </div>
      <p className="truncate text-[13px] text-fg-muted" data-testid="studio-status" aria-live="polite">
        {project ? status : ""}
      </p>
    </div>
  );
}

function InlineName({ name, onCommit }: { name: string; onCommit: (name: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) input.current?.select();
  }, [editing]);

  const commit = () => {
    setEditing(false);
    const next = draft.trim();
    if (next && next !== name) onCommit(next);
    else setDraft(name);
  };

  if (editing) {
    return (
      <input
        ref={input}
        aria-label="Project name"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") { setDraft(name); setEditing(false); }
        }}
        maxLength={80}
        className="h-7 w-full max-w-xs rounded-sm border border-line bg-bg-1 px-2 text-sm font-medium text-fg outline-none focus-visible:focus-ring"
      />
    );
  }
  return (
    <button
      type="button"
      onClick={() => { setDraft(name); setEditing(true); }}
      aria-label={`Project name: ${name}. Rename`}
      title="Rename"
      className="block h-7 max-w-full truncate rounded-sm px-2 text-left text-sm font-medium text-fg transition-colors duration-fast ease-standard hover:bg-bg-2 focus-visible:focus-ring"
    >
      {name}
    </button>
  );
}

/** Top-right of the viewer: the single icon that opens the scene details drawer. */
export function SceneDetailsButton({ className }: { className?: string }) {
  const open = useStudioUi((s) => s.drawerOpen);
  const toggle = useStudioUi((s) => s.toggleDrawer);
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Scene details"
      aria-expanded={open}
      aria-controls="scene-drawer"
      className={cx(
        "flex size-9 cursor-pointer items-center justify-center rounded-full text-fg-muted transition-colors duration-fast ease-standard hover:bg-bg-2 hover:text-fg focus-visible:focus-ring",
        open && "bg-bg-2 text-fg",
        className,
      )}
    >
      <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
        <circle cx="16" cy="7" r="2" />
        <circle cx="10" cy="17" r="2" />
      </svg>
    </button>
  );
}
