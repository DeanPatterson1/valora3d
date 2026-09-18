// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { BRAND } from "@/lib/brand";
import { Hero, HERO_PROOF, HERO_SUB } from "./Hero";
import { LandingNav } from "./LandingNav";
import { Gallery, GALLERY_CREDIT } from "./Gallery";
import { clipMedia, heroMediaFrom, isClip, parseGalleryManifest, type GalleryItem } from "./manifest";
import { playExclusive, resetVideoRegistry } from "./video-registry";
import { Reviews, REVIEWS_LABEL, PLACEHOLDER_REVIEWS, PLACEHOLDER_REVIEW_TEXT } from "./Reviews";
import { Faq, FAQ_ITEMS } from "./Faq";

/** Media queries the component asks about; a test sets what it needs before rendering. */
let media: Record<string, boolean> = {};
const play = vi.fn(() => Promise.resolve());
const pause = vi.fn();

/**
 * `useReducedMotion()` reads `null` on the server and the real preference on the first
 * client render, so any component that branches its markup on it hydrates against HTML the
 * server never wrote. The landing components must not consult it at all: this stub lets a
 * test claim either answer and assert the tree comes out the same.
 */
const motionPref = vi.hoisted(() => ({ reduced: null as boolean | null }));
vi.mock("motion/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react")>();
  return { ...actual, useReducedMotion: () => motionPref.reduced };
});

type FakeEntry = { isIntersecting: boolean };
/**
 * Observers the component under test registered, so a test can fire them. `disconnect`
 * prunes, so a component that forgets to tear an observer down cannot pass by accident.
 */
const observers = new Set<(entries: FakeEntry[]) => void>();
const intersect = (isIntersecting: boolean) => {
  for (const cb of [...observers]) cb([{ isIntersecting }]);
};

/** `change` listeners the component registered per media query, so a test can flip one. */
const mediaListeners = new Map<string, Set<() => void>>();
/** Change a preference the way the OS would, and tell whoever is listening. */
const setMedia = (query: string, matches: boolean) => {
  media[query] = matches;
  for (const listener of mediaListeners.get(query) ?? []) listener();
};

beforeAll(() => {
  // whileInView and the hero's video pause need an observer; jsdom has none.
  class IO {
    constructor(private readonly cb: (entries: FakeEntry[]) => void) {}
    observe() {
      observers.add(this.cb);
    }
    unobserve() {
      observers.delete(this.cb);
    }
    disconnect() {
      observers.delete(this.cb);
    }
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
  // jsdom has no media stack: playback and seeking are not implemented.
  HTMLMediaElement.prototype.play = play as unknown as HTMLMediaElement["play"];
  HTMLMediaElement.prototype.pause = pause;
  Object.defineProperty(HTMLMediaElement.prototype, "currentTime", { writable: true, value: 0 });
  vi.stubGlobal("matchMedia", (query: string) => ({
    media: query,
    get matches() {
      return media[query] ?? false;
    },
    onchange: null,
    addEventListener: (_: string, listener: () => void) => {
      if (!mediaListeners.has(query)) mediaListeners.set(query, new Set());
      mediaListeners.get(query)?.add(listener);
    },
    removeEventListener: (_: string, listener: () => void) => {
      mediaListeners.get(query)?.delete(listener);
    },
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }));
});

beforeEach(() => {
  media = {};
  motionPref.reduced = null;
  observers.clear();
  mediaListeners.clear();
  play.mockClear();
  pause.mockClear();
  resetVideoRegistry();
});
afterEach(cleanup);

/** A pointer that can hover, with no reduced-motion preference. */
const HOVER_POINTER = { "(hover: hover)": true };

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

  it("renders the same tree whatever useReducedMotion reports, so hydration cannot mismatch", () => {
    motionPref.reduced = false;
    const { container } = render(<Hero />);
    const allowed = container.innerHTML;
    cleanup();

    motionPref.reduced = true;
    const { container: reducedContainer } = render(<Hero />);
    expect(reducedContainer.innerHTML).toBe(allowed);
    // The poster-vs-video choice in particular is not a choice: the video is always there.
    const video = screen.getByTestId("hero-video") as HTMLVideoElement;
    expect(video.tagName).toBe("VIDEO");
    expect(video.getAttribute("poster")).toBe("/landing/hero-poster.jpg");
    // Playback belongs to an effect; an `autoPlay` attribute would have to be branched on.
    expect(video.hasAttribute("autoplay")).toBe(false);
    // The parallax is a motion value bound to `style`, which MotionConfig cannot reach.
    // This hook is what app/globals.css freezes it by; losing it loses the whole guard.
    expect(reducedContainer.querySelector("[data-hero-parallax]")).toBeTruthy();
  });

  it("stops the loop when the preference is turned on mid-session", () => {
    render(<Hero />);
    intersect(true);
    expect(play).toHaveBeenCalled();

    setMedia("(prefers-reduced-motion: reduce)", true);
    expect(pause).toHaveBeenCalled();
    // The observer is torn down with it, so nothing can start the loop again.
    play.mockClear();
    intersect(true);
    expect(play).not.toHaveBeenCalled();
  });

  it("starts the loop once the section is on screen", () => {
    render(<Hero />);
    intersect(true);
    expect(play).toHaveBeenCalled();
  });

  it("never starts the loop under prefers-reduced-motion, and keeps the video element", () => {
    media = { "(prefers-reduced-motion: reduce)": true };
    render(<Hero />);
    intersect(true);
    expect(play).not.toHaveBeenCalled();
    expect(screen.getByTestId("hero-video")).toBeTruthy();
  });

  it("plays the media pair it is handed instead of the bundled one", () => {
    render(<Hero media={{ poster: "/landing/gallery/clip-a.jpg", webm: "/landing/gallery/clip-a.webm", mp4: "/landing/gallery/clip-a.mp4" }} />);
    const video = screen.getByTestId("hero-video") as HTMLVideoElement;
    expect(video.getAttribute("poster")).toBe("/landing/gallery/clip-a.jpg");
    const sources = [...video.querySelectorAll("source")].map((s) => s.getAttribute("src"));
    expect(sources).toEqual(["/landing/gallery/clip-a.webm", "/landing/gallery/clip-a.mp4"]);
  });
});

