import { deriveProjectState, type Project } from "@/lib/schema";

export function relativeTime(at: number, now: number): string {
  const s = Math.max(0, Math.round((now - at) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d} d ago`;
  return new Date(at).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const CATEGORY_LABEL: Record<string, string> = { car: "Car", product: "Product" };

/** The card's single muted line: "Car · 3 versions · 2 h ago". */
export function projectMeta(project: Project, versionCount: number, now: number): string {
  const parts: string[] = [];
  const category = project.analysis?.category;
  if (category) parts.push(CATEGORY_LABEL[category] ?? category);
  if (versionCount > 0) parts.push(`${versionCount} ${versionCount === 1 ? "version" : "versions"}`);
  else parts.push(deriveProjectState({ assetId: project.assetId, versionCount }));
  parts.push(relativeTime(project.updatedAt, now));
  return parts.join(" · ");
}
