import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/**
 * `/r/` (share pages) is deliberately NOT disallowed: the pages carry `noindex` in their meta, and link-preview
 * bots (X, LinkedIn, Slack) honor robots.txt, so a disallow would both hide that noindex from search engines
 * and stop shared links from unfurling with their poster.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/dev/", "/projects", "/profile", "/settings", "/login", "/signup"] },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
