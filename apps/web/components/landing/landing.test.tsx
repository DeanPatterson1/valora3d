// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { BRAND } from "@/lib/brand";
import { Hero, HERO_PROOF, HERO_SUB } from "./Hero";
import { Gallery, type GalleryItem } from "./Gallery";
import { Reviews, REVIEWS_LABEL, PLACEHOLDER_REVIEWS, PLACEHOLDER_REVIEW_TEXT } from "./Reviews";
import { Faq, FAQ_ITEMS } from "./Faq";

beforeAll(() => {
  // whileInView and the hero's video pause need an observer; jsdom has none.
  class IO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal("IntersectionObserver", IO);
  // jsdom's <dialog> has no showModal/close.
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});
afterEach(cleanup);

describe("Hero", () => {
  it("renders the headline, the sub-line, the primary CTA and the honest proof line", () => {
    render(<Hero />);
    expect(screen.getByRole("heading", { level: 1, name: BRAND.tagline })).toBeTruthy();
    expect(screen.getByText(HERO_SUB)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Start a project" }).getAttribute("href")).toBe("/projects?new=1");
    expect(screen.getByRole("link", { name: "See how it works" }).getAttribute("href")).toBe("#how-it-works");
    expect(screen.getByText(HERO_PROOF)).toBeTruthy();
    expect(HERO_PROOF).toMatch(/prototype/i);
  });

  it("uses a muted, looping, inline video with a poster", () => {
    render(<Hero />);
    const video = screen.getByTestId("hero-video") as HTMLVideoElement;
    expect(video.hasAttribute("loop")).toBe(true);
    expect(video.hasAttribute("playsinline")).toBe(true);
    expect(video.getAttribute("preload")).toBe("metadata");
    expect(video.getAttribute("poster")).toBe("/landing/hero-poster.jpg");
  });
});

const MANIFEST: GalleryItem[] = [
  { file: "a.jpg", caption: "Rainy night on a city street", prompt: "Rainy night on a city street", model: "car", size: "wide", width: 1600, height: 1000 },
  { file: "b.jpg", caption: "White studio, soft light", prompt: "White studio, soft light", model: "product", size: "large", width: 1600, height: 1000 },
];

describe("Gallery", () => {
  it("renders every manifest item with its caption and opens a lightbox on click", () => {
    render(<Gallery items={MANIFEST} />);
    const figures = screen.getAllByRole("figure");
    expect(figures).toHaveLength(2);
    expect(within(figures[0]).getByText(/Rainy night on a city street/)).toBeTruthy();
    expect(within(figures[0]).getByRole("img").getAttribute("alt")).toBe("Rainy night on a city street");

    const dialog = screen.getByRole("dialog", { hidden: true }) as HTMLDialogElement;
    expect(dialog.hasAttribute("open")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Open: White studio, soft light" }));
    expect(dialog.hasAttribute("open")).toBe(true);
    expect(within(dialog).getByText("White studio, soft light")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(dialog.hasAttribute("open")).toBe(false);
  });
});

describe("Reviews", () => {
  it("is labelled as a placeholder and shows no names, stars or invented quotes", () => {
    render(<Reviews />);
    expect(screen.getByRole("heading", { level: 2, name: REVIEWS_LABEL })).toBeTruthy();
    expect(REVIEWS_LABEL).toMatch(/placeholder/i);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(PLACEHOLDER_REVIEWS.length);
    for (const item of items) expect(within(item).getByText(PLACEHOLDER_REVIEW_TEXT)).toBeTruthy();
    expect(screen.queryByText(/★/)).toBeNull();
  });
});

describe("Faq", () => {
  it("lists four questions that toggle open", () => {
    render(<Faq />);
    expect(FAQ_ITEMS).toHaveLength(4);
    const first = screen.getByText(FAQ_ITEMS[0].q).closest("details") as HTMLDetailsElement;
    expect(first.open).toBe(false);
    fireEvent.click(screen.getByText(FAQ_ITEMS[0].q));
    expect(first.open).toBe(true);
    expect(within(first).getByText(FAQ_ITEMS[0].a)).toBeTruthy();
    expect(FAQ_ITEMS[0].a).toMatch(/^No\./);
  });
});
