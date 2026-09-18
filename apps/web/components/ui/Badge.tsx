import { cx } from "./cx";

export type BadgeTone = "neutral" | "accent" | "success" | "warning";

const TONE: Record<BadgeTone, string> = {
  neutral: "bg-bg-3 text-fg-muted",
  accent: "bg-accent text-accent-fg",
  success: "bg-success/15 text-success",
  warning: "border border-accent/50 text-accent",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cx(
        "inline-flex h-6 items-center rounded-sm px-2 text-xs font-medium whitespace-nowrap",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
