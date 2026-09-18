import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useToastStore } from "./Toast";

describe("useToastStore", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useToastStore.setState({ toasts: [] });
  });
  afterEach(() => vi.useRealTimers());

  it("pushes and auto-dismisses after 4s", () => {
    const id = useToastStore.getState().push({ kind: "info", message: "Saved" });
    expect(useToastStore.getState().toasts).toEqual([{ id, kind: "info", message: "Saved" }]);
    vi.advanceTimersByTime(3999);
    expect(useToastStore.getState().toasts).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("dismisses by id", () => {
    const a = useToastStore.getState().push({ kind: "success", message: "A" });
    const b = useToastStore.getState().push({ kind: "danger", message: "B" });
    useToastStore.getState().dismiss(a);
    expect(useToastStore.getState().toasts.map((t) => t.id)).toEqual([b]);
  });
});
