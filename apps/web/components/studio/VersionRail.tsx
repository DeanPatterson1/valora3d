"use client";

import type { SceneVersion } from "@/lib/schema";
import { Placeholder } from "./Placeholder";

export function VersionRail({ versions }: { versions: SceneVersion[] }) {
  return <Placeholder label="Versions" hint={versions.length === 0 ? "No scenes yet" : `${versions.length} saved`} />;
}
