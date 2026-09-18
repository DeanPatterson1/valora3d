import { cx } from "./cx";

export type BadgeTone = "neutral" | "success" | "warning";

const TONE: Record<BadgeTone, string> = {
  neutral: "bg-bg-3 text-fg-muted",
  success: "bg-bg-3 text-success",
  warning: "bg-bg-3 text-fg",
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
        "inline-flex h-6 items-center rounded-full px-2.5 text-xs font-medium whitespace-nowrap",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
