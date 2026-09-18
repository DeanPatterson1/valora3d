/**
 * Token values shown on /dev/tokens. globals.css is the source of truth;
 * tokens.test.ts fails if these drift from it.
 */
export const SURFACES = [
  { name: "bg-0", hex: "#0d0d0d", role: "Page, main area, viewer backdrop" },
  { name: "bg-1", hex: "#171717", role: "Sidebar" },
  { name: "bg-2", hex: "#212121", role: "Panels, composer, dialogs, inputs" },
  { name: "bg-3", hex: "#2f2f2f", role: "Raised, hover, selected, tracks" },
] as const;

export const TEXT = [
  { name: "fg", hex: "#ececec", role: "Body and headings" },
  { name: "fg-muted", hex: "#b4b4b4", role: "Secondary text, labels" },
] as const;

export const COLOURS = [
  { name: "primary", hex: "#ffffff", role: "Primary action, selection, focus ring" },
  { name: "primary-fg", hex: "#0d0d0d", role: "Text on the primary button" },
  { name: "danger", hex: "#ff6a66", role: "Destructive, errors (text-safe on every surface)" },
  { name: "success", hex: "#10a37f", role: "Done, ready" },
  { name: "line", hex: "#ffffff1a", role: "Hairlines and borders, white at 10%" },
] as const;

export const RADII = [
  { name: "sm", px: 8, role: "Controls, badges, list rows" },
  { name: "md", px: 12, role: "Cards, inputs, toasts" },
  { name: "lg", px: 16, role: "Dialogs, panels, viewer frame" },
] as const;

export const TYPE_SCALE = [
  { name: "4xl", rem: 2.5, lh: 1.1 },
  { name: "3xl", rem: 2, lh: 1.2 },
  { name: "2xl", rem: 1.5, lh: 1.3 },
  { name: "xl", rem: 1.25, lh: 1.4 },
  { name: "lg", rem: 1.125, lh: 1.5 },
  { name: "base", rem: 1, lh: 1.5 },
  { name: "sm", rem: 0.875, lh: 1.5 },
  { name: "xs", rem: 0.75, lh: 1.5 },
] as const;
