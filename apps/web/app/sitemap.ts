import type { MetadataRoute } from "next";
import { PUBLIC_PATHS, SITE_URL } from "@/lib/site";
import { HELP_ARTICLES } from "@/lib/help";

export default function sitemap(): MetadataRoute.Sitemap {
  return [...PUBLIC_PATHS, "/help", ...HELP_ARTICLES.map((article) => `/help/${article.slug}`)]
    .map((path) => ({ url: `${SITE_URL}${path === "/" ? "" : path}` }));
}
