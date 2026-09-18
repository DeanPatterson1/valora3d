import { Container, Reveal, SectionHead } from "./Reveal";

const REALTIME = [
  "Ambient occlusion",
  "Selective bloom on lights and highlights",
  "Film grade and grain",
  "Anti-aliasing",
  "HDRI lighting",
] as const;

/** One calm section about the shared renderer. Generic capability lines only, no benchmarks. */
export function Renderer() {
  return (
    <section aria-labelledby="renderer-title" className="border-y border-line py-20 md:py-28">
      <Container className="grid grid-cols-1 gap-12 md:grid-cols-12 md:gap-10">
        <Reveal className="md:col-span-5">
          <SectionHead
            id="renderer-title"
            title="Same renderer as ModVision"
            lead="The real-time viewer is built on three.js and shared with ModVision, our car configurator. Final frames take an offline path."
          />
        </Reveal>
        <Reveal className="grid grid-cols-1 gap-10 sm:grid-cols-2 md:col-span-7 md:pt-2">
          <div className="flex flex-col gap-4">
            <h3 className="text-sm font-medium text-fg">Real-time, in the browser</h3>
            <ul className="flex flex-col divide-y divide-line border-y border-line">
              {REALTIME.map((line) => (
                <li key={line} className="py-3 text-base text-fg-muted">
                  {line}
                </li>
              ))}
            </ul>
          </div>
          <div className="flex flex-col gap-4">
            <h3 className="text-sm font-medium text-fg">Final frames, offline</h3>
            <ul className="flex flex-col divide-y divide-line border-y border-line">
              <li className="py-3 text-base text-fg-muted">Blender Cycles beauty renders</li>
              <li className="py-3 text-base text-fg-muted">Same scene plan, same camera path</li>
              <li className="py-3 text-base text-fg-muted">Local GPU or cloud queue</li>
            </ul>
            <p className="text-sm text-fg/50">Not connected in this prototype.</p>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
