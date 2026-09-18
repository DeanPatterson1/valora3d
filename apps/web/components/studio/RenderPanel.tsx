"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Badge, Button, cx } from "@/components/ui";
import { fadeRise, reduced } from "@/lib/motion/variants";
import { CREDIT_COSTS, cloudPrice } from "@/lib/pricing";
import type { RenderJob, ScenePlan } from "@/lib/schema";
import { services, type ServiceError } from "@/lib/services";
import { useStudioStore } from "@/lib/stores/studio";
import { JobProgress } from "./JobProgress";
import { RenderResult } from "./RenderResult";

type Target = "local" | "cloud";

const QUALITY_LABEL: Record<ScenePlan["output"]["quality"], string> = {
  draft: "Draft",
  standard: "Standard",
  high: "High",
  ultra: "Ultra",
};

/** "10 s · 1080p · 30 fps · High" */
export function outputSummary(o: ScenePlan["output"]): string {
  return `${o.durationS} s · ${o.resolution} · ${o.fps} fps · ${QUALITY_LABEL[o.quality]}`;
}

type Outcome = null | { kind: "not_connected" } | { kind: "error"; error: ServiceError } | { kind: "job"; job: RenderJob };

type TargetOption = { id: Target; title: string; sub: string; credits: number; tag?: string };

const TARGETS = (cloudCredits: number): TargetOption[] => [
  { id: "local", title: "Local GPU", sub: "Your GPU · renders on your own machine", credits: CREDIT_COSTS.local_final, tag: "Cheapest" },
  { id: "cloud", title: "Cloud GPU", sub: "No setup · renders on our GPUs", credits: cloudCredits, tag: "Fastest" },
];

/**
 * Render tab (spec 7). Every surface around the renderer is here; the renderer itself
 * is not. One primary action (Render); the preview is a quieter secondary and the
 * target sits behind a chip-style disclosure. Pressing either action asks
 * `services.render` and, while nothing is connected, shows a designed "not connected"
 * state rather than an error. Credits are shown, never charged, from this panel.
 */
