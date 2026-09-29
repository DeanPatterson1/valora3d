import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SharedRender } from "@/components/share/SharedRender";
import { shareMetadata } from "@/lib/share/public";
import type { PublicShare } from "@/lib/share/types";

/**
 * Dev only: the public share page (/r/:slug) with a fixture, so its look and its metadata can be reviewed and
 * tested without a backend. `?layout=portrait` for a 9:16 render, `?prompt=0` for an owner who hid the prompt.
 * The proxy 404s /dev/* in production and this page refuses to render there too.
 */
const LANDSCAPE: PublicShare = {
  slug: "fixtureFixtureFixture123",
  kind: "final",
  prompt: "A silver sports car on a wet road at dusk, slow orbit, city lights behind",
  width: 1920,
  height: 1080,
};
const PORTRAIT: PublicShare = { ...LANDSCAPE, kind: "preview", width: 540, height: 960 };

type Props = { searchParams: Promise<{ layout?: string; prompt?: string }> };

async function fixture(searchParams: Props["searchParams"]): Promise<PublicShare> {
  const q = await searchParams;
  const base = q.layout === "portrait" ? PORTRAIT : LANDSCAPE;
  return q.prompt === "0" ? { ...base, prompt: null } : base;
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  return shareMetadata(await fixture(searchParams));
}

export default async function SharePageFixture({ searchParams }: Props) {
  if (process.env.NODE_ENV === "production") notFound();
  const share = await fixture(searchParams);
  const portrait = share.height > share.width;
  return (
    <SharedRender
      share={share}
      media={{
        video: portrait ? "/landing/gallery/camera-01.mp4" : "/landing/hero.mp4",
        poster: portrait ? "/landing/gallery/camera-01-poster.jpg" : "/landing/hero-poster.jpg",
      }}
    />
  );
}
