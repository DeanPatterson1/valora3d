"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button, Skeleton, useToastStore } from "@/components/ui";
import { services } from "@/lib/services";
import { useProjectsStore } from "@/lib/stores/projects";
import { NewProjectDialog } from "./NewProjectDialog";
import { ProjectGrid } from "./ProjectGrid";

let corruptNoticed = false;

function StorageUnavailable() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-24 text-center">
      <div className="flex max-w-md flex-col gap-2">
        <h2 className="text-xl font-semibold tracking-tight text-fg">Browser storage is unavailable</h2>
        <p className="text-sm text-fg-muted">
          Projects and models are kept in your browser. Open this page in a normal, non-private window to
          continue.
        </p>
      </div>
    </div>
  );
}

export function Dashboard() {
  const router = useRouter();
  const params = useSearchParams();
  const projects = useProjectsStore((s) => s.projects);
  const versionCounts = useProjectsStore((s) => s.versionCounts);
  const loaded = useProjectsStore((s) => s.loaded);
  const error = useProjectsStore((s) => s.error);
  const refresh = useProjectsStore((s) => s.refresh);
  const rename = useProjectsStore((s) => s.rename);
  const remove = useProjectsStore((s) => s.remove);

  // Server render assumes storage is available; the client corrects it before paint.
  const storageOk = useSyncExternalStore(
    () => () => {},
    () => "indexedDB" in window,
    () => true,
  );
  const [dialogOpen, setDialogOpen] = useState(false);
  // `?new=1` (sidebar) keeps the dialog open until it is closed, then the URL is cleaned.
  const wantsNew = params.get("new") === "1";
  const noticeHandled = useRef<string | null>(null);

  useEffect(() => {
    if (!storageOk) return;
    void refresh().then(() => {
      if (!corruptNoticed && services.projects.corruptDetected()) {
        corruptNoticed = true;
        useToastStore
          .getState()
          .push({ kind: "info", message: "Some saved data could not be read and was treated as empty." });
      }
    });
  }, [refresh, storageOk]);

  // `?notice=not_found` comes from the studio redirect; toast once per arrival, then strip it.
  useEffect(() => {
    const notice = params.get("notice");
    if (!notice) {
      noticeHandled.current = null;
      return;
    }
    if (noticeHandled.current === notice) return;
    noticeHandled.current = notice;
    if (notice === "not_found") {
      useToastStore.getState().push({ kind: "info", message: "That project no longer exists." });
    }
    router.replace(wantsNew ? "/projects?new=1" : "/projects");
  }, [params, router, wantsNew]);

  const openNew = () => setDialogOpen(true);
  const closeNew = () => {
    setDialogOpen(false);
    if (wantsNew) router.replace("/projects");
  };

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-1 flex-col px-5 pb-16 pt-16 sm:px-8 md:pt-12">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-line pb-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-[-0.04em] text-fg sm:text-4xl">Projects</h1>
          <p className="text-sm text-fg-muted">Your models and scenes, saved in this browser.</p>
        </div>
        {/* While the grid is empty the centred empty-state CTA is the page's only action. */}
        {storageOk && loaded && projects.length > 0 && (
          <Button variant="primary" onClick={openNew} aria-label="New project">
            New project
          </Button>
        )}
      </div>

      {storageOk && error && (
        <div role="alert" className="mb-6 flex flex-col items-start gap-3 rounded-lg border border-line bg-bg-1 p-6">
          <p className="text-sm text-fg-muted">{error.message}</p>
          <Button onClick={() => void refresh()}>Reload projects</Button>
        </div>
      )}
      {!storageOk ? (
        <StorageUnavailable />
      ) : error && projects.length === 0 ? null : loaded ? (
        <ProjectGrid
          projects={projects}
          versionCounts={versionCounts}
          onRename={rename}
          onDelete={remove}
          onNew={openNew}
        />
      ) : (
        <div role="status" aria-live="polite" className="flex flex-col gap-4">
          <span className="text-sm text-fg-muted">Loading projects…</span>
          <div aria-hidden className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((key) => <Skeleton key={key} className="h-56 rounded-lg" />)}
          </div>
        </div>
      )}

      <NewProjectDialog open={dialogOpen || wantsNew} onClose={closeNew} />
    </div>
  );
}
