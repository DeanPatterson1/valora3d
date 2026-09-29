import type { SupabaseClient } from "@supabase/supabase-js";
import { FIRST_CLIP_PACK_ID } from "@/lib/pricing";
import type { CreditTransaction } from "@/lib/schema";
import { supabaseErrorToResult } from "../http";
import { fail, ok, type Result } from "../result";
import type { CreditService } from "../types";
import { rowToTransaction, type LedgerRow } from "./rows";

/**
 * Reads the server ledger (RLS: own rows only). The browser never moves credits: a scene version is charged by
 * the server when it is saved (POST /api/projects/:id/versions), a render when it is created (/api/renders), and
 * credits are added only by the payment webhook.
 */
export class SupabaseCreditService implements CreditService {
  constructor(private readonly db: () => SupabaseClient) {}

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

  /** billing_transactions.pack_id = 'first' (RLS: own rows only): the checkout route and the database refuse a second one. */
  async firstClipUsed(): Promise<Result<boolean>> {
    const { data, error } = await this.db().from("billing_transactions").select("id").eq("pack_id", FIRST_CLIP_PACK_ID).limit(1);
    if (error) return supabaseErrorToResult(error);
    return ok((data ?? []).length > 0);
  }

  async post(tx: Omit<CreditTransaction, "id" | "createdAt"> & { packId?: string }): Promise<Result<CreditTransaction>> {
    if (tx.amount >= 0) {
      return fail("checkout_required", "Credits are added through checkout, which isn't open yet.");
    }
    return fail("invalid_request", "Credits are charged by the server when a scene is saved or a render starts.");
  }
}
