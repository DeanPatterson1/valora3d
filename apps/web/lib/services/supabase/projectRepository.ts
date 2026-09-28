import type { SupabaseClient } from "@supabase/supabase-js";
import { del, get, set } from "idb-keyval";
import type { Asset, Project, SceneVersion } from "@/lib/schema";
import { apiFetch, supabaseErrorToResult } from "../http";
import { fail, ok, type Result } from "../result";
import type { ProjectRepository } from "../types";
import {
  projectPatchToRow,
  rowToProject,
  rowToVersion,
  uploadToAsset,
  type ProjectRow,
  type UploadRow,
  type VersionRow,
} from "./rows";

/** idb-keyval keys for this browser's caches (model bytes, thumbnails). */
const blobCacheKey = (assetId: string) => `blob:${assetId}`;
const thumbKey = (assetId: string) => `thumb:${assetId}`;

/**
 * Projects, versions and assets in Postgres (RLS scopes every query to the signed-in user).
 * Model files go to R2 through /api/uploads (presigned PUT, then server-side verification);
 * thumbnails and downloaded model bytes are cached in this browser only.
 */
export class SupabaseProjectRepository implements ProjectRepository {
  private corrupt = false;

  constructor(
    private readonly db: () => SupabaseClient,
    private readonly fetchImpl: typeof fetch = (...a) => fetch(...a),
  ) {}

  corruptDetected() {
    return this.corrupt;
  }

  private toProject(row: ProjectRow): Project {
    const { project, corrupt } = rowToProject(row);
    if (corrupt) this.corrupt = true;
    return project;
  }

  async listProjects(): Promise<Result<Project[]>> {
    const { data, error } = await this.db().from("projects").select("*").order("updated_at", { ascending: false });
    if (error) return supabaseErrorToResult(error);
    return ok((data as ProjectRow[]).map((r) => this.toProject(r)));
  }

  async getProject(id: string): Promise<Result<Project>> {
    const { data, error } = await this.db().from("projects").select("*").eq("id", id).maybeSingle<ProjectRow>();
    if (error) return isBadUuid(error) ? fail("not_found", "Project not found.") : supabaseErrorToResult(error);
    return data ? ok(this.toProject(data)) : fail("not_found", "Project not found.");
  }

  async createProject(name: string): Promise<Result<Project>> {
    const { data, error } = await this.db().from("projects").insert({ name }).select().single<ProjectRow>();
    if (error) return supabaseErrorToResult(error);
    return ok(this.toProject(data));
  }

  async updateProject(id: string, patch: Partial<Omit<Project, "id" | "createdAt">>): Promise<Result<Project>> {
    const { data, error } = await this.db()
      .from("projects")
      .update(projectPatchToRow(patch))
      .eq("id", id)
      .select()
      .maybeSingle<ProjectRow>();
    if (error) return supabaseErrorToResult(error);
    return data ? ok(this.toProject(data)) : fail("not_found", "Project not found.");
  }

