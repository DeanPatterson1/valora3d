"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { BRAND } from "@/lib/brand";
import { EASE } from "@/lib/motion/tokens";
import { cx } from "@/components/ui";

export const HERO_MEDIA = {
  mp4: "/landing/hero.mp4",
  webm: "/landing/hero.webm",
  poster: "/landing/hero-poster.jpg",
} as const;

export const HERO_SUB = "Upload a model. Describe the shot. Get a cinematic render.";
export const HERO_PROOF = "Prototype · renderer not connected yet";

const CTA = "inline-flex h-12 items-center justify-center rounded-full px-6 text-[15px] font-medium transition-colors duration-fast ease-standard focus-visible:focus-ring";

const rise = (delay: number, rm: boolean) => ({
  initial: rm ? { opacity: 0 } : { opacity: 0, y: 24 },
  animate: rm ? { opacity: 1 } : { opacity: 1, y: 0 },
  transition: { duration: 0.9, ease: EASE.emphasized, delay },
});

/**
 * Full-bleed loop of the viewer's own rainy-night orbit. The section is sticky for one
 * viewport so the content sheet scrolls over it; the video parallaxes up to 8% behind.
 */
export function Hero() {
  const rm = useReducedMotion() ?? false;
  const videoRef = useRef<HTMLVideoElement>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const { scrollY } = useScroll();
  const y = useTransform(scrollY, [0, 1200], ["0%", "8%"]);

  // Pause the loop once the sheet has covered it; resume when the top of the page is back.
  useEffect(() => {
    const video = videoRef.current;
    const section = sectionRef.current;
    if (!video || !section || rm) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) video.play().catch(() => {});
        else video.pause();
      },
      { threshold: 0.05 },
    );
    io.observe(section);
    return () => io.disconnect();
  }, [rm]);

  return (
    <section ref={sectionRef} aria-labelledby="hero-title" className="sticky top-0 z-0 h-svh w-full overflow-hidden bg-bg-0">
      <motion.div style={{ y: rm ? 0 : y }} className="absolute inset-0 scale-[1.1]">
        {rm ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={HERO_MEDIA.poster} alt="" className="h-full w-full object-cover" />
        ) : (
          <video
            ref={videoRef}
            className="h-full w-full object-cover"
            poster={HERO_MEDIA.poster}
            autoPlay
            muted
            loop
            playsInline
            preload="metadata"
            aria-hidden
            data-testid="hero-video"
          >
            <source src={HERO_MEDIA.webm} type="video/webm" />
            <source src={HERO_MEDIA.mp4} type="video/mp4" />
          </video>
        )}
      </motion.div>
      {/* Tint: keeps type legible over the scene and darkens toward the sheet's edge. */}
      <div aria-hidden className="absolute inset-0 bg-[linear-gradient(180deg,rgba(13,13,13,0.35)_0%,rgba(13,13,13,0.25)_45%,rgba(13,13,13,0.85)_100%)]" />

      <div className="relative z-10 mx-auto flex h-full w-full max-w-[1200px] flex-col justify-end px-4 pb-[max(2.5rem,7vh)] sm:px-6 lg:px-10">
        <motion.p {...rise(0.1, rm)} className="mb-5 text-[11px] font-medium uppercase tracking-[0.32em] text-fg/60">
          AI rendering for 3D models
        </motion.p>
        <motion.h1
          id="hero-title"
          {...rise(0.2, rm)}
          className="max-w-[12ch] font-display text-[clamp(2.75rem,9.5vw,8.5rem)] font-extrabold leading-[0.92] tracking-[-0.045em] text-white [text-shadow:0_2px_40px_rgba(0,0,0,0.5)]"
        >
          {BRAND.tagline}
        </motion.h1>
        <motion.p {...rise(0.35, rm)} className="mt-6 max-w-[38ch] text-base leading-relaxed text-fg/85 sm:text-lg">
          {HERO_SUB}
        </motion.p>
        <motion.div {...rise(0.45, rm)} className="mt-8 flex flex-wrap items-center gap-3">
          <Link href="/projects?new=1" className={cx(CTA, "glow bg-primary text-primary-fg hover:bg-primary/90")}>
            Start a project
          </Link>
          <a href="#how-it-works" className={cx(CTA, "border border-white/20 bg-white/[0.04] text-fg backdrop-blur-md hover:bg-white/[0.1]")}>
            See how it works
          </a>
        </motion.div>
        <motion.p {...rise(0.6, rm)} className="mt-6 text-xs text-fg/50">
          {HERO_PROOF}
        </motion.p>
      </div>
    </section>
  );
}
