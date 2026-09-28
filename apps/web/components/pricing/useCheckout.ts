"use client";

import { useCallback, useEffect, useState } from "react";
import { onPaddleEvent, openBillingPortal, startCheckout } from "@/lib/billing/client";
import type { CheckoutItem } from "@/lib/pricing";
import { useAuthStore } from "@/lib/stores/auth";
import { useCreditsStore } from "@/lib/stores/credits";
import { useToastStore } from "@/components/ui/Toast";

/** Webhooks usually land within seconds; re-read the balance a few times after payment. */
const REFRESH_AFTER_MS = [2000, 5000, 10000, 20000];

/**
 * Real checkout (Supabase backend): opens Paddle's overlay for a catalog item. The balance and
 * plan change only when the verified webhook reaches the server, so after payment this re-reads
 * them for a little while instead of adding anything locally.
 */
export function useCheckout() {
  const push = useToastStore((s) => s.push);
  const [pending, setPending] = useState<string | null>(null);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    const off = onPaddleEvent((e) => {
      if (e.name !== "checkout.completed") return;
      push({ kind: "success", message: "Payment received. Your credits will appear in a moment." });
      for (const ms of REFRESH_AFTER_MS) {
        timers.push(setTimeout(() => {
          void useCreditsStore.getState().refresh();
          void useAuthStore.getState().refresh();
        }, ms));
      }
    });
    return () => {
      off();
      timers.forEach(clearTimeout);
    };
  }, [push]);

  const buy = useCallback(
    async (key: string, item: CheckoutItem) => {
      setPending(key);
      try {
        const r = await startCheckout(item);
        if (!r.ok) push({ kind: "danger", message: r.error.message });
        else if (r.value === "changed") {
          push({ kind: "success", message: "Plan changed. Your new credits will appear in a moment." });
          for (const ms of REFRESH_AFTER_MS) setTimeout(() => void useAuthStore.getState().refresh(), ms);
        }
      } finally {
        setPending(null);
      }
    },
    [push],
  );

  const manage = useCallback(async () => {
    setPending("portal");
    try {
      const r = await openBillingPortal();
      if (!r.ok) push({ kind: "danger", message: r.error.message });
    } finally {
      setPending(null);
    }
  }, [push]);

  return { buy, manage, pending };
}
