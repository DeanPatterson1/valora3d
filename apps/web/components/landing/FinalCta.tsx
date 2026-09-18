import Link from "next/link";
import { BRAND } from "@/lib/brand";
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
              <span className="text-sm text-fg/50">Free plan, no card. Renders arrive when the renderer is connected.</span>
            </div>
          </Reveal>
        </Container>
      </section>
      <footer className="border-t border-line py-10">
        <Container className="flex flex-col gap-6 text-sm text-fg-muted md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-fg">{BRAND.name}</span>
            <span className="rounded-full border border-line px-2 py-0.5 text-xs">Prototype</span>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2">
            <a href="#features" className="hover:text-fg focus-visible:focus-ring">Features</a>
            <a href="#gallery" className="hover:text-fg focus-visible:focus-ring">Gallery</a>
            <Link href="/pricing" className="hover:text-fg focus-visible:focus-ring">Pricing</Link>
            <Link href="/projects" className="hover:text-fg focus-visible:focus-ring">Open app</Link>
          </nav>
        </Container>
      </footer>
    </>
  );
}
