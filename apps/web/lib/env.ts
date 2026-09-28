import type { CheckoutItem } from "@/lib/pricing";

/**
 * Environment access in one place.
 *
 * Public values (`NEXT_PUBLIC_*`) are inlined into the client bundle at build time, so they
 * must be present when `next build` / `cf:build` runs (a `.env.production.local` or the CI env).
 * Server secrets are read at request time from `process.env`, which OpenNext fills from the
 * Worker's vars and `wrangler secret`s (and from `.dev.vars` under `wrangler dev`).
 *
 * When the public Supabase pair is absent the app runs on the local in-browser fakes
 * (see lib/services/index.ts), so dev and the unit tests stay hermetic.
 */

export type PublicSupabaseConfig = { url: string; anonKey: string };

/** Pure: picks the Supabase pair out of an env record, or null when either half is missing. */
export function readPublicSupabaseConfig(env: Record<string, string | undefined>): PublicSupabaseConfig | null {
  const url = env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const anonKey = env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim();
  if (!url || !anonKey) return null;
  return { url, anonKey };
}

/** The Supabase pair for this build. Each variable is referenced literally so Next can inline it. */
export function publicSupabaseConfig(): PublicSupabaseConfig | null {
  return readPublicSupabaseConfig({
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  });
}

export type R2Config = {
  accountId: string;
  bucket: string;
  accessKeyId: string;
  secretAccessKey: string;
};

export type ServerConfig = {
  supabase: PublicSupabaseConfig & { serviceRoleKey: string };
  r2: R2Config | null;
};

/** Pure: server-side config from an env record. Missing service role => null (fail closed). */
export function readServerConfig(env: Record<string, string | undefined>): ServerConfig | null {
  const pub = readPublicSupabaseConfig(env);
  const serviceRoleKey = env.SUPABASE_SERVICE_ROLE_KEY?.trim();
  if (!pub || !serviceRoleKey) return null;
  const r2 =
    env.R2_ACCOUNT_ID && env.R2_BUCKET && env.R2_ACCESS_KEY_ID && env.R2_SECRET_ACCESS_KEY
      ? {
          accountId: env.R2_ACCOUNT_ID.trim(),
          bucket: env.R2_BUCKET.trim(),
          accessKeyId: env.R2_ACCESS_KEY_ID.trim(),
          secretAccessKey: env.R2_SECRET_ACCESS_KEY.trim(),
        }
      : null;
  return { supabase: { ...pub, serviceRoleKey }, r2 };
}

/** Server-only. Never call from client code: it reads the service-role secret. */
export function serverConfig(): ServerConfig | null {
  return readServerConfig(process.env);
}

export type PaddleEnvironment = "sandbox" | "production";

/** Pure: sandbox unless explicitly "production" (a typo never charges real cards). */
export function readPaddleEnvironment(value: string | undefined): PaddleEnvironment {
  return value?.trim() === "production" ? "production" : "sandbox";
}

export type PublicPaddleConfig = { clientToken: string; environment: PaddleEnvironment };

/** Paddle.js settings for this build, or null when checkout is not configured. */
export function publicPaddleConfig(): PublicPaddleConfig | null {
  const clientToken = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN?.trim();
  if (!clientToken) return null;
  return { clientToken, environment: readPaddleEnvironment(process.env.NEXT_PUBLIC_PADDLE_ENV) };
}

export type BillingConfig = {
  environment: PaddleEnvironment;
  /** Server API key (`pdl_...`), used for portal sessions and plan changes. */
  apiKey: string | null;
  /** Notification destination secret; verifies webhooks and signs checkout custom data. */
  webhookSecret: string;
  /** Paddle price id per checkout item. A missing entry means that item is not on sale. */
  prices: Partial<Record<CheckoutItem, string>>;
};

const PRICE_ENV = {
  "plan:creator": "PADDLE_PRICE_CREATOR_MONTHLY",
  "plan:pro": "PADDLE_PRICE_PRO_MONTHLY",
  "pack:100": "PADDLE_PRICE_PACK_100",
  "pack:500": "PADDLE_PRICE_PACK_500",
  "pack:2000": "PADDLE_PRICE_PACK_2000",
} as const;

/** Pure: billing config from an env record. No webhook secret => null (fail closed). */
export function readBillingConfig(env: Record<string, string | undefined>): BillingConfig | null {
  const webhookSecret = env.PADDLE_WEBHOOK_SECRET?.trim();
  if (!webhookSecret) return null;
  const prices: BillingConfig["prices"] = {};
  for (const [item, name] of Object.entries(PRICE_ENV) as [keyof typeof PRICE_ENV, string][]) {
    const id = env[name]?.trim();
    if (id && /^pri_[a-z0-9]+$/.test(id)) prices[item] = id;
  }
  return {
    environment: readPaddleEnvironment(env.NEXT_PUBLIC_PADDLE_ENV),
    apiKey: env.PADDLE_API_KEY?.trim() || null,
    webhookSecret,
    prices,
  };
}

/** Server-only: reads the Paddle secrets. */
export function billingConfig(): BillingConfig | null {
  return readBillingConfig(process.env);
}
