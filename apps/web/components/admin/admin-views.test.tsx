import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { FIXTURE_BILLING, FIXTURE_ERRORS, FIXTURE_FLAGS, FIXTURE_GROWTH, FIXTURE_GROWTH_EMPTY, FIXTURE_JOB_DETAIL, FIXTURE_OVERVIEW, FIXTURE_USER_DETAIL } from "./fixtures";
import { ErrorsView } from "./ErrorsView";
import { FlagsView, parseAllowlist } from "./FlagsView";
import { GrowthView } from "./GrowthView";
import { BillingView } from "./BillingView";
import { OverviewView } from "./OverviewView";
import { RenderDetailView } from "./RenderDetailView";
import { UserDetailView } from "./UserDetailView";
import { auditSummary } from "./AuditTable";
import { fmtCredits, fmtMoney, fmtPct, fmtSeconds } from "@/lib/admin/format";
import { canRefund, canRetry, type AuditRow } from "@/lib/admin/types";

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

  it("billing lists refunds that had nothing to take back (security review L9)", () => {
    const { container } = render(<BillingView data={FIXTURE_BILLING} />);
    const table = within(container).getByRole("table", { name: "Unapplied refunds" });
    expect(table.textContent).toMatch(/Account deleted/);
    expect(table.textContent).toMatch(/No payment applied/);
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

describe("growth, errors and flags", () => {
  afterEach(cleanup);

  it("growth shows the north star (last full week) and funnel step conversion", () => {
    render(<GrowthView growth={FIXTURE_GROWTH} days={30} onDaysChange={() => {}} />);
    const weeks = FIXTURE_GROWTH.north_star.weeks;
    expect(screen.getByTestId("north-star-value").textContent).toBe(String(weeks[weeks.length - 2].renders));
    // signup_start 1310 of landing_view 9420 = 13.9%.
    expect(screen.getByText("13.9% of previous")).toBeTruthy();
    expect(screen.getByRole("table", { name: "Weekly signup cohorts" })).toBeTruthy();
  });

  it("growth refetches the funnel window and survives all-zero data", () => {
    const onDays = vi.fn();
    render(<GrowthView growth={FIXTURE_GROWTH_EMPTY} days={30} onDaysChange={onDays} />);
    expect(screen.getByTestId("north-star-value").textContent).toBe("0");
    expect(screen.getByText("Activation rate").nextSibling?.textContent).toBe("—");
    expect(screen.getByText(/Set GPU_USD_PER_SECOND/)).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "90 days" }));
    expect(onDays).toHaveBeenCalledWith(90);
  });

  it("errors list one row per group, most frequent first", () => {
    render(<ErrorsView errors={FIXTURE_ERRORS} days={7} onDaysChange={() => {}} />);
    const rows = within(screen.getByRole("table", { name: "Client error groups" })).getAllByRole("row");
    expect(rows).toHaveLength(FIXTURE_ERRORS.length + 1);
    expect(rows[1].textContent).toMatch(/37WebGLContextLost/);
    expect(rows[3].textContent).toMatch(/ERR_NETWORK, ABORT_ERR \+1/);
  });

  it("errors show an empty state", () => {
    render(<ErrorsView errors={[]} days={1} onDaysChange={() => {}} />);
    expect(screen.getByText("No client errors in this window.")).toBeTruthy();
  });

  it("turning a kill switch off needs a reason and sends enabled:false", async () => {
    const onUpdate = vi.fn().mockResolvedValue({ ok: true, message: "Saved." });
    render(<FlagsView flags={FIXTURE_FLAGS.filter((f) => f.key === "renders_enabled")} onUpdate={onUpdate} />);
    fireEvent.click(screen.getByRole("button", { name: "Turn off" }));
    const confirm = screen.getByRole("button", { name: "Turn off renders_enabled" });
    expect(confirm.hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "GPU outage" } });
    fireEvent.click(confirm);
    await screen.findByText("Saved.");
    expect(onUpdate).toHaveBeenCalledWith("renders_enabled", expect.objectContaining({ enabled: false, reason: "GPU outage" }));
    expect(onUpdate.mock.calls[0][1].requestId).toMatch(/^[0-9a-f]{32}$/);
  });

  it("the rollout form rejects a bad user id", () => {
    const onUpdate = vi.fn();
    render(<FlagsView flags={FIXTURE_FLAGS.filter((f) => f.key === "finals_enabled")} onUpdate={onUpdate} />);
    expect(screen.getByText("Rollout 50%")).toBeTruthy();
    expect(screen.getByText("+2 allowlisted")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Edit rollout" }));
    fireEvent.change(screen.getByLabelText(/Allowlist/), { target: { value: "not-a-uuid\n3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f" } });
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Beta testers" } });
    expect(screen.getByText(/Not a user id: not-a-uuid/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save rollout" }).hasAttribute("disabled")).toBe(true);
    expect(parseAllowlist("3F2C9A1E-8B7D-4C21-9E55-1A2B3C4D5E6F, 3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f").ids).toHaveLength(1);
  });

  it("emptying a limit sends value null", async () => {
    const onUpdate = vi.fn().mockResolvedValue({ ok: true, message: "Saved." });
    render(<FlagsView flags={FIXTURE_FLAGS.filter((f) => f.key === "daily_gpu_budget_seconds")} onUpdate={onUpdate} />);
    expect(screen.getByText("36,000")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Change" }));
    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Launch day" } });
    fireEvent.click(screen.getByRole("button", { name: "Save: no limit" }));
    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
    expect(onUpdate.mock.calls[0][1]).toMatchObject({ value: null, reason: "Launch day" });
  });

  it("summarises a flag change in the audit log", () => {
    const row = (before: Record<string, unknown>, after: Record<string, unknown>) =>
      ({ id: 9, admin_id: "a", admin_email: null, action: "flag_update", target_type: "feature_flag", target_id: "renders_enabled", reason: "x", detail: { key: "renders_enabled", before, after }, created_at: "" }) as unknown as AuditRow;
    expect(auditSummary(row({ enabled: true, rollout_percent: 100 }, { enabled: false, rollout_percent: 100 }))).toBe("renders_enabled: on → off");
    expect(auditSummary(row({ enabled: true, rollout_percent: 100 }, { enabled: true, rollout_percent: 50 }))).toBe("renders_enabled: rollout 100% → 50%");
    expect(auditSummary(row({ value: null }, { value: 12 }))).toBe("renders_enabled: value — → 12");
  });
});
