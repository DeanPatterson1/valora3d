/**
 * Token values shown on /dev/tokens. globals.css is the source of truth;
 * tokens.test.ts fails if these drift from it.
 */
export const SURFACES = [
  { name: "bg-0", hex: "#0f0e0c", role: "Page, viewer backdrop" },
  { name: "bg-1", hex: "#171512", role: "Rails, docks, cards" },
  { name: "bg-2", hex: "#201d19", role: "Inputs, dialogs, toasts" },
  { name: "bg-3", hex: "#2b2723", role: "Hover, raised chips, tracks" },
] as const;

export const TEXT = [
  { name: "fg", hex: "#f4f0e9", role: "Body and headings" },
  { name: "fg-muted", hex: "#ada599", role: "Secondary text, labels" },
] as const;

export const COLOURS = [
  { name: "accent", hex: "#f2a83b", role: "Key light: primary action, selection, focus" },
  { name: "accent-fg", hex: "#1a1206", role: "Text on accent" },
  { name: "danger", hex: "#f0644e", role: "Destructive, errors" },
  { name: "success", hex: "#8acb7a", role: "Done, ready" },
  { name: "line", hex: "#36312b", role: "Hairlines and borders" },
] as const;

export const RADII = [
  { name: "sm", px: 4, role: "Chips (square), badges, small buttons" },
  { name: "md", px: 8, role: "Buttons, inputs, toasts" },
  { name: "lg", px: 14, role: "Cards, dialogs, viewer frame" },
] as const;

export const TYPE_SCALE = [
  { name: "4xl", rem: 2.75, lh: 1.05 },
  { name: "3xl", rem: 2, lh: 1.15 },
  { name: "2xl", rem: 1.5, lh: 1.25 },
  { name: "xl", rem: 1.25, lh: 1.4 },
  { name: "lg", rem: 1.125, lh: 1.55 },
  { name: "base", rem: 1, lh: 1.6 },
  { name: "sm", rem: 0.875, lh: 1.5 },
  { name: "xs", rem: 0.75, lh: 1.5 },
] as const;
