import Image from "next/image";
import { CREDIT_COSTS } from "@/lib/pricing";
import { Container, RevealGroup, RevealItem, SectionHead } from "./Reveal";

type Card = { title: string; line: string; image: string; alt: string };

const CARDS: Card[] = [
  {
    title: "Understands your model",
    line: "Category, parts and real-world scale, read from the file in your browser.",
    image: "/landing/gallery/product-studio-white.jpg",
    alt: "A rangefinder camera model in a white studio",
  },
  {
    title: "Cinematic cameras",
    line: "Slow orbit, push-in, low tracking and handheld walks, all from a sentence.",
    image: "/landing/gallery/car-low-tracking.jpg",
    alt: "A low tracking shot alongside a car on a foggy road",
  },
  {
    title: "Environments and weather",
    line: "Black or white studio, open road, night city; add rain, wet ground and fog.",
    image: "/landing/gallery/car-city-rain.jpg",
    alt: "A car on a rainy city street at night",
  },
  {
    title: "Local or cloud rendering",
    line: `Render on your own GPU for ${CREDIT_COSTS.local_final} credits, or in the cloud from ${CREDIT_COSTS.cloud_final.standard}.`,
    image: "/landing/gallery/car-road-dusk.jpg",
    alt: "A car on an open road at sunset",
  },
];

/** Four glass cards over the dark sheet, each with a still from the viewer. */
export function Capabilities() {
  return (
    <section id="features" aria-labelledby="features-title" className="scroll-mt-24 py-20 md:py-28">
      <Container>
        <SectionHead id="features-title" title="What it can do" lead="Everything below is the prototype's viewer at work. The final frames come from the renderer once it is connected." />
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
