"use client";

import { motion, useReducedMotion } from "motion/react";
import { fadeRise, reduced, staggerList } from "@/lib/motion/variants";
import { cx } from "@/components/ui";

type Props = React.ComponentProps<"section"> & { children: React.ReactNode };

/** A landing section that staggers its `<Item>` children in once it scrolls into view. */
export function Section({ className, children, ...rest }: Props) {
  const rm = useReducedMotion() ?? false;
  return (
    <motion.section
      variants={rm ? reduced(staggerList) : staggerList}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.3 }}
      className={cx("mx-auto flex w-full max-w-[960px] flex-col gap-4 px-4 sm:px-6", className)}
      {...(rest as React.ComponentProps<typeof motion.section>)}
    >
      {children}
    </motion.section>
  );
}

export function Item({ className, children, ...rest }: React.ComponentProps<"div"> & { children: React.ReactNode }) {
  const rm = useReducedMotion() ?? false;
  return (
    <motion.div variants={rm ? reduced(fadeRise) : fadeRise} className={className} {...(rest as React.ComponentProps<typeof motion.div>)}>
      {children}
    </motion.div>
  );
}
