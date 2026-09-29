import { create } from "zustand";
import type { ServiceError } from "@/lib/services";
import { FIRST_CLIP_PACK_ID } from "@/lib/pricing";
import { loadServices } from "@/lib/services/backend";
import type { CreditTransaction } from "@/lib/schema";

type CreditsState = {
  balance: number;
  ledger: CreditTransaction[];
  loaded: boolean;
  /** The once-per-account first-clip pack has been bought: the pricing page hides it. */
  firstClipUsed: boolean;
  error: ServiceError | null;
  refresh: () => Promise<void>;
  add: (amount: number, reason: "pack_purchase" | "plan_grant", packId?: string) => Promise<void>;
};

const firstUsedAfter = (packId: string | undefined, prev: boolean) => prev || packId === FIRST_CLIP_PACK_ID;

export const useCreditsStore = create<CreditsState>((set, get) => ({
  balance: 0, ledger: [], loaded: false, firstClipUsed: false, error: null,
  refresh: async () => {
    const credits = (await loadServices()).credits;
    const [b, l, f] = await Promise.all([credits.balance(), credits.ledger(), credits.firstClipUsed()]);
    // On failure keep the previous balance/ledger rather than showing 0.
    set((s) => ({
      balance: b.ok ? b.value : s.balance,
      ledger: l.ok ? l.value : s.ledger,
      firstClipUsed: f.ok ? f.value : s.firstClipUsed,
      loaded: true,
      error: !b.ok ? b.error : !l.ok ? l.error : null,
    }));
  },
  add: async (amount, reason, packId) => {
    const credits = (await loadServices()).credits;
    const r = await credits.post({ amount, reason, projectId: null, ...(packId ? { packId } : {}) });
    if (!r.ok) { set({ error: r.error }); return; }
    const b = await credits.balance();
    if (!b.ok) { set({ error: b.error }); return; }
    set({ balance: b.value, firstClipUsed: firstUsedAfter(packId, get().firstClipUsed), error: null });
  },
}));
