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
 * Returns a copy of `variants` with every transform key removed, so only opacity (and
 * transitions) remain.
 *
 * THE DEFAULT IS NOT TO CALL THIS. Reduced motion is settled globally, in two places that
 * cost the markup nothing:
 *
 *   - `<MotionConfig reducedMotion="user">` in app/layout.tsx. It is read once, when the
 *     visual element mounts, and it only makes the transition on transform keys instant —
 *     it never changes the values motion renders, so the server HTML and the first client
 *     render stay identical.
 *   - a `@media (prefers-reduced-motion: reduce)` rule in app/globals.css, keyed off a
 *     `data-*` attribute, for the transforms that snap still needs to reach.
 *
 * Ship one set of variants for everyone:
 *   <motion.div variants={fadeRise} initial="hidden" animate="visible" />
 *
 * Branching them on `useReducedMotion()` is a hydration bug, not a style choice: the hook
 * reads `null` on the server and the real preference on the very first client render, so
 * `variants={rm ? reduced(x) : x}` makes `makeLatestValues` bake a different inline `style`
 * into the server HTML than the first client render produces. See components/landing/Hero.tsx
 * and components/landing/Reveal.tsx for the house pattern.
 *
 * What is left for this function is the one case the global snap gets wrong: an element that
 * NEVER exists in the server HTML — it mounts only after an interaction or after client state
 * appears — AND animates out. `reducedMotion="user"` snaps the `exit` transform to its target
 * at once, which lands while the element is still opaque and reads as a jump. Removing the
 * key avoids that. Before using it, prove the element cannot be server-rendered; if it can,
 * ship one variant set and freeze the transform from app/globals.css instead.
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
