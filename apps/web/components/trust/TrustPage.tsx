import type { ReactNode } from "react";

export function TrustPage({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-5 py-12 sm:px-8 sm:py-16">
      <aside aria-label="Draft notice" className="mb-8 rounded-lg border border-line bg-bg-2 px-5 py-4 text-sm">
        <p className="font-medium">Draft — pending owner review</p>
        <p className="mt-1 text-fg-muted">Effective date: [To be confirmed at public launch]</p>
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

export function LegalEmail() {
  return <a href="mailto:legal@valora3d.com">legal@valora3d.com</a>;
}

/*
 * TODO(owner): add a virtual-mailbox postal address before public launch. Until then every legal page says the
 * address is available on request, and the bracketed token below keeps app/legal-placeholders.test.ts red once
 * LEGAL_PLACEHOLDERS_ALLOWED is false, so a public launch stays blocked.
 */
export function PostalAddressNotice() {
  return (
    <>
      Postal address for legal notices is provided on request to <LegalEmail />. [Owner to add virtual-mailbox address before public launch]
    </>
  );
}
