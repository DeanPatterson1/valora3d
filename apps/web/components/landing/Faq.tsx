import { Container, Reveal, SectionHead } from "./Reveal";

export const FAQ_ITEMS = [
  {
    q: "Is this connected to a renderer?",
    a: "No. This is a prototype: the viewer, the director and the credit ledger are real, but no final frames are produced yet. Pressing Render shows the designed “not connected” state.",
  },
  {
    q: "What formats can I add?",
    a: "Single-file .glb is the safest. .gltf works when it has no external files; .fbx and .obj are also read. Files up to 200 MB in the prototype.",
  },
  {
    q: "Local or cloud rendering?",
    a: "Both are planned. Local uses your own GPU and costs the least in credits; cloud queues the job on a hosted GPU at a higher credit price shown beside it.",
  },
  {
    q: "What happens to my files?",
    a: "They stay in your browser. Projects and models are stored in IndexedDB on your machine; nothing is uploaded in the prototype.",
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
