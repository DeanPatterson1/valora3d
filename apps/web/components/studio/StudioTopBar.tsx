"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useStudioStore } from "@/lib/stores/studio";
import { deriveSteps, StepIndicator } from "./StepIndicator";
import { useLabour } from "./useLabour";

/** Project name (click or Enter to rename inline) and the step indicator. */
export function StudioTopBar() {
  const project = useStudioStore((s) => s.project);
  const asset = useStudioStore((s) => s.asset);
  const analysis = useStudioStore((s) => s.analysis);
  const versionCount = useStudioStore((s) => s.versions.length);
  const rename = useStudioStore((s) => s.rename);
  const { labouring, frozenAnalysis, frozenVersionCount } = useLabour();

  // Steps fill when the labour sequence ends, not when the store resolves (spec 10, goal gradient).
  const steps = deriveSteps({
    hasAsset: asset !== null,
    hasAnalysis: (labouring ? frozenAnalysis : analysis) !== null,
    versionCount: labouring ? frozenVersionCount : versionCount,
  });

  return (
    <div className="flex h-12 min-w-0 items-center gap-3 border-b border-line bg-bg-1 px-3 sm:px-4">
      <Link
        href="/projects"
        aria-label="Back to projects"
        className="flex size-8 shrink-0 items-center justify-center rounded-sm text-fg-muted transition-colors duration-fast ease-standard hover:bg-bg-2 hover:text-fg focus-visible:focus-ring"
      >
        <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 3 5 8l5 5" />
        </svg>
      </Link>
      <div className="min-w-0 flex-1">
        {project ? <InlineName name={project.name} onCommit={(n) => void rename(n)} /> : <span className="block h-5 w-32 animate-pulse rounded-sm bg-bg-2" />}
      </div>
      <StepIndicator steps={steps} className="hidden shrink-0 md:flex" />
      <span className="text-xs text-fg-muted md:hidden">
        {steps.filter((s) => s.state === "done").length}/{steps.length - 1}
      </span>
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
        className="h-8 w-full max-w-xs rounded-sm border border-line bg-bg-0 px-2 font-display text-base font-semibold text-fg outline-none focus-visible:focus-ring"
      />
    );
  }
  return (
    <button
      type="button"
      onClick={() => { setDraft(name); setEditing(true); }}
      aria-label={`Project name: ${name}. Rename`}
      title="Rename"
      className="block max-w-full truncate rounded-sm px-2 py-1 text-left font-display text-base font-semibold text-fg transition-colors duration-fast ease-standard hover:bg-bg-2 focus-visible:focus-ring"
    >
      {name}
    </button>
  );
}
