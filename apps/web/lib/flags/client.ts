"use client";

import { useEffect, useState } from "react";
import type { KillSwitch } from "./flags";

/**
 * Browser read of the kill switches (GET /api/flags, cached 30 s by the browser and here for the page's life), for
 * friendly UI ahead of an action: e.g. hide "Render final" while finals are paused. The server refuses on its own
 * regardless, so a stale or failed read only changes what is shown. Until loaded (or on error) everything reads on.
 */
export type PublicFlags = Record<KillSwitch, boolean>;

const ALL_ON: PublicFlags = {
  renders_enabled: true,
  finals_enabled: true,
  signups_enabled: true,
  sharing_enabled: true,
  checkout_enabled: true,
};

let pending: Promise<PublicFlags> | null = null;

export function fetchFlags(): Promise<PublicFlags> {
  pending ??= fetch("/api/flags", { credentials: "same-origin" })
    .then(async (res) => {
      if (!res.ok) return ALL_ON;
      const body = (await res.json()) as { flags?: Partial<PublicFlags> };
      return { ...ALL_ON, ...(body.flags ?? {}) };
    })
    .catch(() => ALL_ON);
  return pending;
}

export function useFlags(): PublicFlags {
  const [flags, setFlags] = useState<PublicFlags>(ALL_ON);
  useEffect(() => {
    let live = true;
    void fetchFlags().then((f) => live && setFlags(f));
    return () => {
      live = false;
    };
  }, []);
  return flags;
}
