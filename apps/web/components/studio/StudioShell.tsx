"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { cx } from "@/components/ui";
import { Viewer } from "@/components/viewer/Viewer";
import { DUR } from "@/lib/motion/tokens";
import { useStudioStore } from "@/lib/stores/studio";
import { Composer } from "./Composer";
import { SceneDrawer } from "./SceneDrawer";
import { ProjectStatus, SceneDetailsButton } from "./StudioOverlay";
import { UploadDropzone } from "./UploadDropzone";
import { useLabour } from "./useLabour";
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
  const { captureKey, onThumbnail } = useThumbnailSync(asset?.id ?? null, versions.length, labouring);
  // Store errors are shown inline by the composer (`PromptErrors`); this ref lets the warning strip refocus the input.
  const promptRef = useRef<HTMLTextAreaElement>(null);

  const plan = labouring ? frozenPlan : currentPlan;
  const scaleFactor = analysis?.scaleFactor ?? 1;

  const [scrub, setPreviewSeconds] = useState<number | null>(null);
  // The preview camera needs a plan; without one the orbit camera shows.
  const previewSeconds = plan ? scrub : null;

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
      <section aria-label="3D preview" className="absolute inset-0">
        <Viewer
          root={model.root}
          plan={plan}
          scaleFactor={scaleFactor}
          previewSeconds={previewSeconds}
          captureKey={captureKey}
          onThumbnail={onThumbnail}
        />
        <ViewerOverlay
          loadingProject={loadingProject}
          loadingModel={model.loading}
          notices={model.notices}
          error={model.error?.message ?? null}
        />
        <UploadDropzone />
      </section>

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
  error: string | null;
};

/** Status messages over the viewer. The upload and re-upload states are `UploadDropzone`, layered above this. */
function ViewerOverlay({ loadingProject, loadingModel, notices, error }: OverlayProps) {
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
            <div key={n} className="pointer-events-auto rounded-md border border-line bg-bg-1/95 px-3 py-2 text-xs text-fg-muted backdrop-blur-sm">
              {n}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
