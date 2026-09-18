import type { Category } from "@/lib/schema";

export function capabilitiesFor(category: Category, wheelCount: number, rigged: boolean): string[] {
  const base =
    category === "car"
      ? wheelCount >= 4
        ? ["drive", "brake", "steer", "wheel_rotation"]
        : ["static", "rotate"]
      : ["rotate", "pedestal"];
  return rigged ? [...base, "rigged_motion"] : base;
}
