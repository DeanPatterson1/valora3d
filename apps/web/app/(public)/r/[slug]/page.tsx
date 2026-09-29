import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { after } from "next/server";
import { SharedRender, SharedRenderGone } from "@/components/share/SharedRender";
import { log } from "@/lib/server/log";
import { loadPublicShare, publicShareReader } from "@/lib/server/publicShare";
import { shareMetadata } from "@/lib/share/public";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

const NOINDEX: Metadata = { title: "Render not available", robots: { index: false, follow: false } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const found = await loadPublicShare((await params).slug);
  return found.state === "live" ? shareMetadata(found.share) : NOINDEX;
}

/** /r/:slug — a render its owner chose to share. Revoked or expired links get a 410 from the proxy. */
export default async function SharedRenderPage({ params }: Props) {
  const { slug } = await params;
  const found = await loadPublicShare(slug);
  if (found.state === "missing") notFound();
  if (found.state === "gone") return <SharedRenderGone reason={found.reason} />;
  // Best effort, after the response: a failed count never costs the viewer anything.
  after(async () => {
    try {
      await publicShareReader()?.bumpView(slug);
    } catch {
      log("warn", "/r/[slug]", "share_view_count_failed");
    }
  });
  return <SharedRender share={found.share} />;
}
