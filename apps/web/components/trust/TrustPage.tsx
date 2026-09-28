import type { ReactNode } from "react";

export function TrustPage({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-5 py-12 sm:px-8 sm:py-16">
      <aside aria-label="Draft notice" className="mb-8 rounded-lg border border-line bg-bg-2 px-5 py-4 text-sm">
        <p className="font-medium">Draft — pending owner review</p>
        <p className="mt-1 text-fg-muted">Effective date: [To be confirmed by owner]</p>
      </aside>
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
      <p className="mt-4 text-base leading-relaxed text-fg-muted">{intro}</p>
      <div className="mt-10 space-y-8 text-base leading-relaxed text-fg-muted [&_h2]:mb-3 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-fg [&_p+p]:mt-3 [&_a]:text-fg [&_a]:underline [&_a]:underline-offset-4 [&_a:focus-visible]:outline [&_a:focus-visible]:outline-offset-4 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-5">
        {children}
      </div>
    </article>
  );
}

export function SupportEmail() {
  return <a href="mailto:support@valora3d.com">support@valora3d.com</a>;
}
