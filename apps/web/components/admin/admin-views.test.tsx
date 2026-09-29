import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FIXTURE_BILLING, FIXTURE_JOB_DETAIL, FIXTURE_OVERVIEW, FIXTURE_USER_DETAIL } from "./fixtures";
import { BillingView } from "./BillingView";
import { OverviewView } from "./OverviewView";
import { RenderDetailView } from "./RenderDetailView";
import { UserDetailView } from "./UserDetailView";
import { auditSummary } from "./AuditTable";
import { fmtCredits, fmtMoney, fmtPct, fmtSeconds } from "@/lib/admin/format";
import { canRefund, canRetry } from "@/lib/admin/types";

describe("admin views", () => {
  it("overview shows the headline numbers and switches windows", () => {
    render(<OverviewView overview={FIXTURE_OVERVIEW} />);
    expect(screen.getByText("Paying users").nextSibling?.textContent).toBe("80");
    fireEvent.click(screen.getByRole("tab", { name: "30 days" }));
    expect(screen.getByText("Gross, USD").nextSibling?.textContent).toBe(fmtMoney(48_300 * 30, "USD"));
  });

  it("render detail offers only the actions the job allows, and hides operator data behind disclosure", () => {
    render(<RenderDetailView detail={FIXTURE_JOB_DETAIL} actions={{ retry: vi.fn(), refund: vi.fn() }} />);
    expect(screen.getByRole("button", { name: "Retry render" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Refund credits" })).toBeNull();
    expect(screen.getByText(/CUDA out of memory/)).toBeTruthy();
    expect(screen.getByText("Log tail").closest("details")?.open).toBe(true);
    expect(screen.getByText("Pin (versions and hashes)").closest("details")?.open).toBe(false);
  });

  it("a credit adjustment needs a reason, sends a signed amount, and reuses its request id when retried", async () => {
    const onAdjust = vi.fn().mockResolvedValueOnce({ ok: false, error: "Network error." }).mockResolvedValueOnce({ ok: true, message: "Done." });
    render(<UserDetailView detail={FIXTURE_USER_DETAIL} onAdjust={onAdjust} />);
    fireEvent.click(screen.getByRole("button", { name: "Adjust credits" }));
    fireEvent.click(screen.getByRole("radio", { name: "deduct" }));
    fireEvent.change(screen.getByLabelText("Credits"), { target: { value: "40" } });
    const confirm = screen.getByRole("button", { name: "Deduct 40 credits" });
    expect(confirm.hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Chargeback" } });
    fireEvent.click(confirm);
    await screen.findByText("Network error.");
    fireEvent.click(screen.getByRole("button", { name: "Deduct 40 credits" }));
    await screen.findByText("Done.");
    expect(onAdjust).toHaveBeenCalledTimes(2);
    const [first, second] = onAdjust.mock.calls.map((c) => c[0]);
    expect(first).toMatchObject({ amount: -40, reason: "Chargeback" });
    expect(second.requestId).toBe(first.requestId);
    // A new action after a success gets a new id.
    fireEvent.click(screen.getByRole("button", { name: "Adjust credits" }));
    fireEvent.click(screen.getByRole("radio", { name: "grant" }));
    fireEvent.change(screen.getByLabelText("Credits"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Goodwill" } });
    onAdjust.mockResolvedValueOnce({ ok: true, message: "Done again." });
    fireEvent.click(screen.getByRole("button", { name: "Grant 5 credits" }));
    await waitFor(() => expect(onAdjust).toHaveBeenCalledTimes(3));
    expect(onAdjust.mock.calls[2][0].requestId).not.toBe(first.requestId);
  });

  it("billing leads with what needs attention", () => {
    render(<BillingView data={FIXTURE_BILLING} />);
    expect(screen.getByRole("alert").textContent).toMatch(/2 webhook events need a look/);
    expect(screen.getByRole("table", { name: "Webhook errors" })).toBeTruthy();
  });
});

describe("admin rules and formatting", () => {
  it("offers retry and refund on the same terms the server enforces", () => {
    expect(canRetry({ status: "failed", retryable: true, upload_id: "u" })).toBe(true);
    expect(canRetry({ status: "failed", retryable: false, upload_id: "u" })).toBe(false);
    expect(canRetry({ status: "cancelled", retryable: true, upload_id: "u" })).toBe(false);
    expect(canRefund({ status: "cancelled", cost_credits: 3, refunded_credits: 0 })).toBe(true);
    expect(canRefund({ status: "failed", cost_credits: 3, refunded_credits: 3 })).toBe(false);
    expect(canRefund({ status: "succeeded", cost_credits: 3, refunded_credits: 0 })).toBe(false);
  });

  it("formats compactly", () => {
    expect(fmtCredits(25)).toBe("+25");
    expect(fmtCredits(-100)).toBe("−100");
    expect(fmtSeconds(212.4)).toBe("3m 32s");
    expect(fmtPct(4 / 59)).toBe("6.8%");
    expect(fmtMoney(4900, "USD")).toMatch(/USD\s?49\.00/);
    expect(auditSummary({ id: 1, admin_id: "a", admin_email: null, action: "credits_adjust", target_type: "user", target_id: "u", reason: "x", detail: { amount: -10, balance_after: 5 }, created_at: "" })).toBe(
      "−10 → balance 5",
    );
  });
});
