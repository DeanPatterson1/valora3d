import { create } from "zustand";

export type DrawerTab = "analysis" | "controls" | "render";

/**
 * UI-only studio chrome state (spec 8, progressive disclosure): the right drawer is
 * closed by default and the camera-path scrubber is hidden until asked for. Nothing
 * here is persisted or read by the domain stores.
 */
type StudioUiState = {
  drawerOpen: boolean;
  drawerTab: DrawerTab;
  scrubberOpen: boolean;
  openDrawer: (tab?: DrawerTab) => void;
  closeDrawer: () => void;
  toggleDrawer: () => void;
  setDrawerTab: (tab: DrawerTab) => void;
  setScrubberOpen: (open: boolean) => void;
  reset: () => void;
};

const initial = { drawerOpen: false, drawerTab: "analysis" as DrawerTab, scrubberOpen: false };

export const useStudioUi = create<StudioUiState>((set) => ({
  ...initial,
  openDrawer: (tab) => set((s) => ({ drawerOpen: true, drawerTab: tab ?? s.drawerTab })),
  closeDrawer: () => set({ drawerOpen: false }),
  toggleDrawer: () => set((s) => ({ drawerOpen: !s.drawerOpen })),
  setDrawerTab: (drawerTab) => set({ drawerTab }),
  setScrubberOpen: (scrubberOpen) => set({ scrubberOpen }),
  reset: () => set(initial),
}));
