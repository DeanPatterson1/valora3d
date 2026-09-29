"use client";

import { useParams } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { AdminShell } from "@/components/admin/AdminShell";
import { AuditTable } from "@/components/admin/AuditTable";
import { BillingView } from "@/components/admin/BillingView";
import { ErrorsView, type ErrorDays } from "@/components/admin/ErrorsView";
import { FlagsView } from "@/components/admin/FlagsView";
import { FeedbackView, type FeedbackFilter } from "@/components/admin/FeedbackView";
import { GrowthView, type FunnelDays } from "@/components/admin/GrowthView";
import {
  FIXTURE_AUDIT,
  FIXTURE_BILLING,
  FIXTURE_ERRORS,
  FIXTURE_FEEDBACK,
  FIXTURE_FLAGS,
  FIXTURE_GROWTH,
  FIXTURE_NOW,
  FIXTURE_JOB_DETAIL,
  FIXTURE_JOBS,
  FIXTURE_OVERVIEW,
  FIXTURE_USER_DETAIL,
  FIXTURE_USERS,
} from "@/components/admin/fixtures";
import { OverviewView } from "@/components/admin/OverviewView";
import { RenderDetailView } from "@/components/admin/RenderDetailView";
import { RenderFilters, RendersTable, type RenderFilter } from "@/components/admin/RendersView";
import { Section } from "@/components/admin/ui";
import { UserDetailView } from "@/components/admin/UserDetailView";
import { UserSearch, UsersTable } from "@/components/admin/UsersView";

/**
 * /dev/admin/<screen>: the owner console with sample data, for design review in Local mode (the real /admin
 * needs the live backend). Actions answer with a canned success. 404 in production (dev layout + proxy).
 */
const BASE = "/dev/admin";
const ok = async () => ({ ok: true as const, message: "Preview only: nothing was changed." });
const noop = () => () => {};

function Screen({ path }: { path: string[] }) {
  const [filter, setFilter] = useState<RenderFilter>({ status: "", user: "" });
  const [funnelDays, setFunnelDays] = useState<FunnelDays>(30);
  const [errorDays, setErrorDays] = useState<ErrorDays>(7);
  const [feedbackFilter, setFeedbackFilter] = useState<FeedbackFilter>("all");
  const [section, id] = path;
  if (section === "renders" && id) return <RenderDetailView detail={FIXTURE_JOB_DETAIL} base={BASE} actions={{ retry: ok, refund: ok }} />;
  if (section === "renders") {
    const jobs = FIXTURE_JOBS.filter((j) => (!filter.status || j.status === filter.status) && (!filter.user || j.user_id === filter.user));
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Renders</h1>
        <RenderFilters value={filter} onChange={setFilter} />
        <RendersTable jobs={jobs} base={BASE} />
      </div>
    );
  }
  if (section === "users" && id) return <UserDetailView detail={FIXTURE_USER_DETAIL} base={BASE} onAdjust={ok} />;
  if (section === "users") {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
        <UserSearch initial="" onSearch={() => {}} />
        <UsersTable users={FIXTURE_USERS} base={BASE} />
      </div>
    );
  }
  if (section === "growth") return <GrowthView growth={FIXTURE_GROWTH} days={funnelDays} onDaysChange={setFunnelDays} />;
  if (section === "errors") return <ErrorsView errors={errorDays === 1 ? FIXTURE_ERRORS.slice(0, 3) : FIXTURE_ERRORS} days={errorDays} onDaysChange={setErrorDays} now={FIXTURE_NOW} />;
  if (section === "feedback") {
    const data = { ...FIXTURE_FEEDBACK, feedback: FIXTURE_FEEDBACK.feedback.filter((f) => feedbackFilter === "all" || f.status === feedbackFilter) };
    return <FeedbackView data={data} filter={feedbackFilter} onFilter={setFeedbackFilter} onStatus={async () => {}} base={BASE} now={FIXTURE_NOW} />;
  }
  if (section === "flags") return <FlagsView flags={FIXTURE_FLAGS} onUpdate={ok} now={FIXTURE_NOW} />;
  if (section === "billing") return <BillingView data={FIXTURE_BILLING} base={BASE} />;
  if (section === "audit") {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
        <Section title="Every admin action" description="Append-only. Who did what, to which account or render, and why.">
          <AuditTable rows={FIXTURE_AUDIT} base={BASE} />
        </Section>
      </div>
    );
  }
  return <OverviewView overview={FIXTURE_OVERVIEW} />;
}

export default function AdminPreviewPage() {
  const params = useParams<{ screen?: string[] }>();
  // Relative times ("3m ago") differ between the server render and the browser: render on the client only.
  const mounted = useSyncExternalStore(noop, () => true, () => false);
  return (
    <div className="fixed inset-0 z-40 overflow-auto bg-bg-0">
      <AdminShell base={BASE}>{mounted ? <Screen path={params.screen ?? []} /> : null}</AdminShell>
    </div>
  );
}
