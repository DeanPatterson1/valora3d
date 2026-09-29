"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import type { AuditRow, BillingResponse, JobDetailResponse, JobStatus, Overview, UserDetailResponse, AdminJob, AdminUserRow } from "@/lib/admin/types";
import { AuditTable } from "./AuditTable";
import { BillingView } from "./BillingView";
import { OverviewView } from "./OverviewView";
import { RenderDetailView } from "./RenderDetailView";
import { RenderFilters, RendersTable, type RenderFilter } from "./RendersView";
import { UserDetailView } from "./UserDetailView";
import { UserSearch, UsersTable } from "./UsersView";
import { Loading, Notice, postAdmin, Section, useAdminData } from "./ui";

/** Data containers: each screen GETs its /api/admin route and hands the result to a presentational view. */

function Failed({ error }: { error: string }) {
  return <Notice tone="danger">{error}</Notice>;
}

export function OverviewScreen() {
  const { data, error } = useAdminData<{ overview: Overview }>("/api/admin/overview");
  if (error) return <Failed error={error} />;
  if (!data) return <Loading />;
  return <OverviewView overview={data.overview} />;
}

const STATUSES: readonly string[] = ["queued", "running", "succeeded", "failed", "cancelled"];

export function RendersScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const status = params.get("status") ?? "";
  const filter: RenderFilter = { status: (STATUSES.includes(status) ? status : "") as JobStatus | "", user: params.get("user") ?? "" };
  const qs = new URLSearchParams();
  if (filter.status) qs.set("status", filter.status);
  if (filter.user) qs.set("user", filter.user);
  const { data, error } = useAdminData<{ jobs: AdminJob[] }>(`/api/admin/renders?${qs}`);
  const setFilter = (f: RenderFilter) => {
    const next = new URLSearchParams();
    if (f.status) next.set("status", f.status);
    if (f.user) next.set("user", f.user);
    router.replace(`/admin/renders${next.size ? `?${next}` : ""}`);
  };
  const userLabel = filter.user ? (data?.jobs.find((j) => j.user_id === filter.user)?.email ?? null) : null;
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Renders</h1>
      <RenderFilters value={filter} onChange={setFilter} userLabel={userLabel} />
      {error ? <Failed error={error} /> : !data ? <Loading /> : <RendersTable jobs={data.jobs} />}
    </div>
  );
}

export function RenderDetailScreen({ id }: { id: string }) {
  const { data, error, reload } = useAdminData<JobDetailResponse>(`/api/admin/renders/${encodeURIComponent(id)}`);
  if (error) return <Failed error={error} />;
  if (!data) return <Loading />;
  return (
    <RenderDetailView
      detail={data}
      actions={{
        retry: async ({ reason }) => {
          const r = await postAdmin<{ result: { job_id: string; replay: boolean } }>(`/api/admin/renders/${id}/retry`, { reason: reason || undefined });
          if (!r.ok) return r;
          reload();
          return { ok: true, message: r.data.result.replay ? `Already retried as job ${r.data.result.job_id.slice(0, 8)}.` : `Retry started as job ${r.data.result.job_id.slice(0, 8)}.` };
        },
        refund: async ({ reason, requestId }) => {
          const r = await postAdmin<{ result: { refunded: number; replay: boolean } }>(`/api/admin/renders/${id}/refund`, { reason, request_id: requestId });
          if (!r.ok) return r;
          reload();
          const n = r.data.result.refunded;
          return { ok: true, message: n > 0 ? `Refunded ${n} credits.` : "Nothing to refund: this render was already refunded." };
        },
      }}
    />
  );
}

export function UsersScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const q = params.get("q") ?? "";
  const { data, error } = useAdminData<{ users: AdminUserRow[] }>(`/api/admin/users?q=${encodeURIComponent(q)}`);
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
      <UserSearch initial={q} onSearch={(next) => router.replace(`/admin/users${next ? `?q=${encodeURIComponent(next)}` : ""}`)} />
      {!q && <p className="text-xs text-fg-muted">Newest accounts first. Search by any part of an email, or paste a user id.</p>}
      {error ? <Failed error={error} /> : !data ? <Loading /> : <UsersTable users={data.users} />}
    </div>
  );
}

export function UserDetailScreen({ id }: { id: string }) {
  const { data, error, reload } = useAdminData<UserDetailResponse>(`/api/admin/users/${encodeURIComponent(id)}`);
  if (error) return <Failed error={error} />;
  if (!data) return <Loading />;
  return (
    <UserDetailView
      detail={data}
      onAdjust={async ({ amount, reason, requestId }) => {
        const r = await postAdmin<{ result: { balance: number; replay: boolean } }>(`/api/admin/users/${id}/credits`, { amount, reason, request_id: requestId });
        if (!r.ok) return r;
        reload();
        return { ok: true, message: `${r.data.result.replay ? "Already applied." : "Done."} Balance is now ${r.data.result.balance}.` };
      }}
    />
  );
}

export function BillingScreen() {
  const { data, error } = useAdminData<BillingResponse>("/api/admin/billing");
  if (error) return <Failed error={error} />;
  if (!data) return <Loading />;
  return <BillingView data={data} />;
}

export function AuditScreen() {
  const [limit, setLimit] = useState(100);
  const { data, error } = useAdminData<{ audit: AuditRow[] }>(`/api/admin/audit?limit=${limit}`);
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
      <Section title="Every admin action" description="Append-only. Who did what, to which account or render, and why.">
        {error ? <Failed error={error} /> : !data ? <Loading /> : <AuditTable rows={data.audit} />}
        {data && data.audit.length >= limit && limit < 500 && (
          <button type="button" onClick={() => setLimit(500)} className="w-fit text-sm text-fg-muted hover:text-fg focus-visible:focus-ring">
            Show more
          </button>
        )}
      </Section>
    </div>
  );
}
