"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, useToastStore } from "@/components/ui";
import { paymentMethodUrl } from "@/lib/account/lifecycleClient";
import type { SubscriptionSummary } from "@/lib/account/history";
import { services, type Result } from "@/lib/services";
import type { PortalResponse } from "@/lib/billing/types";
import { PLAN_LABEL } from "./planLabel";

/** Studio pages get the whole screen; the banner shows on the dashboard, profile and settings. */
const STUDIO = /^\/projects\/[^/]+/;

/** The app shell's banner while the plan's last payment failed (billing_subscriptions.status = past_due). */
export function PastDueBanner({
  subscription: given,
  openPayment = paymentMethodUrl,
}: {
  /** Preview / tests: skip the fetch. */
  subscription?: SubscriptionSummary | null;
  openPayment?: () => Promise<Result<PortalResponse>>;
}) {
  const pathname = usePathname() ?? "";
  const push = useToastStore((s) => s.push);
  const [fetched, setFetched] = useState<SubscriptionSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const server = services.backend === "supabase";

  useEffect(() => {
    if (given !== undefined || !server) return;
    let live = true;
    void services.account.subscription().then((r) => live && r.ok && setFetched(r.value));
    return () => {
      live = false;
    };
  }, [given, server]);

  const sub = given !== undefined ? given : fetched;
  if (!sub || sub.status !== "past_due" || STUDIO.test(pathname)) return null;

  const update = async () => {
    setBusy(true);
    const r = await openPayment();
    setBusy(false);
    if (r.ok) window.location.assign(r.value.url);
    else push({ kind: "danger", message: r.error.message });
  };

  return (
    <div role="status" className="flex flex-col gap-3 border-b border-line bg-bg-2 py-3 pl-16 pr-5 sm:flex-row sm:items-center sm:justify-between sm:pr-8 md:pl-8">
      <p className="text-sm text-fg">
        <span className="font-medium">Your last payment didn&apos;t go through.</span>{" "}
        <span className="text-fg-muted">Update your payment method to keep {PLAN_LABEL[sub.plan]}. Paddle retries automatically in the meantime.</span>
      </p>
      <Button variant="primary" size="sm" className="shrink-0 self-start sm:self-auto" loading={busy} onClick={() => void update()}>
        Update payment method
      </Button>
    </div>
  );
}
