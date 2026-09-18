// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ModelAnalysis, SceneVersion } from "@/lib/schema";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { useCreditsStore } from "@/lib/stores/credits";
import { useStudioStore } from "@/lib/stores/studio";
import { LABOUR_MIN_MS } from "./labour";
import { PromptDock } from "./PromptDock";
import { PRESETS } from "./presets";
import { useLabourStore } from "./useLabour";

const analysis: ModelAnalysis = {
  category: "car", confidence: 0.9, unitGuess: "m", scaleFactor: 1, dimensionsMeters: [4.5, 1.8, 1.4],
  parts: {}, capabilities: ["drive"], rigged: false,
};

function version(): SceneVersion {
  return { id: "v1", projectId: "p", index: 0, prompt: "x", parentId: null, plan: defaultPlan("car"), createdAt: Date.now() };
}

const textarea = () => screen.getByRole("textbox", { name: "Describe your render" }) as HTMLTextAreaElement;

describe("PromptDock", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useStudioStore.getState().reset();
    useLabourStore.getState().end();
    useCreditsStore.setState({ balance: 100, loaded: true });
    useStudioStore.setState({ analysis });
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("labels the action by cost before and after the first version", () => {
    const { rerender } = render(<PromptDock />);
    expect(screen.getByRole("button", { name: "Generate scene · 2 credits" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Start over/ })).toBeNull();

    useStudioStore.setState({ versions: [version()], selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    rerender(<PromptDock />);
    expect(screen.getByRole("button", { name: "Apply edit · 1 credit" })).toBeTruthy();
    expect((screen.getByRole("button", { name: /Start over/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("preset chips fill and focus the textarea without submitting", () => {
    const submitPrompt = vi.fn();
    useStudioStore.setState({ submitPrompt });
    render(<PromptDock />);
    fireEvent.click(screen.getByRole("button", { name: PRESETS[2].label }));
    expect(textarea().value).toBe(PRESETS[2].prompt);
    expect(document.activeElement).toBe(textarea());
    expect(submitPrompt).not.toHaveBeenCalled();
  });

  it("disables the textarea after submit until the labour sequence is done", async () => {
    let resolve!: (v: unknown) => void;
    const submitPrompt = vi.fn(() => new Promise((r) => { resolve = r; }));
    useStudioStore.setState({ submitPrompt: submitPrompt as never });
    render(<PromptDock />);

    fireEvent.change(textarea(), { target: { value: "black studio" } });
    fireEvent.keyDown(textarea(), { key: "Enter" });

    // Synchronous feedback: locked and the planning steps are mounted before any await.
    expect(submitPrompt).toHaveBeenCalledWith("black studio");
    expect(textarea().disabled).toBe(true);
    expect(useLabourStore.getState().labouring).toBe(true);
    expect(screen.getByText("Reading your prompt")).toBeTruthy();

    // The store resolves quickly; the input stays disabled until the minimum labour elapses.
    await act(async () => {
      const v = version();
      useStudioStore.setState({ versions: [v], selectedVersionId: v.id, currentPlan: v.plan });
      resolve({ ok: true, value: v });
    });
    expect(textarea().disabled).toBe(true);
    await act(async () => { vi.advanceTimersByTime(LABOUR_MIN_MS - 50); });
    expect(textarea().disabled).toBe(true);

    await act(async () => { vi.advanceTimersByTime(100); });
    expect(textarea().disabled).toBe(false);
    expect(useLabourStore.getState().labouring).toBe(false);
    expect(textarea().value).toBe("");
  });

  it("Shift+Enter does not submit", () => {
    const submitPrompt = vi.fn();
    useStudioStore.setState({ submitPrompt });
    render(<PromptDock />);
    fireEvent.change(textarea(), { target: { value: "hi" } });
    fireEvent.keyDown(textarea(), { key: "Enter", shiftKey: true });
    expect(submitPrompt).not.toHaveBeenCalled();
  });

  it("warns before an action the balance cannot cover", () => {
    useCreditsStore.setState({ balance: 1, loaded: true });
    render(<PromptDock />);
    const notice = screen.getByTestId("low-credits");
    expect(notice.textContent).toContain("costs 2");
    expect(screen.getByRole("link", { name: "Get credits" }).getAttribute("href")).toBe("/pricing");
  });
});
