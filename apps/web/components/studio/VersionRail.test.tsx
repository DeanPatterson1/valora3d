// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import type { SceneVersion } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";
import { relativeTime, VersionRail, versionLabel } from "./VersionRail";

const plan = defaultPlan("car");
const now = Date.now();

function version(index: number, prompt: string, createdAt = now): SceneVersion {
  return { id: `v${index}`, projectId: "p1", index, prompt, parentId: index ? `v${index - 1}` : null, plan, createdAt };
}

const versions = [
  version(0, "Rainy night city street", now - 5 * 60_000),
  version(1, "manual: fog", now - 40_000),
  version(2, "Make it brighter", now),
];

describe("VersionRail", () => {
  beforeEach(() => useStudioStore.getState().reset());
  afterEach(cleanup);

  it("shows the empty state without versions", () => {
    render(<VersionRail versions={[]} />);
    expect(screen.getByText("Your scene history appears here.")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("labels each version 1-based with its prompt and marks the selected one", () => {
    useStudioStore.setState({ versions, selectedVersionId: "v1" });
    render(<VersionRail versions={versions} />);

    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.getAttribute("aria-label"))).toEqual([
      "Version 1: Rainy night city street",
      "Version 2: manual: fog",
      "Version 3: Make it brighter",
    ]);
    expect(items[1].getAttribute("aria-current")).toBe("true");
    expect(items[0].getAttribute("aria-current")).toBeNull();
    expect(items[2].getAttribute("aria-current")).toBeNull();

    // Manual versions read as a human phrase with a tag; others keep the user's words.
    expect(screen.getByText("Fog adjusted")).toBeTruthy();
    expect(screen.getByText("manual")).toBeTruthy();
    expect(screen.getByText("Make it brighter")).toBeTruthy();
    expect(screen.getByText("5 min ago")).toBeTruthy();
    expect(screen.getAllByText("just now")).toHaveLength(2);
  });

  it("selects on click", () => {
    const selectVersion = vi.fn(async () => {});
    useStudioStore.setState({ versions, selectedVersionId: "v2", selectVersion });
    render(<VersionRail versions={versions} />);
    fireEvent.click(screen.getByRole("listitem", { name: "Version 1: Rainy night city street" }));
    expect(selectVersion).toHaveBeenCalledWith("v0");
  });

  it("ArrowDown then Enter selects the next version", () => {
    const selectVersion = vi.fn(async () => {});
    useStudioStore.setState({ versions, selectedVersionId: "v0", selectVersion });
    render(<VersionRail versions={versions} />);

    const [first, second] = screen.getAllByRole("listitem");
    // The selected item is the single tab stop.
    expect(first.tabIndex).toBe(0);
    expect(second.tabIndex).toBe(-1);

    first.focus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(document.activeElement).toBe(second);
    fireEvent.keyDown(second, { key: "Enter" });
    expect(selectVersion).toHaveBeenCalledWith("v1");

    fireEvent.keyDown(second, { key: "ArrowUp" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: " " });
    expect(selectVersion).toHaveBeenLastCalledWith("v0");
  });

  it("ignores interaction while busy", () => {
    const selectVersion = vi.fn(async () => {});
    useStudioStore.setState({ versions, selectedVersionId: "v0", selectVersion, busy: "planning" });
    render(<VersionRail versions={versions} />);
    const [, second] = screen.getAllByRole("listitem");
    fireEvent.click(second);
    fireEvent.keyDown(second, { key: "Enter" });
    expect(selectVersion).not.toHaveBeenCalled();
    expect(second.getAttribute("data-disabled")).toBe("true");
    expect(screen.getByRole("list").getAttribute("aria-busy")).toBe("true");
  });

  it("phrases manual labels and relative times", () => {
    expect(versionLabel("manual: output")).toEqual({ text: "Output changed", manual: true });
    expect(versionLabel("manual: depthOfField")).toEqual({ text: "Depth of field adjusted", manual: true });
    expect(versionLabel("Slow orbit")).toEqual({ text: "Slow orbit", manual: false });
    expect(relativeTime(now, now)).toBe("just now");
    expect(relativeTime(now - 3 * 60_000, now)).toBe("3 min ago");
    expect(relativeTime(now - 2 * 3_600_000, now)).toBe("2 h ago");
    expect(relativeTime(now - 4 * 86_400_000, now)).toBe("4 d ago");
  });
});
