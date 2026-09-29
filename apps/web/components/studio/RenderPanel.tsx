"use client";

import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Badge, Button, cx } from "@/components/ui";
import { fadeRise, reduced } from "@/lib/motion/variants";
import { renderCost } from "@/lib/render/cost";
import {
  FINISHES,
  MAX_PROMPT,
  OFFERED_DURATIONS,
  SEED_LIMIT,
  parseRenderParams,
  type PaintFinish,
  type RenderAspect,
  type RenderParamsInput,
  type RenderTier,
} from "@/lib/render/params";
import { renderPlanLimits } from "@/lib/render/planLimits";
import { WORLDS, type WorldId } from "@/lib/render/worlds";
import type { RenderJob } from "@/lib/schema";
import { services } from "@/lib/services";
import { useAuthStore } from "@/lib/stores/auth";
import { useCreditsStore } from "@/lib/stores/credits";
import { useRenderStore } from "@/lib/stores/render";
import { useStudioStore } from "@/lib/stores/studio";
import { JobProgress } from "./JobProgress";
import { RenderResult } from "./RenderResult";
import { useStudioUi } from "./useStudioUi";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

type Draft = {
  prompt: string;
  world: WorldId | null;
  aspect: RenderAspect;
  tier: RenderTier;
  duration: number | null;
  paint: string | null;
  finish: PaintFinish;
  seed: string;
};

const INITIAL: Omit<Draft, "prompt"> = { world: null, aspect: "9:16", tier: "preview", duration: null, paint: null, finish: "gloss", seed: "" };

/** The form as the worker contract's params: unset options are left for the director to choose. */
export function draftToParams(d: Draft): RenderParamsInput {
  const p: RenderParamsInput = { prompt: d.prompt, tier: d.tier, aspect: d.aspect };
  if (d.world) p.world = d.world;
  if (d.duration !== null) p.duration = d.duration;
  if (d.paint) {
    p.paint = d.paint;
    p.finish = d.finish;
  }
  const seed = d.seed.trim();
  if (seed !== "") p.seed = Number(seed);
  return p;
}

/**
 * Render tab. One primary action (Render); everything the director can decide on its own (world, length,
 * paint, seed) starts on "Auto" and sits behind a disclosure. Jobs live in the render store, so closing the
 * drawer never stops following a render; the list below the form is the project's recent renders.
 */
