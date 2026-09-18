"use client";

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
 * Right-panel "Analysis" tab (spec 6.2): what the model was read as. Fields reveal one
 * by one after the labour sequence so the reading feels earned, not dumped.
 */
export function AnalysisPanel() {
  const liveAnalysis = useStudioStore((s) => s.analysis);
  const stats = useStudioStore((s) => s.stats);
  const busy = useStudioStore((s) => s.busy);
  const { labouring, frozenAnalysis } = useLabour();
  const rm = useReducedMotion() ?? false;

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
    <motion.dl
      variants={list}
      initial="hidden"
      animate="visible"
      className="flex flex-col gap-5 p-4"
      aria-label="Model analysis"
    >
      <Row variants={item} label="Read as">
        <div className="flex items-center gap-2">
          <span data-testid="analysis-category" className="inline-flex">
            <Badge tone={analysis.category === "car" ? "accent" : "neutral"}>{analysis.category}</Badge>
          </span>
          <span className="font-mono tabular text-xs text-fg-muted">{confidence}% sure</span>
        </div>
      </Row>

      <Row variants={item} label="Size">
        <div className="font-mono tabular text-sm text-fg">
          {metres(l)} <Sep /> {metres(w)} <Sep /> {metres(h)} <span className="text-fg-muted">m</span>
        </div>
        <div className="mt-0.5 text-xs text-fg-muted">
          L × W × H, {UNIT_COPY[analysis.unitGuess]}
        </div>
      </Row>

      <Row variants={item} label="Geometry">
        {stats ? (
          <div className="font-mono tabular text-sm text-fg">
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
              <li key={role} className="flex items-baseline justify-between gap-3 text-sm">
                <span className="text-fg">{humanise(role)}</span>
                <span className="min-w-0 truncate font-mono text-xs text-fg-muted" title={name}>
                  {name}
                </span>
              </li>
            ))}
          </ul>
        )}
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

      <Row variants={item} label="Rig">
        <div className={cx("text-sm", analysis.rigged ? "text-fg" : "text-fg-muted")}>
          {analysis.rigged ? "Rigged" : "No skeleton — static only"}
        </div>
      </Row>
    </motion.dl>
  );
}

function Row({ label, variants, children }: { label: string; variants: Variants; children: React.ReactNode }) {
  return (
    <motion.div variants={variants} className="flex flex-col gap-1">
      <dt className="text-xs font-medium uppercase tracking-wide text-fg-muted">{label}</dt>
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
      {["w-28", "w-40", "w-36", "w-52", "w-32", "w-24"].map((w) => (
        <div key={w} className="flex flex-col gap-1.5">
          <Skeleton className="h-3 w-12" />
          <Skeleton className={cx("h-4", w)} />
        </div>
      ))}
      <span className="sr-only">Reading the model…</span>
    </div>
  );
}