describe("LandingNav", () => {
  it("renders the same tree whatever useReducedMotion reports, so hydration cannot mismatch", () => {
    motionPref.reduced = false;
    const { container } = render(<LandingNav />);
    const allowed = container.innerHTML;
    cleanup();

    motionPref.reduced = true;
    const { container: reducedContainer } = render(<LandingNav />);
    expect(reducedContainer.innerHTML).toBe(allowed);
    // `data-landing-nav` is what app/globals.css drops the -12px travel by; motion's own
    // reduced-motion handling only snaps it, which is visible on the way out.
    expect(reducedContainer.querySelector("[data-landing-nav]")).toBeTruthy();
  });
});

const STILL: GalleryItem = {
  file: "a.jpg",
  caption: "Rainy night on a city street",
  prompt: "Rainy night on a city street, wet asphalt, cinematic",
  model: "car",
  size: "wide",
  width: 1600,
  height: 1000,
};

const CLIP: GalleryItem = {
  file: "b.jpg",
  poster: "b-poster.jpg",
  preview: "b-preview.webm",
  video: "b-clean.mp4",
  caption: "White studio, soft light",
  prompt: "White studio, soft even light, slow turntable",
  model: "product",
  credit: "Sample product model · CC0",
  size: "large",
  width: 1600,
  height: 1000,
};

const MANIFEST: GalleryItem[] = [STILL, CLIP];

