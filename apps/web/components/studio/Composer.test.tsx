// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Asset, ModelAnalysis, SceneVersion } from "@/lib/schema";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { useCreditsStore } from "@/lib/stores/credits";
import { useStudioStore } from "@/lib/stores/studio";
import { Composer } from "./Composer";
import { LABOUR_MIN_MS } from "./labour";
import { PRESETS, SUGGESTED_PRESETS } from "./presets";
import { SceneDrawer } from "./SceneDrawer";
import { useLabourStore } from "./useLabour";
import { useStudioUi } from "./useStudioUi";

const analysis: ModelAnalysis = {
  category: "car", confidence: 0.9, unitGuess: "m", scaleFactor: 1, dimensionsMeters: [4.5, 1.8, 1.4],
  parts: {}, capabilities: ["drive"], rigged: false,
};
const asset: Asset = {
  id: "a1", projectId: "p", fileName: "toycar.glb", format: "glb", sizeBytes: 10, source: "sample", blobKey: null, sampleUrl: "/samples/toycar.glb", thumbnailKey: null,
};

function version(): SceneVersion {
  return { id: "v1", projectId: "p", index: 0, prompt: "x", parentId: null, plan: defaultPlan("car"), createdAt: Date.now() };
}

const textarea = () => screen.getByRole("textbox", { name: "Describe your render" }) as HTMLTextAreaElement;
const withVersion = () => useStudioStore.setState({ versions: [version()], selectedVersionId: "v1", currentPlan: defaultPlan("car") });

