import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

const previousKey = vi.hoisted(() => {
  const old = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = "test-site-key";
  return old;
});
vi.mock("next/script", () => ({ default: ({ onReady, onError }: { onReady: () => void; onError: () => void }) => (
  <><button onClick={onReady}>Load challenge script</button><button onClick={onError}>Fail challenge script</button></>
) }));
import { Turnstile } from "./Turnstile";

afterEach(() => { cleanup(); delete window.turnstile; });
afterAll(() => {
  if (previousKey === undefined) delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  else process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = previousKey;
});

describe("Turnstile lifecycle", () => {
  it("reports solved and expired tokens and removes widgets on remount", () => {
    const renderWidget = vi.fn(() => "widget-id");
    const remove = vi.fn();
    window.turnstile = { render: renderWidget, remove };
    const onToken = vi.fn();
    const { unmount } = render(<Turnstile action="signup" onToken={onToken} />);
    fireEvent.click(screen.getByText("Load challenge script"));
    expect(renderWidget).toHaveBeenCalledOnce();
    const options = (renderWidget.mock.calls[0] as unknown as Parameters<NonNullable<typeof window.turnstile>["render"]>)[1];
    expect(options).toMatchObject({ action: "signup", sitekey: "test-site-key", theme: "dark" });
    options.callback("token");
    expect(onToken).toHaveBeenLastCalledWith("token");
    options["expired-callback"]();
    expect(onToken).toHaveBeenLastCalledWith("");
    unmount();
    expect(remove).toHaveBeenCalledWith("widget-id");
  });
  it("makes script failures visible and clears the token", () => {
    const onToken = vi.fn();
    render(<Turnstile action="forgot-password" onToken={onToken} />);
    fireEvent.click(screen.getByText("Fail challenge script"));
    expect(screen.getByRole("alert").textContent).toContain("Security check unavailable");
    expect(onToken).toHaveBeenCalledWith("");
  });
});
