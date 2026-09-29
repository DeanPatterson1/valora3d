import { config } from "zod";

/**
 * The only place the app imports zod from (`import { z } from "@/lib/zod"`), so the browser configures it before
 * any schema is built.
 *
 * Zod 4 compiles object schemas with `new Function` and probes for it with `Function("")`. Under our CSP (no
 * 'unsafe-eval' in production) the probe is caught in JS, but the BROWSER still reports a script-src violation for
 * it. In the browser we run jitless: the interpreted path gives the same results at these payload sizes. On the
 * server the default stays (Workers is already detected and interpreted).
 */
if (typeof window !== "undefined") config({ jitless: true });

export * from "zod";
