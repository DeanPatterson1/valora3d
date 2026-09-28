import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { PublicSupabaseConfig } from "@/lib/env";

let client: SupabaseClient | null = null;

/**
 * The browser Supabase client (anon key + the user's session cookie). Everything it can read or
 * write is limited by RLS; it never sees the service-role key.
 */
export function getBrowserSupabase(config: PublicSupabaseConfig): SupabaseClient {
  client ??= createBrowserClient(config.url, config.anonKey);
  return client;
}
