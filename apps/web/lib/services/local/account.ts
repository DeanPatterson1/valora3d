import { localHistory, paginate, type AccountRender, type CreditHistoryEntry, type Page, type SubscriptionSummary } from "@/lib/account/history";
import { failFrom, ok, type Result } from "../result";
import type { AccountService, CreditService } from "../types";

/** Local mode: history from the in-browser ledger; no cloud renders and no subscriptions exist here. */
export class LocalAccountService implements AccountService {
  constructor(private readonly credits: CreditService) {}

  async creditHistory(page: number): Promise<Result<Page<CreditHistoryEntry>>> {
    const r = await this.credits.ledger();
    if (!r.ok) return failFrom(r.error);
    return ok(paginate(localHistory(r.value), page));
  }

  async renders(page: number): Promise<Result<Page<AccountRender>>> {
    return ok({ items: [], page: Math.max(0, Math.floor(page) || 0), hasMore: false });
  }

  async subscription(): Promise<Result<SubscriptionSummary | null>> {
    return ok(null);
  }
}
