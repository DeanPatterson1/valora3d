// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Project, RenderJob } from "@/lib/schema";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { services } from "@/lib/services";
import { useStudioStore } from "@/lib/stores/studio";
import { JobProgress, jobFraction } from "./JobProgress";
import { summariseOutput } from "./OutputSettings";
import { RenderPanel } from "./RenderPanel";
import { RenderResult } from "./RenderResult";
import { useStudioUi } from "./useStudioUi";

const job = (patch: Partial<RenderJob>): RenderJob => ({
  id: "job-1", projectId: "p1", versionId: "v1", kind: "final", target: "local",
  status: "QUEUED", frame: 0, totalFrames: 300, error: null, resultUrl: null, ...patch,
});

describe("JobProgress", () => {
  afterEach(cleanup);

  it("shows the frame counter and progress while rendering", () => {
    render(<JobProgress job={job({ status: "RENDERING", frame: 204 })} />);
    expect(screen.getByTestId("frame-counter").textContent).toBe("Frame 204 / 300");
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBe("68");
    expect(bar.getAttribute("aria-valuetext")).toBe("Frame 204 of 300");
  });

  it("shows the error and a Retry button when failed", () => {
    const onRetry = vi.fn();
    render(<JobProgress job={job({ status: "FAILED", frame: 12, error: "GPU ran out of memory." })} onRetry={onRetry} />);
    expect(screen.getByRole("alert").textContent).toBe("GPU ran out of memory.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("uses the queued copy and no counter before rendering", () => {
    render(<JobProgress job={job({ status: "QUEUED" })} />);
    expect(screen.getByText("Waiting for a GPU.")).toBeTruthy();
    expect(screen.queryByTestId("frame-counter")).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("fills the bar past the rendering stage", () => {
    expect(jobFraction(job({ status: "ENCODING", frame: 300 }))).toBe(1);
    expect(jobFraction(job({ status: "PREPARING" }))).toBe(0);
    expect(jobFraction(job({ status: "RENDERING", frame: 150 }))).toBe(0.5);
  });
});

describe("RenderResult", () => {
  afterEach(cleanup);

  it("disables Download without a result url", () => {
    render(<RenderResult job={job({ status: "COMPLETE", frame: 300 })} onRegenerate={() => {}} />);
    const download = screen.getByRole("button", { name: "Download" }) as HTMLButtonElement;
    expect(download.disabled).toBe(true);
    expect(screen.getByText("Your render will appear here")).toBeTruthy();
    expect(document.querySelector("video")).toBeNull();
  });

  it("offers a video and a download link with a url", () => {
    const onRegenerate = vi.fn();
    render(<RenderResult job={job({ status: "COMPLETE", frame: 300, resultUrl: "blob:render" })} onRegenerate={onRegenerate} />);
    expect(document.querySelector("video")?.getAttribute("src")).toBe("blob:render");
    const link = screen.getByRole("link", { name: "Download" });
    expect(link.getAttribute("href")).toBe("blob:render");
    fireEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(onRegenerate).toHaveBeenCalledOnce();
  });
});

describe("RenderPanel", () => {
  const project: Project = { id: "p1", name: "Shoot", createdAt: 0, updatedAt: 0, assetId: "a1", analysis: null, selectedVersionId: "v1" };

  beforeEach(() => useStudioStore.getState().reset());
  afterEach(cleanup);

  /** The chip-style disclosure that hides the target radio cards. */
  const targetChip = () => screen.getByRole("button", { name: /Local GPU|Cloud GPU/ });

  it("disables actions with a hint when there is no plan", () => {
    render(<RenderPanel />);
    expect((screen.getByRole("button", { name: /^Render/ }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /Generate preview/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("note").textContent).toContain("Generate a scene first");
  });

  it("shows prices, the output summary and the not-connected state after Generate preview", async () => {
    useStudioStore.setState({ project, selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    const spy = vi.spyOn(services.render, "requestPreview");
    render(<RenderPanel />);

    expect(screen.getByTestId("output-summary").textContent).toBe("10 s · 1080p · 30 fps · High");

    // Target cards stay behind the chip until asked for.
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    const chip = targetChip();
    expect(chip.textContent).toBe("Cloud GPU · No setup · cloud GPU processing");
    expect(chip.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(chip);
    expect(chip.getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById(chip.getAttribute("aria-controls")!)).toBeTruthy();
    expect((screen.getByRole("radio", { name: /Local GPU/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("radio", { name: /Cloud GPU/ }).textContent).toContain("60 credits");
    expect(screen.getByRole("button", { name: /^Render/ }).textContent).toContain("60 credits");

    fireEvent.click(screen.getByRole("button", { name: "Generate preview · 3 credits" }));
    await waitFor(() => expect(screen.getByTestId("render-not-connected")).toBeTruthy());
    expect(spy).toHaveBeenCalledWith("p1", "v1");
    expect(screen.getByText("Rendering is currently unavailable. Please try again later or contact support.")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps cloud selected with the keyboard and sends cloud jobs at launch", async () => {
    useStudioStore.setState({ project, selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    const spy = vi.spyOn(services.render, "requestFinal");
    render(<RenderPanel />);

    expect(screen.queryByRole("radio", { name: /Local GPU/ })).toBeNull();
    fireEvent.click(targetChip());
    const local = screen.getByRole("radio", { name: /Local GPU/ });
    expect(local.getAttribute("aria-checked")).toBe("false");
    expect((local as HTMLButtonElement).disabled).toBe(true);
    const cloud = screen.getByRole("radio", { name: /Cloud GPU/ });
    fireEvent.keyDown(cloud, { key: "ArrowLeft" });
    expect(cloud.getAttribute("aria-checked")).toBe("true");
    expect(targetChip().textContent).toBe("Cloud GPU · No setup · cloud GPU processing");
    expect(screen.getByRole("button", { name: /^Render/ }).textContent).toContain("60 credits");

    fireEvent.click(screen.getByRole("button", { name: /^Render/ }));
    await waitFor(() => expect(screen.getByTestId("render-not-connected")).toBeTruthy());
    expect(spy).toHaveBeenCalledWith("p1", "v1", "cloud");
  });

  it("shares the composer's output formatter", () => {
    expect(summariseOutput({ fps: 24, durationS: 5, resolution: "4k", quality: "ultra" })).toBe("5 s · 4k · 24 fps · Ultra");
  });

  it("takes focus on its Render button when the composer asks, then clears the request", () => {
    useStudioStore.setState({ project, selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    useStudioUi.getState().openRender();
    render(<RenderPanel />);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: /^Render/ }));
    expect(useStudioUi.getState().focusRequest).toBeNull();
    useStudioUi.getState().reset();
  });
});
