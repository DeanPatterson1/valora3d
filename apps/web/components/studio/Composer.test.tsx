// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Asset, ModelAnalysis, SceneVersion } from "@/lib/schema";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { useCreditsStore } from "@/lib/stores/credits";
import { useStudioStore } from "@/lib/stores/studio";
import { Composer } from "./Composer";
import { LABOUR_MIN_MS } from "./labour";
import { PRESETS, SUGGESTED_PRESETS } from "./presets";
import { useLabourStore } from "./useLabour";
import { useStudioUi } from "./useStudioUi";

const analysis: ModelAnalysis = {
  category: "car", confidence: 0.9, unitGuess: "m", scaleFactor: 1, dimensionsMeters: [4.5, 1.8, 1.4],
  parts: {}, capabilities: ["drive"], rigged: false,
};
const asset: Asset = {
  id: "a1", projectId: "p", fileName: "car.glb", format: "glb", sizeBytes: 10, source: "sample", blobKey: null, sampleUrl: "/samples/car.glb", thumbnailKey: null,
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

  it("keeps Start over and the presets under + once a version exists", () => {
    render(<Composer />);
    fireEvent.click(screen.getByRole("button", { name: "Model options" }));
    expect(screen.getByRole("button", { name: /sample car/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /sample product/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Start over/ })).toBeNull();
    expect(screen.queryByRole("button", { name: PRESETS[4].label })).toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });

    withVersion();
    fireEvent.click(screen.getByRole("button", { name: "Model options" }));
    expect((screen.getByRole("button", { name: "Start over · 2 credits" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: PRESETS[4].label }));
    expect(textarea().value).toBe(PRESETS[4].prompt);
    fireEvent.click(screen.getByRole("button", { name: "Model options" }));
    expect((screen.getByRole("button", { name: "Start over · 2 credits" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows the second row only after a scene exists and opens the drawer on Controls", () => {
    const { rerender } = render(<Composer />);
    expect(screen.queryByRole("button", { name: "Controls" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Output settings/ })).toBeNull();

    withVersion();
    rerender(<Composer />);
    expect(screen.getByRole("button", { name: "Output settings: 10s · 1080p · 30fps · High" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Controls" }));
    expect(useStudioUi.getState().drawerOpen).toBe(true);
    expect(useStudioUi.getState().drawerTab).toBe("controls");
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

  it("warns before an action the balance cannot cover", () => {
    useCreditsStore.setState({ balance: 1, loaded: true });
    render(<Composer />);
    const notice = screen.getByTestId("low-credits");
    expect(notice.textContent).toContain("costs 2");
    expect(screen.getByRole("link", { name: "Get credits" }).getAttribute("href")).toBe("/pricing");
  });

  it("shows one notice at a time: a warning outranks an error, which outranks low credits", () => {
    useCreditsStore.setState({ balance: 1, loaded: true });
    useStudioStore.setState({ error: { code: "at_limit", message: "That's already as far as it goes." } });
    const { rerender } = render(<Composer />);
    expect(screen.getByTestId("prompt-error")).toBeTruthy();
    expect(screen.queryByTestId("low-credits")).toBeNull();

    useStudioStore.setState({ pendingWarning: { code: "capability_mismatch", message: "This model can't drive.", plan: defaultPlan("car"), prompt: "drive" } });
    rerender(<Composer />);
    expect(screen.getByTestId("warning-banner")).toBeTruthy();
    expect(screen.queryByTestId("prompt-error")).toBeNull();
  });
});
