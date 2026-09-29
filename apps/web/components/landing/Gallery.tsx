"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { cx } from "@/components/ui";
import { Container, Reveal, SectionHead } from "./Reveal";
import { assetUrl, clipMedia, GALLERY_BASE, type GalleryItem } from "./manifest";
import { playExclusive, releaseVideo, stopVideo } from "./video-registry";

export type { GalleryItem };

/**
 * Muted line under the grid. Every tile is now an offline Blender Cycles render — the
 * viewer captures that used to pad the grid are gone — and the app still produced none
 * of them. Keep both halves of that on the page for as long as they are true.
 */
export const GALLERY_CREDIT =
  "Every clip here is a Blender Cycles render off the offline pipeline behind this product: the cars through a rain-courtyard scene, the products through a studio cyclorama setup. All of them were rendered at 1920×1080, 192 samples a frame, on a local RTX 5080 and re-encoded for the web. These example clips were produced on a workstation to illustrate the rendering pipeline. Per-model credits are shown on the items that need them.";

const COUNT = ["no", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"] as const;
const count = (n: number) => (n < COUNT.length ? COUNT[n] : String(n));

/**
 * Counted off the manifest rather than written down, so appending a clip cannot leave the
 * lead claiming a number the grid no longer shows.
 */
export function galleryLead(items: GalleryItem[]): string {
  const cars = items.filter((item) => item.model === "car").length;
  const products = items.length - cars;
  const clip = items.length === 1 ? "clip" : "clips";
  return `${count(items.length)} Blender Cycles ${clip} off the offline path — ${cars} ${cars === 1 ? "car" : "cars"} in the rain, ${products} ${products === 1 ? "product" : "products"} in the studio. Each caption is the prompt that set up the shot.`;
}

const SIZES = {
  large: "(min-width: 1024px) 780px, 100vw",
  wide: "(min-width: 1024px) 380px, (min-width: 640px) 50vw, 100vw",
} as const;

/** Reads a media query on the client; false during SSR and the first paint. */
function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = typeof window === "undefined" ? null : window.matchMedia?.(query);
      if (!mql?.addEventListener) return () => {};
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    [query],
  );
  const get = useCallback(() => (typeof window === "undefined" ? false : (window.matchMedia?.(query)?.matches ?? false)), [query]);
  return useSyncExternalStore(subscribe, get, () => false);
}

/**
 * Offline Cycles clips, captioned with the prompt that set up each shot. Tiles preview
 * on hover and play with controls in the lightbox. Still-only entries are still valid
 * manifest items; the shipped set no longer has any.
 */
export function Gallery({ items, base = GALLERY_BASE }: { items: GalleryItem[]; base?: string }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const tiles = useRef(new Map<number, HTMLButtonElement>());
  const lastOpened = useRef<number | null>(null);
  const lightboxVideo = useRef<HTMLVideoElement>(null);

  // Hover previews are a pointer affordance: coarse pointers tap straight into the
  // lightbox, and reduced motion keeps every tile on its poster.
  const canHover = useMediaQuery("(hover: hover)");
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const hoverPlay = canHover && !reducedMotion;

  const open = openIndex === null ? null : (items[openIndex] ?? null);
  const openMedia = open ? clipMedia(open, base) : null;

  const close = useCallback(() => setOpenIndex(null), []);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (openIndex !== null) {
      // Recorded on the way in only: arrowing through the set still returns focus
      // to the tile that opened the dialog.
      if (!el.open) {
        lastOpened.current = openIndex;
        el.showModal();
      }
      return;
    }
    if (el.open) el.close();
    // Focus goes back to the tile that opened the dialog.
    const last = lastOpened.current;
    lastOpened.current = null;
    if (last !== null) tiles.current.get(last)?.focus();
  }, [openIndex]);

  // The lightbox owns the one playing video while it is open.
  useEffect(() => {
    const video = lightboxVideo.current;
    if (!video) return;
    playExclusive(video);
    return () => releaseVideo(video);
  }, [openIndex]);

  const onKeyDown = (event: React.KeyboardEvent<HTMLDialogElement>) => {
    if (openIndex === null) return;
    if (event.key === "Escape") {
      // Handled here so focus restore runs the same way for Escape and the close button.
      event.preventDefault();
      close();
      return;
    }
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (step === 0 || items.length < 2) return;
    event.preventDefault();
    setOpenIndex((index) => (index === null ? index : (index + step + items.length) % items.length));
  };

  return (
    <section id="gallery" aria-labelledby="gallery-title" className="scroll-mt-24 py-20 md:py-28">
      <Container>
        <Reveal>
          <SectionHead
            id="gallery-title"
            title="What it renders"
            lead={galleryLead(items)}
          />
        </Reveal>
        <Reveal className="mt-12 grid grid-flow-dense grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item, index) => (
            <Tile
              key={`${index}-${item.file}`}
              item={item}
              base={base}
              hoverPlay={hoverPlay}
              onOpen={() => setOpenIndex(index)}
              register={(el) => {
                if (el) tiles.current.set(index, el);
                else tiles.current.delete(index);
              }}
            />
          ))}
        </Reveal>
        <Reveal>
          <p className="mt-6 px-1 text-[13px] leading-relaxed text-fg/45">{GALLERY_CREDIT}</p>
          <p className="mt-3 px-1 text-sm">
            <Link href="/examples" className="rounded-sm text-fg-muted underline underline-offset-4 hover:text-fg focus-visible:focus-ring">See each shot with its prompt and why it works</Link>
          </p>
        </Reveal>
      </Container>

      <dialog
        ref={dialogRef}
        onClose={close}
        onKeyDown={onKeyDown}
        onClick={(e) => {
          if (e.target === e.currentTarget) close();
        }}
        aria-label={open ? open.caption : "Image"}
        className="m-auto w-[min(96vw,1200px)] rounded-[18px] border border-white/10 bg-bg-0 p-0 text-fg backdrop:bg-black/80 backdrop:backdrop-blur-sm"
      >
        {open && (
          <figure className="flex flex-col">
            <div className="relative aspect-[16/10] w-full overflow-hidden rounded-t-[18px] bg-bg-1">
              {openMedia ? (
                <video
                  key={openIndex}
                  ref={lightboxVideo}
                  data-testid="lightbox-video"
                  className="h-full w-full object-cover"
                  src={openMedia.video}
                  poster={openMedia.poster}
                  controls
                  autoPlay
                  loop
                  playsInline
                  preload="none"
                >
                  <p className="p-4 text-sm text-fg-muted">This browser cannot play the clip.</p>
                </video>
              ) : (
                <Image src={assetUrl(open.file, base)} alt={open.caption} fill sizes="96vw" className="object-cover" priority />
              )}
            </div>
            <figcaption className="flex items-start justify-between gap-4 px-5 py-4 text-sm">
              <span className="flex flex-col gap-1">
                <span className="text-fg">{open.caption}</span>
                <span className="text-fg-muted">{open.prompt}</span>
                {open.credit && <span className="text-xs text-fg/50">{open.credit}</span>}
              </span>
              <button
                type="button"
                onClick={close}
                className="inline-flex h-8 shrink-0 cursor-pointer items-center rounded-full border border-line px-3 text-xs text-fg hover:bg-bg-3 focus-visible:focus-ring"
              >
                Close
              </button>
            </figcaption>
          </figure>
        )}
      </dialog>
    </section>
  );
}

