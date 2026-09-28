/**
 * The worlds the site may offer a render in.
 *
 * SOURCE: `py -m engine.site_job worlds` in the Rendering repo (engine/site_job.py -> site_catalog(), which
 * keeps only owner-graded growth blocks; engine/catalog_growth.json). Snapshot taken 2026-09-28 at Rendering
 * `renderer/director` d9944e3. When the owner grades or retires a world, update this list by hand: the worker
 * rejects an id the engine does not offer with INPUT_REJECTED (credits refunded), so a stale entry fails safe.
 * The labels and blurbs are site copy; the engine's own descriptions are longer and operator-facing.
 */
export type WorldDef = { id: string; label: string; blurb: string };

export const WORLDS = [
  { id: "studio_cyc", label: "Studio", blurb: "A clean infinity cove. Product-first, always available." },
  { id: "rain_courtyard", label: "Rain courtyard", blurb: "Overcast park court, damp asphalt, trees. Cinematic outdoors." },
  { id: "night_street", label: "Night street", blurb: "City street at dusk or night, lamps and neon." },
  { id: "golden_field", label: "Golden field", blurb: "Open field under a low sun, soft treeline." },
] as const satisfies readonly WorldDef[];

export type WorldId = (typeof WORLDS)[number]["id"];
export const WORLD_IDS = WORLDS.map((w) => w.id) as [WorldId, ...WorldId[]];

export function worldLabel(id: string | null | undefined): string {
  if (!id) return "Auto";
  return WORLDS.find((w) => w.id === id)?.label ?? id;
}
