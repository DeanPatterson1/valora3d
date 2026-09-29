import { ogCard, OG_SIZE } from "@/lib/og";
import { HELP_ARTICLES } from "@/lib/help";

export const alt = "Valora3D help article";
export const size = OG_SIZE;
export const contentType = "image/png";

export function generateStaticParams() {
  return HELP_ARTICLES.map(({ slug }) => ({ slug }));
}

export default async function HelpArticleOpenGraphImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = HELP_ARTICLES.find((a) => a.slug === slug);
  return ogCard({ eyebrow: "Help", title: article?.title ?? "Help center", lead: article?.summary ?? "Guides for Valora3D." });
}