function Tile({
  item,
  base,
  hoverPlay,
  onOpen,
  register,
}: {
  item: GalleryItem;
  base: string;
  hoverPlay: boolean;
  onOpen: () => void;
  register: (el: HTMLButtonElement | null) => void;
}) {
  const media = clipMedia(item, base);
  const videoRef = useRef<HTMLVideoElement>(null);
  // `armed` attaches the src on first intent, so nothing downloads before hover;
  // `active` is the current hover/focus state; `ready` is set once the loop has decoded a
  // frame, which is what the tile fades up to.
  const [armed, setArmed] = useState(false);
  const [active, setActive] = useState(false);
  const [ready, setReady] = useState(false);
  const showVideo = active && ready;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (active) playExclusive(video);
    else stopVideo(video);
  }, [active, armed]);

  // Leaving the page must not leave a torn-down element holding the registry slot.
  useEffect(() => {
    const video = videoRef.current;
    return () => {
      if (video) releaseVideo(video);
    };
  }, []);

  const start = () => {
    if (!media || !hoverPlay) return;
    setArmed(true);
    setActive(true);
  };
  const stop = () => setActive(false);

  return (
    <figure className={cx(item.size === "large" && "sm:col-span-2")}>
      <button
        ref={register}
        type="button"
        onClick={onOpen}
        onMouseEnter={start}
        onMouseLeave={stop}
        onFocus={start}
        onBlur={stop}
        aria-label={media ? `Open clip: ${item.caption}` : `Open: ${item.caption}`}
        className="group relative block aspect-[16/10] w-full cursor-zoom-in overflow-hidden rounded-[14px] border border-white/10 bg-bg-1 focus-visible:focus-ring"
      >
        <Image
          src={media ? media.poster : assetUrl(item.file, base)}
          alt={item.caption}
          fill
          sizes={SIZES[item.size]}
          className="object-cover transition-transform duration-[600ms] ease-standard group-hover:scale-[1.03] motion-reduce:transition-none motion-reduce:group-hover:scale-100"
        />
        {media && (
          <>
            {/* No `poster`: the <Image> above is already showing it, and a poster here
                would make every tile fetch the full-size JPEG a second time for a video
                that is transparent until hover. The fade waits for `loadeddata` instead,
                so the still underneath holds until there is a real frame to swap to. */}
            <video
              ref={videoRef}
              data-testid="clip-preview"
              src={armed ? media.preview : undefined}
              onLoadedData={() => setReady(true)}
              muted
              loop
              playsInline
              preload="none"
              tabIndex={-1}
              aria-hidden
              className={cx(
                "absolute inset-0 h-full w-full object-cover transition-opacity duration-base ease-standard",
                showVideo ? "opacity-100" : "opacity-0",
              )}
            />
            <span
              aria-hidden
              data-testid="clip-glyph"
              className={cx(
                "pointer-events-none absolute bottom-3 left-3 inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/20 bg-black/55 text-white backdrop-blur-md transition-opacity duration-base ease-standard",
                showVideo && "opacity-0",
              )}
            >
              <svg viewBox="0 0 24 24" className="h-3 w-3 translate-x-px fill-current">
                <path d="M8 5v14l11-7z" />
              </svg>
            </span>
          </>
        )}
      </button>
      <figcaption className="mt-2.5 px-1 text-[13px] leading-snug text-fg-muted">
        <span className="text-fg/50">{item.model === "car" ? "Car" : "Product"} · </span>
        {item.caption}
        {item.credit && <span className="mt-1 block text-fg/40">{item.credit}</span>}
      </figcaption>
    </figure>
  );
}
