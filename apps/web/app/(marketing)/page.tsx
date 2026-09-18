import { Capabilities } from "@/components/landing/Capabilities";
import { Faq } from "@/components/landing/Faq";
import { FinalCta } from "@/components/landing/FinalCta";
import { Gallery } from "@/components/landing/Gallery";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { LandingNav } from "@/components/landing/LandingNav";
import { parseGalleryManifest } from "@/components/landing/manifest";
import { Pricing } from "@/components/landing/Pricing";
import { Renderer } from "@/components/landing/Renderer";
import { Reviews } from "@/components/landing/Reviews";
import manifest from "@/public/landing/gallery/manifest.json";

// Parsed at build time: a malformed manifest fails the build instead of the page.
const GALLERY = parseGalleryManifest(manifest);

export default function Landing() {
  return (
    <>
      <LandingNav />
      {/* The hero keeps its own 1280×800 encode of the clip: the gallery copies are sized
          for a lightbox and a hover tile, and either one would be wrong full-bleed. */}
      <Hero />
      {/* The sheet: scrolls over the sticky hero, so the page reads as two layers. */}
      <div className="relative z-10 rounded-t-[28px] bg-bg-0 shadow-[0_-24px_80px_rgba(0,0,0,0.6)]">
        <Capabilities />
        <Gallery items={GALLERY} />
        <HowItWorks />
        <Renderer />
        <Pricing />
        <Reviews />
        <Faq />
        <FinalCta />
      </div>
    </>
  );
}
