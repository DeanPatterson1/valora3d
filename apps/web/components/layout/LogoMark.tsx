import { cx } from "@/components/ui/cx";

/** The Valora3D mark: a ring and a dot. Decorative; the brand name beside it is the accessible text. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className={cx("size-5 shrink-0", className)} fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.75" />
      <circle cx="12" cy="12" r="3.5" fill="currentColor" />
    </svg>
  );
}
