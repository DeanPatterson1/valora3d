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
  User,
  UserPrefs,
} from "@/lib/schema";
import type { RenderParamsInput } from "@/lib/render/params";
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

/** One render request, shaped by the worker contract (lib/render/params.ts). */
export type RenderRequest = {
  projectId: string;
  /** The project's model (uploads.id; the studio's asset id). */
  uploadId: string;
  versionId: string | null;
  params: RenderParamsInput;
  /** Same key => same job, charged once (a retried click). */
  idempotencyKey: string;
};

export type RenderRequestInput = Omit<RenderRequest, "idempotencyKey">;

export interface RenderService {
  /** Fails with "not_connected" when no renderer is wired (Local mode, or RunPod env absent on the server). */
  request(input: RenderRequest): Promise<Result<RenderJob>>;
  get(jobId: string): Promise<Result<RenderJob>>;
  /** The project's recent jobs, newest first. */
  list(projectId: string): Promise<Result<RenderJob[]>>;
  cancel(jobId: string): Promise<Result<RenderJob>>;
  /** A short-lived download link for a finished job's file. */
  downloadUrl(jobId: string, file: "video" | "poster"): Promise<Result<string>>;
  /** Follows a job until it is terminal; returns the unsubscribe. */
  subscribe(jobId: string, onUpdate: (job: RenderJob) => void): () => void;
}

export type AuthProvider = "google" | "apple";

export type ProfilePatch = Partial<Pick<User, "name">> & { prefs?: Partial<UserPrefs> };

/** What an auth implementation offers, so screens show only what works. */
export type AuthFeatures = {
  /** "Continue as guest" (local prototype only; never offered by the real backend). */
  guest: boolean;
  providers: AuthProvider[];
  /** Forgot-password email + set-new-password page. */
  passwordReset: boolean;
  /** Accounts live on a server: deletion removes the account, not just this browser's data. */
  serverAccount: boolean;
};

export interface AuthService {
  readonly features: AuthFeatures;
  /** The signed-in user, or null when signed out. */
  current(): Promise<Result<User | null>>;
  /** Fails with "not_found" for an unknown email, "invalid_password" for a short one. */
  signIn(email: string, password: string, captchaToken?: string): Promise<Result<User>>;
  /**
   * Fails with "exists" when the email already has an account, and with "verification_sent" when
   * the account was created but must be confirmed from the emailed link before signing in.
   */
  signUp(email: string, password: string, name: string, captchaToken?: string): Promise<Result<User>>;
  /** With a real provider this navigates away (the promise stays pending until the page unloads). */
  signInWith(provider: AuthProvider): Promise<Result<User>>;
  /** Sends a reset link. Resolves ok whether or not the email has an account (no enumeration). */
  requestPasswordReset(email: string, captchaToken?: string): Promise<Result<void>>;
  /** Sets a new password for the signed-in (or reset-link) session. */
  updatePassword(password: string): Promise<Result<void>>;
  continueAsGuest(): Promise<Result<User>>;
  signOut(): Promise<Result<void>>;
  updateProfile(patch: ProfilePatch): Promise<Result<User>>;
  /**
   * Local: clears everything the prototype stores in this browser. Server: deletes the account
   * and all its data server-side, then clears this browser's caches.
   */
  deleteAllData(): Promise<Result<void>>;
}

export interface Services {
  /** Which implementation is live: the in-browser fakes or Supabase + R2. */
  backend: "local" | "supabase";
  auth: AuthService;
  projects: ProjectRepository;
  analysis: AnalysisService;
  director: DirectorService;
  credits: CreditService;
  render: RenderService;
}
