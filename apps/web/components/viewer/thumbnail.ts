export const THUMBNAIL_WIDTH = 480;

/** Target size for a downscaled thumbnail, preserving aspect and never upscaling. */
export function thumbnailSize(width: number, height: number, targetWidth = THUMBNAIL_WIDTH): { width: number; height: number } {
  if (width <= 0 || height <= 0) return { width: targetWidth, height: Math.round((targetWidth * 9) / 16) };
  const w = Math.min(width, targetWidth);
  return { width: Math.round(w), height: Math.max(1, Math.round((height * w) / width)) };
}

/** Downscale a captured frame to `THUMBNAIL_WIDTH` px wide as JPEG. */
export async function downscaleThumbnail(source: Blob, targetWidth = THUMBNAIL_WIDTH, quality = 0.82): Promise<Blob> {
  const bitmap = await createImageBitmap(source);
  try {
    const { width, height } = thumbnailSize(bitmap.width, bitmap.height, targetWidth);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas unavailable");
    ctx.drawImage(bitmap, 0, 0, width, height);
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("toBlob failed"))), "image/jpeg", quality);
    });
  } finally {
    bitmap.close();
  }
}
