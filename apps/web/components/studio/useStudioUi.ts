import { create } from "zustand";

export type DrawerTab = "analysis" | "model" | "controls" | "render";

/**
 * Who should take keyboard focus next: the drawer's Render button (after "Render" from
 * the composer) or the icon button that opens the drawer (after it closes). The
 * component that owns the element consumes the request and clears it.
 */
export type FocusRequest = "render" | "trigger" | null;

/**
 * UI-only studio chrome state (spec 8, progressive disclosure): the right drawer is
 * closed by default and the camera-path scrubber is hidden until asked for. Nothing
 * here is persisted or read by the domain stores.
 */
type StudioUiState = {
  drawerOpen: boolean;
  drawerTab: DrawerTab;
  scrubberOpen: boolean;
  focusRequest: FocusRequest;
  openDrawer: (tab?: DrawerTab) => void;
  /** Opens the drawer on the Render tab and asks its primary button to take focus. */
  openRender: () => void;
  closeDrawer: () => void;
  /** Closes the drawer and hands focus back to the icon button that opens it. */
  closeDrawerAndRestore: () => void;
  toggleDrawer: () => void;
  setDrawerTab: (tab: DrawerTab) => void;
  setScrubberOpen: (open: boolean) => void;
  clearFocusRequest: () => void;
  reset: () => void;
};

const initial = { drawerOpen: false, drawerTab: "analysis" as DrawerTab, scrubberOpen: false, focusRequest: null as FocusRequest };

export const useStudioUi = create<StudioUiState>((set) => ({
  ...initial,
  openDrawer: (tab) => set((s) => ({ drawerOpen: true, drawerTab: tab ?? s.drawerTab })),
  openRender: () => set({ drawerOpen: true, drawerTab: "render", focusRequest: "render" }),
  closeDrawer: () => set({ drawerOpen: false }),
  closeDrawerAndRestore: () => set({ drawerOpen: false, focusRequest: "trigger" }),
  toggleDrawer: () => set((s) => ({ drawerOpen: !s.drawerOpen })),
  setDrawerTab: (drawerTab) => set({ drawerTab }),
  setScrubberOpen: (scrubberOpen) => set({ scrubberOpen }),
  clearFocusRequest: () => set({ focusRequest: null }),
  reset: () => set(initial),
}));
