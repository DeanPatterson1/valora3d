import { Container, RevealGroup, RevealItem, SectionHead } from "./Reveal";

export const REVIEWS_LABEL = "Reviews · placeholder";
export const PLACEHOLDER_REVIEW_TEXT = "Sample review — real feedback will appear here.";

/**
 * Placeholders only. No one has reviewed the prototype yet, so these carry no names, no
 * stars and no invented quotes; the section is labelled as a placeholder until real
 * feedback exists.
 */
export const PLACEHOLDER_REVIEWS = [
  { id: "placeholder-1", text: PLACEHOLDER_REVIEW_TEXT },
  { id: "placeholder-2", text: PLACEHOLDER_REVIEW_TEXT },
  { id: "placeholder-3", text: PLACEHOLDER_REVIEW_TEXT },
] as const;

export function Reviews() {
  return (
    <section aria-labelledby="reviews-title" className="py-20 md:py-28">
      <Container>
        <SectionHead id="reviews-title" title="Reviews" suffix="· placeholder" lead="Nothing here is real yet. Reviews will be added when people have used the product." />
        <RevealGroup className="mt-12 grid grid-cols-1 gap-4 md:grid-cols-3" role="list" aria-label="Placeholder reviews">
          {PLACEHOLDER_REVIEWS.map((r) => (
            <RevealItem key={r.id} role="listitem" className="glass flex min-h-[160px] flex-col justify-between gap-6 p-6">
              <p className="text-base leading-relaxed text-fg-muted">{r.text}</p>
              <span className="text-xs text-fg/40">Placeholder</span>
            </RevealItem>
          ))}
        </RevealGroup>
      </Container>
    </section>
  );
}
