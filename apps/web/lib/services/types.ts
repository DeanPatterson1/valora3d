import type {
  Asset,
  CreditTransaction,
  ModelAnalysis,
  Project,
  RenderJob,
  ScenePatch,
  ScenePlan,
  SceneStats,
  SceneVersion,
} from "@/lib/schema";
import type { Result } from "./result";

export interface ProjectRepository {
  /** True if any stored data was unreadable and treated as empty (spec section 11). */
  corruptDetected(): boolean;
  listProjects(): Promise<Result<Project[]>>;
  getProject(id: string): Promise<Result<Project>>;
  createProject(name: string): Promise<Result<Project>>;
  updateProject(id: string, patch: Partial<Omit<Project, "id" | "createdAt">>): Promise<Result<Project>>;
  deleteProject(id: string): Promise<Result<void>>;

  getAsset(id: string): Promise<Result<Asset>>;
  /** Stores metadata and (for uploads) the blob. Fails with "quota_exceeded" if storage is full. */
  saveAsset(asset: Omit<Asset, "id">, blob: Blob | null): Promise<Result<Asset>>;
  /** Returns null blob for samples (use sampleUrl) and for missing blobs. */
  getAssetBlob(asset: Asset): Promise<Result<Blob | null>>;
  saveThumbnail(assetId: string, blob: Blob): Promise<Result<void>>;
  getThumbnail(assetId: string): Promise<Result<Blob | null>>;

  listVersions(projectId: string): Promise<Result<SceneVersion[]>>;
  appendVersion(v: Omit<SceneVersion, "id" | "index" | "createdAt">): Promise<Result<SceneVersion>>;
}

export interface AnalysisService {
  analyze(stats: SceneStats): Promise<Result<ModelAnalysis>>;
}

export interface DirectorService {
  plan(prompt: string, analysis: ModelAnalysis): Promise<Result<ScenePlan>>;
  edit(prompt: string, plan: ScenePlan): Promise<Result<ScenePatch[]>>;
}

export interface CreditService {
  balance(): Promise<Result<number>>;
  ledger(): Promise<Result<CreditTransaction[]>>;
  /** amount negative to spend; fails with "insufficient_credits" */
  post(tx: Omit<CreditTransaction, "id" | "createdAt">): Promise<Result<CreditTransaction>>;
}

export interface RenderService {
  requestPreview(projectId: string, versionId: string): Promise<Result<RenderJob>>;
  requestFinal(projectId: string, versionId: string, target: "local" | "cloud"): Promise<Result<RenderJob>>;
  subscribe(jobId: string, onUpdate: (job: RenderJob) => void): () => void;
}

export interface Services {
  projects: ProjectRepository;
  analysis: AnalysisService;
  director: DirectorService;
  credits: CreditService;
  render: RenderService;
}
