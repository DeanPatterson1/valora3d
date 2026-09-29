// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.stubGlobal("IntersectionObserver", class { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } });
vi.mock("next/font/google", () => ({ Inter: () => ({ variable: "font-text" }), Inter_Tight: () => ({ variable: "font-display" }) }));
import { metadata as rootMetadata } from "@/app/layout";
import { metadata as homeMetadata } from "@/app/(marketing)/page";
import { metadata as pricingMetadata } from "@/app/(public)/pricing/page";
import { metadata as examplesMetadata } from "@/app/(public)/examples/page";
import { generateMetadata as exampleMetadata } from "@/app/(public)/examples/[slug]/page";
import { metadata as guidesMetadata } from "@/app/(public)/guides/page";
import { generateMetadata as guideMetadata } from "@/app/(public)/guides/[slug]/page";
import { metadata as checkerMetadata } from "@/app/(public)/tools/glb-checker/page";
import { EXAMPLES } from "@/lib/examples";
import { GUIDES } from "@/lib/guides";
import robots from "@/app/robots";
import sitemap from "@/app/sitemap";
import { jsonLdString } from "@/components/seo/JsonLd";
import { Capabilities, worldsSentence } from "@/components/landing/Capabilities";
import { SiteFooter, TRADEMARK_NOTICE } from "@/components/layout/SiteFooter";
import { viewerLabel } from "@/components/viewer/viewerLabel";
import { CREDIT_PACKS, PLANS } from "@/lib/pricing";
import { WORLDS } from "@/lib/render/worlds";
import { HOME_TITLE, OPERATOR_NAME } from "@/lib/site";
import { homeStructuredData } from "@/lib/structuredData";

type Node = { "@type": string; offers?: { name: string; price: string; priceCurrency: string }[] };

describe("titles", () => {
  it("brands every page title once through the root template, and the home title says what it is", () => {
    expect(rootMetadata.title).toEqual({ default: HOME_TITLE, template: "%s · Valora3D" });
    expect(homeMetadata.title).toEqual({ absolute: HOME_TITLE });
    expect(HOME_TITLE).toMatch(/3D models?/i);
    expect(HOME_TITLE).toMatch(/video/i);
    expect(pricingMetadata.title).toBe("Pricing");
  });
});

describe("structured data", () => {
  const graph = (homeStructuredData() as { "@graph": Node[] })["@graph"];

  it("describes the organization, the site and the product", () => {
    expect(graph.map((n) => n["@type"])).toEqual(["Organization", "WebSite", "SoftwareApplication"]);
  });

  it("lists exactly the plans and packs on the pricing page, at their prices", () => {
    const offers = graph.find((n) => n["@type"] === "SoftwareApplication")!.offers!;
    expect(offers.map((o) => Number(o.price))).toEqual([...PLANS.map((p) => p.priceUsd), ...CREDIT_PACKS.map((p) => p.priceUsd)]);
    expect(new Set(offers.map((o) => o.priceCurrency))).toEqual(new Set(["USD"]));
  });

  it("claims no ratings or reviews, and cannot be broken out of its script tag", () => {
    const text = jsonLdString(homeStructuredData());
    expect(text).not.toMatch(/aggregateRating|review/i);
    expect(jsonLdString({ name: "</script><script>alert(1)</script>" })).not.toContain("</script>");
  });
});

describe("crawling", () => {
  it("dates every sitemap entry and keeps share pages reachable for unfurls", () => {
    expect(sitemap().every((e) => e.lastModified instanceof Date)).toBe(true);
    const disallow = (robots().rules as { disallow: string[] }).disallow;
    expect(disallow.some((d) => "/r/some-slug".startsWith(d))).toBe(false);
  });

  it("lists the examples, export guides and the .glb checker, and robots allows them", () => {
    const urls = sitemap().map((e) => e.url);
    const paths = ["/examples", ...EXAMPLES.map((e) => `/examples/${e.slug}`), "/guides", ...GUIDES.map((g) => `/guides/${g.slug}`), "/tools/glb-checker"];
    for (const p of paths) expect(urls).toContain(`https://valora3d.com${p}`);
    expect(new Set(urls).size).toBe(urls.length);
    const disallow = (robots().rules as { disallow: string[] }).disallow;
    for (const p of paths) expect(disallow.some((d) => p.startsWith(d))).toBe(false);
  });

  it("gives the new public pages their own canonical, title and description", async () => {
    const pages = [examplesMetadata, guidesMetadata, checkerMetadata];
    expect(pages.map((m) => m.alternates?.canonical)).toEqual(["/examples", "/guides", "/tools/glb-checker"]);
    expect(new Set(pages.map((m) => m.title)).size).toBe(3);
    for (const m of pages) expect(String(m.description).length).toBeGreaterThan(80);
    const example = await exampleMetadata({ params: Promise.resolve({ slug: EXAMPLES[0].slug }) });
    expect(example.alternates?.canonical).toBe(`/examples/${EXAMPLES[0].slug}`);
    const guide = await guideMetadata({ params: Promise.resolve({ slug: GUIDES[0].slug }) });
    expect(guide.alternates?.canonical).toBe(`/guides/${GUIDES[0].slug}`);
  });
});

describe("trust copy", () => {
  it("offers only the worlds that exist", () => {
    expect(worldsSentence()).toBe(`${WORLDS.slice(0, -1).map((w) => w.label).join(", ")} or ${WORLDS[WORLDS.length - 1].label}`);
    render(<Capabilities />);
    const text = document.body.textContent ?? "";
    for (const w of WORLDS) expect(text).toContain(w.label);
    // Worlds the renderer does not offer.
    expect(text).not.toMatch(/white studio|open road|night city|fog/i);
  });

  it("shows the copyright holder, the year and the trademark notice in the footer", () => {
    render(<SiteFooter />);
    expect(screen.getByText(new RegExp(`© ${new Date().getFullYear()} ${OPERATOR_NAME}`))).toBeTruthy();
    expect(screen.getByText(TRADEMARK_NOTICE)).toBeTruthy();
    expect(TRADEMARK_NOTICE).toMatch(/not affiliated/);
    for (const href of ["/examples", "/guides", "/tools/glb-checker"]) {
      expect(document.querySelector(`footer a[href="${href}"]`)).toBeTruthy();
    }
  });
});

describe("3D preview text alternative", () => {
  it("names the model, then the planned scene", () => {
    expect(viewerLabel({})).toBe("3D preview. No model loaded.");
    expect(viewerLabel({ fileName: "toycar.glb", category: "car" })).toBe("3D preview of toycar.glb, a car model.");
    const plan = {
      scene: { environment: "studio_black", time: "day" },
      shots: [{ action: "slow_orbit" }, { action: "hero_push_in" }],
      effects: { rain: 0 },
    } as unknown as Parameters<typeof viewerLabel>[0]["plan"];
    expect(viewerLabel({ fileName: "toycar.glb", category: "car", plan })).toBe(
      "3D preview of toycar.glb, a car model. Scene: studio black at day; camera: slow orbit then hero push in.",
    );
  });
});
