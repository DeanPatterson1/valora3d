import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { reportHref } from "@/lib/share/public";
import { shareMediaPath, type GoneReason, type PublicShare } from "@/lib/share/types";

/**
 * The public page for a shared render: the video on its own, the prompt only if the owner chose to show it,
 * one quiet invitation to try Valora3D, and a report link. Server component: nothing here needs the client.
 */
export function SharedRender({ share, media }: { share: PublicShare; /** Fixture override (/dev/share-page only). */ media?: { video: string; poster: string } }) {
  const video = media?.video ?? shareMediaPath(share.slug, "video");
  const poster = media?.poster ?? shareMediaPath(share.slug, "poster");
  const portrait = share.height > share.width;
  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col items-center gap-8 px-4 pb-16 pt-8 sm:px-8 sm:pt-12">
      <h1 className="sr-only">A render made with {BRAND.name}</h1>
      <div
        className="relative w-full overflow-hidden rounded-lg border border-line bg-bg-1 shadow-raise"
        style={{
          aspectRatio: `${share.width} / ${share.height}`,
          // Portrait videos are held to the viewport height so the whole frame fits without scrolling.
          maxWidth: portrait ? `min(100%, calc((100dvh - 15rem) * ${share.width / share.height}))` : "960px",
        }}
      >
        <video
          controls
          playsInline
          loop
          preload="metadata"
          poster={poster}
          src={video}
          width={share.width}
          height={share.height}
          aria-label="Shared render"
          className="absolute inset-0 size-full bg-bg-0 object-contain"
        />
      </div>

      <div className="flex w-full max-w-[640px] flex-col items-center gap-6 text-center">
        {share.prompt && (
          <figure className="flex flex-col gap-1.5">
            <figcaption className="text-xs text-fg-muted">Prompt</figcaption>
            <blockquote className="text-base leading-relaxed text-fg">“{share.prompt}”</blockquote>
          </figure>
        )}
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm text-fg-muted">
            Made with {BRAND.name}. Upload a 3D model, describe the shot, get a video.
          </p>
          <Link
            href="/signup"
            className="inline-flex h-10 items-center justify-center rounded-full border border-line px-5 text-sm font-medium text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring"
          >
            Try {BRAND.name} free
          </Link>
        </div>
        <a href={reportHref(share.slug)} className="text-xs text-fg-muted underline-offset-2 hover:text-fg hover:underline focus-visible:focus-ring">
          Report this video
        </a>
      </div>
    </div>
  );
}

const GONE_COPY: Record<GoneReason, string> = {
  revoked: "The person who shared this render has stopped sharing it.",
  expired: "This render has expired and its video was deleted.",
};

/** Fallback when the proxy did not answer a revoked/expired link with its 410 page (same copy). */
export function SharedRenderGone({ reason }: { reason: GoneReason }) {
  return (
    <div className="mx-auto flex max-w-[440px] flex-col items-center gap-3 px-4 py-24 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-fg">This render is no longer available</h1>
      <p className="text-fg-muted">{GONE_COPY[reason]}</p>
      <Link href="/signup" className="mt-3 inline-flex h-10 items-center rounded-full border border-line px-5 text-sm font-medium text-fg hover:bg-bg-3 focus-visible:focus-ring">
        Make your own with {BRAND.name}
      </Link>
    </div>
  );
}
