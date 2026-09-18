import { cx } from "./cx";

/** Shimmering placeholder. Size it with className (e.g. `h-4 w-40`). */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cx(
        "animate-shimmer rounded-sm bg-[linear-gradient(90deg,var(--color-bg-2)_25%,var(--color-bg-3)_50%,var(--color-bg-2)_75%)] bg-[length:200%_100%] motion-reduce:animate-none motion-reduce:bg-bg-2",
        className,
      )}
    />
  );
}
