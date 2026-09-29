import { test as base, expect } from "@playwright/test";

/**
 * `test` with a Content-Security-Policy guard: every page in the context records `securitypolicyviolation` events
 * (fired by the browser whenever the CSP blocks a script, style, frame, image or request), and the test fails at
 * teardown if any of this site's own documents saw one. The nonce-based script-src (lib/securityHeaders.ts) breaks
 * silently otherwise: a blocked inline script looks like a page that "just never hydrated".
 * Opt out for one test with `test.use({ cspGuard: false })`.
 */
type Violation = { directive: string; blocked: string; document: string; sample: string };

export const test = base.extend<{ cspGuard: boolean }>({
  cspGuard: [true, { option: true }],
  context: async ({ context, cspGuard }, use) => {
    if (cspGuard) {
      await context.addInitScript(() => {
        const w = window as unknown as { __cspViolations?: unknown[] };
        w.__cspViolations = [];
        document.addEventListener("securitypolicyviolation", (e) => {
          w.__cspViolations!.push({ directive: e.effectiveDirective, blocked: e.blockedURI, document: e.documentURI, sample: (e.sample || "").slice(0, 80) });
        });
      });
    }
    await use(context);
    if (!cspGuard) return;
    const found: Violation[] = [];
    for (const page of context.pages()) {
      if (page.isClosed()) continue;
      const own = new URL(page.url() === "about:blank" ? "http://none.invalid" : page.url()).origin;
      const list = (await page.evaluate(() => (window as unknown as { __cspViolations?: Violation[] }).__cspViolations ?? []).catch(() => [])) as Violation[];
      found.push(...list.filter((v) => new URL(v.document).origin === own));
    }
    expect(found, `CSP violations:\n${JSON.stringify(found, null, 2)}`).toEqual([]);
  },
});

export { expect };
