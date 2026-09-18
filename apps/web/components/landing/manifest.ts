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

export const GALLERY_BASE = "/landing/gallery/";

export function parseGalleryManifest(raw: unknown): GalleryItem[] {
  return GalleryManifestSchema.parse(raw);
}

/** Absolute and remote paths pass through; bare file names resolve against the gallery folder. */
export function assetUrl(path: string, base: string = GALLERY_BASE): string {
  return path.startsWith("/") || /^https?:\/\//.test(path) ? path : `${base}${path}`;
}

export function isClip(item: GalleryItem): boolean {
  return Boolean(item.preview ?? item.video);
}

export type ClipMedia = {
  poster: string;
  /** Hover loop. Falls back to the full clip when no short preview exists. */
  preview: string;
  /** Lightbox source. Falls back to the preview when no full clip exists. */
  video: string;
};

/** Resolved media for a clip, or null for a still-only item. */
export function clipMedia(item: GalleryItem, base: string = GALLERY_BASE): ClipMedia | null {
  const preview = item.preview ?? item.video;
  if (!preview) return null;
  return {
    poster: assetUrl(item.poster ?? item.file, base),
    preview: assetUrl(preview, base),
    video: assetUrl(item.video ?? preview, base),
  };
}

/**
 * The hero's own media pair. It is deliberately not derived from this manifest: a gallery
 * entry is encoded for a lightbox and a hover tile, and the hero needs a third size (a
 * full-bleed background loop on a weight budget). `/landing/hero.*` is that third encode.
 */
export type HeroMedia = { poster: string; webm?: string; mp4?: string };
