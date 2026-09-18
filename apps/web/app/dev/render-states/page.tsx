"use client";

import { useEffect } from "react";
import { useToastStore } from "@/components/ui";
import { JOB_STATUS, JobProgress } from "@/components/studio/JobProgress";
import { RenderPanel } from "@/components/studio/RenderPanel";
import { RenderResult } from "@/components/studio/RenderResult";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { RenderJobStatus, type Project, type RenderJob } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";

/**
 * Fixture jobs, one per status. Numbers are hand-written so the design can be
 * reviewed; nothing here advances. The renderer will own real jobs later.
 */
const BASE: RenderJob = {
  id: "fixture", projectId: "dev", versionId: "v1", kind: "final", target: "local",
  status: "QUEUED", frame: 0, totalFrames: 300, error: null, resultUrl: null,
};

const FIXTURES: Record<RenderJobStatus, RenderJob> = {
  QUEUED: { ...BASE, id: "queued", target: "cloud" },
  PREPARING: { ...BASE, id: "preparing" },
  RENDERING: { ...BASE, id: "rendering", frame: 204 },
  ENCODING: { ...BASE, id: "encoding", status: "ENCODING", frame: 300 },
  UPLOADING: { ...BASE, id: "uploading", status: "UPLOADING", frame: 300, target: "cloud" },
  COMPLETE: { ...BASE, id: "complete", status: "COMPLETE", frame: 300 },
  FAILED: { ...BASE, id: "failed", status: "FAILED", frame: 57, error: "GPU ran out of memory at frame 57. Try a lower resolution or the cloud." },
};
for (const s of RenderJobStatus.options) FIXTURES[s].status = s;

const DEV_PROJECT: Project = {
  id: "dev-render-states", name: "Render states", createdAt: 0, updatedAt: 0,
  assetId: "dev-asset", analysis: null, selectedVersionId: "dev-v1",
};

const SECTIONS = [
  ["progress", "JobProgress"],
  ["result", "RenderResult"],
  ["panel", "RenderPanel"],
] as const;

export default function RenderStatesPage() {
  const push = useToastStore((s) => s.push);
  const note = (what: string) => push({ kind: "info", message: `${what} pressed. Nothing happens on this page.` });

  return (
    <div className="mx-auto w-full max-w-6xl px-4 pb-32 pt-12 sm:px-6">
      <header className="mb-20 grid gap-8 md:grid-cols-[1fr_auto] md:items-end">
        <div className="flex max-w-2xl flex-col gap-4">
          <h1 className="tracking-tight text-4xl font-semibold text-fg">Render states</h1>
          <p className="max-w-prose text-lg text-fg-muted">
            Every surface that wraps the renderer, in every state, driven by fixture props.
            The process itself is intentionally blank: nothing on this page ticks, polls or plays.
          </p>
        </div>
        <nav aria-label="Sections" className="flex flex-wrap gap-1 md:justify-end">
          {SECTIONS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="rounded-md px-3 py-1.5 text-sm text-fg-muted transition-colors hover:bg-bg-1 hover:text-fg focus-visible:focus-ring">
              {label}
            </a>
          ))}
        </nav>
      </header>

      <div className="flex flex-col gap-24">
        <section aria-labelledby="progress">
          <Heading id="progress" note="Seven statuses. The bar fills from the frame counter while rendering, sits full once past it, and turns red where it stopped.">
            JobProgress
          </Heading>
          <div className="grid gap-4 md:grid-cols-2">
            {RenderJobStatus.options.map((s) => (
              <div key={s} className="flex flex-col gap-2">
                <span className="text-xs text-fg-muted">{s} · {JOB_STATUS[s].copy}</span>
                <JobProgress job={FIXTURES[s]} onRetry={s === "FAILED" ? () => note("Retry") : undefined} />
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="result">
          <Heading id="result" note="The product's best moment when rendering is connected. Left: a finished job with a file. Right: the same frame with no file, as it looks today.">
            RenderResult
          </Heading>
          <div className="grid gap-10 lg:grid-cols-2">
            <Labelled label="with resultUrl (a data: URL that carries no video; the player is real, the file is not)">
              <RenderResult job={{ ...FIXTURES.COMPLETE, resultUrl: "data:video/mp4;base64," }} onRegenerate={() => note("Regenerate")} />
            </Labelled>
            <Labelled label="without resultUrl">
              <RenderResult job={FIXTURES.COMPLETE} onRegenerate={() => note("Regenerate")} />
            </Labelled>
          </div>
        </section>

        <section aria-labelledby="panel">
          <Heading id="panel" note="The Render tab with a fixture plan in the studio store. Press either action to see the not-connected state; the real service answers, no credits move.">
            RenderPanel
          </Heading>
          <Labelled label="360px, as mounted in the studio">
            <div className="w-full max-w-[360px] rounded-lg border border-line bg-bg-1">
              <PanelWithFixturePlan />
            </div>
          </Labelled>
        </section>
      </div>
    </div>
  );
}

/** Seeds the studio store with a project, a version id and a plan so the panel is live. Resets on unmount. */
function PanelWithFixturePlan() {
  useEffect(() => {
    useStudioStore.setState({ project: DEV_PROJECT, selectedVersionId: "dev-v1", currentPlan: defaultPlan("car") });
    return () => useStudioStore.getState().reset();
  }, []);
  // The panel subscribes to the store, so it re-renders enabled once the effect has seeded it.
  return <RenderPanel />;
}

function Heading({ id, children, note }: { id: string; children: React.ReactNode; note?: string }) {
  return (
    <div className="mb-6 flex flex-col gap-1">
      <h2 id={id} className="scroll-mt-20 tracking-tight text-2xl font-semibold text-fg">{children}</h2>
      {note && <p className="max-w-prose text-sm text-fg-muted">{note}</p>}
    </div>
  );
}

function Labelled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      <span className="text-xs text-fg-muted">{label}</span>
      {children}
    </div>
  );
}
