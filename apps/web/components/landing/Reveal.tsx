"use client";

import { motion, type Variants } from "motion/react";
import { EASE } from "@/lib/motion/tokens";
import { cx } from "@/components/ui";

/** Scroll reveal for landing sections: fade + 30px rise over 0.7s, once, opacity only under reduced motion. */
export const REVEAL_DURATION = 0.7;

/**
 * The one set of variants, for every visitor. There is deliberately no reduced-motion
 * variant to pick between: `initial="hidden"` is what motion renders into the SSR `style`,
 * and `useReducedMotion()` returns `null` on the server but the real preference on the
 * first client render, so choosing the variant in JS would hand React a `transform` the
 * server never wrote. `<MotionConfig reducedMotion="user">` in `app/layout.tsx` snaps `y`
 * to its target instead, which leaves the fade and drops the travel.
 */
export const reveal: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: REVEAL_DURATION, ease: EASE.standard } },
};

/** Parent that staggers `RevealItem` children as they enter the viewport. */
export const revealGroup: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

type Props = React.ComponentProps<typeof motion.div> & { children: React.ReactNode; className?: string };

export function Reveal({ children, className, ...rest }: Props) {
  return (
    <motion.div
      variants={reveal}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.2 }}
      className={className}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/** Stagger container: children use `RevealItem`. */
export function RevealGroup({ children, className, ...rest }: Props) {
  return (
    <motion.div variants={revealGroup} initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.15 }} className={className} {...rest}>
      {children}
    </motion.div>
  );
}

export function RevealItem({ children, className, ...rest }: Props) {
  return (
    <motion.div variants={reveal} className={className} {...rest}>
      {children}
    </motion.div>
  );
}

/** Page-width container shared by every landing section. */
export function Container({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cx("mx-auto w-full max-w-[1200px] px-4 sm:px-6 lg:px-10", className)}>{children}</div>;
}

/** Section title and a one-line lead, left-aligned. */
export function SectionHead({ id, title, suffix, lead, className }: { id: string; title: string; suffix?: string; lead?: string; className?: string }) {
  return (
    <div className={cx("flex max-w-[720px] flex-col gap-3", className)}>
      <h2 id={id} className="font-display text-[clamp(2rem,4.5vw,3.5rem)] font-bold leading-[1.02] tracking-[-0.035em] text-fg">
        {title}
        {suffix && " "}
        {suffix && <span className="ml-2 align-middle font-sans text-base font-normal tracking-normal text-fg/50 md:text-lg">{suffix}</span>}
      </h2>
      {lead && <p className="text-base leading-relaxed text-fg-muted md:text-lg">{lead}</p>}
    </div>
  );
}
