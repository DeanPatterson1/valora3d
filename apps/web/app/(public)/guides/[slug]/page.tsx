import Link from "next/link";
import { notFound } from "next/navigation";
import { SignupCta } from "@/components/public/SignupCta";
import { JsonLd } from "@/components/seo/JsonLd";
import { GUIDES, GUIDES_CHECKED_ON, guideBySlug } from "@/lib/guides";
import { publicMetadata, SITE_URL } from "@/lib/site";

export const dynamicParams = false;
export function generateStaticParams() {
  return GUIDES.map(({ slug }) => ({ slug }));
}

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props) {
  const { slug } = await params;
  const guide = guideBySlug(slug);
  if (!guide) notFound();
  return publicMetadata(guide.title, guide.summary, `/guides/${guide.slug}`);
}

export default async function GuidePage({ params }: Props) {
  const { slug } = await params;
  const guide = guideBySlug(slug);
  if (!guide) notFound();
  const schema = {
    "@context": "https://schema.org",
    "@type": "TechArticle",
    headline: guide.title,
    description: guide.summary,
    url: `${SITE_URL}/guides/${guide.slug}`,
    dateModified: GUIDES_CHECKED_ON,
    about: { "@type": "SoftwareApplication", name: guide.app },
    citation: guide.sources.map((s) => s.url),
    publisher: { "@id": `${SITE_URL}/#organization` },
  };
  const others = GUIDES.filter((g) => g.slug !== guide.slug);
  return (
    <article className="mx-auto max-w-[800px] px-5 py-10 sm:px-8 sm:py-16">
      <nav aria-label="Breadcrumb" className="mb-8 text-sm text-fg-muted">
        <Link href="/guides" className="rounded-sm hover:text-fg focus-visible:focus-ring">← All export guides</Link>
      </nav>
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{guide.title}</h1>
      <p className="mt-4 text-lg leading-relaxed text-fg-muted">{guide.summary}</p>
      <p className="mt-4 text-sm text-fg-muted">Applies to: {guide.appliesTo}</p>

      <section aria-labelledby="steps-heading" className="mt-10">
        <h2 id="steps-heading" className="text-xl font-semibold tracking-tight">Steps</h2>
        <ol className="mt-4 list-decimal space-y-3 pl-6 text-base leading-7 text-fg-muted">
          {guide.steps.map((step) => <li key={step} className="pl-1">{step}</li>)}
        </ol>
      </section>

      <section aria-labelledby="settings-heading" className="mt-10">
        <h2 id="settings-heading" className="text-xl font-semibold tracking-tight">Settings to check</h2>
        <dl className="mt-4 divide-y divide-line rounded-lg border border-line bg-bg-1">
          {guide.settings.map((s) => (
            <div key={s.label} className="flex flex-col gap-1 p-4 sm:flex-row sm:gap-6">
              <dt className="shrink-0 font-medium sm:w-56">{s.label}</dt>
              <dd className="text-sm leading-relaxed text-fg-muted">{s.advice}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="pitfalls-heading" className="mt-10">
        <h2 id="pitfalls-heading" className="text-xl font-semibold tracking-tight">{guide.app} pitfalls</h2>
        <ul className="mt-4 list-disc space-y-3 pl-6 text-base leading-7 text-fg-muted">
          {guide.pitfalls.map((p) => <li key={p} className="pl-1">{p}</li>)}
        </ul>
      </section>

      <section aria-labelledby="sources-heading" className="mt-10 border-t border-line pt-8">
        <h2 id="sources-heading" className="text-lg font-semibold tracking-tight">Sources</h2>
        <p className="mt-2 text-sm text-fg-muted">{guide.vendor}&apos;s official documentation, checked on {GUIDES_CHECKED_ON}. If your version&apos;s menus differ, follow the documentation for your version.</p>
        <ul className="mt-3 flex flex-col gap-2 text-sm">
          {guide.sources.map((s) => (
            <li key={s.url}><a href={s.url} rel="noopener noreferrer" className="break-words rounded-sm underline underline-offset-4 focus-visible:focus-ring">{s.label}</a></li>
          ))}
        </ul>
      </section>

      <SignupCta
        title="Check it, then render it"
        lead="Run the exported file through the free checker, then upload it to Valora3D and describe the shot in a sentence."
        secondary={{ href: "/tools/glb-checker", label: "Check your .glb" }}
      />

      <nav aria-label="Other export guides" className="mt-12 border-t border-line pt-6 text-sm">
        <h2 className="font-medium">Other apps</h2>
        <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
          {others.map((g) => <li key={g.slug}><Link href={`/guides/${g.slug}`} className="rounded-sm text-fg-muted underline underline-offset-4 hover:text-fg focus-visible:focus-ring">{g.app}</Link></li>)}
        </ul>
      </nav>
      <JsonLd data={schema} />
    </article>
  );
}
