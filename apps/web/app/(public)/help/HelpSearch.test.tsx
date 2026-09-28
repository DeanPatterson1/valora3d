import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { HelpSearch } from "./HelpSearch";
import { helpSearchEntries, HELP_FAQS } from "@/lib/help";
import HelpPage from "./page";
import HelpArticlePage, { generateMetadata, generateStaticParams } from "./[slug]/page";

afterEach(cleanup);

describe("help pages", () => {
  it("filters the article links, announces results and clears an empty search", () => {
    render(<HelpSearch entries={helpSearchEntries()} />);
    const input = screen.getByRole("searchbox");
    expect(screen.getAllByRole("link")).toHaveLength(8);
    fireEvent.change(input, { target: { value: "Paddle" } });
    expect(screen.getByRole("status").textContent).toBe("1 article found");
    expect(screen.getByRole("link").getAttribute("href")).toBe("/help/credits-plans-and-refunds");
    fireEvent.change(input, { target: { value: "unknown-topic" } });
    expect(screen.getByRole("heading", { name: "No matching articles" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(screen.getAllByRole("link")).toHaveLength(8);
  });

  it("publishes FAQ structured data that matches the visible answers", () => {
    const { container } = render(<HelpPage />);
    const json = JSON.parse(container.querySelector('script[type="application/ld+json"]')!.textContent!);
    expect(json["@type"]).toBe("FAQPage");
    expect(json.mainEntity).toHaveLength(HELP_FAQS.length);
    for (const faq of HELP_FAQS) {
      const details = screen.getByText(faq.question).closest("details")!;
      expect(within(details).getByText(faq.answer)).toBeTruthy();
      expect(json.mainEntity).toContainEqual({ "@type": "Question", name: faq.question, acceptedAnswer: { "@type": "Answer", text: faq.answer } });
    }
  });

  it("generates all article routes and rejects unknown slugs", async () => {
    expect(generateStaticParams()).toHaveLength(8);
    await expect(HelpArticlePage({ params: Promise.resolve({ slug: "missing" }) })).rejects.toThrow("NEXT_HTTP_ERROR_FALLBACK;404");
    const props = { params: Promise.resolve({ slug: "preparing-your-model" }) };
    expect(await generateMetadata(props)).toMatchObject({ alternates: { canonical: "/help/preparing-your-model" } });
    render(await HelpArticlePage(props));
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Preparing your model");
    expect(screen.getByRole("navigation", { name: "On this page" })).toBeTruthy();
  });
});
