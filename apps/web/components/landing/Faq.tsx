import { Container, Reveal, SectionHead } from "./Reveal";

export const FAQ_ITEMS = [
  { q: "How does rendering work?", a: "Upload a .glb model, describe the shot and review the scene in your browser. Final renders and videos are processed on cloud GPUs supplied by RunPod. Render time depends on the model, settings and queue." },
  { q: "What formats can I upload?", a: "At launch, uploads support .glb only, up to 200 MB per file. Export a single file with its textures included. You must own or license the model and its materials for the use you intend." },
  { q: "Where are my files and account stored?", a: "Supabase provides accounts and database storage. Cloudflare hosts the site and stores uploads and outputs in R2. RunPod processes rendering jobs, and Resend delivers service email. File retention depends on your plan; download work you want to keep." },
  { q: "Who owns my renders?", a: "You own your renders and keep ownership of your uploaded models. You are responsible for source-model licences and any third-party rights in the output." },
  { q: "How do payments work?", a: "Paddle is the merchant of record and seller of record for paid orders. It handles payments, applicable transaction taxes and payment refunds. Plans and credit costs are listed on the pricing page; review renewal details at checkout." },
] as const;

/** Native disclosure items; the browser handles toggling and keyboard access. */
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
