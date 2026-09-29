import { z } from "@/lib/zod";
import { CreditTransactionSchema, type CreditTransaction } from "@/lib/schema";
import { FIRST_CLIP_PACK_ID, STARTING_BALANCE } from "@/lib/pricing";
import { fail, failFrom, ok, type Result } from "../result";
import type { CreditService } from "../types";
import { KEYS, newId, readJson, writeJson } from "./storage";

const Ledger = z.array(CreditTransactionSchema);

export class LocalCreditService implements CreditService {
  private readOrSeedLedger(): CreditTransaction[] {
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
    return ok(this.readOrSeedLedger());
  }
  async balance() {
    return ok(this.readOrSeedLedger().reduce((s, t) => s + t.amount, 0));
  }
  private firstClipSpent(): boolean {
    try {
      return localStorage.getItem(KEYS.firstClip) === "1";
    } catch {
      return false;
    }
  }
  async firstClipUsed() {
    return ok(this.firstClipSpent());
  }
  async post(tx: Omit<CreditTransaction, "id" | "createdAt"> & { packId?: string }): Promise<Result<CreditTransaction>> {
    if (tx.packId === FIRST_CLIP_PACK_ID && this.firstClipSpent()) {
      return fail("first_clip_used", "You've already used the first-clip offer.");
    }
    const all = this.readOrSeedLedger();
    const bal = all.reduce((s, t) => s + t.amount, 0);
    if (bal + tx.amount < 0) return fail("insufficient_credits", `You need ${-tx.amount} credits but have ${bal}.`);
    const { packId, ...row } = tx;
    const full: CreditTransaction = { ...row, id: newId(), createdAt: Date.now() };
    const w = writeJson(KEYS.ledger, [...all, full]);
    if (!w.ok) return failFrom(w.error);
    if (packId === FIRST_CLIP_PACK_ID) {
      try {
        localStorage.setItem(KEYS.firstClip, "1");
      } catch {
        // Private mode: the offer just is not remembered.
      }
    }
    return ok(full);
  }
}
