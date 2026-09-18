import { z } from "zod";
import { CreditTransactionSchema, type CreditTransaction } from "@/lib/schema";
import { STARTING_BALANCE } from "@/lib/pricing";
import { fail, failFrom, ok, type Result } from "../result";
import type { CreditService } from "../types";
import { KEYS, newId, readJson, writeJson } from "./storage";

const Ledger = z.array(CreditTransactionSchema);

export class LocalCreditService implements CreditService {
  private ledgerSync(): CreditTransaction[] {
    const { value } = readJson(KEYS.ledger, Ledger, []);
    if (value.length === 0) {
      const seed: CreditTransaction = {
        id: newId(),
        amount: STARTING_BALANCE,
        reason: "starting_balance",
        projectId: null,
        createdAt: Date.now(),
      };
      writeJson(KEYS.ledger, [seed]);
      return [seed];
    }
    return value;
  }
  async ledger() {
    return ok(this.ledgerSync());
  }
  async balance() {
    return ok(this.ledgerSync().reduce((s, t) => s + t.amount, 0));
  }
  async post(tx: Omit<CreditTransaction, "id" | "createdAt">): Promise<Result<CreditTransaction>> {
    const all = this.ledgerSync();
    const bal = all.reduce((s, t) => s + t.amount, 0);
    if (bal + tx.amount < 0) return fail("insufficient_credits", `You need ${-tx.amount} credits but have ${bal}.`);
    const full: CreditTransaction = { ...tx, id: newId(), createdAt: Date.now() };
    const w = writeJson(KEYS.ledger, [...all, full]);
    return w.ok ? ok(full) : failFrom(w.error);
  }
}
