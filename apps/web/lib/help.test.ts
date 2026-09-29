import { describe, expect, it } from "vitest";
import { HELP_ARTICLES, HELP_FAQS, helpSearchEntries, filterHelp } from "./help";
import { PLAN_LIMITS, CREDIT_COSTS } from "./pricing";
import { WORLDS } from "./render/worlds";
import { INPUT_FAILURE_FEE } from "./render/failurePolicy";
import sitemap from "@/app/sitemap";
import manifest from "@/app/manifest";

describe("help content and discovery", () => {
  it("publishes eight unique articles and includes every route in the sitemap", () => {
    expect(HELP_ARTICLES).toHaveLength(8);
    expect(new Set(HELP_ARTICLES.map((a) => a.slug)).size).toBe(8);
    const urls = sitemap().map((entry) => entry.url);
    for (const article of HELP_ARTICLES) {
      expect(urls).toContain(`https://valora3d.com/help/${article.slug}`);
      expect(article.sections.length).toBeGreaterThan(0);
    }
    expect(urls).toContain("https://valora3d.com/help");
  });

  it("searches article bodies, ignores case and whitespace, and handles no results", () => {
    const entries = helpSearchEntries();
    expect(filterHelp(entries, "  BLENDER  ").map((a) => a.slug)).toContain("preparing-your-model");
    expect(filterHelp(entries, "missing textures").map((a) => a.slug)).toContain("troubleshooting");
    expect(filterHelp(entries, " ")).toHaveLength(8);
    expect(filterHelp(entries, "no-such-topic")).toEqual([]);
  });

  it("uses current plan, render cost and world definitions", () => {
    const plans = HELP_ARTICLES.find((a) => a.slug === "credits-plans-and-refunds")!;
    const text = JSON.stringify(plans);
    for (const limits of Object.values(PLAN_LIMITS)) {
      expect(text).toContain(`${limits.retentionDays}-day retention`);
      expect(text).toContain(`${limits.maxActiveJobs} render`);
    }
    expect(text).toContain(`${CREDIT_COSTS.preview_render} credits`);
    expect(text).toContain(`${CREDIT_COSTS.final_render} credits`);
    const worlds = JSON.stringify(HELP_ARTICLES.find((a) => a.slug === "worlds-formats-and-quality"));
    for (const world of WORLDS) expect(worlds).toContain(world.label);
    expect(HELP_FAQS.some((faq) => faq.answer.includes("refunded automatically"))).toBe(true);
    // The refund copy follows lib/render/failurePolicy.ts: the fee, and no refund once a cancelled render started.
    expect(text).toContain(`${INPUT_FAILURE_FEE} credits are kept`);
    expect(text).toContain("cancelled after it started rendering isn't refunded");
    expect(JSON.stringify(HELP_ARTICLES)).not.toMatch(/failed or cancelled renders are refunded automatically/i);
  });

  it("offers installable PNG icons including a separate maskable icon", () => {
    expect(manifest().icons).toEqual(expect.arrayContaining([
      expect.objectContaining({ sizes: "192x192", type: "image/png", purpose: "any" }),
      expect.objectContaining({ sizes: "512x512", type: "image/png", purpose: "any" }),
      expect.objectContaining({ sizes: "512x512", type: "image/png", purpose: "maskable" }),
    ]));
  });
});
