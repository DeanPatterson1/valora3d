import { z } from "zod";
import { get, set, del } from "idb-keyval";
import { AssetSchema, ProjectSchema, SceneVersionSchema, type Asset, type Project, type SceneVersion } from "@/lib/schema";
import { fail, failFrom, ok, type Result } from "../result";
import type { ProjectRepository } from "../types";
import { KEYS, newId, readJson, storageFailure, writeJson } from "./storage";

const ProjectsFile = z.array(ProjectSchema);
const AssetsFile = z.array(AssetSchema);
const VersionsFile = z.array(SceneVersionSchema);

export class LocalProjectRepository implements ProjectRepository {
  private corrupt = false;
  corruptDetected() {
    return this.corrupt;
  }

  private read<T>(key: string, schema: z.ZodType<T[]>): T[] {
    const r = readJson(key, schema, [] as T[]);
    if (r.corrupt) this.corrupt = true;
    return r.value;
  }
  private projects() {
    return this.read(KEYS.projects, ProjectsFile);
  }
  private assets() {
    return this.read(KEYS.assets, AssetsFile);
  }
  private versions() {
    return this.read(KEYS.versions, VersionsFile);
  }

  async listProjects() {
    return ok(this.projects().sort((a, b) => b.updatedAt - a.updatedAt));
  }

  async getProject(id: string) {
    const p = this.projects().find((x) => x.id === id);
    return p ? ok(p) : fail<Project>("not_found", "Project not found.");
  }

  async createProject(name: string) {
    const now = Date.now();
    const p: Project = { id: newId(), name, createdAt: now, updatedAt: now, assetId: null, analysis: null, selectedVersionId: null };
    const w = writeJson(KEYS.projects, [...this.projects(), p]);
    return w.ok ? ok(p) : failFrom<Project>(w.error);
  }

  async updateProject(id: string, patch: Partial<Omit<Project, "id" | "createdAt">>) {
    const all = this.projects();
    const i = all.findIndex((x) => x.id === id);
    if (i === -1) return fail<Project>("not_found", "Project not found.");
    all[i] = { ...all[i], ...patch, updatedAt: Date.now() };
    const w = writeJson(KEYS.projects, all);
    return w.ok ? ok(all[i]) : failFrom<Project>(w.error);
  }

  async deleteProject(id: string): Promise<Result<void>> {
    // Write failures here are ignored on purpose: removing data cannot exceed quota,
    // and a partial delete is preferable to a stuck project.
    for (const a of this.assets().filter((x) => x.projectId === id)) {
      if (a.blobKey) await del(a.blobKey).catch(() => {});
      if (a.thumbnailKey) await del(a.thumbnailKey).catch(() => {});
    }
    writeJson(KEYS.assets, this.assets().filter((x) => x.projectId !== id));
    writeJson(KEYS.versions, this.versions().filter((x) => x.projectId !== id));
    writeJson(KEYS.projects, this.projects().filter((x) => x.id !== id));
    return ok(undefined);
  }

  async getAsset(id: string) {
    const a = this.assets().find((x) => x.id === id);
    return a ? ok(a) : fail<Asset>("not_found", "Asset not found.");
  }

  async saveAsset(asset: Omit<Asset, "id">, blob: Blob | null) {
    const id = newId();
    let blobKey: string | null = null;
    if (blob && asset.source === "upload") {
      blobKey = `blob:${id}`;
      try {
        await set(blobKey, blob);
      } catch (e) {
        return storageFailure<Asset>(e);
      }
    }
    const full: Asset = { ...asset, id, blobKey };
    const w = writeJson(KEYS.assets, [...this.assets(), full]);
    if (!w.ok) {
      if (blobKey) await del(blobKey).catch(() => {});
      return failFrom<Asset>(w.error);
    }
    return ok(full);
  }

  async getAssetBlob(asset: Asset): Promise<Result<Blob | null>> {
    if (!asset.blobKey) return ok(null);
    try {
      return ok((await get<Blob>(asset.blobKey)) ?? null);
    } catch {
      return fail("storage_unavailable", "Browser storage is unavailable.");
    }
  }

  async saveThumbnail(assetId: string, blob: Blob): Promise<Result<void>> {
    const key = `thumb:${assetId}`;
    try {
      await set(key, blob);
    } catch {
      return ok(undefined); // thumbnails are best-effort
    }
    const all = this.assets();
    const i = all.findIndex((x) => x.id === assetId);
    if (i !== -1) {
      all[i] = { ...all[i], thumbnailKey: key };
      writeJson(KEYS.assets, all);
    }
    return ok(undefined);
  }

  async getThumbnail(assetId: string): Promise<Result<Blob | null>> {
    try {
      return ok((await get<Blob>(`thumb:${assetId}`)) ?? null);
    } catch {
      return ok(null);
    }
  }

  async listVersions(projectId: string) {
    return ok(this.versions().filter((v) => v.projectId === projectId).sort((a, b) => a.index - b.index));
  }

  async appendVersion(v: Omit<SceneVersion, "id" | "index" | "createdAt">) {
    const all = this.versions();
    const index = all.filter((x) => x.projectId === v.projectId).length;
    const full: SceneVersion = { ...v, id: newId(), index, createdAt: Date.now() };
    const w = writeJson(KEYS.versions, [...all, full]);
    return w.ok ? ok(full) : failFrom<SceneVersion>(w.error);
  }
}
