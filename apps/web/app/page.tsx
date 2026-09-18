import { Footer } from "@/components/landing/Footer";
import { Hero } from "@/components/landing/Hero";
import { LocalVsCloud } from "@/components/landing/LocalVsCloud";
import { PricingTeaser } from "@/components/landing/PricingTeaser";
import { Steps } from "@/components/landing/Steps";

export default function Home() {
  return (
    <div className="flex w-full flex-col gap-16 pb-8 md:gap-20">
      <Hero />
      <Steps />
      <LocalVsCloud />
      <PricingTeaser />
      <Footer />
    </div>
  );
}
