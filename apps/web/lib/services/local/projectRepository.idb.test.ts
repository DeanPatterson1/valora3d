import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { clear, get, set } from "idb-keyval";
import type { Asset } from "@/lib/schema";
import { LocalProjectRepository } from "./projectRepository";

// idb-keyval's `set` is wrapped so individual tests can make the IndexedDB write reject.
vi.mock("idb-keyval", async (orig) => {
  const actual = await orig<typeof import("idb-keyval")>();
  return { ...actual, set: vi.fn(actual.set) };
});

const upload = (projectId: string): Omit<Asset, "id"> => ({
  projectId,
  fileName: "m.glb",
  format: "glb",
  sizeBytes: 3,
  source: "upload",
  blobKey: null,
  sampleUrl: null,
  thumbnailKey: null,
});

describe("LocalProjectRepository with IndexedDB failures", () => {
  beforeEach(async () => {
    localStorage.clear();
    await clear();
  });
  afterEach(() => {
    vi.mocked(set).mockReset(); // vitest >= 3: restores the original implementation passed to vi.fn
    vi.restoreAllMocks();
  });

  it("saveAsset reports quota_exceeded when the blob write hits quota", async () => {
    const r = new LocalProjectRepository();
    const p = await r.createProject("X");
    if (!p.ok) throw new Error(p.error.message);
    vi.mocked(set).mockRejectedValueOnce(new DOMException("", "QuotaExceededError"));
    const a = await r.saveAsset(upload(p.value.id), new Blob(["abc"]));
    expect(!a.ok && a.error.code).toBe("quota_exceeded");
    expect(!a.ok && a.error.message).toBe("Storage is full. Delete an old project to free space.");
  });

  it("saveAsset reports storage_unavailable when the blob write fails for another reason", async () => {
    const r = new LocalProjectRepository();
    const p = await r.createProject("X");
    if (!p.ok) throw new Error(p.error.message);
    vi.mocked(set).mockRejectedValueOnce(new DOMException("", "SecurityError"));
    const a = await r.saveAsset(upload(p.value.id), new Blob(["abc"]));
    expect(!a.ok && a.error.code).toBe("storage_unavailable");
  });

  it("saveAsset writes no metadata when the blob write fails", async () => {
    const r = new LocalProjectRepository();
    const p = await r.createProject("X");
    if (!p.ok) throw new Error(p.error.message);
    vi.mocked(set).mockRejectedValueOnce(new DOMException("", "QuotaExceededError"));
    const a = await r.saveAsset(upload(p.value.id), new Blob(["abc"]));
    expect(a.ok).toBe(false);
    expect(localStorage.getItem("rs.assets")).toBeNull();
  });

  it("saveAsset deletes the blob when the metadata write fails after the blob succeeded", async () => {
    const r = new LocalProjectRepository();
    const p = await r.createProject("X");
    if (!p.ok) throw new Error(p.error.message);
    const realSet = Storage.prototype.setItem;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, key, value) {
      if (key === "rs.assets") throw new DOMException("", "QuotaExceededError");
      realSet.call(this, key, value);
    });
    const a = await r.saveAsset(upload(p.value.id), new Blob(["abc"]));
    expect(!a.ok && a.error.code).toBe("quota_exceeded");
    expect(vi.mocked(set)).toHaveBeenCalledTimes(1);
    const blobKey = vi.mocked(set).mock.calls[0][0];
    expect(String(blobKey)).toMatch(/^blob:/);
    expect(await get(blobKey)).toBeUndefined();
  });
});
