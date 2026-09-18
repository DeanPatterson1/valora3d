"use client";

import { useId, useState } from "react";
import { motion, useReducedMotion, type Variants } from "motion/react";
import { Badge, Skeleton, cx } from "@/components/ui";
import { fadeRise, reduced, staggerList } from "@/lib/motion/variants";
import type { ModelAnalysis } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";
import { useLabour } from "./useLabour";

const UNIT_COPY: Record<ModelAnalysis["unitGuess"], string> = {
  m: "read as metres",
  mm: "read as millimetres",
  cm: "read as centimetres",
  in: "read as inches",
  unknown: "units unknown — assumed metres",
};

const count = new Intl.NumberFormat("en-GB");

/** `front_left_wheel` → "Front left wheel". */
export function humanise(id: string): string {
  const words = id.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function metres(n: number): string {
  return n.toFixed(2);
}

/**
 * Right-panel "Analysis" tab (spec 6.2): what the model was read as. Three rows by
 * default (read as, size, can do); geometry, parts and rig sit behind "More". Fields
 * reveal one by one after the labour sequence so the reading feels earned, not dumped.
 */
export function AnalysisPanel() {
  const liveAnalysis = useStudioStore((s) => s.analysis);
  const stats = useStudioStore((s) => s.stats);
  const busy = useStudioStore((s) => s.busy);
  const { labouring, frozenAnalysis } = useLabour();
  const rm = useReducedMotion() ?? false;
  const [more, setMore] = useState(false);
  const moreId = useId();

  // While the labour sequence runs, a fresh analysis stays behind the skeleton until it ends.
  const analysis = labouring ? frozenAnalysis : liveAnalysis;
  if (busy === "analyzing" || (labouring && frozenAnalysis !== liveAnalysis)) return <AnalysisSkeleton />;
  if (!analysis) {
    return (
      <div className="flex h-full min-h-16 items-center justify-center p-6 text-center">
        <p className="text-sm text-fg-muted">Load a model to see what it is.</p>
      </div>
    );
  }

  const list = rm ? reduced(staggerList) : staggerList;
  const item = rm ? reduced(fadeRise) : fadeRise;
  const [l, w, h] = [...analysis.dimensionsMeters].sort((a, b) => b - a);
  const parts = Object.entries(analysis.parts);
  const confidence = Math.round(analysis.confidence * 100);

  // Mounts fresh after every analysis (the skeleton replaces it while busy), so the stagger replays.
  return (
    <div className="flex flex-col gap-3 p-4">
      <motion.dl
        variants={list}
        initial="hidden"
        animate="visible"
        className="flex flex-col gap-5"
        aria-label="Model analysis"
      >
        <Row variants={item} label="Read as">
          <div className="flex items-center gap-2">
            <span data-testid="analysis-category" className="inline-flex">
              <Badge tone="neutral">{analysis.category}</Badge>
            </span>
            <span className="tabular text-xs text-fg-muted">{confidence}% sure</span>
          </div>
        </Row>

        <Row variants={item} label="Size">
          <div className="text-sm text-fg">
            <span className="tabular">
              {metres(l)} <Sep /> {metres(w)} <Sep /> {metres(h)} <span className="text-fg-muted">m</span>
            </span>
            <span className="text-fg-muted"> · {UNIT_COPY[analysis.unitGuess]}</span>
          </div>
        </Row>

        <Row variants={item} label="Can do">
          {analysis.capabilities.length === 0 ? (
            <div className="text-sm text-fg-muted">Nothing beyond a static shot</div>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {analysis.capabilities.map((c) => (
                <li
                  key={c}
                  className="inline-flex h-7 items-center rounded-full border border-line bg-bg-2 px-2.5 text-xs text-fg"
                >
                  {humanise(c)}
                </li>
              ))}
            </ul>
          )}
        </Row>
      </motion.dl>

      <button
        type="button"
        aria-expanded={more}
        aria-controls={moreId}
        onClick={() => setMore((m) => !m)}
        className="inline-flex h-8 w-fit cursor-pointer items-center gap-1 rounded-full px-2 text-xs text-fg-muted transition-colors duration-fast ease-standard hover:text-fg focus-visible:focus-ring"
      >
        {more ? "Less" : "More"}
        <Chevron open={more} />
      </button>

      {more && (
        <motion.dl
          id={moreId}
          variants={list}
          initial="hidden"
          animate="visible"
          className="flex flex-col gap-5"
          aria-label="More about the model"
        >
          <Row variants={item} label="Geometry">
            {stats ? (
              <div className="tabular text-sm text-fg">
                {count.format(stats.triangleCount)} <span className="text-fg-muted">triangles</span>
                <span className="mx-2 text-fg-muted/60">·</span>
                {count.format(stats.meshCount)} <span className="text-fg-muted">{stats.meshCount === 1 ? "mesh" : "meshes"}</span>
              </div>
            ) : (
              <div className="text-sm text-fg-muted">Counts not available for this session</div>
            )}
          </Row>

          <Row variants={item} label="Parts">
            {parts.length === 0 ? (
              <div className="text-sm text-fg-muted">No named parts recognised</div>
            ) : (
              <ul className="flex flex-col gap-1">
                {parts.map(([role, name]) => (
                  <li key={role} className="text-sm text-fg" title={name}>
                    {humanise(role)}
                  </li>
                ))}
              </ul>
            )}
          </Row>

          <Row variants={item} label="Rig">
            <div className={cx("text-sm", analysis.rigged ? "text-fg" : "text-fg-muted")}>
              {analysis.rigged ? "Rigged" : "No skeleton — static only"}
            </div>
          </Row>
        </motion.dl>
      )}
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 16 16"
      className={cx("size-3.5 transition-transform duration-fast ease-standard", open && "rotate-180")}
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

function Row({ label, variants, children }: { label: string; variants: Variants; children: React.ReactNode }) {
  return (
    <motion.div variants={variants} className="flex flex-col gap-1">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd>{children}</dd>
    </motion.div>
  );
}

function Sep() {
  return <span className="text-fg-muted/60">×</span>;
}

function AnalysisSkeleton() {
  return (
    <div className="flex flex-col gap-5 p-4" role="status" aria-label="Analysing model">
      {["w-28", "w-52", "w-40"].map((w) => (
        <div key={w} className="flex flex-col gap-1.5">
          <Skeleton className="h-3 w-12" />
          <Skeleton className={cx("h-4", w)} />
        </div>
      ))}
      <span className="sr-only">Reading the model…</span>
    </div>
  );
}
