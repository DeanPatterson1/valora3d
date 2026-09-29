import Link from "next/link";
import { HELP_FAQS, helpSearchEntries } from "@/lib/help";
import { publicMetadata } from "@/lib/site";
import { JsonLd } from "@/components/seo/JsonLd";
import { HelpSearch } from "./HelpSearch";

export const metadata = publicMetadata("Help center", "Learn how to prepare your model, direct a shot and manage your Valora3D renders.", "/help", { ownImage: true });

export default function HelpPage() {
  const faqSchema = {
    "@context": "https://schema.org", "@type": "FAQPage",
    mainEntity: HELP_FAQS.map(({ question, answer }) => ({
      "@type": "Question", name: question, acceptedAnswer: { "@type": "Answer", text: answer },
    })),
  };
  return (
    <div className="mx-auto max-w-[920px] px-5 py-12 sm:px-8 sm:py-20">
      <p className="mb-3 text-sm text-fg-muted">Valora3D help</p>
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Your next shot starts here.</h1>
      <p className="mt-5 max-w-xl text-base leading-relaxed text-fg-muted">A little guidance, from preparing your first model to saving the finished video.</p>
      <HelpSearch entries={helpSearchEntries()} />
      <section aria-labelledby="faq-heading" className="mt-14 border-t border-line pt-10">
        <h2 id="faq-heading" className="text-2xl font-semibold tracking-tight">Quick answers</h2>
        <div className="mt-5 divide-y divide-line">
          {HELP_FAQS.map(({ question, answer, slug }) => (
            <details key={question} className="py-4">
              <summary className="cursor-pointer rounded-sm py-1 font-medium focus-visible:focus-ring">{question}</summary>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-fg-muted">{answer}</p>
              <Link href={`/help/${slug}`} className="mt-3 inline-block rounded-sm text-sm underline underline-offset-4 focus-visible:focus-ring">Read the guide<span className="sr-only">: {question}</span></Link>
            </details>
          ))}
        </div>
      </section>
      <p className="mt-10 text-sm text-fg-muted">Still need a hand? <Link href="/contact" className="rounded-sm text-fg underline underline-offset-4 focus-visible:focus-ring">Contact support</Link>, or <Link href="/projects?feedback=question" className="rounded-sm text-fg underline underline-offset-4 focus-visible:focus-ring">send feedback</Link> from the app.</p>
      <JsonLd data={faqSchema} />
    </div>
  );
}
