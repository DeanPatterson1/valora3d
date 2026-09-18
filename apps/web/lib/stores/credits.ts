import { create } from "zustand";
import { services, type ServiceError } from "@/lib/services";
import type { CreditTransaction } from "@/lib/schema";

type CreditsState = {
  balance: number;
  ledger: CreditTransaction[];
  loaded: boolean;
  error: ServiceError | null;
  refresh: () => Promise<void>;
  add: (amount: number, reason: "pack_purchase" | "plan_grant") => Promise<void>;
};

export const useCreditsStore = create<CreditsState>((set) => ({
  balance: 0, ledger: [], loaded: false, error: null,
  refresh: async () => {
    const [b, l] = await Promise.all([services.credits.balance(), services.credits.ledger()]);
    // On failure keep the previous balance/ledger rather than showing 0.
    set((s) => ({
      balance: b.ok ? b.value : s.balance,
      ledger: l.ok ? l.value : s.ledger,
      loaded: true,
      error: !b.ok ? b.error : !l.ok ? l.error : null,
    }));
  },
  add: async (amount, reason) => {
    const r = await services.credits.post({ amount, reason, projectId: null });
    if (!r.ok) { set({ error: r.error }); return; }
    const b = await services.credits.balance();
    if (!b.ok) { set({ error: b.error }); return; }
    set({ balance: b.value, error: null });
  },
}));
