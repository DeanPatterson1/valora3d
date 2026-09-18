import { BRAND } from "@/lib/brand";

export function Footer() {
  return (
    <footer className="mx-auto flex w-full max-w-[960px] items-center justify-between gap-3 border-t border-line px-4 py-5 text-xs text-fg-muted sm:px-6">
      <span className="font-medium text-fg">{BRAND.name}</span>
      <span>Prototype — no renders are produced yet.</span>
    </footer>
  );
}
