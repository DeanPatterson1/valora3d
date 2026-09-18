// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { ScenePlan } from "@/lib/schema";
import { BRAND } from "@/lib/brand";
import { PLANS } from "@/lib/pricing";

vi.mock("@/components/viewer/Viewer", () => ({
  Viewer: ({ plan, showPath }: { plan: ScenePlan | null; showPath?: boolean }) => (
    <div data-testid="viewer" data-env={plan?.scene.environment} data-rain={plan?.effects.rain} data-show-path={String(showPath ?? true)} />
  ),
}));
vi.mock("@/components/viewer/loadModel", () => ({
  loadModel: vi.fn(() => new Promise(() => {})),
}));

import { Hero } from "./Hero";
import { PricingTeaser } from "./PricingTeaser";

beforeAll(() => {
  // whileInView needs an observer; jsdom has none.
  class IO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal("IntersectionObserver", IO);
});
afterEach(cleanup);

describe("Hero", () => {
  it("renders the headline, the sub-line and the primary CTA", () => {
    render(<Hero />);
    expect(screen.getByRole("heading", { level: 1, name: BRAND.tagline })).toBeTruthy();
    expect(screen.getByText("Upload a 3D model, describe the shot, get a cinematic render.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Start a project" }).getAttribute("href")).toBe("/projects?new=1");
  });

  it("chips change the plan passed to the viewer", () => {
    render(<Hero />);
    const viewer = screen.getByTestId("viewer");
    // The hero hides the camera path so the car fills the frame.
    expect(viewer.getAttribute("data-show-path")).toBe("false");
    expect(viewer.getAttribute("data-env")).toBe("urban_night");
    expect(Number(viewer.getAttribute("data-rain"))).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Sunset road" }));
    expect(viewer.getAttribute("data-env")).toBe("outdoor_road");
    expect(Number(viewer.getAttribute("data-rain"))).toBe(0);

    fireEvent.click(screen.getByRole("button", { name: "Studio" }));
    expect(viewer.getAttribute("data-env")).toBe("studio_black");
    expect(screen.getByRole("button", { name: "Studio" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Rainy night" }).getAttribute("aria-pressed")).toBe("false");
  });
});

describe("PricingTeaser", () => {
  it("lists the three plans and links to pricing", () => {
    render(<PricingTeaser />);
    const list = screen.getByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(items.map((i) => i.getAttribute("data-plan"))).toEqual(PLANS.map((p) => p.name));
    expect(within(items[1]).getByText("$19/mo")).toBeTruthy();
    expect(screen.getByRole("link", { name: "See pricing" }).getAttribute("href")).toBe("/pricing");
  });
});
