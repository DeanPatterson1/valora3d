import { Container, Reveal, SectionHead } from "./Reveal";

export const FAQ_ITEMS = [
  {
    q: "Is this connected to a renderer?",
    a: "Yes, on your own machine. Render runs Blender and ffmpeg locally and hands you an MP4. Cloud rendering is not connected yet, so that option still shows a designed placeholder.",
  },
  {
    q: "What formats can I add?",
    a: "Single-file .glb is the safest. .gltf works when it has no external files; .fbx and .obj are also read. Files up to 200 MB in the prototype.",
  },
  {
    q: "Local or cloud rendering?",
    a: "Local is built: it uses your own GPU and costs the least in credits. Cloud would queue the job on a hosted GPU at the higher credit price shown beside it, and is still to come.",
  },
  {
    q: "What happens to my files?",
    a: "They stay on your machine. Projects and models live in IndexedDB, and rendering hands the scene to a render server running on the same machine. Nothing is uploaded anywhere.",
  },
] as const;

/** Four native disclosure items; the browser handles toggling and keyboard access. */
export function Faq() {
  return (
    <section aria-labelledby="faq-title" className="py-20 md:py-28">
      <Container className="grid grid-cols-1 gap-10 md:grid-cols-12">
        <Reveal className="md:col-span-4">
          <SectionHead id="faq-title" title="Questions" />
        </Reveal>
        <Reveal className="md:col-span-8">
          <div className="divide-y divide-line border-y border-line">
            {FAQ_ITEMS.map((item) => (
              <details key={item.q} className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-6 py-5 text-base font-medium text-fg marker:content-none focus-visible:focus-ring [&::-webkit-details-marker]:hidden">
                  {item.q}
                  <svg aria-hidden viewBox="0 0 16 16" className="size-4 shrink-0 text-fg-muted transition-transform duration-base ease-standard group-open:rotate-45" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <path d="M8 3v10M3 8h10" />
                  </svg>
                </summary>
                <p className="max-w-[60ch] pb-6 text-base leading-relaxed text-fg-muted">{item.a}</p>
              </details>
            ))}
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
