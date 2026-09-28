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
