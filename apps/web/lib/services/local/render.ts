import type { RenderJob, ScenePlan } from "@/lib/schema";
import { buildRenderJob, frameCount, presetFor, MAX_FRAMES } from "@/lib/render/job";
import { RenderServerError, STATUS_MAP, fileUrl, getJob, submit, subscribe } from "@/lib/render/provider";
import { SnapshotError, exportSnapshot } from "@/lib/render/snapshot";
import { currentScene } from "@/lib/render/sceneSource";
import { fail, ok, type Result } from "../result";
import type { RenderService } from "../types";
import { LocalProjectRepository } from "./projectRepository";

/**
 * Renders on this machine, through the local Blender + ffmpeg pipeline in
 * `tools/render-studio/`. The scene the user directed travels two ways: the geometry
 * as a GLB snapshot, and the `ScenePlan` itself, which the pipeline reads to trace the
 * same camera path the viewer drew.
 *
 * Cloud rendering is a different target and is still not connected.
 */
export class LocalRenderService implements RenderService {
  private readonly projects = new LocalProjectRepository();
  /** Job id to the plan it was submitted with, so a finished job can name its file. */
  private readonly jobs = new Map<string, { projectId: string; versionId: string; kind: "preview" | "final" }>();

  async requestPreview(projectId: string, versionId: string): Promise<Result<RenderJob>> {
    return this.start(projectId, versionId, "preview", "local");
  }

  async requestFinal(projectId: string, versionId: string, target: "local" | "cloud"): Promise<Result<RenderJob>> {
    if (target === "cloud") {
      return fail("not_connected", "Cloud rendering is not connected yet. Render on this machine instead.");
    }
    return this.start(projectId, versionId, "final", target);
  }

  private async start(
    projectId: string,
    versionId: string,
    kind: "preview" | "final",
    target: "local" | "cloud",
  ): Promise<Result<RenderJob>> {
    const project = await this.projects.getProject(projectId);
    if (!project.ok) return project;
    if (!project.value.assetId) return fail("no_model", "Load a model before rendering.");

    const versions = await this.projects.listVersions(projectId);
    if (!versions.ok) return versions;
    const version = versions.value.find((v) => v.id === versionId);
    if (!version) return fail("no_version", "That scene version no longer exists.");
    const plan: ScenePlan = version.plan;

    const preset = presetFor(plan, kind);
    const frames = frameCount(plan);
    if (frames > MAX_FRAMES[preset]) {
      return fail(
        "too_many_frames",
        `${frames} frames is past this quality's limit of ${MAX_FRAMES[preset]}. Shorten the shot or lower the frame rate.`,
      );
    }

    const scene = currentScene();
    if (!scene) return fail("no_scene", "The viewer is still loading this model.");

    let snapshot: string;
    try {
      snapshot = (await exportSnapshot(scene.root, scene.scaleFactor, scene.selection)).data;
    } catch (error) {
      if (error instanceof SnapshotError) return fail(error.code, error.message);
      throw error;
    }

    try {
      const queued = await submit(buildRenderJob(project.value.assetId, plan, kind), snapshot);
      this.jobs.set(queued.jobId, { projectId, versionId, kind });
      return ok(toRenderJob(queued, projectId, versionId, kind, target));
    } catch (error) {
      if (error instanceof RenderServerError) return fail(error.code, error.message);
      throw error;
    }
  }

  subscribe(jobId: string, onUpdate: (job: RenderJob) => void): () => void {
    const known = this.jobs.get(jobId);
    return subscribe(jobId, (job) => {
      onUpdate(toRenderJob(job, known?.projectId ?? "", known?.versionId ?? "", known?.kind ?? "final", "local"));
    });
  }

  /** One-shot read, for a job the UI picked up after a reload. */
  async refresh(jobId: string): Promise<Result<RenderJob>> {
    try {
      const job = await getJob(jobId);
      const known = this.jobs.get(jobId);
      return ok(toRenderJob(job, known?.projectId ?? "", known?.versionId ?? "", known?.kind ?? "final", "local"));
    } catch (error) {
      if (error instanceof RenderServerError) return fail(error.code, error.message);
      throw error;
    }
  }
}

function toRenderJob(
  job: { jobId: string; status: keyof typeof STATUS_MAP; frame: number; totalFrames: number; error?: string },
  projectId: string,
  versionId: string,
  kind: "preview" | "final",
  target: "local" | "cloud",
): RenderJob {
  const status = STATUS_MAP[job.status];
  return {
    id: job.jobId,
    projectId,
    versionId,
    kind,
    target,
    status,
    frame: job.frame ?? 0,
    // The schema wants a positive count even before the pipeline reports one.
    totalFrames: job.totalFrames > 0 ? job.totalFrames : 1,
    error: job.error ?? (job.status === "cancelled" ? "The render was cancelled." : null),
    resultUrl: status === "COMPLETE" ? fileUrl(job.jobId, "video.mp4") : null,
  };
}
