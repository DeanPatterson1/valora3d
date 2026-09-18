import Image from "next/image";
import { cx } from "@/components/ui";
import { Container, Reveal, SectionHead } from "./Reveal";

type Step = { title: string; body: string; image: string; alt: string };

const STEPS: Step[] = [
  {
    title: "Add a model",
    body: "Drop a .glb, .gltf, .fbx or .obj, or start from a sample. It is read in your browser: category, parts and real-world scale, nothing uploaded.",
    image: "/landing/app/01-upload.jpg",
    alt: "The studio's upload card with sample models",
  },
  {
    title: "Describe the shot",
    body: "Write it the way you would brief a filmmaker: “rainy night, handheld, walking toward the car”. The director turns that into a camera path, lighting and weather.",
    image: "/landing/app/02-planning.jpg",
    alt: "The planning sequence running after a prompt",
  },
  {
    title: "Review, then render",
    body: "Scrub the preview, adjust lens, height and exposure, and pick local or cloud output. The renderer itself is the next piece to connect.",
    image: "/landing/app/03-scene.jpg",
    alt: "A planned scene with the scene details drawer open",
  },
];

/** Three steps with real studio screenshots in glass frames; the step number sticks on desktop. */
export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-title" className="scroll-mt-24 py-20 md:py-28">
      <Container>
        <Reveal>
          <SectionHead id="how-title" title="How it works" lead="Three screens, in the order you meet them." />
        </Reveal>
        <ol className="mt-12 flex flex-col gap-16 md:mt-16 md:gap-24">
          {STEPS.map((s, i) => (
            <li key={s.title} className="grid grid-cols-1 gap-6 md:grid-cols-[72px_1fr] md:gap-10">
              <div className="md:sticky md:top-28 md:self-start">
                <span aria-hidden className="font-display text-[clamp(2.5rem,5vw,4rem)] font-bold leading-none tracking-[-0.04em] text-fg/25">
                  {i + 1}
                </span>
              </div>
              <Reveal className={cx("grid grid-cols-1 items-center gap-6 md:grid-cols-12 md:gap-10", i % 2 === 1 && "md:[&>*:first-child]:order-2")}>
                <div className="glass overflow-hidden p-2 md:col-span-8">
                  <div className="relative aspect-[16/10] w-full overflow-hidden rounded-[12px] bg-bg-1">
                    <Image src={s.image} alt={s.alt} fill sizes="(min-width: 768px) 720px, 100vw" className="object-cover object-top" />
                  </div>
                </div>
                <div className="flex flex-col gap-3 md:col-span-4">
                  <h3 className="text-xl font-semibold tracking-tight text-fg md:text-2xl">
                    <span className="sr-only">Step {i + 1}: </span>
                    {s.title}
                  </h3>
                  <p className="text-base leading-relaxed text-fg-muted">{s.body}</p>
                </div>
              </Reveal>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}
