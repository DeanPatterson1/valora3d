import type { CancelRequestBody, CancelResponse } from "@/lib/billing/cancel";
import type { PortalResponse } from "@/lib/billing/types";
import type { FeedbackKind } from "@/lib/feedback/shared";
import { apiFetch } from "@/lib/services/http";
import { fail, type Result } from "@/lib/services/result";

/**
 * Browser calls for the lifecycle features (Supabase mode only; the UI hides or explains them in Local mode):
 * feedback, the cancel flow, the update-payment-method link and "Download my data".
 */

export function sendFeedback(body: { kind: FeedbackKind; message: string; page?: string; release?: string }, fetchImpl: typeof fetch = fetch): Promise<Result<{ ok: true }>> {
  return apiFetch("/api/feedback", { method: "POST", body: JSON.stringify(body) }, fetchImpl);
}

export function cancelPlan(body: CancelRequestBody, fetchImpl: typeof fetch = fetch): Promise<Result<CancelResponse>> {
  return apiFetch("/api/billing/cancel", { method: "POST", body: JSON.stringify(body) }, fetchImpl);
}

export function paymentMethodUrl(fetchImpl: typeof fetch = fetch): Promise<Result<PortalResponse>> {
  return apiFetch("/api/billing/payment-method", { method: "POST", body: "{}" }, fetchImpl);
}

/** GET /api/account/export as a file download. */
export async function downloadMyData(fetchImpl: typeof fetch = fetch): Promise<Result<{ fileName: string }>> {
  let res: Response;
  try {
    res = await fetchImpl("/api/account/export", { credentials: "same-origin" });
  } catch {
    return fail("offline", "You appear to be offline. Check your connection and try again.");
  }
  if (!res.ok) {
    let message = "Couldn't prepare your data. Try again in a minute.";
    try {
      const body = (await res.json()) as { error?: { message?: string } };
      if (res.status < 500 && body.error?.message) message = body.error.message;
    } catch {
      // Keep the generic message.
    }
    return fail(res.status === 429 ? "rate_limited" : "server", message);
  }
  const blob = await res.blob();
  const fileName = `valora3d-data-${new Date().toISOString().slice(0, 10)}.json`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return { ok: true, value: { fileName } };
}
