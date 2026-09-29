"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useTransform } from "motion/react";
import { BRAND } from "@/lib/brand";
import { START_PATH, signupHref } from "@/lib/nav/next";
import { LogoMark } from "@/components/layout/LogoMark";
import { EASE } from "@/lib/motion/tokens";
import { cx } from "@/components/ui";
import type { HeroMedia } from "./manifest";
import { playExclusive, releaseVideo } from "./video-registry";

/** Everything at and above this width gets the native-resolution rungs. Tailwind's `md`. */
export const HERO_WIDE = "(min-width: 768px)";

/**
 * The loop is the CC0 toy car (Khronos glTF-Sample-Assets) on a draped cloth: a fictional car with no
 * real-world badges or logos, so the first thing a visitor sees carries nobody's trademark. It plays
 * forward then backward, so the 4 s orbit loops without a cut (7.9 s).
 *
 * Both tiers are encoded straight off the original 1920×1080 Cycles PNG frames (Rendering
 * `assets-in/renders/products/toycar/frames`) — never off an already-compressed mp4 — and cropped
 * to the hero's 16:10 framing at the render's own height. The ladder exists because the hero is the
 * one eagerly-loaded asset on the page:
 *
 *   ≥768px  1728×1080  AV1 1.1 MB · VP9 1.5 MB · H.264 2.4 MB
 *   <768px  1280×800   AV1 0.7 MB · VP9 0.9 MB · H.264 1.5 MB
 *
 * A phone never sees the full frame anyway — `object-cover` on a 375px-wide viewport crops
 * to under a third of the width — so the small rungs cost it nothing visible. Within a
 * tier the order is best-per-byte first: most visitors take the AV1 and never fetch the
 * rest, and the bare `video/mp4` at the bottom is the rung that always plays.
 */
export const HERO_MEDIA: HeroMedia = {
  poster: "/landing/hero-poster.jpg",
  sources: [
    { media: HERO_WIDE, src: "/landing/hero.av1.mp4", type: 'video/mp4; codecs="av01.0.08M.08"' },
    { media: HERO_WIDE, src: "/landing/hero.webm", type: 'video/webm; codecs="vp9"' },
    { media: HERO_WIDE, src: "/landing/hero.mp4", type: "video/mp4" },
    { src: "/landing/hero-sm.av1.mp4", type: 'video/mp4; codecs="av01.0.05M.08"' },
    { src: "/landing/hero-sm.webm", type: 'video/webm; codecs="vp9"' },
    { src: "/landing/hero-sm.mp4", type: "video/mp4" },
  ],
};

/** What it is, in the H1 under the tagline: the phrase people search for, said plainly. */
export const HERO_WHAT = "Turn your 3D model into a cinematic video.";
export const HERO_SUB = "Upload a .glb, describe the shot in one sentence, and get a Blender Cycles render from the cloud.";
/**
 * The loop above is a real Blender Cycles render off the offline path, but nobody pressed
 * a button in this app to get it. Both halves of that have to stay on the page.
 */
export const HERO_PROOF = "Example shot · rendered with Blender Cycles";

/**
 * At display size the apostrophe's own side bearings plus the tight tracking left a visible hole ("don ’t").
 * The glyph is pulled in on both sides; the text (and so the accessible name) is unchanged.
 */
