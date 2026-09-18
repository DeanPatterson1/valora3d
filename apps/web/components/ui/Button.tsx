"use client";

import { motion, type HTMLMotionProps } from "motion/react";
import { scalePress } from "@/lib/motion/variants";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = Omit<HTMLMotionProps<"button">, "children"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
  children?: React.ReactNode;
};

const VARIANT: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-accent-fg font-medium hover:brightness-110 disabled:hover:brightness-100",
  secondary:
    "bg-bg-2 text-fg border border-line hover:bg-bg-3 hover:border-fg-muted/60 disabled:hover:bg-bg-2 disabled:hover:border-line",
  ghost:
    "bg-transparent text-fg-muted hover:text-fg hover:bg-bg-2 disabled:hover:text-fg-muted disabled:hover:bg-transparent",
  danger:
    "bg-danger/12 text-danger border border-danger/40 hover:bg-danger/20 disabled:hover:bg-danger/12",
};

const SIZE: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-sm gap-1.5 rounded-sm",
  md: "h-10 px-4 text-sm gap-2 rounded-md",
  lg: "h-12 px-5 text-base gap-2.5 rounded-md",
};

function Spinner() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 16 16"
      className="size-4 animate-spin motion-reduce:animate-none"
      fill="none"
    >
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2" />
      <path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  className,
  disabled,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <motion.button
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      whileTap={isDisabled ? undefined : scalePress.whileTap}
      transition={scalePress.transition}
      className={cx(
        "inline-flex shrink-0 cursor-pointer select-none items-center justify-center whitespace-nowrap transition-colors duration-fast ease-standard focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50",
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Spinner /> : icon ? <span className="inline-flex size-4 items-center justify-center [&>svg]:size-4">{icon}</span> : null}
      {children}
    </motion.button>
  );
}
