import { cache } from "react";
import { serverConfig } from "@/lib/env";
import type { PublicShareLookup } from "@/lib/share/types";
import { createPublicShareReader, lookupPublicShare, type PublicShareReader } from "./shareLookup";

/** Server-only: the service-role public reader, or null in Local mode (no backend, so no shares). */
export function publicShareReader(): PublicShareReader | null {
  const config = serverConfig();
  return config ? createPublicShareReader(config) : null;
}

/** One lookup per request, shared by generateMetadata and the page. */
export const loadPublicShare = cache(async (slug: string): Promise<PublicShareLookup> => {
  const reader = publicShareReader();
  if (!reader) return { state: "missing" };
  return lookupPublicShare(reader, slug);
});