function Tagline({ text }: { text: string }) {
  const parts = text.split("’");
  return (
    <>
      {parts.map((part, i) => (
        <span key={i}>
          {i > 0 && <span className="mx-[-0.05em]">’</span>}
          {part}
        </span>
      ))}
    </>
  );
}

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
 * The headline is the page's LCP element, so it must paint with the server HTML: it rises by transform only
 * and is fully opaque from the first frame. (An opacity-0 start held mobile LCP back until hydration plus the
 * animation, 6.7 s under Lighthouse's mobile throttling.)
 */
const riseVisible = (delay: number) => ({
  initial: { y: 24 },
  animate: { y: 0 },
  transition: { duration: 0.9, ease: EASE.emphasized, delay },
});

/**
 * Full-bleed loop of the toy-car orbit, a Blender Cycles render cropped to 16:10 and
 * re-encoded for the web. The section is sticky for one viewport so the content sheet
 * scrolls over it; the video parallaxes up to 8% behind.
 *
 * `media` defaults to `HERO_MEDIA`, the quality ladder documented above. The gallery ships
 * its own derivatives of the same clip, so the two are deliberately not shared.
 *
 * `preload="metadata"` is load-bearing: the browser takes the header and then streams the
 * rest behind the first frame, so even the 10.7 MB H.264 rung never blocks the page. Every
 * mp4 is written with `+faststart` so that header is at the front of the file.
 */
export function Hero({ media = HERO_MEDIA }: { media?: HeroMedia }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const manuallyPaused = useRef(false);
  const [playing, setPlaying] = useState(false);
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
          if (entry.isIntersecting && !manuallyPaused.current) playExclusive(video);
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
          id="hero-background-video"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          // From md up the subject (centered in the render) moves right, clear of the headline; the scrim
          // below hides the uncovered left edge. Phones keep it centered above the text.
          className="h-full w-full object-cover object-[50%_0%] md:object-center md:translate-x-[27%]"
          poster={media.poster}
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden
          data-testid="hero-video"
        >
          {media.sources.map((source) => (
            <source key={source.src} src={source.src} type={source.type} media={source.media} />
          ))}
        </video>
      </motion.div>
      {/* Tint: keeps type legible over the scene and darkens toward the sheet's edge. */}
      <div aria-hidden className="absolute inset-0 bg-[linear-gradient(180deg,rgba(13,13,13,0.35)_0%,rgba(13,13,13,0.25)_45%,rgba(13,13,13,0.85)_100%)]" />
      {/* Phones stack the copy over the subject: fade the lower part so the headline reads on the render. */}
      <div aria-hidden className="absolute inset-0 bg-[linear-gradient(180deg,rgba(13,13,13,0)_18%,rgba(13,13,13,0.8)_40%,rgba(13,13,13,0.94)_58%)] md:hidden" />
      <div aria-hidden className="absolute inset-0 hidden bg-[linear-gradient(90deg,#0d0d0d_0%,#0d0d0d_24%,rgba(13,13,13,0.6)_40%,rgba(13,13,13,0)_58%)] md:block" />

      {/* First-screen header: the brand and a way in for both new and returning visitors. The floating pill
          (LandingNav) takes over once the sheet scrolls past the hero. */}
      <header className="absolute inset-x-0 top-0 z-20">
        <nav aria-label="Site" className="mx-auto flex h-16 w-full max-w-[1200px] items-center justify-between px-4 sm:h-20 sm:px-6 lg:px-10">
          <Link href="/" className="flex items-center gap-2 rounded-full text-[15px] font-semibold tracking-tight text-white focus-visible:focus-ring">
            <LogoMark className="size-6" />
            {BRAND.name}
          </Link>
          <div className="flex items-center gap-1">
            <Link href="/login" className="inline-flex h-10 items-center rounded-full px-4 text-sm text-fg/85 transition-colors duration-fast ease-standard hover:text-fg focus-visible:focus-ring">
              Log in
            </Link>
            <Link href={signupHref()} className="inline-flex h-10 items-center rounded-full bg-white/[0.12] px-4 text-sm font-medium text-fg backdrop-blur-md transition-colors duration-fast ease-standard hover:bg-white/[0.2] focus-visible:focus-ring">
              Get started
            </Link>
          </div>
        </nav>
      </header>

      <div className="relative z-10 mx-auto flex h-full w-full max-w-[1200px] flex-col justify-end px-4 pb-[max(2.5rem,7vh)] sm:px-6 lg:px-10">
        <motion.p {...rise(0.1)} className="mb-5 text-[11px] font-medium uppercase tracking-[0.32em] text-fg/60">
          AI rendering for 3D models
        </motion.p>
        <motion.h1 id="hero-title" {...riseVisible(0.2)}>
          <span className="block max-w-[12ch] font-display text-[clamp(2.75rem,9.5vw,8.5rem)] md:text-[clamp(3rem,6.2vw,6rem)] font-extrabold leading-[0.92] tracking-[-0.045em] text-white [text-shadow:0_2px_40px_rgba(0,0,0,0.5)]">
            <Tagline text={BRAND.tagline} />
          </span>
          <span className="mt-6 block max-w-[28ch] text-xl font-semibold leading-snug tracking-[-0.01em] text-fg sm:text-2xl">{HERO_WHAT}</span>
        </motion.h1>
        <motion.p {...riseVisible(0.3)} className="mt-3 max-w-[44ch] text-base leading-relaxed text-fg/80 sm:text-lg">
          {HERO_SUB}
        </motion.p>
        <motion.div {...rise(0.45)} className="mt-8 flex flex-wrap items-center gap-3">
          <Link href={signupHref(START_PATH)} className={cx(CTA, "glow bg-primary text-primary-fg hover:bg-primary/90")}>
            Start a project
          </Link>
          <a href="#how-it-works" className={cx(CTA, "border border-white/20 bg-white/[0.04] text-fg backdrop-blur-md hover:bg-white/[0.1]")}>
            See how it works
          </a>
        </motion.div>
        <motion.p {...rise(0.6)} className="mt-6 text-xs text-fg/50">
          {HERO_PROOF}
        </motion.p>
        <button
          type="button"
          aria-controls="hero-background-video"
          aria-label={playing ? "Pause background video" : "Play background video"}
          className="mt-4 inline-flex min-h-11 w-fit items-center rounded-full border border-white/30 bg-bg-0/70 px-4 text-sm text-fg hover:bg-bg-0 focus-visible:focus-ring"
          onClick={() => {
            const video = videoRef.current;
            if (!video) return;
            if (playing) {
              manuallyPaused.current = true;
              video.pause();
              releaseVideo(video);
            } else {
              manuallyPaused.current = false;
              playExclusive(video);
            }
          }}
        >
          {playing ? "Pause video" : "Play video"}
        </button>
      </div>
    </section>
  );
}
