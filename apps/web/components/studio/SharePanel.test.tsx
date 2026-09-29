// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useToastStore } from "@/components/ui";
import type { RenderJob } from "@/lib/schema";
import { fail, ok } from "@/lib/services/result";
import type { RenderShareService } from "@/lib/services/types";
import type { RenderShare } from "@/lib/share/types";
import { RenderResult } from "./RenderResult";

const SHARE: RenderShare = { slug: "AbCdEfGhIjKlMnOpQrStUv12", path: "/r/AbCdEfGhIjKlMnOpQrStUv12", showPrompt: false, createdAt: 0, viewCount: 7 };
const job: RenderJob = {
  id: "job-1", projectId: "p1", versionId: "v1", kind: "final", target: "cloud",
  status: "COMPLETE", frame: 300, totalFrames: 300, error: null, resultUrl: "blob:render",
};

function service(initial: RenderShare | null = null): RenderShareService & { [K in keyof RenderShareService]: ReturnType<typeof vi.fn> } {
  let current = initial;
  return {
    getShare: vi.fn(async () => ok(current)),
    share: vi.fn(async (_id: string, { showPrompt }: { showPrompt: boolean }) => ok((current = { ...SHARE, showPrompt }))),
    unshare: vi.fn(async () => {
      current = null;
      return ok(undefined);
    }),
  };
}

const toasts = () => useToastStore.getState().toasts.map((t) => t.message);

describe("sharing a finished render", () => {
  const writeText = vi.fn(async () => {});
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    writeText.mockClear();
  });
  afterEach(cleanup);

  it("offers no Share without a share service or without a file", () => {
    render(<RenderResult job={job} onRegenerate={() => {}} />);
    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
    cleanup();
    render(<RenderResult job={{ ...job, resultUrl: null, expired: true }} onRegenerate={() => {}} share={service()} />);
    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
  });

  it("creates nothing until the owner asks, keeps the prompt private by default, then copies the link", async () => {
    const svc = service();
    render(<RenderResult job={job} onRegenerate={() => {}} share={svc} />);
    const toggle = screen.getByRole("button", { name: "Share" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    const create = await screen.findByRole("button", { name: "Create link" });
    expect(svc.share).not.toHaveBeenCalled();
    expect((screen.getByLabelText("Show my prompt on the page") as HTMLInputElement).checked).toBe(false);
    fireEvent.click(create);
    await waitFor(() => expect(svc.share).toHaveBeenCalledWith("job-1", { showPrompt: false }));
    const link = (await screen.findByLabelText("Share link")) as HTMLInputElement;
    expect(link.value).toBe(`${window.location.origin}/r/${SHARE.slug}`);
    expect(writeText).toHaveBeenCalledWith(link.value);
    await waitFor(() => expect(toasts()).toContain("Link created and copied."));
  });

  it("shows the live link, copies it, toggles the prompt and stops sharing", async () => {
    const svc = service({ ...SHARE });
    render(<RenderResult job={job} onRegenerate={() => {}} share={svc} />);
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    await screen.findByLabelText("Share link");
    expect(screen.getByText("7 views")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));
    await waitFor(() => expect(toasts()).toContain("Link copied."));

    fireEvent.click(screen.getByLabelText("Show my prompt on the page"));
    await waitFor(() => expect(svc.share).toHaveBeenCalledWith("job-1", { showPrompt: true }));

    fireEvent.click(screen.getByRole("button", { name: "Stop sharing" }));
    await waitFor(() => expect(svc.unshare).toHaveBeenCalledWith("job-1"));
    expect(await screen.findByRole("button", { name: "Create link" })).toBeTruthy();
    expect(toasts()).toContain("Sharing stopped. The old link no longer works.");
  });

  it("reports a refused link (rate limit) without pretending it worked", async () => {
    const svc = service();
    svc.share.mockResolvedValueOnce(fail("rate_limited", "You've created a lot of links recently. Try again in an hour."));
    render(<RenderResult job={job} onRegenerate={() => {}} share={svc} />);
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    fireEvent.click(await screen.findByRole("button", { name: "Create link" }));
    await waitFor(() => expect(toasts()).toContain("You've created a lot of links recently. Try again in an hour."));
    expect(screen.queryByLabelText("Share link")).toBeNull();
  });
});
