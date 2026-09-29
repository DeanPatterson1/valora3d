import type { Metadata } from "next";

export const SITE_URL = "https://valora3d.com";

/**
 * Who runs Valora3D, as shown in the footer copyright and the Organization structured data.
 * OWNER DECISION: replace with the operator's legal or trading name before launch (the legal pages carry the
 * same pending item). Until then the brand name stands in.
 */
export const OPERATOR_NAME = "Valora3D";

/** The home page's full title (no template suffix) and its description. Keyword first, brand once. */
export const HOME_TITLE = "Valora3D — Turn 3D models into cinematic videos";
export const HOME_DESCRIPTION =
  "Upload a .glb 3D model, describe the shot in one sentence and get a cinematic video rendered with Blender Cycles on cloud GPUs. Start free, no card needed.";

/** Every page title ends with the brand once: "Pricing · Valora3D". */
export const TITLE_TEMPLATE = "%s · Valora3D";
export const PUBLIC_PATHS = ["/", "/pricing", "/terms", "/privacy", "/acceptable-use", "/refunds", "/contact"] as const;

// A page's openGraph/twitter object replaces the parent's wholesale, so the root
// opengraph-image is lost unless each page names it again.
const SHARE_IMAGE = { url: "/opengraph-image", width: 1200, height: 630, alt: "Valora3D" };

/**
 * `absolute` skips the "%s · Valora3D" template (the home title already carries the brand). `ownImage`: the route
 * has its own opengraph-image file (Next names nested ones with a hash, e.g. /pricing/opengraph-image-1tkyak), so
 * no image is named here and the file convention fills og:image; X falls back to og:image without twitter:image.
 */
export function publicMetadata(title: string, description: string, path: string, options: { absolute?: boolean; ownImage?: boolean } = {}): Metadata {
  const images = options.ownImage ? {} : { images: [SHARE_IMAGE] };
  const twitterImages = options.ownImage ? {} : { images: [SHARE_IMAGE.url] };
  return {
    title: options.absolute ? { absolute: title } : title,
    description,
    alternates: { canonical: path },
    openGraph: { title, description, url: path, siteName: "Valora3D", type: "website", ...images },
    twitter: { card: "summary_large_image", title, description, ...twitterImages },
  };
}
