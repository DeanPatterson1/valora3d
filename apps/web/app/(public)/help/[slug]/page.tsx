import Link from "next/link";
import { notFound } from "next/navigation";
import { HELP_ARTICLES } from "@/lib/help";
import { publicMetadata } from "@/lib/site";

export const dynamicParams = false;
export function generateStaticParams() {
  return HELP_ARTICLES.map(({ slug }) => ({ slug }));
}
type Props = { params: Promise<{ slug: string }> };
export async function generateMetadata({ params }: Props) {
  const { slug } = await params;
  const article = HELP_ARTICLES.find((item) => item.slug === slug);
  if (!article) notFound();
  return publicMetadata(article.title, article.summary, `/help/${article.slug}`);
}

export default async function HelpArticlePage({ params }: Props) {
  const { slug } = await params;
  const article = HELP_ARTICLES.find((item) => item.slug === slug);
  if (!article) notFound();
  return (
    <article className="mx-auto max-w-[800px] px-5 py-10 sm:px-8 sm:py-16">
      <nav aria-label="Breadcrumb" className="mb-8 text-sm text-fg-muted">
        <Link href="/help" className="rounded-sm hover:text-fg focus-visible:focus-ring">← Help centre</Link>
      </nav>
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{article.title}</h1>
      <p className="mt-4 text-lg leading-relaxed text-fg-muted">{article.summary}</p>
      <nav aria-label="On this page" className="my-8 rounded-lg border border-line bg-bg-1 p-5">
        <h2 className="text-sm font-medium">On this page</h2>
        <ul className="mt-3 flex flex-col gap-2">
          {article.sections.map((section) => <li key={section.id}><a href={`#${section.id}`} className="rounded-sm text-sm text-fg-muted underline-offset-4 hover:text-fg hover:underline focus-visible:focus-ring">{section.title}</a></li>)}
        </ul>
      </nav>
      <div className="space-y-9">
        {article.sections.map((section) => (
          <section key={section.id} id={section.id} aria-labelledby={`${section.id}-heading`} className="scroll-mt-8">
            <h2 id={`${section.id}-heading`} className="text-xl font-semibold tracking-tight">{section.title}</h2>
            {section.paragraphs.map((text) => <p key={text} className="mt-3 text-base leading-7 text-fg-muted">{text}</p>)}
            {section.steps && <ol className="mt-4 list-decimal space-y-3 pl-6 text-base leading-7 text-fg-muted">{section.steps.map((step) => <li key={step} className="pl-1">{step}</li>)}</ol>}
            {section.links && <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-3">{section.links.map((link) => <li key={link.href}><Link href={link.href} className="rounded-sm text-sm underline underline-offset-4 focus-visible:focus-ring">{link.label}</Link></li>)}</ul>}
          </section>
        ))}
      </div>
      <div className="mt-12 flex flex-wrap gap-5 border-t border-line pt-6 text-sm">
        <Link href="/help" className="rounded-sm underline underline-offset-4 focus-visible:focus-ring">All help articles</Link>
        <Link href="/contact" className="rounded-sm underline underline-offset-4 focus-visible:focus-ring">Contact support</Link>
      </div>
    </article>
  );
}
