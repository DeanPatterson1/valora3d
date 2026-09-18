import { cx } from "@/components/ui";

/** Small stable hash so the same seed always gets the same look. */
function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Three monochrome tones; the seed picks one for the life of the account. */
const TONES = ["bg-bg-3 text-fg", "bg-fg-muted text-bg-0", "bg-fg text-bg-0"] as const;

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

export type AvatarProps = {
  name: string;
  seed: string;
  size?: "sm" | "md" | "lg";
  className?: string;
};

const SIZE = {
  sm: "size-7 text-[11px]",
  md: "size-9 text-xs",
  lg: "size-16 text-xl",
} as const;

/** Deterministic monochrome initials avatar. No images, no colour. */
export function Avatar({ name, seed, size = "md", className }: AvatarProps) {
  const tone = TONES[hash(seed) % TONES.length];
  return (
    <span
      aria-hidden
      data-tone={hash(seed) % TONES.length}
      className={cx(
        "inline-flex shrink-0 select-none items-center justify-center rounded-full font-semibold tracking-tight",
        SIZE[size],
        tone,
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}
