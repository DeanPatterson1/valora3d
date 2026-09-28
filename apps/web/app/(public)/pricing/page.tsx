import { publicMetadata } from "@/lib/site";
import { ActionCostTable } from "@/components/pricing/ActionCostTable";
import { CreditPacks } from "@/components/pricing/CreditPacks";
import { PlanCards } from "@/components/pricing/PlanCards";

export const metadata = publicMetadata("Plans", "Compare Valora3D plans, rendering credits and storage retention for your 3D projects.", "/pricing");

export default function PricingPage() {
  return (
    // Same frame as the dashboard, so the two page headers sit at the same spot.
    <div className="mx-auto w-full max-w-[1100px] px-5 pb-16 pt-16 sm:px-8 md:pt-12">
      <header className="mb-8 flex flex-col gap-3 border-b border-line pb-6">
        <h1 className="text-3xl font-semibold tracking-[-0.04em] text-fg sm:text-4xl">Plans</h1>
        <p className="text-sm text-fg-muted">Credits pay for scenes and renders. Pick a plan or top up as you go.</p>
      </header>

      <aside aria-label="Billing and storage" className="mb-6 rounded-lg border border-line bg-bg-1 px-5 py-4 text-sm leading-relaxed text-fg-muted">
        Paddle is the merchant of record and seller of record for paid orders. Storage retention depends on your plan; download your renders before it expires. Review the total and renewal terms at checkout.
      </aside>

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
