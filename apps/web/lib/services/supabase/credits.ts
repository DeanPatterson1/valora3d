import type { SupabaseClient } from "@supabase/supabase-js";
import type { CreditTransaction } from "@/lib/schema";
import { apiFetch, supabaseErrorToResult } from "../http";
import { fail, ok, type Result } from "../result";
import type { CreditService } from "../types";
import { rowToTransaction, type LedgerRow } from "./rows";

const SPENDABLE = new Set(["scene_generation", "prompt_edit", "preview_render"]);

/**
 * Reads the server ledger (RLS: own rows only). Spending goes through /api/credits/spend, which
 * prices the action server-side; the browser can never add credits (that is the payment webhook).
 */
export class SupabaseCreditService implements CreditService {
  constructor(
    private readonly db: () => SupabaseClient,
    private readonly newRef: () => string = () => crypto.randomUUID().replace(/-/g, ""),
  ) {}

  async balance(): Promise<Result<number>> {
    const { data, error } = await this.db().from("credit_balances").select("balance").maybeSingle<{ balance: number }>();
    if (error) return supabaseErrorToResult(error);
    return ok(data?.balance ?? 0);
  }

  async ledger(): Promise<Result<CreditTransaction[]>> {
    const { data, error } = await this.db()
      .from("credit_ledger")
      .select("id, amount, reason, project_id, created_at")
      .order("created_at", { ascending: true })
      .limit(500);
    if (error) return supabaseErrorToResult(error);
    return ok((data as LedgerRow[]).map(rowToTransaction));
  }

  async post(tx: Omit<CreditTransaction, "id" | "createdAt">): Promise<Result<CreditTransaction>> {
    if (tx.amount >= 0) {
      return fail("checkout_required", "Credits are added through checkout, which isn't open yet.");
    }
    if (!SPENDABLE.has(tx.reason)) return fail("invalid_request", "That action can't be charged here.");
    const r = await apiFetch<{ transaction: LedgerRow }>("/api/credits/spend", {
      method: "POST",
      body: JSON.stringify({ reason: tx.reason, amount: tx.amount, projectId: tx.projectId, ref: this.newRef() }),
    });
    return r.ok ? ok(rowToTransaction(r.value.transaction)) : r;
  }
}
