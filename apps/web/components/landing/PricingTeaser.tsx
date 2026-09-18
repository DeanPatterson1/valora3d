"use client";

import Link from "next/link";
import { PLANS } from "@/lib/pricing";
import { cx } from "@/components/ui";
import { Item, Section } from "./Section";

export function PricingTeaser() {
  return (
    <Section aria-label="Plans">
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {PLANS.map((p) => (
          <Item
            key={p.name}
            role="listitem"
            data-plan={p.name}
            className={cx(
              "flex items-baseline justify-between gap-3 rounded-md border p-5",
              p.highlighted ? "border-primary bg-primary text-primary-fg" : "border-line bg-bg-1 text-fg",
            )}
          >
            <span className="text-base font-semibold tracking-tight">{p.name}</span>
            <span className={cx("text-sm tabular", p.highlighted ? "text-primary-fg/70" : "text-fg-muted")}>
              ${p.priceUsd}
              {p.period === "month" ? "/mo" : ""}
            </span>
          </Item>
        ))}
      </ul>
      <Item className="text-center">
        <Link href="/pricing" className="rounded-sm text-sm text-fg-muted underline underline-offset-4 transition-colors duration-fast ease-standard hover:text-fg focus-visible:focus-ring">
          See pricing
        </Link>
      </Item>
    </Section>
  );
}
