import { afterEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { _forceAnalytics, _queued, _resetTracking } from "@/lib/analytics/track";
import { Analytics, ctaFor, signupMethodFor } from "./Analytics";

vi.mock("next/navigation", () => ({ usePathname: () => window.location.pathname }));

const el = (html: string) => {
  const host = document.createElement("div");
  host.innerHTML = html;
  document.body.appendChild(host);
  return host;
};

afterEach(() => {
  document.body.innerHTML = "";
  _forceAnalytics(null);
  _resetTracking();
  window.history.pushState({}, "", "/");
});

describe("CTA and signup capture", () => {
  it("names a CTA by data-cta, else by its target and the page template", () => {
    const host = el('<a href="/signup" data-cta="hero_signup"><span>Start</span></a><a href="/pricing">Pricing</a><a href="/help">Help</a><a href="https://x.com/signup">X</a>');
    const [named, pricing, help, external] = [...host.querySelectorAll("a")];
    expect(ctaFor(named.querySelector("span"), "/")).toBe("hero_signup");
    expect(ctaFor(pricing, "/r/AbCdEfGhIjKlMnOpQrStUvWx")).toBe("pricing:/r/slug");
    expect(ctaFor(help, "/")).toBeNull();
    expect(ctaFor(external, "/")).toBeNull();
  });

  it("tells email and Google sign-up starts apart, only on /signup", () => {
    const host = el('<form><button type="button">Continue with Google</button></form>');
    const button = host.querySelector("button")!;
    const click = new MouseEvent("click", { bubbles: true });
    Object.defineProperty(click, "target", { value: button });
    expect(signupMethodFor(click)).toBeNull();
    window.history.pushState({}, "", "/signup");
    expect(signupMethodFor(click)).toBe("google");
    expect(signupMethodFor(new Event("submit"))).toBe("email");
  });

  it("records the landing view and each signup method once per page", () => {
    _forceAnalytics(true);
    render(<Analytics />);
    expect(_queued().map((e) => e.event)).toEqual(["landing_view"]);
    window.history.pushState({}, "", "/signup");
    const form = el('<form><input name="email"></form>').querySelector("form")!;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(_queued().filter((e) => e.event === "signup_start")).toEqual([{ event: "signup_start", props: { method: "email" }, path: "/signup" }]);
  });
});
