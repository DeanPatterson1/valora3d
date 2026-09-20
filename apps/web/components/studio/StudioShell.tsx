"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { cx } from "@/components/ui";
import { Viewer } from "@/components/viewer/Viewer";
import { DUR } from "@/lib/motion/tokens";
import { setSceneSource } from "@/lib/render/sceneSource";
import { useEditorStore } from "@/lib/stores/editor";
import { useStudioStore } from "@/lib/stores/studio";
import { Composer } from "./Composer";
import { SceneDrawer } from "./SceneDrawer";
import { OverlayScrim, ProjectStatus, SceneDetailsButton } from "./StudioOverlay";
import { UploadDropzone } from "./UploadDropzone";
import { useEditorShortcuts } from "./useEditorShortcuts";
import { useLabour } from "./useLabour";
import { useIngestStore } from "./useModelIngest";
import { useStudioModel } from "./useStudioModel";
import { useStudioUi } from "./useStudioUi";
import { useThumbnailSync } from "./useThumbnailSync";

const WIDE = "(min-width: 1100px)";

function useMedia(query: string): boolean {
  const [match, setMatch] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const update = () => setMatch(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [query]);
  return match;
}

/**
 * Studio layout (spec 8, revised): the viewer fills the main area edge to edge. Three
 * quiet overlays sit on it: the project name and status line top-left, one icon button
 * top-right that opens the scene-details drawer, and the composer floating at the
 * bottom centre. Version history lives in the sidebar. Under 1100px the drawer is a
 * bottom sheet.
 */
export function StudioShell() {
  const project = useStudioStore((s) => s.project);
  const asset = useStudioStore((s) => s.asset);
  const blobMissing = useStudioStore((s) => s.blobMissing);
  const analysis = useStudioStore((s) => s.analysis);
  const versions = useStudioStore((s) => s.versions);
  const currentPlan = useStudioStore((s) => s.currentPlan);
  const busy = useStudioStore((s) => s.busy);

  const { labouring, frozenPlan } = useLabour();
  const model = useStudioModel(asset, blobMissing);
  useEditorShortcuts();
  const { captureKey, onThumbnail } = useThumbnailSync(asset?.id ?? null, versions.length, labouring);
  // Store errors are shown inline by the composer (`PromptErrors`); this ref lets the warning strip refocus the input.
  const promptRef = useRef<HTMLTextAreaElement>(null);

  const plan = labouring ? frozenPlan : currentPlan;
  const scaleFactor = analysis?.scaleFactor ?? 1;

  // The renderer needs the live, edited geometry, which only the viewer holds. Read it
  // through the store each time rather than closing over it, so a render started after
  // an edit sends the edited scene.
  useEffect(() => {
    setSceneSource(() => {
      const { root, selection } = useEditorStore.getState();
      return root ? { root, scaleFactor, selection } : null;
    });
    return () => setSceneSource(null);
  }, [scaleFactor]);

  const [scrub, setPreviewSeconds] = useState<number | null>(null);
  // The preview camera needs a plan; without one the orbit camera shows.
  const previewSeconds = plan ? scrub : null;

  // Loader notices ("OBJ loaded without materials"): the ingest reports them first, the viewer's own
  // load repeats them. Shown once per asset, until dismissed.
  const ingestNotices = useIngestStore((s) => s.notices);
  const [noticesDismissedFor, setNoticesDismissedFor] = useState<string | null>(null);
  const notices = noticesDismissedFor === asset?.id ? [] : Array.from(new Set([...ingestNotices, ...model.notices]));

  const wide = useMedia(WIDE);
  const loadingProject = !project && busy === "loading";

  // Drawer and scrubber state is per visit to the studio.
  const drawerOpen = useStudioUi((s) => s.drawerOpen);
  const resetUi = useStudioUi((s) => s.reset);
  useEffect(() => () => resetUi(), [resetUi]);

  return (
    <div
      className="relative h-full w-full max-w-full overflow-hidden bg-bg-0"
      data-studio-shell
      aria-busy={loadingProject || undefined}
    >
      {/* `data-viewer-area`: a pointerdown here closes the scene drawer; the overlays and composer do not. */}
      <section aria-label="3D preview" data-viewer-area className="absolute inset-0">
        <Viewer
          root={model.root}
          plan={plan}
          scaleFactor={scaleFactor}
          previewSeconds={previewSeconds}
          captureKey={captureKey}
          onThumbnail={onThumbnail}
          editable
        />
        <ViewerOverlay
          loadingProject={loadingProject}
          loadingModel={model.loading}
          notices={notices}
          onDismissNotices={() => setNoticesDismissedFor(asset?.id ?? null)}
          error={model.error?.message ?? null}
        />
        <UploadDropzone />
      </section>

      {/* Behind the top overlays: a soft scrim so they read over a bright model. */}
      <OverlayScrim className="z-20" />

      {/* Top-left: name and status. Under md the sidebar's menu button sits at the left edge. */}
      <ProjectStatus className="absolute left-4 top-3 z-20 max-md:left-14" />

      {/* Top-right: the one control. */}
      <SceneDetailsButton className="absolute right-3 top-3 z-20" />

      {/* Bottom-centre: suggestions, notices and the composer. */}
      <div
        className={cx(
          "pointer-events-none absolute bottom-0 left-0 z-20 flex flex-col items-center px-3 pb-3 transition-[right] duration-base ease-emphasized sm:px-6 sm:pb-5",
          wide && drawerOpen ? "right-[360px]" : "right-0",
        )}
      >
        <Composer promptRef={promptRef} plan={plan} previewSeconds={previewSeconds} onScrub={setPreviewSeconds} />
      </div>

      <SceneDrawer wide={wide} />
    </div>
  );
}

type OverlayProps = {
  loadingProject: boolean;
  loadingModel: boolean;
  notices: string[];
  onDismissNotices: () => void;
  error: string | null;
};

/** Status messages over the viewer. The upload and re-upload states are `UploadDropzone`, layered above this. */
function ViewerOverlay({ loadingProject, loadingModel, notices, onDismissNotices, error }: OverlayProps) {
  const rm = useReducedMotion();
  let centre: string | null = null;
  if (loadingProject) centre = "Opening project";
  else if (loadingModel) centre = "Loading model";

  return (
    <>
      {centre && (
        <motion.div
          key={centre}
          className="pointer-events-none absolute inset-0 flex items-center justify-center px-6 text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: rm ? 0 : DUR.base }}
          role="status"
        >
          <span className="text-sm text-fg-muted">{centre}</span>
        </motion.div>
      )}
      {(error || notices.length > 0) && (
        <div className="pointer-events-none absolute right-3 top-14 z-10 flex max-w-sm flex-col items-end gap-1.5">
          {error && (
            <div role="alert" className="pointer-events-auto rounded-md border border-danger/40 bg-bg-1/95 px-3 py-2 text-sm text-fg shadow-raise backdrop-blur-sm">
              {error}
            </div>
          )}
          {notices.map((n) => (
            <div key={n} role="status" data-testid="model-notice" className="pointer-events-auto flex items-start gap-2 rounded-md border border-line bg-bg-1/95 px-3 py-2 text-xs text-fg-muted backdrop-blur-sm">
              <span>{n}</span>
              <button type="button" onClick={onDismissNotices} aria-label="Dismiss notice" className="-mr-1 shrink-0 cursor-pointer rounded-sm px-1 hover:text-fg focus-visible:focus-ring">
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
