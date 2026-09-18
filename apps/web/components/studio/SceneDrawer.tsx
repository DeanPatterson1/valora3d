"use client";

import { useEffect, useId, useRef } from "react";
import { AnimatePresence, motion, useReducedMotion, type Variants } from "motion/react";
import { cx, TabPanel, Tabs } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import { reduced } from "@/lib/motion/variants";
import { useStudioStore } from "@/lib/stores/studio";
import { AnalysisPanel } from "./AnalysisPanel";
import { ControlsPanel } from "./ControlsPanel";
import { RenderPanel } from "./RenderPanel";
import { useLabour } from "./useLabour";
import { useStudioUi, type DrawerTab } from "./useStudioUi";

const ALL_TABS: { id: DrawerTab; label: string }[] = [
  { id: "analysis", label: "Analysis" },
  { id: "controls", label: "Controls" },
  { id: "render", label: "Render" },
];

const slideRight: Variants = {
  hidden: { opacity: 0, x: 24 },
  visible: { opacity: 1, x: 0, transition: { duration: DUR.base, ease: EASE.emphasized } },
  exit: { opacity: 0, x: 24, transition: { duration: DUR.fast, ease: EASE.standard } },
};
const slideUp: Variants = {
  hidden: { opacity: 0, y: 32 },
  visible: { opacity: 1, y: 0, transition: { duration: DUR.base, ease: EASE.emphasized } },
  exit: { opacity: 0, y: 32, transition: { duration: DUR.fast, ease: EASE.standard } },
};

type Props = {
  /** Right drawer at 1100px and up; bottom sheet below. */
  wide: boolean;
};

/**
 * Scene details (spec 8, progressive disclosure): analysis, controls and render behind
 * one icon button, closed by default. Controls and Render unlock with the first version.
 * Escape, the close button or a click on the viewer closes it.
 */
export function SceneDrawer({ wide }: Props) {
  const rm = useReducedMotion() ?? false;
  const open = useStudioUi((s) => s.drawerOpen);
  const tab = useStudioUi((s) => s.drawerTab);
  const setTab = useStudioUi((s) => s.setDrawerTab);
  const close = useStudioUi((s) => s.closeDrawer);
  /** Escape and the close button hand focus back to the icon button that opens the drawer. */
  const closeAndRestore = useStudioUi((s) => s.closeDrawerAndRestore);
  const versionCount = useStudioStore((s) => s.versions.length);
  const { labouring, frozenVersionCount } = useLabour();
  const unlocked = (labouring ? frozenVersionCount : versionCount) > 0;

  const tabsId = useId();
  const ref = useRef<HTMLDivElement>(null);

  // A locked tab cannot stay selected (e.g. after "Start over" the count never drops, but be safe).
  useEffect(() => {
    if (!unlocked && tab !== "analysis") setTab("analysis");
  }, [unlocked, tab, setTab]);

  // Keyboard users land in the drawer when it opens (on the selected tab) unless something
  // inside it, e.g. the Render button focused by `openRender`, already took focus.
  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => {
      const el = ref.current;
      if (!el || el.contains(document.activeElement)) return;
      el.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.focus();
    });
    return () => cancelAnimationFrame(id);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeAndRestore();
    };
    const onPointer = (e: PointerEvent) => {
      const t = e.target as Element | null;
      if (!t || ref.current?.contains(t)) return;
      // Only the viewer closes it: the composer, the sidebar and the top overlays leave it open
      // (the toggle button handles itself).
      if (t.closest("[data-viewer-area]")) close();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open, close, closeAndRestore]);

  const items = unlocked ? ALL_TABS : ALL_TABS.slice(0, 1);
  const variants = rm ? reduced(wide ? slideRight : slideUp) : wide ? slideRight : slideUp;

  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          key={wide ? "drawer" : "sheet"}
          ref={ref}
          id="scene-drawer"
          aria-label="Scene details"
          data-testid="scene-drawer"
          variants={variants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className={cx(
            "absolute z-30 flex flex-col bg-bg-1 shadow-raise",
            wide
              ? "inset-y-0 right-0 w-[360px] border-l border-line"
              : "inset-x-0 bottom-0 h-[85dvh] max-h-full rounded-t-2xl border-t border-line",
          )}
        >
          <div className="flex items-center justify-between gap-2 px-3 pt-3 pb-2">
            <Tabs id={tabsId} items={items} value={tab} onChange={(id) => setTab(id as DrawerTab)} label="Scene details" />
            <button
              type="button"
              onClick={closeAndRestore}
              aria-label="Close scene details"
              className="flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-full text-fg-muted transition-colors duration-fast ease-standard hover:bg-bg-2 hover:text-fg focus-visible:focus-ring"
            >
              <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M4 4l8 8M12 4l-8 8" />
              </svg>
            </button>
          </div>
          <div className="relative min-h-0 flex-1">
            <div className="h-full overflow-y-auto pb-6" data-testid="scene-drawer-body">
              <TabPanel tabsId={tabsId} id="analysis" active={tab === "analysis"} className="h-full">
                <AnalysisPanel />
                {!unlocked && (
                  <p className="px-4 pb-4 text-xs text-fg-muted">Generate a scene to unlock controls and rendering.</p>
                )}
              </TabPanel>
              {unlocked && (
                <>
                  <TabPanel tabsId={tabsId} id="controls" active={tab === "controls"} className="h-full"><ControlsPanel /></TabPanel>
                  <TabPanel tabsId={tabsId} id="render" active={tab === "render"} className="h-full"><RenderPanel /></TabPanel>
                </>
              )}
            </div>
            {/* Bottom fade: hints that the sheet scrolls. */}
            {!wide && (
              <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-bg-1 to-transparent" />
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
