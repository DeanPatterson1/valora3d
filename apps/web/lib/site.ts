import type { Metadata } from "next";

export const SITE_URL = "https://valora3d.com";
export const PUBLIC_PATHS = ["/", "/pricing", "/terms", "/privacy", "/acceptable-use", "/refunds", "/contact"] as const;

// A page's openGraph/twitter object replaces the parent's wholesale, so the root
// opengraph-image is lost unless each page names it again.
const SHARE_IMAGE = { url: "/opengraph-image", width: 1200, height: 630, alt: "Valora3D" };

export function publicMetadata(title: string, description: string, path: string): Metadata {
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: { title, description, url: path, siteName: "Valora3D", type: "website", images: [SHARE_IMAGE] },
    twitter: { card: "summary_large_image", title, description, images: [SHARE_IMAGE.url] },
  };
}
