"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Button, Field, cx, useToastStore } from "@/components/ui";
import { useAuthStore } from "@/lib/stores/auth";
import { useCreditsStore } from "@/lib/stores/credits";
import { useProjectsStore } from "@/lib/stores/projects";
import { relativeTime } from "@/components/dashboard/meta";
import { Avatar } from "./Avatar";
import { PLAN_LABEL } from "./planLabel";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-line bg-bg-2 px-4 py-3">
      <span className="text-2xl font-semibold tracking-tight tabular text-fg">{value.toLocaleString("en-US")}</span>
      <span className="text-xs text-fg-muted">{label}</span>
    </div>
  );
}

export function ProfileScreen() {
  const user = useAuthStore((s) => s.user);
  const updateProfile = useAuthStore((s) => s.updateProfile);
  const push = useToastStore((s) => s.push);
  const projects = useProjectsStore((s) => s.projects);
  const versionCounts = useProjectsStore((s) => s.versionCounts);
  const projectsLoaded = useProjectsStore((s) => s.loaded);
  const balance = useCreditsStore((s) => s.balance);
  const ledger = useCreditsStore((s) => s.ledger);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [nameError, setNameError] = useState<string | undefined>();
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
    setEditing(false);
  };

  return (
    <div className="mx-auto w-full max-w-[1100px] px-4 pb-24 pt-14 sm:px-8 md:pt-8">
      <header className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-6">
        <Avatar name={user.name} seed={user.avatarSeed} size="lg" />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {editing ? (
            <form
              className="flex max-w-sm items-end gap-2"
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
                onKeyDown={(e) => e.key === "Escape" && setEditing(false)}
                error={nameError}
                className="flex-1"
              />
              <Button type="submit" variant="primary" className={cx(nameError && "mb-7")}>
                Save
              </Button>
              <Button onClick={() => setEditing(false)} className={cx(nameError && "mb-7")}>
                Cancel
              </Button>
            </form>
          ) : (
            <div className="flex items-center gap-3">
              <h1 className="truncate text-2xl font-semibold tracking-tight text-fg">{user.name}</h1>
              <Button size="sm" variant="ghost" onClick={startEdit} aria-label="Edit name">
                Edit
              </Button>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-fg-muted">{user.email}</span>
            <Badge>{PLAN_LABEL[user.plan]}</Badge>
          </div>
        </div>
      </header>

      <div role="group" aria-label="Usage" className="mb-10 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Projects" value={projects.length} />
        <Stat label="Scene versions" value={versions} />
        <Stat label="Credits left" value={balance} />
        <Stat label="Credits spent" value={spent} />
      </div>

      <section aria-labelledby="recent" className="flex flex-col gap-3">
        <h2 id="recent" className="text-lg font-semibold tracking-tight text-fg">
          Recent projects
        </h2>
        {recent.length === 0 ? (
          <p className="text-sm text-fg-muted">
            No projects yet.{" "}
            <Link href="/projects?new=1" className="text-fg underline-offset-4 hover:underline focus-visible:focus-ring">
              Start one
            </Link>
          </p>
        ) : (
          <ul className="flex flex-col rounded-lg border border-line bg-bg-2 px-2">
            {recent.map((p) => (
              <li key={p.id} className="border-b border-line last:border-b-0">
                <Link
                  href={`/projects/${p.id}`}
                  className="flex h-12 items-center justify-between gap-4 rounded-sm px-3 text-sm text-fg transition-colors hover:bg-bg-3 focus-visible:focus-ring"
                >
                  <span className="truncate">{p.name}</span>
                  <span className="shrink-0 text-xs text-fg-muted">
                    {versionCounts[p.id] ?? 0} {versionCounts[p.id] === 1 ? "version" : "versions"} · {relativeTime(p.updatedAt, now)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
