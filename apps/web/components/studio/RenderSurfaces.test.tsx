// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderCost } from "@/lib/render/cost";
import { WORLDS } from "@/lib/render/worlds";
import type { Asset, Project, RenderJob, User } from "@/lib/schema";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { services } from "@/lib/services";
import { useAuthStore } from "@/lib/stores/auth";
import { useRenderStore } from "@/lib/stores/render";
import { useStudioStore } from "@/lib/stores/studio";
import { JobProgress, jobFraction } from "./JobProgress";
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
  const asset: Asset = { id: "a1", projectId: "p1", fileName: "car.glb", format: "glb", sizeBytes: 10, source: "sample", blobKey: null, sampleUrl: "/samples/car.glb", thumbnailKey: null };

  beforeEach(() => {
    useStudioStore.getState().reset();
    useRenderStore.getState().reset();
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  const renderButton = () => screen.getByRole("button", { name: /^Render ·/ }) as HTMLButtonElement;

  it("disables Render with a hint when there is no model", () => {
    render(<RenderPanel />);
    expect(renderButton().disabled).toBe(true);
    expect(screen.getByRole("note").textContent).toContain("Add a model first");
  });

  it("offers every graded world, both formats and prices each tier; Final is a Creator feature on Free", () => {
    useStudioStore.setState({ project, asset, selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    render(<RenderPanel />);
    const world = screen.getByRole("radiogroup", { name: "World" });
    const worlds = within(world).getAllByRole("radio");
    expect(worlds.map((w) => w.querySelector("span")?.textContent)).toEqual(["Auto", ...WORLDS.map((w) => w.label)]);
    expect(within(world).getByRole("radio", { name: /^Auto/ }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByRole("radio", { name: "Vertical 9:16" }).getAttribute("aria-checked")).toBe("true");

    const quality = screen.getByRole("radiogroup", { name: "Quality" });
    expect(within(quality).getByRole("radio", { name: /Preview/ }).textContent).toContain(`${renderCost("preview")} credits`);
    const final = within(quality).getByRole("radio", { name: /Final/ }) as HTMLButtonElement;
    expect(final.disabled).toBe(true);
    expect(final.textContent).toContain("Creator");
    expect(renderButton().textContent).toContain(`${renderCost("preview")} credits`);
    // The optional controls stay behind the disclosure.
    expect(screen.queryByLabelText("Seed")).toBeNull();
  });

  it("starts from the scene's format, else the Settings defaults, never from a tier the plan lacks", () => {
    const user: User = {
      id: "u1", email: "a@b.co", name: "A", avatarSeed: "s", plan: "free", createdAt: 0,
      prefs: { defaultOutput: { tier: "final", aspect: "16:9" }, localAgent: "not_connected" },
    };
    useAuthStore.setState({ user });
    useStudioStore.setState({ project, asset, selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    const { unmount } = render(<RenderPanel />);
    // Settings asked for Final, but Free renders Preview only.
    expect(screen.getByRole("radio", { name: "Landscape 16:9" }).getAttribute("aria-checked")).toBe("true");
    expect(within(screen.getByRole("radiogroup", { name: "Quality" })).getByRole("radio", { name: /Preview/ }).getAttribute("aria-checked")).toBe("true");
    unmount();

    // A scene that asked for "vertical" wins over the Settings default.
    const plan = { ...defaultPlan("car"), output: { durationS: 10 as const, aspect: "9:16" as const } };
    useStudioStore.setState({ versions: [{ id: "v1", projectId: "p1", index: 0, prompt: "vertical", parentId: null, plan, createdAt: 0 }] });
    render(<RenderPanel />);
    expect(screen.getByRole("radio", { name: "Vertical 9:16" }).getAttribute("aria-checked")).toBe("true");
    useAuthStore.setState({ user: null });
  });

  it("sends the contract params and shows the not-connected state (Local mode)", async () => {
    useStudioStore.setState({ project, asset, selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    const spy = vi.spyOn(services.render, "request");
    render(<RenderPanel />);

    fireEvent.change(screen.getByLabelText("Direction"), { target: { value: "slow orbit at dusk" } });
    fireEvent.click(screen.getByRole("radio", { name: /^Night street/ }));
    fireEvent.click(screen.getByRole("radio", { name: "Landscape 16:9" }));
    const more = screen.getByRole("button", { name: /More options/ });
    fireEvent.click(more);
    expect(more.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(screen.getByRole("radio", { name: "10 s" }));
    fireEvent.click(screen.getByRole("radio", { name: "Custom" }));
    fireEvent.change(screen.getByLabelText("Paint colour"), { target: { value: "#1a2b3c" } });
    fireEvent.click(screen.getByRole("radio", { name: "Metallic" }));
    fireEvent.change(screen.getByLabelText("Seed"), { target: { value: "12345" } });

    fireEvent.click(renderButton());
    await waitFor(() => expect(screen.getByTestId("render-not-connected")).toBeTruthy());
    expect(spy).toHaveBeenCalledOnce();
    const req = spy.mock.calls[0][0];
    expect(req).toMatchObject({ projectId: "p1", uploadId: "a1", versionId: "v1" });
    expect(req.params).toEqual({
      prompt: "slow orbit at dusk", tier: "preview", aspect: "16:9", world: "night_street",
      duration: 10, paint: "#1a2b3c", finish: "metallic", seed: 12345,
    });
    expect(req.idempotencyKey.length).toBeGreaterThanOrEqual(8);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("refuses an out-of-range seed before sending anything", () => {
    useStudioStore.setState({ project, asset, selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    render(<RenderPanel />);
    fireEvent.click(screen.getByRole("button", { name: /More options/ }));
    fireEvent.change(screen.getByLabelText("Seed"), { target: { value: "9999999999" } });
    expect(renderButton().disabled).toBe(true);
    expect(screen.getByRole("note").textContent).toContain("Seed must be a whole number");
  });

  it("follows the newest job: progress with Cancel while live, the result once complete", () => {
    useStudioStore.setState({ project, asset, selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    useRenderStore.setState({ projectId: "p1", loaded: true, jobs: [job({ projectId: "p1", status: "RENDERING", frame: 30, target: "cloud" })] });
    const cancel = vi.spyOn(services.render, "cancel");
    const { rerender } = render(<RenderPanel />);
    expect(screen.getByTestId("frame-counter").textContent).toBe("Frame 30 / 300");
    fireEvent.click(screen.getByRole("button", { name: "Cancel render" }));
    expect(cancel).toHaveBeenCalledWith("job-1");

    useRenderStore.setState({
      jobs: [job({ projectId: "p1", kind: "preview", status: "COMPLETE", frame: 300, resultUrl: "blob:v", params: { prompt: "", tier: "preview", world: "golden_field", aspect: "9:16" } })],
    });
    rerender(<RenderPanel />);
    expect(screen.getByText("Your render is ready")).toBeTruthy();
    expect(screen.getByText(/Preview · Golden field · 9:16/)).toBeTruthy();
  });

  it("takes focus on its Render button when the composer asks, then clears the request", () => {
    useStudioStore.setState({ project, asset, selectedVersionId: "v1", currentPlan: defaultPlan("car") });
    useStudioUi.getState().openRender();
    render(<RenderPanel />);
    expect(document.activeElement).toBe(renderButton());
    expect(useStudioUi.getState().focusRequest).toBeNull();
    useStudioUi.getState().reset();
  });
});
