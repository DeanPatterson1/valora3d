import { create } from "zustand";
import { services } from "@/lib/services";
import type { CreditTransaction } from "@/lib/schema";

type CreditsState = {
  balance: number;
  ledger: CreditTransaction[];
  loaded: boolean;
  refresh: () => Promise<void>;
  add: (amount: number, reason: "pack_purchase" | "plan_grant") => Promise<void>;
};

export const useCreditsStore = create<CreditsState>((set) => ({
  balance: 0, ledger: [], loaded: false,
  refresh: async () => {
    const [b, l] = await Promise.all([services.credits.balance(), services.credits.ledger()]);
    set({ balance: b.ok ? b.value : 0, ledger: l.ok ? l.value : [], loaded: true });
  },
  add: async (amount, reason) => {
    await services.credits.post({ amount, reason, projectId: null });
    const b = await services.credits.balance();
    set({ balance: b.ok ? b.value : 0 });
  },
}));
