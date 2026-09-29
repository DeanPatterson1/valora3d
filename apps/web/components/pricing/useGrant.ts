"use client";

import { useCallback, useState } from "react";
import { useCreditsStore } from "@/lib/stores/credits";
import { useToastStore } from "@/components/ui/Toast";

type Reason = "plan_grant" | "pack_purchase";

/**
 * Posts credits to the local ledger and reports the outcome as a toast.
 * Returns the grant function and a key for whichever grant is in flight.
 */
export function useGrant() {
  const add = useCreditsStore((s) => s.add);
  const push = useToastStore((s) => s.push);
  const [pending, setPending] = useState<string | null>(null);

  const grant = useCallback(
    async (key: string, credits: number, reason: Reason, packId?: string) => {
      setPending(key);
      try {
        await add(credits, reason, packId);
        const error = useCreditsStore.getState().error;
        if (error) {
          push({ kind: "danger", message: error.message });
        } else {
          push({ kind: "success", message: `Added ${credits.toLocaleString("en-US")} credits` });
        }
      } finally {
        setPending(null);
      }
    },
    [add, push],
  );

  return { grant, pending };
}
