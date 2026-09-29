// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FeedbackDialog } from "@/components/feedback/FeedbackDialog";
import { ok, fail } from "@/lib/services/result";
import type { SubscriptionSummary } from "@/lib/account/history";
import { CancelPlanDialog } from "./CancelPlanDialog";
import { PastDueBanner } from "./PastDueBanner";

vi.mock("next/navigation", () => ({ usePathname: () => "/projects", useSearchParams: () => new URLSearchParams() }));

beforeEach(() => {
  const proto = HTMLDialogElement.prototype as HTMLDialogElement & { showModal?: () => void; close?: () => void };
  proto.showModal = function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  proto.close = function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
});
afterEach(cleanup);

const PRO: SubscriptionSummary = { plan: "pro", status: "active", next: { kind: "renews", at: Date.parse("2026-10-28T12:00:00Z") } };

describe("CancelPlanDialog", () => {
  it("asks why, offers a cheaper plan and a pause, then cancels at period end", async () => {
    const submit = vi.fn(async () => ok({ outcome: "canceled" as const, at: "2026-10-28T12:00:00Z" }));
    const onChanged = vi.fn();
    render(<CancelPlanDialog open onClose={() => {}} onChanged={onChanged} subscription={PRO} submit={submit} />);
    const next = screen.getByRole("button", { name: "Continue" });
    expect((next as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: "It's too expensive" }));
    fireEvent.change(screen.getByLabelText("Anything else we should know? (optional)"), { target: { value: " Only a few a month " } });
    fireEvent.click(next);
    expect(screen.getByRole("button", { name: "Switch to Creator" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Pause instead" })).toBeTruthy();
    expect(submit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel at period end" }));
    await screen.findByText("Your plan will end");
    expect(submit).toHaveBeenCalledWith({ action: "cancel", reason: "too_expensive", detail: "Only a few a month" });
    expect(onChanged).toHaveBeenCalled();
  });

  it("offers no pause while payment is overdue and no downgrade from Creator; shows errors", async () => {
    const submit = vi.fn(async () => fail("server", "Couldn't reach billing."));
    render(
      <CancelPlanDialog open onClose={() => {}} subscription={{ ...PRO, plan: "creator", status: "past_due" }} submit={submit} initialStep="offer" initialReason="other" />,
    );
    expect(screen.queryByRole("button", { name: "Pause instead" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Switch to Creator" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Cancel at period end" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Couldn't reach billing.");
  });
});

describe("PastDueBanner", () => {
  it("shows only for a past_due plan and opens the payment update", async () => {
    const openPayment = vi.fn(async () => fail<{ url: string }>("server", "nope"));
    const { rerender } = render(<PastDueBanner subscription={{ ...PRO, status: "active" }} openPayment={openPayment} />);
    expect(screen.queryByRole("status")).toBeNull();
    rerender(<PastDueBanner subscription={{ ...PRO, status: "past_due" }} openPayment={openPayment} />);
    expect(screen.getByRole("status").textContent).toContain("didn't go through");
    fireEvent.click(screen.getByRole("button", { name: "Update payment method" }));
    await waitFor(() => expect(openPayment).toHaveBeenCalled());
  });
});

describe("FeedbackDialog", () => {
  it("sends kind, message, the page template and the build", async () => {
    const submit = vi.fn(async () => ok({ ok: true as const }));
    const onClose = vi.fn();
    render(<FeedbackDialog open onClose={onClose} page="/projects/3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f" submit={submit} local={false} />);
    expect(screen.getByText(/We'll attach the page \(\/projects\/\[id\]\)/)).toBeTruthy();
    const send = screen.getByRole("button", { name: "Send" });
    expect((send as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: "Idea" }));
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Loop the turntable" } });
    fireEvent.click(send);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({ kind: "idea", message: "Loop the turntable", page: "/projects/[id]" }));
  });

  it("in Local mode offers email instead of sending", () => {
    render(<FeedbackDialog open onClose={() => {}} page="/projects" local />);
    expect(screen.queryByRole("button", { name: "Send" })).toBeNull();
    expect(screen.getByRole("link", { name: "Email it" }).getAttribute("href")).toMatch(/^mailto:support@valora3d\.com/);
  });
});
