import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { clear, get } from "idb-keyval";
import { LocalProjectRepository } from "./projectRepository";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { VERSION_ACTION_COST } from "@/lib/scene/versionAction";
import { LocalCreditService } from "./credits";

const repo = () => new LocalProjectRepository();

describe("LocalProjectRepository", () => {
  beforeEach(async () => {
    localStorage.clear();
    await clear();
  });
  afterEach(() => vi.restoreAllMocks());

  it("treats corrupt project data as empty and flags corruptDetected", async () => {
    localStorage.setItem("rs.projects", "junk");
    const r = repo();
    expect(r.corruptDetected()).toBe(false);
    const list = await r.listProjects();
    expect(list.ok && list.value).toEqual([]);
    expect(r.corruptDetected()).toBe(true);
  });

  it("saveThumbnail links the thumbnail to the asset", async () => {
    const r = repo();
    const p = await r.createProject("X");
    if (!p.ok) throw new Error(p.error.message);
    const a = await r.saveAsset(
      { projectId: p.value.id, fileName: "m.glb", format: "glb", sizeBytes: 3, source: "upload", blobKey: null, sampleUrl: null, thumbnailKey: null },
      new Blob(["abc"]),
    );
    if (!a.ok) throw new Error(a.error.message);
    const t = await r.saveThumbnail(a.value.id, new Blob(["png"]));
    expect(t.ok).toBe(true);
    const again = await r.getAsset(a.value.id);
    expect(again.ok && again.value.thumbnailKey).toBe(`thumb:${a.value.id}`);
    const thumb = await r.getThumbnail(a.value.id);
    expect(thumb.ok && thumb.value && (await thumb.value.text())).toBe("png");
  });

  it("saveThumbnail does not keep a blob for an unknown asset", async () => {
    const r = repo();
    const t = await r.saveThumbnail("nope", new Blob(["png"]));
    expect(t.ok).toBe(true);
    expect(await get("thumb:nope")).toBeUndefined();
  });

  it("saveThumbnail deletes the thumbnail blob when the metadata write fails", async () => {
    const r = repo();
    const p = await r.createProject("X");
    if (!p.ok) throw new Error(p.error.message);
    const a = await r.saveAsset(
      { projectId: p.value.id, fileName: "m.glb", format: "glb", sizeBytes: 3, source: "upload", blobKey: null, sampleUrl: null, thumbnailKey: null },
      new Blob(["abc"]),
    );
    if (!a.ok) throw new Error(a.error.message);
    const realSet = Storage.prototype.setItem;
    vi.spyOn(Storage.prototype, "setItem").mockImplementationOnce(function (this: Storage, key, value) {
      if (key === "rs.assets") throw new DOMException("", "QuotaExceededError");
      realSet.call(this, key, value);
    });
    const t = await r.saveThumbnail(a.value.id, new Blob(["png"]));
    expect(t.ok).toBe(true); // best-effort: the caller is not told
    expect(await get(`thumb:${a.value.id}`)).toBeUndefined();
    const again = await r.getAsset(a.value.id);
    expect(again.ok && again.value.thumbnailKey).toBeNull();
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
    const a = await r.appendVersion({ projectId: p.value.id, prompt: "night", parentId: null, plan: defaultPlan("car") }, "generate");
    const b = await r.appendVersion({
      projectId: p.value.id,
      prompt: "rain",
      parentId: a.ok ? a.value.id : null,
      plan: defaultPlan("car"),
    }, "edit");
    expect(a.ok && a.value.index).toBe(0);
    expect(b.ok && b.value.index).toBe(1);
    const list = await r.listVersions(p.value.id);
    expect(list.ok && list.value.length).toBe(2);
  });

  it("charges the action the project says it is: first version = generate, then the declared action", async () => {
    const credits = new LocalCreditService();
    const r = new LocalProjectRepository(credits);
    const p = await r.createProject("X");
    if (!p.ok) return;
    const s0 = await credits.balance();
    const start = s0.ok ? s0.value : NaN;
    const a = await r.appendVersion({ projectId: p.value.id, prompt: "night", parentId: null, plan: defaultPlan("car") }, "adjust");
    if (!a.ok) throw new Error("first version refused");
    const parent = a.value.id;
    await r.appendVersion({ projectId: p.value.id, prompt: "rain", parentId: parent, plan: defaultPlan("car") }, "edit");
    await r.appendVersion({ projectId: p.value.id, prompt: "manual: fog", parentId: parent, plan: defaultPlan("car") }, "adjust");
    const b = await credits.balance();
    expect(b.ok && start - b.value).toBe(VERSION_ACTION_COST.generate + VERSION_ACTION_COST.edit);
  });

  it("saves nothing when the balance is short or negative", async () => {
    const credits = new LocalCreditService();
    const r = new LocalProjectRepository(credits);
    const p = await r.createProject("X");
    if (!p.ok) return;
    const b = await credits.balance();
    await credits.post({ amount: -((b.ok ? b.value : 0) - 1), reason: "pack_purchase", projectId: null });
    const refused = await r.appendVersion({ projectId: p.value.id, prompt: "x", parentId: null, plan: defaultPlan("car") }, "generate");
    expect(!refused.ok && refused.error).toEqual({ code: "insufficient_credits", message: "You need 5 credits but have 1." });
    const list = await r.listVersions(p.value.id);
    expect(list.ok && list.value).toEqual([]);
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
    await r.appendVersion({ projectId: p.value.id, prompt: "x", parentId: null, plan: defaultPlan("car") }, "generate");
    await r.deleteProject(p.value.id);
    const versions = await r.listVersions(p.value.id);
    expect(versions.ok && versions.value).toEqual([]);
    if (a.ok) expect(!(await r.getAsset(a.value.id)).ok).toBe(true);
  });
});
