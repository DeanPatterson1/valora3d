"use client";

import { CREDIT_COSTS } from "@/lib/pricing";
import { Item, Section } from "./Section";

const OPTIONS = [
  {
    title: "Local render",
    credits: CREDIT_COSTS.local_final,
    line: "Uses your own GPU. Cheapest way to a final.",
  },
  {
    title: "Cloud render",
    credits: CREDIT_COSTS.cloud_final.standard,
    line: "No hardware needed. Standard quality, higher tiers available.",
  },
] as const;

export function LocalVsCloud() {
  return (
    <Section aria-label="Local or cloud">
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {OPTIONS.map((o) => (
          <Item key={o.title} role="listitem" className="flex flex-col gap-1 rounded-md border border-line bg-bg-1 p-5">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-base font-semibold tracking-tight text-fg">{o.title}</h2>
              <span className="text-sm text-fg-muted tabular">{o.credits} credits</span>
            </div>
            <p className="text-sm text-fg-muted">{o.line}</p>
          </Item>
        ))}
      </ul>
      <Item>
        <p className="text-center text-xs text-fg-muted">Renderer not connected in this prototype.</p>
      </Item>
    </Section>
  );
}
