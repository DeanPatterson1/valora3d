import Link from "next/link";
import { SiteFooter } from "@/components/layout/SiteFooter";

export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col bg-bg-0 text-fg">
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-5 px-6 py-20">
        <p className="text-sm text-fg-muted">Valora3D · 404</p>
        <h1 className="text-4xl font-semibold tracking-tight">Page not found</h1>
        <p className="text-base leading-relaxed text-fg-muted">This page may have moved, or the address may be incorrect.</p>
        <Link href="/" className="mt-3 inline-flex h-11 w-fit items-center rounded-full bg-primary px-5 text-sm font-medium text-primary-fg focus-visible:focus-ring">Back to home</Link>
      </main>
      <SiteFooter />
    </div>
  );
}
