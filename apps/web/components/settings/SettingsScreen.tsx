"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Dialog, cx, useToastStore } from "@/components/ui";
import { services } from "@/lib/services";
import { useAuthStore } from "@/lib/stores/auth";
import { KEY_PREFIX } from "@/lib/services/local/storage";
import type { RenderDefaults } from "@/lib/schema";
import { renderPlanLimits } from "@/lib/render/planLimits";
import { PLAN_LABEL } from "@/components/account/planLabel";
import { Segmented } from "./Segmented";
import { Switch } from "./Switch";

type Output = RenderDefaults;

const SECTIONS = [
  { id: "general", label: "General" },
  { id: "rendering", label: "Rendering" },
  { id: "notifications", label: "Notifications" },
  { id: "local", label: "Local renderer" },
  { id: "data", label: "Data controls" },
  { id: "account", label: "Account" },
] as const;
export type SectionId = (typeof SECTIONS)[number]["id"];

const NOTE: Partial<Record<SectionId, string>> = {
  general: "Appearance and language for this workspace.",
  rendering: "Where the Render tab starts. You can still change both for each render.",
  notifications: "Emails about your renders. Account and security emails are always sent.",
  local: "Connect your own computer for final renders when the desktop agent is available.",
  data: "Manage the data saved in this browser.",
  account: "Your local account, plan and session.",
};

const FORMATS: { value: Output["aspect"]; label: string }[] = [
  { value: "9:16", label: "Vertical 9:16" },
  { value: "16:9", label: "Landscape 16:9" },
];

/** One settings row: label (and optional note) on the left, the control on the right. */
function Row({ label, note, children, className }: { label: string; note?: string; children?: React.ReactNode; className?: string }) {
  return (
    <div className={cx("flex min-h-14 flex-col items-start justify-between gap-2 border-b border-line py-4 last:border-b-0 sm:flex-row sm:items-center sm:gap-6", className)}>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-sm text-fg">{label}</span>
        {note && <span className="text-xs text-fg-muted">{note}</span>}
      </div>
      {children && <div className="flex max-w-full flex-wrap items-center gap-2 break-all sm:shrink-0">{children}</div>}
    </div>
  );
}

/** A right-hand value that cannot currently be changed. Shown as plain text, not a fake control. */
function Fixed({ children }: { children: React.ReactNode }) {
  return <span className="text-sm text-fg-muted">{children}</span>;
}

/** Everything under rs.* in localStorage as one JSON object, for the export. */
export function collectLocalData(): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (!k?.startsWith(KEY_PREFIX)) continue;
    const raw = localStorage.getItem(k);
    try {
      out[k] = raw === null ? null : JSON.parse(raw);
    } catch {
      out[k] = raw;
    }
  }
  return out;
}

