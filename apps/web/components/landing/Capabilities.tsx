import Image from "next/image";
import { CREDIT_COSTS } from "@/lib/pricing";
import { WORLDS } from "@/lib/render/worlds";
import { Container, RevealGroup, RevealItem, SectionHead } from "./Reveal";

type Card = { title: string; line: string; image: string; alt: string };

/** "Studio, Rain courtyard, Night street or Golden field": read from WORLDS, so the copy offers only real worlds. */
export function worldsSentence(labels: readonly string[] = WORLDS.map((w) => w.label)): string {
  if (labels.length <= 1) return labels.join("");
  return `${labels.slice(0, -1).join(", ")} or ${labels[labels.length - 1]}`;
}

const CARDS: Card[] = [
  {
    title: "Understands your model",
    line: "Category, parts and real-world scale, read from the file in your browser.",
    image: "/landing/gallery/camera-01-poster.jpg",
    alt: "A vintage rangefinder camera and leather strap on a black cyclorama",
  },
  {
    title: "Cinematic cameras",
    line: "Slow orbit, push-in, low tracking and handheld walks, all from a sentence.",
    image: "/landing/gallery/toycar-poster.jpg",
    alt: "A toy car on a draped red cloth, lit on a black studio floor",
  },
  {
    title: "Worlds to shoot in",
    line: `Pick ${worldsSentence()}, or let the director choose one for your model.`,
    image: "/landing/gallery/gt3rs-rain-close-poster.jpg",
    alt: "A low view along the side of a car on wet tarmac, rain falling among trees",
  },
  {
    title: "Cloud GPU rendering",
    line: `Render in the cloud from ${CREDIT_COSTS.preview_render} credits. No workstation setup needed.`,
    image: "/landing/gallery/mid-century-lounge-chair-poster.jpg",
    alt: "A leather lounge chair lit in a white studio",
  },
];

/** Four glass cards over the dark sheet, each with a frame from one of the rendered clips. */
export function Capabilities() {
  return (
    <section id="features" aria-labelledby="features-title" className="scroll-mt-24 py-20 md:py-28">
      <Container>
        <SectionHead id="features-title" title="What it can do" lead="You describe the shot; the scene, camera and lighting are built for you. Every frame below is off the Cycles renderer." />
        <RevealGroup className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {CARDS.map((c) => (
            <RevealItem key={c.title} className="glass flex flex-col overflow-hidden p-2">
              <div className="relative aspect-[16/10] w-full overflow-hidden rounded-[12px] bg-bg-1">
                <Image src={c.image} alt={c.alt} fill sizes="(min-width: 1280px) 280px, (min-width: 640px) 50vw, 100vw" className="object-cover" />
              </div>
              <div className="flex flex-col gap-1.5 px-3 pb-3 pt-4">
                <h3 className="text-base font-semibold tracking-tight text-fg">{c.title}</h3>
                <p className="text-sm leading-relaxed text-fg-muted">{c.line}</p>
              </div>
            </RevealItem>
          ))}
        </RevealGroup>
      </Container>
    </section>
  );
}
