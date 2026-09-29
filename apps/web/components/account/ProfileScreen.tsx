"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Badge, Button, Field, TabPanel, Tabs, cx, useToastStore } from "@/components/ui";
import { useAuthStore } from "@/lib/stores/auth";
import { useCreditsStore } from "@/lib/stores/credits";
import { useProjectsStore } from "@/lib/stores/projects";
import { relativeTime } from "@/components/dashboard/meta";
import { services } from "@/lib/services";
import { useCheckout } from "@/components/pricing/useCheckout";
import { Avatar } from "./Avatar";
import { PLAN_LABEL } from "./planLabel";
import { UsageBilling } from "./UsageBilling";

export type ProfileTab = "overview" | "billing";
const TABS = [
  { id: "overview", label: "Overview" },
  { id: "billing", label: "Usage & billing" },
];

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-line bg-bg-1 px-5 py-5">
      <span className="text-3xl font-semibold tracking-tight tabular text-fg">{value === null ? "—" : value.toLocaleString("en-US")}</span>
      <span className="text-xs text-fg-muted">{label}</span>
    </div>
  );
}

export function ProfileScreen({ initialTab = "overview" }: { initialTab?: ProfileTab }) {
  const user = useAuthStore((s) => s.user);
  const updateProfile = useAuthStore((s) => s.updateProfile);
  const push = useToastStore((s) => s.push);
  const projects = useProjectsStore((s) => s.projects);
  const versionCounts = useProjectsStore((s) => s.versionCounts);
  const projectsLoaded = useProjectsStore((s) => s.loaded);
  const balance = useCreditsStore((s) => s.balance);
  const creditsLoaded = useCreditsStore((s) => s.loaded);
  const ledger = useCreditsStore((s) => s.ledger);
  const billing = useCheckout();

  const [tab, setTab] = useState<ProfileTab>(initialTab);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [nameError, setNameError] = useState<string | undefined>();
  const editButtonRef = useRef<HTMLButtonElement>(null);
  // Read once per mount: "2 h ago" does not need to tick on this page.
  const [now] = useState(() => Date.now());

  // The stores are refreshed by the sidebar on mount; this page only reads them.
  useEffect(() => {
    if (!projectsLoaded) void useProjectsStore.getState().refresh();
  }, [projectsLoaded]);

  if (!user) return null;

  const versions = Object.values(versionCounts).reduce((s, n) => s + n, 0);
  const spent = ledger.filter((t) => t.amount < 0).reduce((s, t) => s - t.amount, 0);
  const recent = [...projects].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 5);

  // Closing the inline edit puts focus back on the Edit button (it remounts next frame).
  const stopEdit = () => {
    setEditing(false);
    requestAnimationFrame(() => editButtonRef.current?.focus());
  };
  const startEdit = () => {
    setDraft(user.name);
    setNameError(undefined);
    setEditing(true);
  };
  const saveName = async () => {
    const name = draft.trim();
    if (!name) {
      setNameError("Enter your name.");
      return;
    }
    if (name !== user.name) {
      const ok = await updateProfile({ name });
      if (!ok) {
        push({ kind: "danger", message: useAuthStore.getState().error?.message ?? "Could not save." });
        return;
      }
      push({ kind: "success", message: "Name saved" });
    }
    stopEdit();
  };

  return (
    <div className="mx-auto w-full max-w-[1100px] px-5 pb-16 pt-16 sm:px-8 md:pt-12">
      <div className="mb-8 flex flex-col gap-3 border-b border-line pb-6">
        <h1 className="text-3xl font-semibold tracking-[-0.04em] text-fg sm:text-4xl">Profile</h1>
        <p className="text-sm text-fg-muted">Your account and activity in this browser.</p>
      </div>
      <header className="mb-8 flex items-start gap-4 sm:items-center sm:gap-6">
        <Avatar name={user.name} seed={user.avatarSeed} size="lg" />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {editing ? (
            <form
              className="flex max-w-sm flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void saveName();
              }}
            >
              <Field
                label="Name"
                name="name"
                autoFocus
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value);
                  if (nameError) setNameError(undefined);
                }}
                onKeyDown={(e) => e.key === "Escape" && stopEdit()}
                error={nameError}
                className="min-w-0 basis-full sm:flex-1 sm:basis-auto"
              />
              <Button type="submit" variant="primary" className={cx(nameError && "mb-7")}>
                Save
              </Button>
              <Button onClick={stopEdit} className={cx(nameError && "mb-7")}>
                Cancel
              </Button>
            </form>
          ) : (
            <div className="flex items-center gap-3">
              <h2 className="min-w-0 break-words text-2xl font-semibold tracking-tight text-fg">{user.name}</h2>
              <Button ref={editButtonRef} size="sm" variant="ghost" onClick={startEdit} aria-label="Edit name">
                Edit
              </Button>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <span className="min-w-0 break-all text-sm text-fg-muted">{user.email}</span>
            <Badge>{PLAN_LABEL[user.plan]}</Badge>
            {services.backend === "supabase" && user.plan !== "free" && (
              <Button size="sm" variant="ghost" loading={billing.pending === "portal"} onClick={() => void billing.manage()}>
                Manage billing
              </Button>
            )}
          </div>
        </div>
      </header>

      <div className="mb-8">
        <Tabs id="profile" label="Profile sections" items={TABS} value={tab} onChange={(id) => setTab(id as ProfileTab)} />
      </div>

      <TabPanel tabsId="profile" id="billing" active={tab === "billing"} className="focus-visible:focus-ring rounded-sm">
        <UsageBilling />
      </TabPanel>

      <TabPanel tabsId="profile" id="overview" active={tab === "overview"} className="focus-visible:focus-ring rounded-sm">
        <div role="group" aria-label="Usage" aria-busy={!projectsLoaded || !creditsLoaded} className="mb-10 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Projects" value={projectsLoaded ? projects.length : null} />
          <Stat label="Scene versions" value={projectsLoaded ? versions : null} />
          <Stat label="Credits left" value={creditsLoaded ? balance : null} />
          <Stat label="Credits spent" value={creditsLoaded ? spent : null} />
        </div>

        <section aria-labelledby="recent" className="flex flex-col gap-3">
          <h2 id="recent" className="text-lg font-semibold tracking-tight text-fg">
            Recent projects
          </h2>
          {!projectsLoaded ? <p role="status" className="text-sm text-fg-muted">Loading projects…</p> : recent.length === 0 ? (
            <p className="text-sm text-fg-muted">
              No projects yet.{" "}
              <Link href="/projects?new=1" className="text-fg underline-offset-4 hover:underline focus-visible:focus-ring">
                Start one
              </Link>
            </p>
          ) : (
            <ul className="flex flex-col rounded-lg border border-line bg-bg-1 px-2">
              {recent.map((p) => (
                <li key={p.id} className="border-b border-line last:border-b-0">
                  <Link
                    href={`/projects/${p.id}`}
                    className="flex min-h-16 flex-col justify-center gap-1 rounded-sm px-3 py-3 text-sm text-fg transition-colors hover:bg-bg-3 focus-visible:focus-ring sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                  >
                    <span className="min-w-0 truncate">{p.name}</span>
                    <span className="shrink-0 text-xs text-fg-muted">
                      {versionCounts[p.id] ?? 0} {versionCounts[p.id] === 1 ? "version" : "versions"} · {relativeTime(p.updatedAt, now)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </TabPanel>
    </div>
  );
}
