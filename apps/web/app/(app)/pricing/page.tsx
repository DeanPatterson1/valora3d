import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { ActionCostTable } from "@/components/pricing/ActionCostTable";
import { CreditPacks } from "@/components/pricing/CreditPacks";
import { PlanCards } from "@/components/pricing/PlanCards";

export const metadata: Metadata = {
  title: `Plans · ${BRAND.name}`,
};

export default function PricingPage() {
  return (
    // Same frame as the dashboard, so the two page headers sit at the same spot.
    <div className="mx-auto w-full max-w-[1100px] px-4 pb-24 pt-14 sm:px-8 md:pt-8">
      <header className="mb-8 flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">Plans</h1>
        <p className="text-sm text-fg-muted">Credits pay for scenes and renders. Pick a plan or top up as you go.</p>
      </header>

      <PlanCards />

      <section aria-labelledby="packs" className="mt-16 flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <h2 id="packs" className="text-xl font-semibold tracking-tight text-fg">
            Credit packs
          </h2>
          <p className="text-sm text-fg-muted">One-off top-ups on any plan. Credits never expire.</p>
        </div>
        <CreditPacks />
      </section>

      <section aria-labelledby="costs" className="mt-16 flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <h2 id="costs" className="text-xl font-semibold tracking-tight text-fg">
            What things cost
          </h2>
          <p className="text-sm text-fg-muted">Analysis and slider changes are free. You are charged when a scene version is saved.</p>
        </div>
        <ActionCostTable />
      </section>
    </div>
  );
}
