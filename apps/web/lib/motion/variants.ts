import type { Variants } from "motion/react";
import { DUR, EASE } from "./tokens";

/** Opacity 0→1 with a short rise. Use with `initial="hidden" animate="visible"`. */
export const fadeRise: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.base, ease: EASE.standard },
  },
  exit: {
    opacity: 0,
    y: 12,
    transition: { duration: DUR.fast, ease: EASE.standard },
  },
};

/** Container that staggers its children's `hidden`→`visible` transitions. */
export const staggerList: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05 } },
};

/** Press feedback. Spread onto a motion element: `{...scalePress}`. */
export const scalePress = {
  whileTap: { scale: 0.98 },
  transition: { duration: DUR.fast, ease: EASE.standard },
} as const;

const TRANSFORM_KEYS = new Set([
  "x",
  "y",
  "z",
  "scale",
  "scaleX",
  "scaleY",
  "rotate",
  "rotateX",
  "rotateY",
  "rotateZ",
  "skew",
  "skewX",
  "skewY",
  "translateX",
  "translateY",
  "originX",
  "originY",
]);

/**
 * Returns a copy of `variants` with every transform key removed, so under
 * `prefers-reduced-motion` only opacity (and transitions) remain.
 * Call-site pattern:
 *   const rm = useReducedMotion();
 *   <motion.div variants={rm ? reduced(fadeRise) : fadeRise} />
 */
export function reduced(variants: Variants): Variants {
  const out: Variants = {};
  for (const [name, state] of Object.entries(variants)) {
    if (typeof state === "function") {
      out[name] = state;
      continue;
    }
    const copy: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(state)) {
      if (!TRANSFORM_KEYS.has(key)) copy[key] = value;
    }
    out[name] = copy as (typeof variants)[string];
  }
  return out;
}
