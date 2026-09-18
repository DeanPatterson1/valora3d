"use client";

import { useEffect, useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion, type Variants } from "motion/react";
import { Button, cx, TabPanel, Tabs } from "@/components/ui";
import { Viewer } from "@/components/viewer/Viewer";
import { Scrubber } from "@/components/viewer/Scrubber";
import { panelSlide, reduced } from "@/lib/motion/variants";
import { DUR, EASE } from "@/lib/motion/tokens";
import { useStudioStore } from "@/lib/stores/studio";
import { AnalysisPanel } from "./AnalysisPanel";
import { ControlsPanel } from "./ControlsPanel";
import { PromptDock } from "./PromptDock";
import { RenderPanel } from "./RenderPanel";
import { StudioTopBar } from "./StudioTopBar";
import { UploadDropzone } from "./UploadDropzone";
import { VersionRail } from "./VersionRail";
import { useLabour } from "./useLabour";
import { useStudioModel } from "./useStudioModel";
import { useThumbnailSync } from "./useThumbnailSync";

const TABS = [
  { id: "analysis", label: "Analysis" },
  { id: "controls", label: "Controls" },
  { id: "render", label: "Render" },
];
type TabId = (typeof TABS)[number]["id"];

/** Left rail enters from the left; the mobile sheet rises from the bottom. */
const railSlide: Variants = {
  hidden: { opacity: 0, x: -24 },
  visible: { opacity: 1, x: 0, transition: { duration: DUR.base, ease: EASE.emphasized } },
  exit: { opacity: 0, x: -24, transition: { duration: DUR.fast, ease: EASE.standard } },
};
const sheetSlide: Variants = {
  hidden: { opacity: 0, y: 32 },
  visible: { opacity: 1, y: 0, transition: { duration: DUR.base, ease: EASE.emphasized } },
  exit: { opacity: 0, y: 32, transition: { duration: DUR.fast, ease: EASE.standard } },
};

const WIDE = "(min-width: 1100px)";
const PHONE = "(max-width: 767px)";

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
 * Studio layout (spec 8): top bar, left version rail (240px, collapsible), the viewer as
 * the hero in the centre with the scrubber under it, right panel with tabs (360px), and
 * the prompt dock along the bottom. Under 1100px the right panel becomes a bottom sheet.
 */
