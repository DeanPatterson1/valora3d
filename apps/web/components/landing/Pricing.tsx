import Link from "next/link";
import { PlanCards } from "@/components/pricing/PlanCards";
import { Container, Reveal, SectionHead } from "./Reveal";

/** The three plans, reused from /pricing; only the wrapper is landing-styled. */
export function Pricing() {
  return (
    <section id="pricing" aria-labelledby="pricing-title" className="scroll-mt-24 py-20 md:py-28">
      <Container>
        <Reveal className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <SectionHead id="pricing-title" title="Pricing" lead="Credits pay for scene generation and renders. Local renders cost a fraction of cloud ones." />
          <Link href="/pricing" className="inline-flex h-10 shrink-0 items-center rounded-full border border-line px-4 text-sm text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring">
            See full pricing
          </Link>
        </Reveal>
        <Reveal className="mt-12">
          <PlanCards />
        </Reveal>
      </Container>
    </section>
  );
}
