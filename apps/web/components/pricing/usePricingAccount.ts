"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/lib/stores/auth";

/** Public pricing can read the existing session without mounting the gated app shell. */
export function usePricingAccount() {
  const user = useAuthStore((s) => s.user);
  const loaded = useAuthStore((s) => s.loaded);
  const refresh = useAuthStore((s) => s.refresh);
  useEffect(() => {
    if (!loaded) void refresh();
  }, [loaded, refresh]);
  return user;
}
