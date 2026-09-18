"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";
import { BRAND } from "@/lib/brand";
import { EASE } from "@/lib/motion/tokens";
import { cx } from "@/components/ui";
import type { HeroMedia } from "./manifest";
import { playExclusive, releaseVideo } from "./video-registry";

export const HERO_MEDIA: HeroMedia = {
  mp4: "/landing/hero.mp4",
  webm: "/landing/hero.webm",
  poster: "/landing/hero-poster.jpg",
};

export const HERO_SUB = "Upload a model. Describe the shot. Get a cinematic render.";
/**
 * The loop above is a real Blender Cycles render off the offline path, but nobody pressed
 * a button in this app to get it. Both halves of that have to stay on the page.
 */
export const HERO_PROOF = "Prototype · real Blender Cycles render, rendering from the app not connected yet";

const CTA = "inline-flex h-12 items-center justify-center rounded-full px-6 text-[15px] font-medium transition-colors duration-fast ease-standard focus-visible:focus-ring";

const REDUCE_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * One set of values for every visitor: branching these on `useReducedMotion()` would
 * change the inline `style` motion renders during SSR and break hydration, because the
 * hook reads `null` on the server and the real preference on the very first client
 * render. `<MotionConfig reducedMotion="user">` in `app/layout.tsx` snaps the transform
 * keys instead, so reduced-motion visitors get the fade with no travel.
 */
const rise = (delay: number) => ({
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.9, ease: EASE.emphasized, delay },
});

/**
 * Full-bleed loop of the rainy-courtyard walk-in, a Blender Cycles render cropped to 16:10
 * and re-encoded for the web. The section is sticky for one viewport so the content sheet
 * scrolls over it; the video parallaxes up to 8% behind.
 *
 * `media` defaults to the bundled `/landing/hero.*` pair, which is encoded for a background
 * loop (1280×800, ~2.6 MB). The gallery ships its own, heavier derivatives of the same
 * clip, so the two are deliberately not shared.
 */
export function Hero({ media = HERO_MEDIA }: { media?: HeroMedia }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const { scrollY } = useScroll();
  const y = useTransform(scrollY, [0, 1200], ["0%", "8%"]);

  // Playback is decided here, never in the markup: the <video> exists for everyone and
  // carries no `autoPlay`, so the server HTML and the first client render are identical
  // and nothing has moved by the time this effect reads the preference. Under reduced
  // motion the loop never starts, so the poster is what stays on screen. (Switching the
  // preference on mid-session only pauses, leaving the current frame — there is no way
  // back to a poster once a video has painted.)
  useEffect(() => {
    const video = videoRef.current;
    const section = sectionRef.current;
    if (!video || !section) return;
    const query = window.matchMedia?.(REDUCE_QUERY) ?? null;
    let io: IntersectionObserver | null = null;

    // Pause the loop once the sheet has covered it; resume when the top of the page is back.
    const sync = () => {
      io?.disconnect();
      io = null;
      if (query?.matches) {
        video.pause();
        releaseVideo(video);
        return;
      }
      io = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) playExclusive(video);
          else {
            video.pause();
            releaseVideo(video);
          }
        },
        { threshold: 0.05 },
      );
      io.observe(section);
    };

    sync();
    query?.addEventListener?.("change", sync);
    return () => {
      query?.removeEventListener?.("change", sync);
      io?.disconnect();
      releaseVideo(video);
    };
  }, []);

  return (
    <section ref={sectionRef} aria-labelledby="hero-title" className="sticky top-0 z-0 h-svh w-full overflow-hidden bg-bg-0">
      {/* The scroll parallax is bound to a motion value, which `reducedMotion="user"` does
          not govern, so `data-hero-parallax` freezes it from app/globals.css instead. */}
      <motion.div data-hero-parallax style={{ y }} className="absolute inset-0 scale-[1.1]">
        <video
          ref={videoRef}
          className="h-full w-full object-cover"
          poster={media.poster}
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden
          data-testid="hero-video"
        >
          {media.webm && <source src={media.webm} type="video/webm" />}
          {media.mp4 && <source src={media.mp4} type="video/mp4" />}
        </video>
      </motion.div>
      {/* Tint: keeps type legible over the scene and darkens toward the sheet's edge. */}
      <div aria-hidden className="absolute inset-0 bg-[linear-gradient(180deg,rgba(13,13,13,0.35)_0%,rgba(13,13,13,0.25)_45%,rgba(13,13,13,0.85)_100%)]" />

      <div className="relative z-10 mx-auto flex h-full w-full max-w-[1200px] flex-col justify-end px-4 pb-[max(2.5rem,7vh)] sm:px-6 lg:px-10">
        <motion.p {...rise(0.1)} className="mb-5 text-[11px] font-medium uppercase tracking-[0.32em] text-fg/60">
          AI rendering for 3D models
        </motion.p>
        <motion.h1
          id="hero-title"
          {...rise(0.2)}
          className="max-w-[12ch] font-display text-[clamp(2.75rem,9.5vw,8.5rem)] font-extrabold leading-[0.92] tracking-[-0.045em] text-white [text-shadow:0_2px_40px_rgba(0,0,0,0.5)]"
        >
          {BRAND.tagline}
        </motion.h1>
        <motion.p {...rise(0.35)} className="mt-6 max-w-[38ch] text-base leading-relaxed text-fg/85 sm:text-lg">
          {HERO_SUB}
        </motion.p>
        <motion.div {...rise(0.45)} className="mt-8 flex flex-wrap items-center gap-3">
          <Link href="/projects?new=1" className={cx(CTA, "glow bg-primary text-primary-fg hover:bg-primary/90")}>
            Start a project
          </Link>
          <a href="#how-it-works" className={cx(CTA, "border border-white/20 bg-white/[0.04] text-fg backdrop-blur-md hover:bg-white/[0.1]")}>
            See how it works
          </a>
        </motion.div>
        <motion.p {...rise(0.6)} className="mt-6 text-xs text-fg/50">
          {HERO_PROOF}
        </motion.p>
      </div>
    </section>
  );
}
