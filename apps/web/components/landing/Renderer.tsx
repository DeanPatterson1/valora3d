import { Container, Reveal, SectionHead } from "./Reveal";

const REALTIME = [
  "Ambient occlusion",
  "Selective bloom on lights and highlights",
  "Film grade and grain",
  "Anti-aliasing",
  "HDRI lighting",
] as const;

/**
 * One calm section about the two render paths. Capability lines plus the clips on this page
 * that actually came off the offline path — every number below is read out of the renders'
 * own `render-stats.json` / `stats.json`, so none of it is invented. Nothing about
 * throughput or queue speed: there is no benchmark.
 */
export function Renderer() {
  return (
    <section aria-labelledby="renderer-title" className="border-y border-line py-20 md:py-28">
      <Container className="grid grid-cols-1 gap-12 md:grid-cols-12 md:gap-10">
        <Reveal className="md:col-span-5">
          <SectionHead
            id="renderer-title"
            title="Real-time preview, offline finals"
            lead="You plan the shot in a real-time 3D preview in your browser. The finished frames take a separate offline path through Blender Cycles."
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
              <li className="py-3 text-base text-fg-muted">Cloud GPU processing at launch</li>
            </ul>
            <p className="text-sm text-fg/50">
              The hero loop and every clip in the gallery came off this path: 1920×1080 at 24 fps, 192 samples a frame, Cycles on a local RTX 5080.
              The rain-courtyard car shots took about 35 seconds a frame, the studio products two to four. These workstation examples illustrate the pipeline; cloud job times depend on your scene and the queue.
            </p>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