describe("Composer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useStudioStore.getState().reset();
    useLabourStore.getState().end();
    useStudioUi.getState().reset();
    useCreditsStore.setState({ balance: 100, loaded: true });
    useStudioStore.setState({ analysis, asset, blobMissing: false });
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("labels the send button by cost before and after the first version", () => {
    const { rerender } = render(<Composer />);
    expect(screen.getByRole("button", { name: "Generate scene · 2 credits" })).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "Describe your render" }).getAttribute("placeholder")).toBe("Describe the shot you want");

    withVersion();
    rerender(<Composer />);
    expect(screen.getByRole("button", { name: "Apply edit · 1 credit" })).toBeTruthy();
  });

  it("is disabled with a hint until a model is loaded", () => {
    useStudioStore.setState({ asset: null, analysis: null });
    render(<Composer />);
    expect(textarea().disabled).toBe(true);
    expect(textarea().getAttribute("placeholder")).toBe("Load a model first");
    expect(screen.queryByRole("list", { name: "Example prompts" })).toBeNull();
    expect(screen.queryByTestId("low-credits")).toBeNull();
  });

  it("suggestion chips fill and focus the textarea without submitting, then leave once a scene exists", () => {
    const submitPrompt = vi.fn();
    useStudioStore.setState({ submitPrompt });
    const { rerender } = render(<Composer />);
    const chips = screen.getByRole("list", { name: "Example prompts" });
    expect(chips.querySelectorAll("button")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: SUGGESTED_PRESETS[1].label }));
    expect(textarea().value).toBe(SUGGESTED_PRESETS[1].prompt);
    expect(document.activeElement).toBe(textarea());
    expect(submitPrompt).not.toHaveBeenCalled();

    withVersion();
    rerender(<Composer />);
    expect(screen.queryByRole("list", { name: "Example prompts" })).toBeNull();
  });

  it("keeps the presets under + once a version exists", () => {
    render(<Composer />);
    fireEvent.click(screen.getByRole("button", { name: "Model options" }));
    expect(screen.getByRole("button", { name: /sample car/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /sample product/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Start over/ })).toBeNull();
    expect(screen.queryByRole("button", { name: PRESETS[4].label })).toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });

    withVersion();
    fireEvent.click(screen.getByRole("button", { name: "Model options" }));
    expect(screen.queryByRole("button", { name: /Start over/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: PRESETS[4].label }));
    expect(textarea().value).toBe(PRESETS[4].prompt);
  });

  it("shows Start over inline in the second row only while the box has text, and it starts a new scene", () => {
    const startOver = vi.fn(() => new Promise(() => {}));
    useStudioStore.setState({ startOver: startOver as never });
    withVersion();
    render(<Composer />);
    expect(screen.queryByRole("button", { name: "Start over · 2 credits" })).toBeNull();

    fireEvent.change(textarea(), { target: { value: "  a fresh idea " } });
    const button = screen.getByRole("button", { name: "Start over · 2 credits" }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    expect(startOver).toHaveBeenCalledWith("a fresh idea");
  });

  it("offers one item, Add a model, under + while there is no model, which opens the file picker", () => {
    useStudioStore.setState({ asset: null, analysis: null });
    const click = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
    render(<Composer />);
    fireEvent.click(screen.getByRole("button", { name: "Model options" }));
    expect(screen.queryByRole("button", { name: /sample car/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /upload model/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Add a model" }));
    expect(click).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Model options" }).getAttribute("aria-expanded")).toBe("false");
    click.mockRestore();
  });

  it("shows the second row only after a scene exists and opens the drawer on Controls", () => {
    const { rerender } = render(<Composer />);
    expect(screen.queryByRole("button", { name: "Controls" })).toBeNull();
    expect(screen.queryByTestId("render-pill")).toBeNull();

    withVersion();
    rerender(<Composer />);
    expect(screen.getByTestId("render-pill")).toBeTruthy();
    // Render options (world, format, quality) live in the Render tab now, not as a composer chip.
    expect(screen.queryByRole("button", { name: /Output settings/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Controls" }));
    expect(useStudioUi.getState().drawerOpen).toBe(true);
    expect(useStudioUi.getState().drawerTab).toBe("controls");
  });

  it("the Render pill is the primary action once a scene exists: it opens the drawer on Render and focuses its button", () => {
    withVersion();
    useStudioStore.setState({ project: { id: "p", name: "Shoot", createdAt: 0, updatedAt: 0, assetId: "a1", analysis: null, selectedVersionId: "v1" } });
    render(
      <>
        <Composer />
        <SceneDrawer wide />
      </>,
    );
    fireEvent.click(screen.getByTestId("render-pill"));
    expect(useStudioUi.getState().drawerOpen).toBe(true);
    expect(useStudioUi.getState().drawerTab).toBe("render");
    // The send button is still there for edits.
    expect(screen.getByRole("button", { name: "Apply edit · 1 credit" })).toBeTruthy();
    // The drawer's Render button consumed the focus request.
    const inDrawer = within(screen.getByTestId("scene-drawer")).getByRole("button", { name: /^Render ·/ });
    expect(document.activeElement).toBe(inDrawer);
    expect(useStudioUi.getState().focusRequest).toBeNull();
  });

  it("folds only Controls and Preview path into the ⋯ menu; the Render pill stays at every width", () => {
    withVersion();
    render(<Composer />);
    expect(screen.getByTestId("render-pill").className).not.toContain("max-sm:hidden");
    const more = screen.getByRole("button", { name: "More" });
    expect(more.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(more);
    const menu = screen.getByRole("group", { name: "More" });
    expect(Array.from(menu.querySelectorAll("button")).map((b) => b.textContent)).toEqual(["Controls", "Preview path"]);
    fireEvent.click(menu.querySelectorAll("button")[0]);
    expect(useStudioUi.getState().drawerTab).toBe("controls");
    expect(more.getAttribute("aria-expanded")).toBe("false");
  });

  it("swaps the textarea for the planning steps after submit until the labour sequence is done", async () => {
    let resolve!: (v: unknown) => void;
    const submitPrompt = vi.fn(() => new Promise((r) => { resolve = r; }));
    useStudioStore.setState({ submitPrompt: submitPrompt as never });
    render(<Composer />);

    fireEvent.change(textarea(), { target: { value: "black studio" } });
    fireEvent.keyDown(textarea(), { key: "Enter" });

    // Synchronous feedback: the steps are mounted in the textarea's place before any await.
    expect(submitPrompt).toHaveBeenCalledWith("black studio");
    expect(screen.queryByRole("textbox", { name: "Describe your render" })).toBeNull();
    expect(useLabourStore.getState().labouring).toBe(true);
    expect(screen.getByText("Reading your prompt")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Generate scene · 2 credits" }) as HTMLButtonElement).disabled).toBe(true);

    // The store resolves quickly; the steps stay until the minimum labour elapses.
    await act(async () => {
      const v = version();
      useStudioStore.setState({ versions: [v], selectedVersionId: v.id, currentPlan: v.plan });
      resolve({ ok: true, value: v });
    });
    expect(screen.queryByRole("textbox", { name: "Describe your render" })).toBeNull();
    await act(async () => { vi.advanceTimersByTime(LABOUR_MIN_MS - 50); });
    expect(screen.queryByRole("textbox", { name: "Describe your render" })).toBeNull();

    await act(async () => { vi.advanceTimersByTime(100); });
    expect(textarea().disabled).toBe(false);
    expect(useLabourStore.getState().labouring).toBe(false);
    expect(textarea().value).toBe("");
  });

  it("Shift+Enter does not submit", () => {
    const submitPrompt = vi.fn();
    useStudioStore.setState({ submitPrompt });
    render(<Composer />);
    fireEvent.change(textarea(), { target: { value: "hi" } });
    fireEvent.keyDown(textarea(), { key: "Enter", shiftKey: true });
    expect(submitPrompt).not.toHaveBeenCalled();
  });

  it("warns before an action the balance cannot cover, once there is something to send", () => {
    useCreditsStore.setState({ balance: 1, loaded: true });
    render(<Composer />);
    expect(screen.queryByTestId("low-credits")).toBeNull();
    fireEvent.change(textarea(), { target: { value: "night" } });
    const notice = screen.getByTestId("low-credits");
    expect(notice.textContent).toContain("costs 2");
    expect(screen.getByRole("link", { name: "Get credits" }).getAttribute("href")).toBe("/pricing");
  });

  it("shows one notice at a time: a warning outranks an error, which outranks low credits", () => {
    useCreditsStore.setState({ balance: 1, loaded: true });
    useStudioStore.setState({ error: { code: "at_limit", message: "That's already as far as it goes." } });
    const { rerender } = render(<Composer />);
    fireEvent.change(textarea(), { target: { value: "night" } });
    expect(screen.getByTestId("prompt-error")).toBeTruthy();
    expect(screen.queryByTestId("low-credits")).toBeNull();

    useStudioStore.setState({ pendingWarning: { code: "capability_mismatch", message: "This model can't drive.", plan: defaultPlan("car"), prompt: "drive" } });
    rerender(<Composer />);
    expect(screen.getByTestId("warning-banner")).toBeTruthy();
    expect(screen.queryByTestId("prompt-error")).toBeNull();
  });
});