describe("gallery manifest", () => {
  it("accepts still-only entries and clip entries, and fills in the intrinsic size", () => {
    const items = parseGalleryManifest([
      { file: "a.jpg", caption: "A still", prompt: "A still", model: "car", size: "wide" },
      {
        file: "b.jpg",
        poster: "b-poster.jpg",
        preview: "b-preview.webm",
        video: "b-clean.mp4",
        caption: "A clip",
        prompt: "A clip",
        model: "product",
        credit: "Sample model · CC0",
        size: "large",
        placeholder: true,
      },
    ]);
    expect(items).toHaveLength(2);
    expect(items[0].width).toBe(1600);
    expect(items[0].height).toBe(1000);
    expect(isClip(items[0])).toBe(false);
    expect(isClip(items[1])).toBe(true);
    expect(items[1].credit).toBe("Sample model · CC0");
    expect(items[1].placeholder).toBe(true);
  });

  it("treats a placeholder clip as a normal clip", () => {
    const [item] = parseGalleryManifest([
      {
        file: "/landing/hero-poster.jpg",
        preview: "/landing/hero.webm",
        video: "/landing/hero.mp4",
        caption: "Placeholder",
        prompt: "Placeholder",
        model: "car",
        size: "wide",
        placeholder: true,
      },
    ]);
    expect(isClip(item)).toBe(true);
    expect(clipMedia(item)).toEqual({ poster: "/landing/hero-poster.jpg", preview: "/landing/hero.webm", video: "/landing/hero.mp4" });
  });

  it("rejects an entry with a bad model or a missing caption", () => {
    expect(() => parseGalleryManifest([{ file: "a.jpg", caption: "A", prompt: "A", model: "spaceship", size: "wide" }])).toThrow();
    expect(() => parseGalleryManifest([{ file: "a.jpg", prompt: "A", model: "car", size: "wide" }])).toThrow();
  });

  it("resolves relative paths against the gallery folder and leaves absolute ones alone", () => {
    expect(clipMedia(STILL)).toBeNull();
    expect(clipMedia(CLIP)).toEqual({
      poster: "/landing/gallery/b-poster.jpg",
      preview: "/landing/gallery/b-preview.webm",
      video: "/landing/gallery/b-clean.mp4",
    });
  });

  it("takes the hero pair from the first clip entry, or none when the manifest is stills only", () => {
    expect(heroMediaFrom([STILL])).toBeNull();
    expect(heroMediaFrom(MANIFEST)).toEqual({
      poster: "/landing/gallery/b-poster.jpg",
      webm: "/landing/gallery/b-preview.webm",
      mp4: "/landing/gallery/b-clean.mp4",
    });
  });
});