export function RenderPanel() {
  const rm = useReducedMotion() ?? false;
  const project = useStudioStore((s) => s.project);
  const asset = useStudioStore((s) => s.asset);
  const versionId = useStudioStore((s) => s.selectedVersionId);
  const versionPrompt = useStudioStore((s) => s.versions.find((v) => v.id === s.selectedVersionId)?.prompt ?? "");
  const plan = useAuthStore((s) => s.user?.plan ?? "free");
  const limits = renderPlanLimits(plan);
  // Tier and format start from what the scene asked for ("4k", "vertical"), else the Settings defaults,
  // and never from a tier this plan cannot render.
  const prefTier = useAuthStore((s) => s.user?.prefs.defaultOutput.tier ?? INITIAL.tier);
  const prefAspect = useAuthStore((s) => s.user?.prefs.defaultOutput.aspect ?? INITIAL.aspect);
  const sceneTier = useStudioStore((s) => s.versions.find((v) => v.id === s.selectedVersionId)?.plan.output.tier);
  const sceneAspect = useStudioStore((s) => s.versions.find((v) => v.id === s.selectedVersionId)?.plan.output.aspect);
  const wantTier = sceneTier ?? prefTier;
  const startOutput = { tier: limits.tiers.includes(wantTier) ? wantTier : INITIAL.tier, aspect: sceneAspect ?? prefAspect };
  const startKey = `${startOutput.tier}|${startOutput.aspect}`;

  const jobs = useRenderStore((s) => s.jobs);
  const pending = useRenderStore((s) => s.pending);
  const outcome = useRenderStore((s) => s.outcome);
  const request = useRenderStore((s) => s.request);
  const cancel = useRenderStore((s) => s.cancel);
  const load = useRenderStore((s) => s.load);

  const projectId = project?.id ?? null;
  useEffect(() => {
    if (projectId) void load(projectId);
  }, [projectId, load]);

  const [draft, setDraft] = useState<Draft>({ ...INITIAL, ...startOutput, prompt: versionPrompt });
  // A newly selected scene version brings its words along, unless the user already typed their own.
  const [touched, setTouched] = useState(false);
  const [seenPrompt, setSeenPrompt] = useState(versionPrompt);
  if (versionPrompt !== seenPrompt) {
    setSeenPrompt(versionPrompt);
    if (!touched) setDraft((d) => ({ ...d, prompt: versionPrompt }));
  }
  // Likewise tier and format follow the scene / Settings until the user picks their own.
  const [outputTouched, setOutputTouched] = useState(false);
  const [seenStart, setSeenStart] = useState(startKey);
  if (startKey !== seenStart) {
    setSeenStart(startKey);
    if (!outputTouched) setDraft((d) => ({ ...d, ...startOutput }));
  }
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));

  const [moreOpen, setMoreOpen] = useState(false);
  const moreId = useId();
  const promptId = useId();

  const params = useMemo(() => draftToParams(draft), [draft]);
  const check = useMemo(() => parseRenderParams(params), [params]);
  const ready = Boolean(project && asset);
  const cost = renderCost(draft.tier);
  const tierAllowed = limits.tiers.includes(draft.tier);
  const balance = useCreditsStore((s) => s.balance);
  const creditsLoaded = useCreditsStore((s) => s.loaded);

  // "Render" from the composer opens the drawer here and asks this button to take focus.
  const renderButton = useRef<HTMLButtonElement>(null);
  const focusRequest = useStudioUi((s) => s.focusRequest);
  const clearFocusRequest = useStudioUi((s) => s.clearFocusRequest);
  useEffect(() => {
    if (focusRequest !== "render") return;
    renderButton.current?.focus();
    clearFocusRequest();
  }, [focusRequest, clearFocusRequest]);

  const submit = (p: RenderParamsInput = params) => {
    if (!project || !asset || pending) return;
    void request({ projectId: project.id, uploadId: asset.id, versionId, params: p });
  };

  const v = rm ? reduced(fadeRise) : fadeRise;
  const [latest, ...older] = jobs;

  return (
    <div className="flex flex-col gap-6 p-4">
      <section aria-label="New render" className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor={promptId} className="text-xs text-fg-muted">Direction</label>
          <textarea
            id={promptId}
            value={draft.prompt}
            onChange={(e) => {
              setTouched(true);
              set({ prompt: e.target.value });
            }}
            maxLength={MAX_PROMPT}
            rows={3}
            placeholder="Describe the shot, or leave it empty and let the director choose."
            className="w-full resize-none rounded-md border border-line bg-bg-0 px-3 py-2 text-sm text-fg placeholder:text-fg-muted/70 focus-visible:focus-ring"
          />
          {draft.prompt.length > MAX_PROMPT - 200 && (
            <span className="self-end tabular text-[11px] text-fg-muted">{draft.prompt.length} / {MAX_PROMPT}</span>
          )}
        </div>

        <CardGroup
          label="World"
          value={draft.world ?? "auto"}
          onChange={(id) => set({ world: id === "auto" ? null : (id as WorldId) })}
          options={[
            { id: "auto", title: "Auto", sub: "The director picks a world for your model." },
            ...WORLDS.map((w) => ({ id: w.id, title: w.label, sub: w.blurb })),
          ]}
        />

        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-fg-muted" id={`${promptId}-format`}>Format</span>
          <Pills
            labelledBy={`${promptId}-format`}
            value={draft.aspect}
            onChange={(aspect) => {
              setOutputTouched(true);
              set({ aspect });
            }}
            options={[
              { value: "9:16", label: "Vertical 9:16" },
              { value: "16:9", label: "Landscape 16:9" },
            ]}
          />
        </div>

        <CardGroup
          label="Quality"
          value={draft.tier}
          onChange={(id) => {
            setOutputTouched(true);
            set({ tier: id as RenderTier });
          }}
          options={[
            {
              id: "preview",
              title: "Preview",
              sub: limits.watermark ? "540p · fast, to check the shot · watermarked" : "540p · fast, to check the shot",
              credits: renderCost("preview"),
            },
            {
              id: "final",
              title: "Final",
              sub: "1080p · full quality",
              credits: renderCost("final"),
              ...(limits.tiers.includes("final") ? {} : { tag: "Creator", disabled: true }),
            },
          ]}
        />

        <div className="flex flex-col gap-3">
          <button
            type="button"
            aria-expanded={moreOpen}
            aria-controls={moreId}
            onClick={() => setMoreOpen((o) => !o)}
            className="inline-flex h-8 w-fit cursor-pointer select-none items-center gap-1.5 rounded-full border border-line bg-transparent px-3 text-sm text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring"
          >
            More options
            <span className="text-fg-muted">· {summariseMore(draft)}</span>
            <Chevron open={moreOpen} />
          </button>
          {moreOpen && (
            <div id={moreId} className="flex flex-col gap-4 rounded-md border border-line bg-bg-1 p-3">
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-fg-muted" id={`${moreId}-len`}>Length</span>
                <Pills
                  labelledBy={`${moreId}-len`}
                  value={draft.duration ?? 0}
                  onChange={(d) => set({ duration: d === 0 ? null : d })}
                  options={[{ value: 0, label: "Auto" }, ...OFFERED_DURATIONS.map((d) => ({ value: d, label: `${d} s` }))]}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-fg-muted" id={`${moreId}-paint`}>Paint</span>
                <div className="flex flex-wrap items-center gap-2">
                  <Pills
                    labelledBy={`${moreId}-paint`}
                    value={draft.paint ? "custom" : "model"}
                    onChange={(m) => set({ paint: m === "model" ? null : (draft.paint ?? "#1a2b3c") })}
                    options={[
                      { value: "model", label: "As modelled" },
                      { value: "custom", label: "Custom" },
                    ]}
                  />
                  {draft.paint && (
                    <input
                      type="color"
                      aria-label="Paint colour"
                      value={draft.paint}
                      onChange={(e) => set({ paint: e.target.value })}
                      className="h-8 w-10 cursor-pointer rounded-sm border border-line bg-bg-0"
                    />
                  )}
                </div>
                {draft.paint && (
                  <Pills
                    label="Finish"
                    value={draft.finish}
                    onChange={(finish) => set({ finish })}
                    options={FINISHES.map((f) => ({ value: f, label: cap(f) }))}
                  />
                )}
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor={`${moreId}-seed`} className="text-xs text-fg-muted">Seed</label>
                <input
                  id={`${moreId}-seed`}
                  inputMode="numeric"
                  value={draft.seed}
                  onChange={(e) => set({ seed: e.target.value.replace(/[^0-9]/g, "").slice(0, 10) })}
                  placeholder="Random"
                  aria-describedby={`${moreId}-seed-hint`}
                  className="h-9 w-full rounded-md border border-line bg-bg-0 px-3 text-sm text-fg tabular placeholder:text-fg-muted/70 focus-visible:focus-ring"
                />
                <span id={`${moreId}-seed-hint`} className="text-[11px] text-fg-muted">
                  The same seed and settings direct the same shot. 0 to {(SEED_LIMIT - 1).toLocaleString("en-US")}.
                </span>
              </div>
            </div>
          )}
        </div>

        <Button
          ref={renderButton}
          variant="primary"
          size="lg"
          className="w-full"
          disabled={!ready || !check.ok || !tierAllowed}
          loading={pending}
          onClick={() => submit()}
        >
          Render · {cost} credits
        </Button>

        {!ready && (
          <p className="text-xs text-fg-muted" role="note">
            Add a model first. Renders start from your model.
          </p>
        )}
        {ready && !check.ok && (
          <p className="text-xs text-danger" role="note">
            {check.message.startsWith("seed")
              ? `Seed must be a whole number from 0 to ${(SEED_LIMIT - 1).toLocaleString("en-US")}.`
              : "Check the options above."}
          </p>
        )}
        {creditsLoaded && <LowBalanceNote balance={balance} />}
      </section>

      {/* Persistent live region: the request outcome (unavailable, error) is announced when it appears. */}
      <div aria-live="polite">
        <AnimatePresence mode="wait">
          {outcome?.kind === "not_connected" && (
            <motion.div key="nc" variants={v} initial="hidden" animate="visible" exit="exit">
              <NotConnected />
            </motion.div>
          )}
          {outcome?.kind === "error" && (
            <motion.div
              key="err"
              variants={v}
              initial="hidden"
              animate="visible"
              exit="exit"
              role="alert"
              className="rounded-md border border-danger/40 bg-bg-2 px-3 py-2 text-sm text-fg"
            >
              {outcome.error.message}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {latest && (
        <section aria-label="Renders" className="flex flex-col gap-4">
          <motion.div key={latest.id} variants={v} initial="hidden" animate="visible" className="flex flex-col gap-4">
            <JobView job={latest} onRetry={() => latest.params && submit(latest.params as RenderParamsInput)} onCancel={() => void cancel(latest.id)} />
          </motion.div>
          {older.length > 0 && <OlderJobs jobs={older} />}
        </section>
      )}
    </div>
  );
}

function JobView({ job, onRetry, onCancel }: { job: RenderJob; onRetry: () => void; onCancel: () => void }) {
  if (job.status === "COMPLETE") {
    return (
      <RenderResult
        job={job}
        onRegenerate={onRetry}
        onDownload={async () => {
          const r = await services.render.downloadUrl(job.id, "video");
          if (r.ok) window.location.assign(r.value);
        }}
      />
    );
  }
  const stopped = job.status === "FAILED" || job.status === "CANCELLED";
  return <JobProgress job={job} onRetry={stopped && job.params ? onRetry : undefined} onCancel={stopped ? undefined : onCancel} />;
}

function OlderJobs({ jobs }: { jobs: RenderJob[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-fg-muted">Earlier renders</span>
      <ul className="flex flex-col divide-y divide-line rounded-md border border-line">
        {jobs.map((j) => (
          <li key={j.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
            <span className="min-w-0 truncate text-fg">
              {j.kind === "preview" ? "Preview" : "Final"}
              <span className="text-fg-muted"> · {j.params?.world ? (WORLDS.find((w) => w.id === j.params?.world)?.label ?? j.params.world) : "Auto"}</span>
            </span>
            {j.status === "COMPLETE" && j.expired ? (
              <span className="shrink-0 text-xs text-fg-muted">Expired</span>
            ) : j.status === "COMPLETE" && j.resultUrl ? (
              <a href={j.resultUrl} target="_blank" rel="noreferrer" className="shrink-0 text-xs text-fg underline-offset-2 hover:underline focus-visible:focus-ring">
                Open
              </a>
            ) : (
              <span className="shrink-0 text-xs text-fg-muted">{cap(j.status.toLowerCase())}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * A quiet line under the Render button once the balance cannot cover a Final render: one element, no banner.
 * Exported for the unit test.
 */
export function LowBalanceNote({ balance }: { balance: number }) {
  const finalCost = renderCost("final");
  if (balance >= finalCost) return null;
  return (
    <p className="text-xs text-fg-muted" role="note" data-testid="low-balance">
      {balance.toLocaleString("en-US")} credits left. A Final render uses {finalCost}.{" "}
      <Link href="/pricing" className="text-fg underline underline-offset-2 focus-visible:focus-ring">
        Get credits
      </Link>
    </p>
  );
}

function summariseMore(d: Draft): string {
  const bits = [d.duration ? `${d.duration} s` : "Auto length"];
  if (d.paint) bits.push(`${cap(d.finish)} paint`);
  if (d.seed.trim()) bits.push(`seed ${d.seed.trim()}`);
  return bits.join(" · ");
}

/** Recovery state when the render service cannot accept a job. */
export function NotConnected() {
  return (
    <div className="flex flex-col gap-4" data-testid="render-not-connected">
      <div className="relative flex aspect-video w-full flex-col items-center justify-center gap-2 overflow-hidden rounded-lg border border-dashed border-line bg-bg-0 px-6 text-center">
        <span
          aria-hidden
          className="mb-1 size-10 rounded-full border border-line"
          style={{
            background:
              "radial-gradient(circle at 50% 40%, color-mix(in oklab, var(--color-primary) 30%, transparent), transparent 70%)",
          }}
        />
        <p className="text-sm font-medium text-fg">Rendering is currently unavailable. Please try again later or contact support.</p>
      </div>
      <p className="text-xs leading-relaxed text-fg-muted">Your settings are kept. No credits were charged.</p>
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

type PillsProps<T extends string | number> = {
  label?: string;
  labelledBy?: string;
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (v: T) => void;
};

/** A compact radio group: arrows move and select, the chosen option is the tab stop. */
function Pills<T extends string | number>({ label, labelledBy, value, options, onChange }: PillsProps<T>) {
  const ref = useRef<HTMLDivElement>(null);
  const pick = (i: number) => {
    const j = (i + options.length) % options.length;
    onChange(options[j].value);
    ref.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[j]?.focus();
  };
  const onKeyDown = (e: KeyboardEvent, i: number) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); pick(i + 1); }
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); pick(i - 1); }
  };
  return (
    <div
      ref={ref}
      role="radiogroup"
      aria-label={label}
      aria-labelledby={labelledBy}
      className="grid w-full auto-cols-fr grid-flow-col rounded-md border border-line bg-bg-0 p-0.5"
    >
      {options.map((o, i) => {
        const checked = o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cx(
              "h-8 cursor-pointer whitespace-nowrap rounded-sm px-1.5 text-xs transition-colors duration-fast ease-standard focus-visible:focus-ring",
              checked ? "bg-bg-3 text-fg" : "text-fg-muted hover:text-fg",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

type CardOption = { id: string; title: string; sub: string; credits?: number; tag?: string; disabled?: boolean };

/** Selectable cards with radio semantics: arrow keys move among the enabled ones, Tab lands on the checked one. */
function CardGroup({ label, value, onChange, options }: { label: string; value: string; onChange: (id: string) => void; options: CardOption[] }) {
  const groupId = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const order = options.filter((o) => !o.disabled).map((o) => o.id);
    const i = order.indexOf(value);
    let next: string | null = null;
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
    <div className="flex flex-col gap-1.5">
      <span id={`${groupId}-label`} className="text-xs text-fg-muted">{label}</span>
      <div role="radiogroup" aria-labelledby={`${groupId}-label`} className="grid grid-cols-2 gap-2">
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
              disabled={o.disabled}
              onClick={() => onChange(o.id)}
              onKeyDown={onKeyDown}
              className={cx(
                "flex min-h-20 flex-col items-start gap-1.5 rounded-md border p-3 text-left transition-colors duration-fast ease-standard focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50",
                checked ? "border-primary bg-bg-2" : "border-line bg-bg-1 hover:border-fg-muted/60 hover:bg-bg-2",
              )}
            >
              <div className="flex w-full flex-wrap items-center justify-between gap-x-2 gap-y-1">
                <span className="text-sm font-medium text-fg">{o.title}</span>
                {o.tag && <Badge tone="neutral">{o.tag}</Badge>}
              </div>
              <span className="text-xs leading-snug text-fg-muted">{o.sub}</span>
              {o.credits !== undefined && <span className="mt-auto tabular text-sm text-fg">{o.credits} credits</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