  async deleteProject(id: string): Promise<Result<void>> {
    const assets = await this.db().from("uploads").select("id").eq("project_id", id);
    const r = await apiFetch<void>(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" }, this.fetchImpl);
    if (!r.ok && r.error.code !== "not_found") return r;
    for (const a of (assets.data ?? []) as { id: string }[]) {
      await del(blobCacheKey(a.id)).catch(() => {});
      await del(thumbKey(a.id)).catch(() => {});
    }
    return ok(undefined);
  }

  async getAsset(id: string): Promise<Result<Asset>> {
    const { data, error } = await this.db().from("uploads").select("*").eq("id", id).maybeSingle<UploadRow>();
    if (error) return isBadUuid(error) ? fail("not_found", "Asset not found.") : supabaseErrorToResult(error);
    if (!data || data.status !== "ready") return fail("not_found", "Asset not found.");
    return ok(uploadToAsset(data));
  }

  async saveAsset(asset: Omit<Asset, "id">, blob: Blob | null): Promise<Result<Asset>> {
    if (asset.source === "sample") {
      const r = await apiFetch<{ upload: UploadRow }>(
        "/api/uploads",
        {
          method: "POST",
          body: JSON.stringify({
            kind: "sample",
            projectId: asset.projectId,
            fileName: asset.fileName,
            sizeBytes: asset.sizeBytes,
            sampleUrl: asset.sampleUrl ?? "",
          }),
        },
        this.fetchImpl,
      );
      return r.ok ? ok(uploadToAsset(r.value.upload)) : r;
    }
    if (!blob) return fail("invalid_request", "No file to upload.");

    const start = await apiFetch<{ upload: UploadRow; putUrl: string; putHeaders: Record<string, string> }>(
      "/api/uploads",
      {
        method: "POST",
        body: JSON.stringify({ kind: "upload", projectId: asset.projectId, fileName: asset.fileName, sizeBytes: blob.size }),
      },
      this.fetchImpl,
    );
    if (!start.ok) return start;

    try {
      const put = await this.fetchImpl(start.value.putUrl, { method: "PUT", body: blob, headers: start.value.putHeaders });
      if (!put.ok) return fail("upload_failed", "The upload did not finish. Try again.");
    } catch {
      return fail("offline", "The upload was interrupted. Check your connection and try again.");
    }

    const done = await apiFetch<{ upload: UploadRow }>(
      `/api/uploads/${encodeURIComponent(start.value.upload.id)}/complete`,
      { method: "POST", body: "{}" },
      this.fetchImpl,
    );
    if (!done.ok) return done;
    const saved = uploadToAsset(done.value.upload);
    await set(blobCacheKey(saved.id), blob).catch(() => {});
    return ok(saved);
  }

  async getAssetBlob(asset: Asset): Promise<Result<Blob | null>> {
    if (asset.source !== "upload" || !asset.blobKey) return ok(null);
    const cached = await get<Blob>(blobCacheKey(asset.id)).catch(() => undefined);
    if (cached) return ok(cached);
    const link = await apiFetch<{ url: string }>(`/api/uploads/${encodeURIComponent(asset.id)}/download`, {}, this.fetchImpl);
    if (!link.ok) return link.error.code === "not_found" ? ok(null) : link;
    try {
      const res = await this.fetchImpl(link.value.url);
      if (!res.ok) return fail("server", "Could not download the model.");
      const blob = await res.blob();
      await set(blobCacheKey(asset.id), blob).catch(() => {});
      return ok(blob);
    } catch {
      return fail("offline", "Could not download the model. Check your connection.");
    }
  }

  async saveThumbnail(assetId: string, blob: Blob): Promise<Result<void>> {
    await set(thumbKey(assetId), blob).catch(() => {}); // best-effort, this browser only
    return ok(undefined);
  }

  async getThumbnail(assetId: string): Promise<Result<Blob | null>> {
    try {
      return ok((await get<Blob>(thumbKey(assetId))) ?? null);
    } catch {
      return ok(null);
    }
  }

  async listVersions(projectId: string): Promise<Result<SceneVersion[]>> {
    const { data, error } = await this.db()
      .from("scene_versions")
      .select("*")
      .eq("project_id", projectId)
      .order("index", { ascending: true });
    if (error) return isBadUuid(error) ? ok([]) : supabaseErrorToResult(error);
    const versions: SceneVersion[] = [];
    for (const row of data as VersionRow[]) {
      const v = rowToVersion(row);
      if (v) versions.push(v);
      else this.corrupt = true;
    }
    return ok(versions);
  }

  async appendVersion(v: Omit<SceneVersion, "id" | "index" | "createdAt">): Promise<Result<SceneVersion>> {
    // index = count so far; the unique (project_id, index) constraint turns a race into one retry.
    for (let attempt = 0; attempt < 2; attempt++) {
      const { count, error: countError } = await this.db()
        .from("scene_versions")
        .select("id", { count: "exact", head: true })
        .eq("project_id", v.projectId);
      if (countError) return supabaseErrorToResult(countError);
      const { data, error } = await this.db()
        .from("scene_versions")
        .insert({ project_id: v.projectId, index: count ?? 0, prompt: v.prompt, parent_id: v.parentId, plan: v.plan })
        .select()
        .single<VersionRow>();
      if (!error) {
        const saved = rowToVersion(data);
        return saved ? ok(saved) : fail("server", "The saved scene could not be read back.");
      }
      if (error.code !== "23505") return supabaseErrorToResult(error);
    }
    return fail("conflict", "Another tab saved a scene at the same time. Try again.");
  }
}

/** PostgREST answers a malformed uuid with 22P02; for a lookup that simply means "not found". */
function isBadUuid(error: { code?: string }): boolean {
  return error.code === "22P02";
}
