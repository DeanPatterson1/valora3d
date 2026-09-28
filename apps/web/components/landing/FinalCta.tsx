import Link from "next/link";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { Container, Reveal } from "./Reveal";

/** Closing action and the footer. */
export function FinalCta() {
  return (
    <>
      <section aria-labelledby="cta-title" className="border-t border-line py-28 md:py-40">
        <Container>
          <Reveal className="flex flex-col items-start gap-8">
            <h2 id="cta-title" className="max-w-[14ch] font-display text-[clamp(2.5rem,7vw,6rem)] font-extrabold leading-[0.95] tracking-[-0.045em] text-fg">
              Your model. One sentence. A shot.
            </h2>
            <div className="flex flex-wrap items-center gap-4">
              <Link
                href="/projects?new=1"
                className="glow inline-flex h-12 items-center rounded-full bg-primary px-6 text-[15px] font-medium text-primary-fg transition-colors duration-fast ease-standard hover:bg-primary/90 focus-visible:focus-ring"
              >
                Start a project
              </Link>
              <span className="text-sm text-fg/50">Start with the free plan. No card needed.</span>
            </div>
          </Reveal>
        </Container>
      </section>
      <SiteFooter />
    </>
  );
}
