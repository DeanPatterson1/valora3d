import { describe, it, expect, beforeEach } from "vitest";
import { clear } from "idb-keyval";
import { LocalProjectRepository } from "./projectRepository";
import { defaultPlan } from "@/lib/scene/defaultPlan";

const repo = () => new LocalProjectRepository();

describe("LocalProjectRepository", () => {
  beforeEach(async () => {
    localStorage.clear();
    await clear();
  });

  it("creates, lists, renames, deletes", async () => {
    const r = repo();
    const p = await r.createProject("Car");
    expect(p.ok && p.value.name).toBe("Car");
    if (!p.ok) return;
    expect((await r.listProjects()).ok).toBe(true);
    const u = await r.updateProject(p.value.id, { name: "Car 2" });
    expect(u.ok && u.value.name).toBe("Car 2");
    await r.deleteProject(p.value.id);
    const g = await r.getProject(p.value.id);
    expect(!g.ok && g.error.code).toBe("not_found");
  });

  it("appends versions with incrementing index", async () => {
    const r = repo();
    const p = await r.createProject("X");
    if (!p.ok) return;
    const a = await r.appendVersion({ projectId: p.value.id, prompt: "night", parentId: null, plan: defaultPlan("car") });
    const b = await r.appendVersion({
      projectId: p.value.id,
      prompt: "rain",
      parentId: a.ok ? a.value.id : null,
      plan: defaultPlan("car"),
    });
    expect(a.ok && a.value.index).toBe(0);
    expect(b.ok && b.value.index).toBe(1);
    const list = await r.listVersions(p.value.id);
    expect(list.ok && list.value.length).toBe(2);
  });

  it("stores upload blobs and returns null for missing blobs", async () => {
    const r = repo();
    const p = await r.createProject("X");
    if (!p.ok) return;
    const a = await r.saveAsset(
      { projectId: p.value.id, fileName: "m.glb", format: "glb", sizeBytes: 3, source: "upload", blobKey: null, sampleUrl: null, thumbnailKey: null },
      new Blob(["abc"]),
    );
    expect(a.ok && a.value.blobKey).toBeTruthy();
    if (!a.ok) return;
    const b = await r.getAssetBlob(a.value);
    expect(b.ok && b.value && (await b.value.text())).toBe("abc");
    await clear();
    const missing = await r.getAssetBlob(a.value);
    expect(missing.ok && missing.value).toBeNull();
  });

  it("deleting a project removes versions, asset and blob", async () => {
    const r = repo();
    const p = await r.createProject("X");
    if (!p.ok) return;
    const a = await r.saveAsset(
      { projectId: p.value.id, fileName: "m.glb", format: "glb", sizeBytes: 3, source: "upload", blobKey: null, sampleUrl: null, thumbnailKey: null },
      new Blob(["abc"]),
    );
    await r.appendVersion({ projectId: p.value.id, prompt: "x", parentId: null, plan: defaultPlan("car") });
    await r.deleteProject(p.value.id);
    const versions = await r.listVersions(p.value.id);
    expect(versions.ok && versions.value).toEqual([]);
    if (a.ok) expect(!(await r.getAsset(a.value.id)).ok).toBe(true);
  });
});
