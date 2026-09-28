import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

// The site key is read at module load, so it must be set before the form is imported.
const previousKey = vi.hoisted(() => {
  const old = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = "test-site-key";
  return old;
});
vi.mock("next/script", () => ({ default: ({ onReady }: { onReady: () => void }) => (
  <button type="button" onClick={onReady}>Load challenge script</button>
) }));
import { EmailPasswordForm } from "./EmailPasswordForm";

type Options = { callback: (token: string) => void };
afterEach(() => { cleanup(); delete window.turnstile; });
afterAll(() => {
  if (previousKey === undefined) delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  else process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = previousKey;
});

describe("EmailPasswordForm with Turnstile configured", () => {
  it("log-in: needs a solved challenge, passes it as the CAPTCHA token, then asks for a fresh one", async () => {
    const renderWidget = vi.fn((_el: HTMLElement, _options: Options) => `w${renderWidget.mock.calls.length}`);
    window.turnstile = { render: renderWidget as never, remove: vi.fn() };
    const onSubmit = vi.fn(async () => "That email and password don't match.");
    render(<EmailPasswordForm mode="login" onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText("Load challenge script"));
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "ada@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "longenough" } });

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getAllByText("Complete the security check and try again.").length).toBeGreaterThan(0);

    act(() => renderWidget.mock.calls[0][1].callback("solved"));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ captchaToken: "solved" })));
    // Single-use token: the widget is rebuilt for the next attempt.
    fireEvent.click(await screen.findByText("Load challenge script"));
    await waitFor(() => expect(renderWidget).toHaveBeenCalledTimes(2));
  });
});