export function RenderPanel() {
  const rm = useReducedMotion() ?? false;
  const project = useStudioStore((s) => s.project);
  const versionId = useStudioStore((s) => s.selectedVersionId);
  const plan = useStudioStore((s) => s.currentPlan);

  const [target, setTarget] = useState<Target>("local");
  const [targetOpen, setTargetOpen] = useState(false);
  const targetId = useId();
  const [outcome, setOutcome] = useState<Outcome>(null);
  const [pending, setPending] = useState<"preview" | "final" | null>(null);

  const ready = Boolean(project && versionId && plan);
  const cloud = plan ? cloudPrice(plan.output) : CREDIT_COSTS.cloud_final.standard;

  // Follow a job if the renderer ever hands one back. The service decides when to call.
  const jobId = outcome?.kind === "job" ? outcome.job.id : null;
  useEffect(() => {
    if (!jobId) return;
    return services.render.subscribe(jobId, (job) => setOutcome({ kind: "job", job }));
  }, [jobId]);

  const request = async (kind: "preview" | "final") => {
    if (!project || !versionId || pending) return;
    setPending(kind);
    try {
      const r = kind === "preview"
        ? await services.render.requestPreview(project.id, versionId)
        : await services.render.requestFinal(project.id, versionId, target);
      if (r.ok) setOutcome({ kind: "job", job: r.value });
      else if (r.error.code === "not_connected") setOutcome({ kind: "not_connected" });
      else setOutcome({ kind: "error", error: r.error });
    } finally {
      setPending(null);
    }
  };

  const v = rm ? reduced(fadeRise) : fadeRise;
  const selected = TARGETS(cloud).find((o) => o.id === target)!;

  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <section aria-label="Render" className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-bg-2 px-3 py-2">
          <span className="text-xs text-fg-muted">Output</span>
          <span className="font-mono tabular text-xs text-fg" data-testid="output-summary">
            {plan ? outputSummary(plan.output) : "—"}
          </span>
        </div>

        <div className="flex flex-col gap-2">
          <button
            type="button"
            aria-expanded={targetOpen}
            aria-controls={targetId}
            onClick={() => setTargetOpen((o) => !o)}
            className={cx(
              "inline-flex h-8 w-fit cursor-pointer select-none items-center gap-1.5 rounded-full border border-line bg-transparent px-3 text-sm text-fg",
              "transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            <span>
              {selected.title}
              <span className="text-fg-muted"> · {selected.tag ?? selected.sub}</span>
            </span>
            <Chevron open={targetOpen} />
          </button>
          {targetOpen && (
            <div id={targetId}>
              <TargetChoice value={target} onChange={setTarget} cloudCredits={cloud} disabled={!ready} />
            </div>
          )}
        </div>

        <Button
          variant="primary"
          size="lg"
          className="w-full"
          disabled={!ready}
          loading={pending === "final"}
          onClick={() => request("final")}
        >
          Render · {target === "local" ? CREDIT_COSTS.local_final : cloud} credits
        </Button>

        <Button
          variant="secondary"
          className="w-full"
          disabled={!ready}
          loading={pending === "preview"}
          onClick={() => request("preview")}
        >
          Generate preview · {CREDIT_COSTS.preview_render} credits
        </Button>

        {!ready && (
          <p className="text-xs text-fg-muted" role="note">
            Generate a scene first. Rendering starts from a saved version.
          </p>
        )}
      </section>

      <AnimatePresence mode="wait">
        {outcome?.kind === "not_connected" && (
          <motion.div key="nc" variants={v} initial="hidden" animate="visible" exit="exit">
            <NotConnected />
          </motion.div>
        )}
        {outcome?.kind === "error" && (
          <motion.div key="err" variants={v} initial="hidden" animate="visible" exit="exit" role="alert"
            className="rounded-md border border-danger/40 bg-bg-2 px-3 py-2 text-sm text-fg">
            {outcome.error.message}
          </motion.div>
        )}
        {outcome?.kind === "job" && (
          <motion.div key={outcome.job.id} variants={v} initial="hidden" animate="visible" exit="exit" className="flex flex-col gap-4">
            {outcome.job.status === "COMPLETE"
              ? <RenderResult job={outcome.job} onRegenerate={() => request(outcome.job.kind)} />
              : <JobProgress job={outcome.job} onRetry={outcome.job.status === "FAILED" ? () => request(outcome.job.kind) : undefined} />}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** The designed empty state for a renderer that is not wired up yet. Not an error. */
export function NotConnected() {
  return (
    <div className="flex flex-col gap-4" data-testid="render-not-connected">
      <div className="relative flex aspect-video w-full flex-col items-center justify-center gap-2 overflow-hidden rounded-lg border border-dashed border-line bg-bg-0 px-6 text-center">
        <span
          aria-hidden
          className="mb-1 size-10 rounded-full border border-line"
          style={{
            background:
              "radial-gradient(circle at 50% 40%, color-mix(in oklab, var(--color-accent) 30%, transparent), transparent 70%)",
          }}
        />
        <p className="text-sm font-medium text-fg">Renderer not connected yet — this is where your render will appear.</p>
      </div>
      <p className="text-xs leading-relaxed text-fg-muted">
        Your scene, camera path and output settings are saved with this version. When the render service is
        connected, this button sends them straight to it. No credits were charged.
      </p>
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 16 16"
      className={cx("size-3.5 text-fg-muted transition-transform duration-fast ease-standard", open && "rotate-180")}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 6l4 4 4-4" />
    </svg>
  );
}

type ChoiceProps = {
  value: Target;
  onChange: (t: Target) => void;
  cloudCredits: number;
  disabled?: boolean;
};

/** Two selectable cards with radio semantics: arrow keys move, Space/Enter select, Tab lands on the checked one. */
function TargetChoice({ value, onChange, cloudCredits, disabled }: ChoiceProps) {
  const groupId = useId();
  const refs = useRef<Record<Target, HTMLButtonElement | null>>({ local: null, cloud: null });
  const options = TARGETS(cloudCredits);

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const order: Target[] = ["local", "cloud"];
    const i = order.indexOf(value);
    let next: Target | null = null;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = order[(i + 1) % order.length];
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = order[(i - 1 + order.length) % order.length];
    if (e.key === "Home") next = order[0];
    if (e.key === "End") next = order[order.length - 1];
    if (!next) return;
    e.preventDefault();
    onChange(next);
    refs.current[next]?.focus();
  };

  return (
    <div role="radiogroup" aria-labelledby={`${groupId}-label`} className="grid grid-cols-2 gap-2">
      <span id={`${groupId}-label`} className="sr-only">Where to render</span>
      {options.map((o) => {
        const checked = value === o.id;
        return (
          <button
            key={o.id}
            ref={(el) => { refs.current[o.id] = el; }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            disabled={disabled}
            onClick={() => onChange(o.id)}
            onKeyDown={onKeyDown}
            className={cx(
              "flex min-h-24 flex-col items-start gap-2 rounded-md border p-3 text-left transition-colors duration-fast ease-standard focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50",
              checked ? "border-accent bg-bg-2" : "border-line bg-bg-1 hover:border-fg-muted/60 hover:bg-bg-2",
            )}
          >
            <div className="flex w-full flex-wrap items-center justify-between gap-x-2 gap-y-1">
              <span className="whitespace-nowrap text-sm font-medium text-fg">{o.title}</span>
              {o.tag && <Badge tone={checked ? "accent" : "neutral"}>{o.tag}</Badge>}
            </div>
            <span className="text-xs leading-snug text-fg-muted">{o.sub}</span>
            <span className="mt-auto font-mono tabular text-sm text-fg">{o.credits} credits</span>
          </button>
        );
      })}
    </div>
  );
}
