"use client";

import { useState } from "react";
import { CREDIT_COSTS } from "@/lib/pricing";
import { cx } from "@/components/ui";

type Row = { label: string; credits: number; group?: "local" | "cloud" };

/** Rows in the order a user meets them; local final sits directly above the cloud tiers. */
export const COST_ROWS: Row[] = [
  { label: "Model analysis", credits: CREDIT_COSTS.model_analysis },
  { label: "Scene generation", credits: CREDIT_COSTS.scene_generation },
  { label: "Prompt edit", credits: CREDIT_COSTS.prompt_edit },
  { label: "Slider or output-setting change", credits: CREDIT_COSTS.slider_change },
  { label: "Preview render", credits: CREDIT_COSTS.preview_render },
  { label: "Local final render", credits: CREDIT_COSTS.local_final, group: "local" },
  { label: "Cloud final render, standard", credits: CREDIT_COSTS.cloud_final.standard, group: "cloud" },
  { label: "Cloud final render, high", credits: CREDIT_COSTS.cloud_final.high, group: "cloud" },
  { label: "Cloud final render, ultra", credits: CREDIT_COSTS.cloud_final.ultra, group: "cloud" },
  { label: "Cloud final render, 4K", credits: CREDIT_COSTS.cloud_final["4k"], group: "cloud" },
];

/** How many times cheaper a local final render is than a standard cloud one. */
export const LOCAL_VS_CLOUD = CREDIT_COSTS.cloud_final.standard / CREDIT_COSTS.local_final;

function formatRatio(r: number): string {
  return Number.isInteger(r) ? String(r) : r.toFixed(1);
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 16 16"
      className={cx("size-4 transition-transform duration-fast ease-standard", open && "rotate-180")}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 6l4 4 4-4" />
    </svg>
  );
}

export function ActionCostTable() {
  const [open, setOpen] = useState(false);
  const id = "action-costs";

  return (
    <div className="flex flex-col gap-4">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex h-9 w-fit cursor-pointer items-center gap-2 rounded-full border border-line px-4 text-sm text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring"
      >
        {open ? "Hide costs" : "See all costs"}
        <ChevronIcon open={open} />
      </button>

      {open && (
        <div id={id} className="flex flex-col gap-4">
          <dl className="rounded-lg border border-line bg-bg-2">
            {COST_ROWS.map((row, i) => (
              <div
                key={row.label}
                data-group={row.group}
                className={cx(
                  "flex items-baseline justify-between gap-4 px-5 py-3 text-sm",
                  i > 0 && "border-t border-line",
                  row.group === "local" && "text-fg",
                )}
              >
                <dt className={row.group === "local" ? "font-medium text-fg" : "text-fg"}>{row.label}</dt>
                <dd className={cx("tabular", row.credits === 0 ? "text-fg-muted" : "text-fg")}>
                  {row.credits === 0 ? "Free" : `${row.credits} ${row.credits === 1 ? "credit" : "credits"}`}
                </dd>
              </div>
            ))}
          </dl>
          <p className="text-sm text-fg-muted">
            Local rendering is {formatRatio(LOCAL_VS_CLOUD)}× cheaper than cloud standard. Preview, local and
            cloud prices are shown for reference; the renderer is not connected in this prototype.
          </p>
        </div>
      )}
    </div>
  );
}