export function StudioShell() {
  const rm = useReducedMotion() ?? false;
  const project = useStudioStore((s) => s.project);
  const asset = useStudioStore((s) => s.asset);
  const blobMissing = useStudioStore((s) => s.blobMissing);
  const analysis = useStudioStore((s) => s.analysis);
  const versions = useStudioStore((s) => s.versions);
  const currentPlan = useStudioStore((s) => s.currentPlan);
  const busy = useStudioStore((s) => s.busy);
  const error = useStudioStore((s) => s.error);
  const clearError = useStudioStore((s) => s.clearError);

  const { labouring, frozenPlan, frozenVersionCount } = useLabour();
  const model = useStudioModel(asset, blobMissing);
  const { captureKey, onThumbnail } = useThumbnailSync(asset?.id ?? null, versions.length, labouring);

  const plan = labouring ? frozenPlan : currentPlan;
  const railVersions = labouring ? versions.slice(0, frozenVersionCount) : versions;
  const scaleFactor = analysis?.scaleFactor ?? 1;

  const [scrub, setPreviewSeconds] = useState<number | null>(null);
  // The preview camera needs a plan; without one the orbit camera shows.
  const previewSeconds = plan ? scrub : null;
  const [tab, setTab] = useState<TabId>("analysis");
  const tabsId = useId();

  const wide = useMedia(WIDE);
  const phone = useMedia(PHONE);
  // Phones start with the rail closed so the viewer gets the width; a tap overrides that until the breakpoint changes.
  const [railPref, setRailPref] = useState<{ phone: boolean; open: boolean } | null>(null);
  const railOpen = railPref?.phone === phone ? railPref.open : !phone;
  const setRailOpen = (open: boolean) => setRailPref({ phone, open });
  const [sheetPref, setSheetOpen] = useState(false);
  const sheetOpen = !wide && sheetPref;

  const v = (variants: Variants) => (rm ? reduced(variants) : variants);
  const loadingProject = !project && busy === "loading";

  const panelTabs = (
    <>
      <div className="flex items-end">
        <Tabs id={tabsId} items={TABS} value={tab} onChange={(id) => setTab(id as TabId)} label="Studio panels" className="flex-1 px-2" />
        {!wide && (
          <button
            type="button"
            onClick={() => setSheetOpen(false)}
            aria-label="Hide panels"
            className="mb-1 mr-2 flex size-7 items-center justify-center rounded-sm text-fg-muted transition-colors duration-fast ease-standard hover:bg-bg-2 hover:text-fg focus-visible:focus-ring"
          >
            <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6l5 5 5-5" />
            </svg>
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <TabPanel tabsId={tabsId} id="analysis" active={tab === "analysis"} className="h-full"><AnalysisPanel /></TabPanel>
        <TabPanel tabsId={tabsId} id="controls" active={tab === "controls"} className="h-full"><ControlsPanel /></TabPanel>
        <TabPanel tabsId={tabsId} id="render" active={tab === "render"} className="h-full"><RenderPanel /></TabPanel>
      </div>
    </>
  );

  return (
    <div
      className="grid h-[calc(100dvh-3.5rem-1px)] w-full max-w-full grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden bg-bg-0"
      data-studio-shell
      aria-busy={loadingProject || undefined}
    >
      <StudioTopBar />

      <div className="relative flex min-h-0 min-w-0">
        {/* Left rail */}
        <AnimatePresence initial={false}>
          {railOpen && (
            <motion.aside
              key="rail"
              aria-label="Version history"
              variants={v(railSlide)}
              initial="hidden"
              animate="visible"
              exit="exit"
              className={cx(
                "flex min-h-0 shrink-0 flex-col border-r border-line bg-bg-1",
                phone ? "absolute inset-y-0 left-0 z-20 w-[240px] shadow-raise" : "w-[240px]",
              )}
            >
              <div className="flex h-9 items-center justify-between border-b border-line px-3">
                <span className="text-xs font-medium uppercase tracking-wide text-fg-muted">History</span>
                <RailToggle open onClick={() => setRailOpen(false)} />
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                <VersionRail versions={railVersions} />
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Centre: the viewer is the hero */}
        <section aria-label="3D preview" className="relative flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="relative min-h-0 flex-1">
            <Viewer
              root={model.root}
              plan={plan}
              scaleFactor={scaleFactor}
              previewSeconds={previewSeconds}
              captureKey={captureKey}
              onThumbnail={onThumbnail}
            />

            {!railOpen && (
              <div className="absolute left-3 top-3 z-10">
                <RailToggle open={false} onClick={() => setRailOpen(true)} />
              </div>
            )}

            <ViewerOverlay
              loadingProject={loadingProject}
              loadingModel={model.loading}
              notices={model.notices}
              error={error?.message ?? model.error?.message ?? null}
              onDismissError={error ? clearError : undefined}
            />

            <UploadDropzone />

            {!wide && (
              <div className="absolute bottom-3 right-3 z-10">
                <Button size="sm" onClick={() => setSheetOpen((o) => !o)} aria-expanded={sheetOpen} aria-controls={`${tabsId}-sheet`}>
                  {sheetOpen ? "Hide panels" : "Panels"}
                </Button>
              </div>
            )}
          </div>

          {plan && <Scrubber plan={plan} seconds={previewSeconds} onChange={setPreviewSeconds} disabled={labouring} />}

          {/* Bottom sheet (under 1100px) */}
          <AnimatePresence>
            {!wide && sheetOpen && (
              <motion.div
                key="sheet"
                id={`${tabsId}-sheet`}
                role="region"
                aria-label="Studio panels"
                variants={v(sheetSlide)}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="absolute inset-x-0 bottom-0 z-20 flex max-h-[60%] min-h-48 flex-col border-t border-line bg-bg-1 shadow-overlay"
              >
                {panelTabs}
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* Right panel (1100px and up) */}
        {wide && (
          <motion.aside
            aria-label="Studio panels"
            variants={v(panelSlide)}
            initial="hidden"
            animate="visible"
            className="flex w-[360px] min-h-0 shrink-0 flex-col border-l border-line bg-bg-1"
          >
            {panelTabs}
          </motion.aside>
        )}
      </div>

      <div className="border-t border-line bg-bg-1">
        <PromptDock />
      </div>
    </div>
  );
}

function RailToggle({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={open ? "Hide version history" : "Show version history"}
      aria-expanded={open}
      className={cx(
        "flex size-7 items-center justify-center rounded-sm text-fg-muted transition-colors duration-fast ease-standard hover:text-fg focus-visible:focus-ring",
        open ? "hover:bg-bg-2" : "border border-line bg-bg-1/85 backdrop-blur-sm hover:bg-bg-2",
      )}
    >
      <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="12" height="10" rx="1.5" />
        <path d="M6 3v10" />
      </svg>
    </button>
  );
}

type OverlayProps = {
  loadingProject: boolean;
  loadingModel: boolean;
  notices: string[];
  error: string | null;
  onDismissError?: () => void;
};

/** Status messages over the viewer. The upload and re-upload states are `UploadDropzone`, layered above this. */
function ViewerOverlay({ loadingProject, loadingModel, notices, error, onDismissError }: OverlayProps) {
  const rm = useReducedMotion();
  let centre: { title: string; hint: string } | null = null;
  if (loadingProject) centre = { title: "Opening project", hint: "" };
  else if (loadingModel) centre = { title: "Loading model", hint: "" };

  return (
    <>
      {centre && (
        <motion.div
          key={centre.title}
          className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1 px-6 text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: rm ? 0 : DUR.base }}
          role="status"
        >
          <span className="font-display text-lg font-semibold text-fg">{centre.title}</span>
          {centre.hint && <span className="max-w-sm text-sm text-fg-muted">{centre.hint}</span>}
        </motion.div>
      )}
      {(error || notices.length > 0) && (
        <div className="pointer-events-none absolute inset-x-3 top-3 z-10 flex flex-col items-end gap-1.5 sm:left-auto sm:max-w-sm">
          {error && (
            <div role="alert" className="pointer-events-auto flex items-start gap-2 rounded-md border border-danger/40 bg-bg-1/95 px-3 py-2 text-sm text-fg shadow-raise backdrop-blur-sm">
              <span className="flex-1">{error}</span>
              {onDismissError && (
                <button type="button" onClick={onDismissError} aria-label="Dismiss" className="rounded-sm px-1 text-fg-muted hover:text-fg focus-visible:focus-ring">
                  ×
                </button>
              )}
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
