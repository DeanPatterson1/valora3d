// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Project } from "@/lib/schema";
import { useProjectsStore } from "@/lib/stores/projects";
import { useToastStore } from "@/components/ui";
import { Dashboard } from "./Dashboard";
import { projectMeta, relativeTime } from "./meta";

const push = vi.fn();
const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(search),
}));

// jsdom has no <dialog> methods; mirror the open attribute so queries work.
beforeEach(() => {
  const proto = HTMLDialogElement.prototype as HTMLDialogElement & { showModal?: () => void; close?: () => void };
  proto.showModal = function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  proto.close = function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});

const now = Date.now();
function project(id: string, name: string, extra: Partial<Project> = {}): Project {
  return {
    id,
    name,
    createdAt: now - 3 * 3600_000,
    updatedAt: now - 2 * 3600_000,
    assetId: null,
    analysis: null,
    selectedVersionId: null,
    ...extra,
  };
}

const carAnalysis: Project["analysis"] = {
  category: "car",
  confidence: 0.9,
  unitGuess: "m",
  scaleFactor: 1,
  dimensionsMeters: [4.7, 1.4, 1.9],
  parts: {},
  capabilities: [],
  rigged: false,
};

function seed(projects: Project[], versionCounts: Record<string, number> = {}) {
  useProjectsStore.setState({
    projects,
    versionCounts,
    loaded: true,
    error: null,
    refresh: vi.fn(async () => {}),
    rename: vi.fn(async () => {}),
    remove: vi.fn(async () => {}),
  });
}

describe("projectMeta", () => {
  it("formats category, versions and relative time", () => {
    const p = project("p1", "Coupe", { assetId: "a1", analysis: carAnalysis });
    expect(projectMeta(p, 3, now)).toBe("Car · 3 versions · 2 h ago");
    expect(projectMeta(p, 1, now)).toBe("Car · 1 version · 2 h ago");
  });

  it("falls back to the project state label when there are no versions", () => {
    expect(projectMeta(project("p1", "A"), 0, now)).toBe("No model · 2 h ago");
    expect(projectMeta(project("p1", "A", { assetId: "a1" }), 0, now)).toBe("Model ready · 2 h ago");
  });

  it("relativeTime buckets", () => {
    expect(relativeTime(now - 10_000, now)).toBe("just now");
    expect(relativeTime(now - 5 * 60_000, now)).toBe("5 min ago");
    expect(relativeTime(now - 3 * 24 * 3600_000, now)).toBe("3 d ago");
  });
});

describe("Dashboard", () => {
  beforeEach(() => {
    search = "";
    push.mockReset();
    replace.mockReset();
    useToastStore.setState({ toasts: [] });
  });
  afterEach(cleanup);

  it("shows the empty state with one primary action", () => {
    seed([]);
    render(<Dashboard />);
    expect(screen.getByText("Create your first project")).toBeTruthy();
    expect(screen.getByText("Upload a model, describe the shot, get a cinematic render.")).toBeTruthy();
    expect(screen.queryByRole("list", { name: "Projects" })).toBeNull();
    // The centred CTA is the only "New project" action; the header button waits for the first project.
    expect(screen.getAllByRole("button", { name: "New project" }).length).toBe(1);
  });

  it("renders a card with name, meta line and a link to the studio", () => {
    seed([project("p1", "Coupe", { assetId: "a1", analysis: carAnalysis })], { p1: 3 });
    render(<Dashboard />);
    // With projects present the header button returns.
    expect(screen.getAllByRole("button", { name: "New project" }).length).toBe(1);
    expect(screen.getByRole("heading", { level: 3, name: "Coupe" })).toBeTruthy();
    expect(screen.getByText("Car · 3 versions · 2 h ago")).toBeTruthy();
    const link = screen.getByRole("link", { name: "Open Coupe" });
    expect(link.getAttribute("href")).toBe("/projects/p1");
  });

  it("deletes a project only after confirmation", async () => {
    seed([project("p1", "Coupe")]);
    const remove = useProjectsStore.getState().remove;
    render(<Dashboard />);

    fireEvent.click(screen.getByRole("button", { name: "More options for Coupe" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));
    expect(screen.getByRole("heading", { name: "Delete project and its model?" })).toBeTruthy();
    expect(remove).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith("p1"));
  });

  it("renames inline from the overflow menu", async () => {
    seed([project("p1", "Coupe")]);
    const rename = useProjectsStore.getState().rename;
    render(<Dashboard />);

    fireEvent.click(screen.getByRole("button", { name: "More options for Coupe" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    const input = screen.getByLabelText("Rename") as HTMLInputElement;
    expect(input.value).toBe("Coupe");
    fireEvent.change(input, { target: { value: "Roadster" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(rename).toHaveBeenCalledWith("p1", "Roadster"));
  });

  it("toasts on ?notice=not_found and strips the param", () => {
    seed([]);
    search = "notice=not_found";
    render(<Dashboard />);
    expect(useToastStore.getState().toasts.map((t) => t.message)).toEqual(["That project no longer exists."]);
    expect(replace).toHaveBeenCalledWith("/projects");
  });

  it("opens the new-project dialog on ?new=1 with the default name and a Create button", () => {
    seed([]);
    search = "new=1";
    render(<Dashboard />);
    expect(screen.getByRole("heading", { name: "New project" })).toBeTruthy();
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Untitled project");
    expect(screen.getByRole("button", { name: "Create" })).toBeTruthy();
    // The param is stripped once the dialog is dismissed.
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(replace).toHaveBeenCalledWith("/projects");
  });
});
