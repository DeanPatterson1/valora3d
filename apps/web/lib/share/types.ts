/** An owner's view of a render's live share link (GET/POST /api/renders/:id/share). */
export type RenderShare = {
  slug: string;
  /** Site-relative path of the public page, e.g. `/r/<slug>`. */
  path: string;
  showPrompt: boolean;
  createdAt: number;
  viewCount: number;
};

/** What the public page may show, only for a live share. */
export type PublicShare = {
  slug: string;
  kind: "preview" | "final";
  /** Null unless the owner ticked "show prompt". */
  prompt: string | null;
  width: number;
  height: number;
};

export type GoneReason = "revoked" | "expired";

export type PublicShareLookup =
  | { state: "live"; share: PublicShare; jobId: string; userId: string }
  | { state: "gone"; reason: GoneReason }
  | { state: "missing" };

export const sharePath = (slug: string) => `/r/${slug}`;
export const shareMediaPath = (slug: string, file: "video" | "poster") => `/r/${slug}/${file}`;
