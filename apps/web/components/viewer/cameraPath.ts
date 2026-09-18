import type { ScenePlan, Shot } from "@/lib/schema";

/** Subject extents in scene metres after normalisation: `radius` on the ground plane, `height` above it. */
export type Bounds = { radius: number; height: number };

export type Vec3 = { x: number; y: number; z: number };

/** The camera always looks at the middle of the subject. */
export function subjectCentre(b: Bounds): Vec3 {
  return { x: 0, y: b.height / 2, z: 0 };
}

/**
 * Camera position for `t` in [0, 1] within a shot.
 * Base distance grows with subject size, the shot's distance multiplier and the lens
 * (longer lenses back off so the subject stays framed).
 */
export function shotPathPoint(plan: ScenePlan, shot: Shot, t: number, b: Bounds): Vec3 {
  const base = b.radius * 4 * shot.distanceMultiplier * (plan.camera.lensMm / 50) ** 0.5;
  const y = plan.camera.heightM;
  switch (shot.action) {
    case "slow_orbit": {
      const a = -Math.PI * 0.25 + t * Math.PI * 0.9;
      return { x: Math.sin(a) * base, y, z: Math.cos(a) * base };
    }
    case "hero_push_in": {
      const r = base * (1.6 - 0.8 * t);
      const a = -Math.PI * 0.2;
      return { x: Math.sin(a) * r, y, z: Math.cos(a) * r };
    }
    case "low_tracking": {
      return { x: -base * 0.8 + t * base * 1.6, y: Math.min(y, 0.6), z: base * 0.9 };
    }
    case "handheld_walk_toward": {
      const r = base * (1.8 - 1.0 * t);
      const a = -Math.PI * 0.3 + t * 0.2;
      return { x: Math.sin(a) * r, y, z: Math.cos(a) * r };
    }
  }
}

/** Handheld sway. `seconds` is absolute timeline time so the frequency is per second, not per shot. */
export function handheldOffset(seconds: number, strength: number): { x: number; y: number; roll: number } {
  if (strength <= 0) return { x: 0, y: 0, roll: 0 };
  return {
    x: Math.sin(seconds * 7.3) * 0.02 * strength,
    y: Math.abs(Math.sin(seconds * 5.1)) * 0.03 * strength,
    roll: Math.sin(seconds * 2.1) * 0.01 * strength,
  };
}

/** The shot active at an absolute timeline time and the local progress through it. */
export function shotAt(plan: ScenePlan, seconds: number): { shot: Shot; t: number } {
  const shot =
    plan.shots.find((s) => seconds >= s.start && seconds <= s.end) ??
    (seconds < plan.shots[0].start ? plan.shots[0] : plan.shots[plan.shots.length - 1]);
  const t = Math.min(1, Math.max(0, (seconds - shot.start) / (shot.end - shot.start)));
  return { shot, t };
}

/** Vertical field of view in degrees for a lens on a 35 mm sensor (half-height 12 mm). */
export function lensToFov(lensMm: number): number {
  return (2 * Math.atan(12 / lensMm) * 180) / Math.PI;
}

/** Human label for a shot action. */
export const SHOT_LABEL: Record<Shot["action"], string> = {
  slow_orbit: "Slow orbit",
  hero_push_in: "Hero push-in",
  low_tracking: "Low tracking",
  handheld_walk_toward: "Walk toward",
};
