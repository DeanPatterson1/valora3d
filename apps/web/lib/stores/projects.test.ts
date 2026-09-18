import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { clear } from "idb-keyval";
import { useProjectsStore } from "./projects";
import { services } from "@/lib/services";

describe("useProjectsStore", () => {
  beforeEach(async () => {
    localStorage.clear();
    await clear();
    useProjectsStore.setState({ projects: [], versionCounts: {}, loaded: false, error: null });
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it("creates, renames and removes projects", async () => {
    const p = await useProjectsStore.getState().create("A");
    expect(p?.name).toBe("A");
    await useProjectsStore.getState().rename(p!.id, "B");
    expect(useProjectsStore.getState().projects[0].name).toBe("B");
    await useProjectsStore.getState().remove(p!.id);
    expect(useProjectsStore.getState().projects.length).toBe(0);
    expect(useProjectsStore.getState().error).toBeNull();
  });

  it("rename sets error and does not refresh when updateProject fails", async () => {
    const p = await useProjectsStore.getState().create("A");
    const list = vi.spyOn(services.projects, "listProjects");
    vi.spyOn(services.projects, "updateProject").mockResolvedValueOnce({ ok: false, error: { code: "quota_exceeded", message: "full" } });
    await useProjectsStore.getState().rename(p!.id, "B");
    expect(useProjectsStore.getState().error?.code).toBe("quota_exceeded");
    expect(list).not.toHaveBeenCalled();
    expect(useProjectsStore.getState().projects[0].name).toBe("A");
  });

  it("remove sets error and does not refresh when deleteProject fails", async () => {
    const p = await useProjectsStore.getState().create("A");
    const list = vi.spyOn(services.projects, "listProjects");
    vi.spyOn(services.projects, "deleteProject").mockResolvedValueOnce({ ok: false, error: { code: "storage_unavailable", message: "nope" } });
    await useProjectsStore.getState().remove(p!.id);
    expect(useProjectsStore.getState().error?.code).toBe("storage_unavailable");
    expect(list).not.toHaveBeenCalled();
    expect(useProjectsStore.getState().projects.length).toBe(1);
  });
});
