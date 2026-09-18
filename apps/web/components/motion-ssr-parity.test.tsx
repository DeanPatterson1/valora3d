// @vitest-environment jsdom
import type { ReactElement } from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `useReducedMotion()` reads `null` on the server and the real preference on the very first
 * client render. Any server-rendered tree that branches on it hydrates against HTML the
 * server never wrote — not only a different element or attribute, but the inline `style`
 * motion bakes out of `initial`/`animate`/`variants`, which is what the earlier landing bug
 * was. This stub lets a test claim either answer and assert the markup comes out the same.
 *
 * The components below are all reachable from a server render, so they must ship one set of
 * values for everyone. Reduced motion is settled by `<MotionConfig reducedMotion="user">` in
 * app/layout.tsx (it is read at mount and only makes transform transitions instant, so it
 * never touches the rendered values) plus the `data-*` freeze in app/globals.css.
 */
const motionPref = vi.hoisted(() => ({ reduced: null as boolean | null }));
vi.mock("motion/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react")>();
  return { ...actual, useReducedMotion: () => motionPref.reduced };
});

import TokensPage from "../app/(app)/dev/tokens/page";
import { RenderResult } from "./studio/RenderResult";
import type { RenderJob } from "@/lib/schema";

/** `null` is the only answer a server render can give; the other two are first-client-render answers. */
const SERVER = null;
const CLIENT_ANSWERS: Array<[string, boolean]> = [
  ["the preference is on", true],
  ["the preference is off", false],
];

/** Render `ui` with `useReducedMotion()` pinned to `pref`, and return the part that matters. */
function markup(ui: ReactElement, pref: boolean | null, pick: (container: HTMLElement) => Element | null): string {
  motionPref.reduced = pref;
  const { container } = render(ui);
  const el = pick(container);
  expect(el).toBeTruthy();
  const html = el!.outerHTML;
  cleanup();
  return html;
}

afterEach(() => {
  cleanup();
  motionPref.reduced = null;
});

const COMPLETE_JOB: RenderJob = {
  id: "job-1", projectId: "p1", versionId: "v1", kind: "final", target: "local",
  status: "COMPLETE", frame: 300, totalFrames: 300, error: null, resultUrl: null,
};

describe("RenderResult", () => {
  // /dev/render-states mounts this section straight into the page, so `initial="hidden"`
  // is rendered on the server: its `style` is hydrated markup, not a client-only detail.
  const pick = (c: HTMLElement) => c.querySelector('section[aria-label="Render result"]');

  it("bakes its hidden state into the rendered style, so the parity below is load-bearing", () => {
    const html = markup(<RenderResult job={COMPLETE_JOB} onRegenerate={() => {}} />, SERVER, pick);
    expect(html).toMatch(/transform:\s*translateY\(12px\)\s*scale\(0\.98\)/);
  });

  for (const [label, pref] of CLIENT_ANSWERS) {
    it(`renders the same tree when ${label} as it does on the server`, () => {
      const server = markup(<RenderResult job={COMPLETE_JOB} onRegenerate={() => {}} />, SERVER, pick);
      const client = markup(<RenderResult job={COMPLETE_JOB} onRegenerate={() => {}} />, pref, pick);
      expect(client).toBe(server);
    });
  }
});

describe("/dev/tokens motion section", () => {
  // A "use client" page is still server-rendered by Next: nothing here is behind a dynamic
  // import with `ssr: false`, so the demos' `initial="hidden"` style is in the server HTML.
  const pick = (c: HTMLElement) => c.querySelector('section[aria-labelledby="motion"]');

  for (const [label, pref] of CLIENT_ANSWERS) {
    it(`renders the same section when ${label} as it does on the server`, () => {
      const server = markup(<TokensPage />, SERVER, pick);
      const client = markup(<TokensPage />, pref, pick);
      expect(client).toBe(server);
    });
  }

  it("keeps the data-motion-demo hook the reduced-motion freeze is written against", () => {
    // `reducedMotion="user"` only snaps `fadeRise.exit`'s 12px to its target, which lands
    // while the chip is still opaque. app/globals.css drops the travel by this attribute;
    // losing it loses the whole guard.
    const html = markup(<TokensPage />, SERVER, pick);
    expect(html).toContain("data-motion-demo");
  });
});
