import type { SupabaseClient } from "@supabase/supabase-js";
import {
  historyRowToEntry,
  pageRange,
  summariseSubscription,
  toPage,
  type AccountRender,
  type CreditHistoryEntry,
  type CreditHistoryRow,
  type Page,
  type SubscriptionRow,
  type SubscriptionSummary,
} from "@/lib/account/history";
import { apiFetch, supabaseErrorToResult } from "../http";
import { ok, type Result } from "../result";
import type { AccountService } from "../types";

/**
 * Reads with the user's own session, so RLS returns only their rows: `credit_history` (the ledger with a
 * running balance, security_invoker) and `billing_subscriptions`. Renders go through /api/account/renders,
 * which mints the short-lived poster links server-side.
 */
export class SupabaseAccountService implements AccountService {
  constructor(
    private readonly db: () => SupabaseClient,
    private readonly fetchImpl: typeof fetch = (...args) => fetch(...args),
  ) {}

  async creditHistory(page: number): Promise<Result<Page<CreditHistoryEntry>>> {
    const { from, to } = pageRange(page);
    const { data, error } = await this.db()
      .from("credit_history")
      .select("id, amount, reason, project_id, created_at, balance_after, plan, job_status")
      .order("id", { ascending: false })
      .range(from, to);
    if (error) return supabaseErrorToResult(error);
    return ok(toPage((data as CreditHistoryRow[]).map(historyRowToEntry), page));
  }

  async renders(page: number): Promise<Result<Page<AccountRender>>> {
    const p = Math.max(0, Math.floor(page) || 0);
    return apiFetch<Page<AccountRender>>(`/api/account/renders?page=${p}`, {}, this.fetchImpl);
  }

  async subscription(): Promise<Result<SubscriptionSummary | null>> {
    const { data, error } = await this.db()
      .from("billing_subscriptions")
      .select("plan, status, current_period_end, paid_through, canceled_at, scheduled_change")
      .order("updated_at", { ascending: false })
      .limit(10);
    if (error) return supabaseErrorToResult(error);
    return ok(summariseSubscription((data ?? []) as SubscriptionRow[]));
  }
}