describe("Gallery", () => {
  it("renders every manifest item with its caption and opens a lightbox on click", () => {
    render(<Gallery items={MANIFEST} />);
    const figures = screen.getAllByRole("figure");
    expect(figures).toHaveLength(2);
    expect(within(figures[0]).getByText(/Rainy night on a city street/)).toBeTruthy();
    expect(within(figures[0]).getByRole("img").getAttribute("alt")).toBe("Rainy night on a city street");

    const dialog = screen.getByRole("dialog", { hidden: true }) as HTMLDialogElement;
    expect(dialog.hasAttribute("open")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Open clip: White studio, soft light" }));
    expect(dialog.hasAttribute("open")).toBe(true);
    expect(within(dialog).getByText("White studio, soft light")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(dialog.hasAttribute("open")).toBe(false);
  });

  it("shows the credit line under the grid and any per-item credit", () => {
    render(<Gallery items={MANIFEST} />);
    expect(screen.getByText(GALLERY_CREDIT)).toBeTruthy();
    expect(screen.getAllByText("Sample product model · CC0").length).toBeGreaterThan(0);
  });

  it("gives a clip tile a poster and a play glyph, and leaves a still tile plain", () => {
    render(<Gallery items={MANIFEST} />);
    const [still, clip] = screen.getAllByRole("figure");
    expect(within(still).queryByTestId("clip-glyph")).toBeNull();
    expect(within(still).queryByTestId("clip-preview")).toBeNull();

    expect(within(clip).getByTestId("clip-glyph")).toBeTruthy();
    const preview = within(clip).getByTestId("clip-preview") as HTMLVideoElement;
    expect(preview.getAttribute("poster")).toBe("/landing/gallery/b-poster.jpg");
    expect(preview.getAttribute("preload")).toBe("none");
    expect(preview.hasAttribute("muted") || preview.muted).toBe(true);
    expect(preview.hasAttribute("loop")).toBe(true);
    expect(preview.hasAttribute("playsinline")).toBe(true);
    // Nothing is downloaded before intent.
    expect(preview.hasAttribute("src")).toBe(false);
  });

  it("attaches the preview src and plays it only once the tile is hovered", () => {
    media = HOVER_POINTER;
    render(<Gallery items={MANIFEST} />);
    const clip = screen.getAllByRole("figure")[1];
    const preview = within(clip).getByTestId("clip-preview") as HTMLVideoElement;
    expect(preview.hasAttribute("src")).toBe(false);
    expect(play).not.toHaveBeenCalled();

    fireEvent.mouseOver(within(clip).getByRole("button"));
    expect(preview.getAttribute("src")).toBe("/landing/gallery/b-preview.webm");
    expect(play).toHaveBeenCalled();

    fireEvent.mouseOut(within(clip).getByRole("button"), { relatedTarget: document.body });
    expect(pause).toHaveBeenCalled();
    expect(preview.currentTime).toBe(0);
  });

  it("plays the preview on keyboard focus as well as hover", () => {
    media = HOVER_POINTER;
    render(<Gallery items={MANIFEST} />);
    const clip = screen.getAllByRole("figure")[1];
    fireEvent.focusIn(within(clip).getByRole("button"));
    expect((within(clip).getByTestId("clip-preview") as HTMLVideoElement).getAttribute("src")).toBe("/landing/gallery/b-preview.webm");
    expect(play).toHaveBeenCalled();
  });

  it("never attaches or plays a preview under prefers-reduced-motion", () => {
    media = { ...HOVER_POINTER, "(prefers-reduced-motion: reduce)": true };
    render(<Gallery items={MANIFEST} />);
    const clip = screen.getAllByRole("figure")[1];
    fireEvent.mouseOver(within(clip).getByRole("button"));
    expect((within(clip).getByTestId("clip-preview") as HTMLVideoElement).hasAttribute("src")).toBe(false);
    expect(play).not.toHaveBeenCalled();
  });

  it("skips hover play on a coarse pointer and opens the lightbox on tap", () => {
    media = {}; // no `(hover: hover)`
    render(<Gallery items={MANIFEST} />);
    const clip = screen.getAllByRole("figure")[1];
    const button = within(clip).getByRole("button");
    fireEvent.mouseOver(button);
    expect((within(clip).getByTestId("clip-preview") as HTMLVideoElement).hasAttribute("src")).toBe(false);
    expect(play).not.toHaveBeenCalled();

    fireEvent.click(button);
    expect((screen.getByRole("dialog", { hidden: true }) as HTMLDialogElement).hasAttribute("open")).toBe(true);
  });

  it("plays a clip with controls in the lightbox and shows a plain image for a still", () => {
    render(<Gallery items={MANIFEST} />);
    const dialog = screen.getByRole("dialog", { hidden: true });

    fireEvent.click(screen.getByRole("button", { name: "Open clip: White studio, soft light" }));
    const video = screen.getByTestId("lightbox-video") as HTMLVideoElement;
    expect(video.hasAttribute("controls")).toBe(true);
    expect(video.hasAttribute("autoplay")).toBe(true);
    expect(video.hasAttribute("loop")).toBe(true);
    expect(video.hasAttribute("playsinline")).toBe(true);
    expect(video.getAttribute("src")).toBe("/landing/gallery/b-clean.mp4");
    expect(video.getAttribute("poster")).toBe("/landing/gallery/b-poster.jpg");
    // Caption and prompt sit under the video.
    expect(within(dialog).getByText(CLIP.caption)).toBeTruthy();
    expect(within(dialog).getByText(CLIP.credit as string)).toBeTruthy();

    fireEvent.keyDown(dialog, { key: "Escape" });
    fireEvent.click(screen.getByRole("button", { name: "Open: Rainy night on a city street" }));
    expect(screen.queryByTestId("lightbox-video")).toBeNull();
    expect(within(dialog).getByRole("img").getAttribute("alt")).toBe("Rainy night on a city street");
  });

  it("moves between items with the arrow keys and closes on Escape, restoring focus to the tile", () => {
    render(<Gallery items={MANIFEST} />);
    const dialog = screen.getByRole("dialog", { hidden: true }) as HTMLDialogElement;
    const tile = screen.getByRole("button", { name: "Open: Rainy night on a city street" });
    tile.focus();
    fireEvent.click(tile);
    expect(dialog.hasAttribute("open")).toBe(true);
    expect(within(dialog).getByText(STILL.prompt)).toBeTruthy();

    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(within(dialog).getByText(CLIP.caption)).toBeTruthy();
    fireEvent.keyDown(dialog, { key: "ArrowLeft" });
    expect(within(dialog).getByText(STILL.prompt)).toBeTruthy();
    // Wraps around, and focus still belongs to the tile that opened the dialog.
    fireEvent.keyDown(dialog, { key: "ArrowLeft" });
    expect(within(dialog).getByText(CLIP.caption)).toBeTruthy();

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(dialog.hasAttribute("open")).toBe(false);
    expect(document.activeElement).toBe(tile);
  });
});

describe("video registry", () => {
  it("pauses the video that was playing when another one starts", () => {
    const first = document.createElement("video");
    const second = document.createElement("video");
    playExclusive(first);
    expect(pause).not.toHaveBeenCalled();
    playExclusive(second);
    expect(pause).toHaveBeenCalledTimes(1);
    expect(play).toHaveBeenCalledTimes(2);
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