function downloadJson(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function SettingsScreen({ initialSection = "general" }: { initialSection?: SectionId }) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const updateProfile = useAuthStore((s) => s.updateProfile);
  const signOut = useAuthStore((s) => s.signOut);
  const push = useToastStore((s) => s.push);
  const [section, setSection] = useState<SectionId>(initialSection);
  const [confirmOpen, setConfirmOpen] = useState(false);
  // With the real backend this deletes the account itself, server-side, not just this browser's copy.
  const serverAccount = services.auth.features.serverAccount;
  const del = serverAccount
    ? {
        row: "Delete account",
        note: "Permanently deletes your account, projects, models, scenes, renders and credits.",
        button: "Delete account",
        title: "Delete your account?",
        description: "Your account and everything in it (projects, uploaded models, scenes, renders and remaining credits) will be deleted from our servers. This cannot be undone.",
      }
    : {
        row: "Delete all data",
        note: "Removes every project, model, scene and credit from this browser and signs you out.",
        button: "Delete all",
        title: "Delete all data?",
        description: "Every project, model, scene and credit in this browser will be removed, and you will be signed out. This cannot be undone.",
      };
  const [deleting, setDeleting] = useState(false);

  if (!user) return null;
  const output = user.prefs.defaultOutput;

  // The worker renders Preview (540p) or Final (1080p); Final needs a plan that includes it.
  const limits = renderPlanLimits(user.plan);
  const finalAllowed = limits.tiers.includes("final");
  const tiers: { value: Output["tier"]; label: string; disabled?: boolean }[] = [
    { value: "preview", label: "Preview 540p" },
    { value: "final", label: "Final 1080p", disabled: !finalAllowed },
  ];
  const tier = limits.tiers.includes(output.tier) ? output.tier : "preview";

  // Read by the Render tab when it opens (components/studio/RenderPanel.tsx).
  const setOutput = async (patch: Partial<Output>) => {
    const ok = await updateProfile({ prefs: { defaultOutput: { ...output, ...patch } } });
    if (!ok) push({ kind: "danger", message: useAuthStore.getState().error?.message ?? "Could not save." });
  };

  const setRenderEmails = async (on: boolean) => {
    const ok = await updateProfile({ emailRenderReady: on });
    if (!ok) push({ kind: "danger", message: useAuthStore.getState().error?.message ?? "Could not save." });
  };

  const exportData = () => {
    const stamp = new Date().toISOString().slice(0, 10);
    downloadJson(`render-studio-${stamp}.json`, { exportedAt: Date.now(), data: collectLocalData() });
    push({ kind: "success", message: "Exported projects (JSON)" });
  };

  const logOut = async () => {
    await signOut();
    router.replace("/login");
  };

  const deleteAll = async () => {
    setDeleting(true);
    const r = await services.auth.deleteAllData();
    setDeleting(false);
    if (!r.ok) {
      push({ kind: "danger", message: r.error.message });
      return;
    }
    setConfirmOpen(false);
    await logOut();
  };

  const panel: Record<SectionId, React.ReactNode> = {
    general: (
      <>
        <Row label="Theme" note="Dark appearance is the current default.">
          <Fixed>Dark</Fixed>
        </Row>
        <Row label="Language">
          <Fixed>English</Fixed>
        </Row>
      </>
    ),
    rendering: (
      <>
        <Row label="Quality" note={finalAllowed ? undefined : "Final 1080p renders come with Creator and Pro."}>
          <Segmented label="Default quality" options={tiers} value={tier} onChange={(v) => void setOutput({ tier: v })} />
        </Row>
        <Row label="Format">
          <Segmented label="Default format" options={FORMATS} value={output.aspect} onChange={(v) => void setOutput({ aspect: v })} />
        </Row>
      </>
    ),
    notifications: (
      <Row
        label="Render ready"
        note={
          serverAccount
            ? "Email me when a render finishes, with a still and a link to it."
            : "Email me when a render finishes. Emails are sent once you use a Valora3D account."
        }
      >
        <Switch label="Email me when a render is ready" checked={user.emailRenderReady !== false} onChange={(on) => void setRenderEmails(on)} />
      </Row>
    ),
    local: (
      <>
        <Row label="Status">
          <span className="inline-flex items-center gap-2 text-sm text-fg-muted">
            <span aria-hidden className="size-1.5 rounded-full bg-fg-muted/50" />
            Cloud rendering at launch
          </span>
        </Row>
        <Row label="Desktop render agent" note="Desktop rendering is unavailable at launch. Use cloud rendering for your shots.">
          <Button disabled>Connect</Button>
        </Row>
      </>
    ),
    data: (
      <>
        <Row label="Export projects (JSON)" note="Project records, scenes, credits and account data. Model files and thumbnails are not included; this is not a complete backup.">
          <Button onClick={exportData}>Export</Button>
        </Row>
        <Row label={del.row} note={del.note}>
          <Button variant="danger" onClick={() => setConfirmOpen(true)}>
            {del.button}
          </Button>
        </Row>
      </>
    ),
    account: (
      <>
        <Row label="Email">
          <Fixed>{user.email}</Fixed>
        </Row>
        <Row label="Plan">
          <Badge>{PLAN_LABEL[user.plan]}</Badge>
          <Link href="/pricing" className="inline-flex h-9 items-center rounded-full border border-line px-4 text-sm text-fg transition-colors hover:bg-bg-3 focus-visible:focus-ring">
            Manage plan
          </Link>
        </Row>
        <Row label="Log out of this browser">
          <Button onClick={() => void logOut()}>Log out</Button>
        </Row>
      </>
    ),
  };

  return (
    <div className="mx-auto w-full max-w-[1100px] px-5 pb-16 pt-16 sm:px-8 md:pt-12">
      <header className="mb-8 flex flex-col gap-3 border-b border-line pb-6">
        <h1 className="text-3xl font-semibold tracking-[-0.04em] text-fg sm:text-4xl">Settings</h1>
        <p className="text-sm text-fg-muted">Make this workspace your own.</p>
      </header>

      <div className="flex flex-col gap-6 md:flex-row md:gap-10">
        {/* Wrap on phones so every section is discoverable without horizontal scrolling. */}
        <nav aria-label="Settings sections" className="md:w-44 md:shrink-0">
          <ul className="flex flex-wrap gap-1 md:flex-col">
            {SECTIONS.map((s) => {
              const active = s.id === section;
              return (
                <li key={s.id} className="shrink-0">
                  <button
                    type="button"
                    aria-current={active ? "true" : undefined}
                    onClick={() => setSection(s.id)}
                    className={cx(
                      "flex min-h-11 w-full cursor-pointer items-center whitespace-nowrap rounded-md px-3 text-sm transition-colors duration-fast ease-standard focus-visible:focus-ring",
                      active ? "bg-bg-3 text-fg" : "text-fg-muted hover:bg-bg-3 hover:text-fg",
                    )}
                  >
                    {s.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <section aria-labelledby={`settings-${section}`} className="min-w-0 flex-1">
          <div className="mb-5 flex max-w-prose flex-col gap-2">
            <h2 id={`settings-${section}`} className="text-lg font-semibold tracking-tight text-fg">
              {SECTIONS.find((s) => s.id === section)?.label}
            </h2>
            {NOTE[section] && <p className="text-sm text-fg-muted">{NOTE[section]}</p>}
          </div>
          <div className="rounded-lg border border-line bg-bg-1 px-5">{panel[section]}</div>
        </section>
      </div>

      <Dialog
        open={confirmOpen}
        onClose={() => !deleting && setConfirmOpen(false)}
        title={del.title}
        description={del.description}
        footer={
          <>
            <Button onClick={() => setConfirmOpen(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="danger" loading={deleting} onClick={() => void deleteAll()} className="bg-danger/10">
              {serverAccount ? "Delete account" : "Delete all data"}
            </Button>
          </>
        }
      />
    </div>
  );
}
