import Link from "next/link";
import { notFound } from "next/navigation";
import { SignupCta } from "@/components/public/SignupCta";
import { JsonLd } from "@/components/seo/JsonLd";
import { EXAMPLES, EXAMPLES_PROVENANCE, exampleBySlug, exampleVideoSchema, relatedExamples } from "@/lib/examples";
import { publicMetadata } from "@/lib/site";

export const dynamicParams = false;
export function generateStaticParams() {
  return EXAMPLES.map(({ slug }) => ({ slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props) {
  const { slug } = await params;
  const example = exampleBySlug(slug);
  if (!example) notFound();
  const base = publicMetadata(example.title, example.description, `/examples/${example.slug}`);
  // The clip's own poster is the share image.
  const image = { url: example.media.poster, width: example.item.width, height: example.item.height, alt: example.item.caption };
  return { ...base, openGraph: { ...base.openGraph, images: [image] }, twitter: { ...base.twitter, images: [image.url] } };
}

export default async function ExamplePage({ params }: Props) {
  const { slug } = await params;
  const example = exampleBySlug(slug);
  if (!example) notFound();
  const related = relatedExamples(example);
  return (
    <article className="mx-auto max-w-[860px] px-5 py-10 sm:px-8 sm:py-16">
      <nav aria-label="Breadcrumb" className="mb-8 text-sm text-fg-muted">
        <Link href="/examples" className="rounded-sm hover:text-fg focus-visible:focus-ring">← All examples</Link>
      </nav>
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{example.title}</h1>
      <p className="mt-4 text-lg leading-relaxed text-fg-muted">{example.description}</p>

      <figure className="mt-8">
        <div className="relative aspect-[16/10] w-full overflow-hidden rounded-lg border border-line bg-bg-1">
          <video className="h-full w-full object-cover" src={example.media.video} poster={example.media.poster} controls loop muted playsInline preload="none">
            <p className="p-4 text-sm text-fg-muted">This browser cannot play the clip.</p>
          </video>
        </div>
        <figcaption className="mt-3 text-sm text-fg-muted">
          {example.item.caption}
          {example.item.credit && <span className="mt-1 block text-xs text-fg/50">Model: {example.item.credit}</span>}
        </figcaption>
      </figure>

      <dl className="mt-8 grid grid-cols-1 gap-4 rounded-lg border border-line bg-bg-1 p-5 text-sm sm:grid-cols-3">
        <div><dt className="text-fg-muted">World</dt><dd className="mt-1">{example.worldLabel}</dd></div>
        <div><dt className="text-fg-muted">Model type</dt><dd className="mt-1">{example.item.model === "car" ? "Car" : "Product"}</dd></div>
        <div><dt className="text-fg-muted">Clip length</dt><dd className="mt-1">{example.durationSeconds} seconds</dd></div>
      </dl>

      <section aria-labelledby="shot-heading" className="mt-10">
        <h2 id="shot-heading" className="text-xl font-semibold tracking-tight">The shot</h2>
        <p className="mt-3 text-base leading-7 text-fg-muted">{example.shotIdea}</p>
        <p className="mt-4 text-sm text-fg-muted">Prompt used:</p>
        <blockquote className="mt-2 rounded-lg border border-line bg-bg-1 p-4 text-sm leading-relaxed">{example.item.prompt}</blockquote>
      </section>

      <div className="mt-10 space-y-9">
        {example.sections.map((section) => (
          <section key={section.heading}>
            <h2 className="text-xl font-semibold tracking-tight">{section.heading}</h2>
            {section.paragraphs.map((text) => <p key={text} className="mt-3 text-base leading-7 text-fg-muted">{text}</p>)}
          </section>
        ))}
        <section>
          <h2 className="text-xl font-semibold tracking-tight">Adapt it to your model</h2>
          <ul className="mt-4 list-disc space-y-3 pl-6 text-base leading-7 text-fg-muted">
            {example.adapt.map((tip) => <li key={tip} className="pl-1">{tip}</li>)}
          </ul>
        </section>
      </div>

      <p className="mt-10 text-xs leading-relaxed text-fg-muted">{EXAMPLES_PROVENANCE}</p>

      <SignupCta
        title="Make a shot like this"
        lead="Upload your .glb, pick a world and describe the camera move. Start with a preview, then change one thing at a time."
        secondary={{ href: "/help/writing-a-good-shot-prompt", label: "Prompt writing tips" }}
      />

      <section aria-labelledby="related-heading" className="mt-14 border-t border-line pt-8">
        <h2 id="related-heading" className="text-lg font-semibold tracking-tight">More examples</h2>
        <ul className="mt-4 flex flex-col gap-3">
          {related.map((r) => (
            <li key={r.slug}>
              <Link href={`/examples/${r.slug}`} className="rounded-sm text-sm underline underline-offset-4 focus-visible:focus-ring">{r.title}</Link>
              <span className="ml-2 text-xs text-fg-muted">{r.worldLabel}</span>
            </li>
          ))}
        </ul>
      </section>
      <JsonLd data={exampleVideoSchema(example)} />
    </article>
  );
}
