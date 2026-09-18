// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStudioStore } from "@/lib/stores/studio";
import { PromptErrors, stripTry } from "./PromptErrors";

describe("PromptErrors", () => {
  beforeEach(() => useStudioStore.getState().reset());
  afterEach(cleanup);

  it("renders nothing without an error", () => {
    render(<PromptErrors onHint={() => {}} />);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders edit_not_understood hints as chips that fill the textarea without submitting", () => {
    const onHint = vi.fn();
    useStudioStore.setState({
      error: { code: "edit_not_understood", message: "I didn't catch that.", hints: ['Try: "make it darker"', 'Try: "add rain"', 'Try: "move the camera closer"'] },
    });
    render(<PromptErrors onHint={onHint} />);

    expect(screen.getByRole("alert").textContent).toContain("I didn't catch that.");
    const chips = screen.getAllByRole("button", { pressed: false });
    expect(chips.map((c) => c.textContent)).toEqual(["make it darker", "add rain", "move the camera closer"]);

    fireEvent.click(chips[1]);
    expect(onHint).toHaveBeenCalledWith("add rain");
    // Picking a hint clears the error; nothing was submitted.
    expect(useStudioStore.getState().error).toBeNull();
  });

  it("links to pricing on insufficient_credits", () => {
    useStudioStore.setState({ error: { code: "insufficient_credits", message: "You need 2 credits but have 1." } });
    render(<PromptErrors onHint={() => {}} />);
    const link = screen.getByRole("link", { name: "Get credits" });
    expect(link.getAttribute("href")).toBe("/pricing");
  });

  it("shows at_limit and generic messages, and dismisses via the store", () => {
    useStudioStore.setState({ error: { code: "at_limit", message: "Already as wide as it goes." } });
    render(<PromptErrors onHint={() => {}} />);
    expect(screen.getByRole("alert").textContent).toContain("Already as wide as it goes.");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(useStudioStore.getState().error).toBeNull();
    cleanup();

    useStudioStore.setState({ error: { code: "something_else", message: "Odd failure." } });
    render(<PromptErrors onHint={() => {}} />);
    expect(screen.getByRole("alert").textContent).toContain("Odd failure.");
  });

  it("prefers a local error (busy) and dismisses it locally", () => {
    const onDismissLocal = vi.fn();
    render(<PromptErrors onHint={() => {}} local={{ code: "busy", message: "x" }} onDismissLocal={onDismissLocal} />);
    expect(screen.getByRole("alert").textContent).toContain("Still working on the last change.");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismissLocal).toHaveBeenCalled();
  });

  it("stripTry removes the Try: wrapper", () => {
    expect(stripTry('Try: "make it darker"')).toBe("make it darker");
    expect(stripTry("add rain")).toBe("add rain");
  });
});
