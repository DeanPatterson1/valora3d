import { z } from "zod";

/**
 * The landing gallery manifest (`public/landing/gallery/manifest.json`).
 *
 * `file` is always the still. An item that also carries `preview` and/or `video` is a
 * clip: the tile plays `preview` on hover and the lightbox plays `video`. Still-only
 * items from the first capture pass stay valid, so the manifest can be filled in one
 * entry at a time as real renders land.
 *
 * Paths are relative to the gallery folder unless they start with `/`, which lets an
 * entry point at media that lives elsewhere under `public/`.
 */
export const GalleryItemSchema = z.object({
  /** Still frame. Also the poster when `poster` is absent. */
  file: z.string().min(1),
  /** Poster for the clip; falls back to `file`. */
  poster: z.string().min(1).optional(),
  /** Short, muted loop played on hover. */
  preview: z.string().min(1).optional(),
  /** Full clip played in the lightbox. */
  video: z.string().min(1).optional(),
  caption: z.string().min(1),
  prompt: z.string().min(1),
  model: z.enum(["car", "product"]),
  /** Model author and licence, when the subject is not ours. */
  credit: z.string().min(1).optional(),
  /** Large items span two columns on wide screens. */
  size: z.enum(["wide", "large"]),
  width: z.number().int().positive().default(1600),
  height: z.number().int().positive().default(1000),
  /** True while an entry points at stand-in media. Treated as a normal clip. */
  placeholder: z.boolean().optional(),
});

export const GalleryManifestSchema = z.array(GalleryItemSchema);

export type GalleryItem = z.infer<typeof GalleryItemSchema>;

export function parseGalleryManifest(raw: unknown): GalleryItem[] {
  return GalleryManifestSchema.parse(raw);
}
