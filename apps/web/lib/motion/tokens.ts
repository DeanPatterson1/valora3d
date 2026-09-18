/** Durations in seconds (motion uses seconds). Mirrored as --duration-* in globals.css. */
export const DUR = { fast: 0.15, base: 0.25, slow: 0.45 } as const;

/** Cubic-bezier easings. Mirrored as --ease-* in globals.css. */
export const EASE = {
  standard: [0.2, 0, 0, 1],
  emphasized: [0.3, 0, 0, 1],
} as const;

export const SPRING = {
  gentle: { type: "spring", stiffness: 260, damping: 30 },
  snappy: { type: "spring", stiffness: 500, damping: 35 },
} as const;
