import type { ScenePlan } from "@/lib/schema";
import { shotPathPoint, subjectCentre, type Bounds, type Vec3 } from "./cameraPath";

/** Three-quarter hero azimuth (horizontal direction from the subject to the camera), unit length. */
const HERO_AZIMUTH = unit({ x: 0.66, y: 0, z: 0.7 });
/** Default hero elevation, and the steepest the fit will go to look down on a raised camera path. */
const HERO_ELEVATION = Math.asin(0.27 / Math.hypot(0.66, 0.27, 0.7));
const MAX_ELEVATION = (38 * Math.PI) / 180;
/** The eye sits above the path's highest point by this share of the path's horizontal reach, so a ring never turns edge-on. */
const PATH_CLEARANCE = 0.35;

/** Share of the half-frame the model may fill on its own (the classic loose hero framing). */
const MODEL_OCCUPANCY = 0.62;
/** Share of the half-frame the camera path may reach out to: nearly the edge, so the model stays as large as possible. */
const PATH_OCCUPANCY = 0.92;
/** Samples per shot when measuring the path's extent. */
const PATH_SAMPLES = 32;

export type Framing = {
  target: Vec3;
  position: Vec3;
  distance: number;
  /** Fraction of the frame height the subject's tallest projected extent takes up. */
  modelHeightFraction: number;
};

/** The default hero direction (subject to camera), unit length. */
export const HERO_DIRECTION: Vec3 = heroDirection(HERO_ELEVATION);

/**
 * Hero framing for a subject and, when a plan exists, every shot's camera route: the
 * closest distance along the hero direction at which the model sits loosely in frame and
 * the whole path is visible. The path may push the camera back (a smaller model beats a
 * cropped path) and tilt it down (so a path above the subject is seen as a ring rather
 * than a line), but never changes the aim, which stays on the subject.
 */
export function heroFraming(bounds: Bounds, plan: ScenePlan | null, fovDeg: number, aspect: number): Framing {
  const target = subjectCentre(bounds);
  const tanV = Math.tan((fovDeg * Math.PI) / 360);
  const tanH = tanV * Math.max(aspect, 0.5);

  const modelPoints: Vec3[] = [];
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) for (const y of [0, bounds.height]) modelPoints.push({ x: sx * bounds.radius, y, z: sz * bounds.radius });

  const pathPoints: Vec3[] = [];
  if (plan) for (const shot of plan.shots) for (let i = 0; i < PATH_SAMPLES; i++) pathPoints.push(shotPathPoint(plan, shot, i / (PATH_SAMPLES - 1), bounds));
  let pathTop = -Infinity;
  let pathReach = 0;
  for (const p of pathPoints) {
    pathTop = Math.max(pathTop, p.y);
    pathReach = Math.max(pathReach, Math.hypot(p.x, p.z));
  }

  let elevation = HERO_ELEVATION;
  let dir = heroDirection(elevation);
  let distance = 0;
  const fit = () => {
    distance = fitDistance(modelPoints, target, dir, tanV, tanH, MODEL_OCCUPANCY);
    if (pathPoints.length) distance = Math.max(distance, fitDistance(pathPoints, target, dir, tanV, tanH, PATH_OCCUPANCY));
  };
  fit();
  if (pathPoints.length) {
    // Elevation and distance depend on each other; two passes converge closely enough.
    for (let pass = 0; pass < 2; pass++) {
      const eyeMin = pathTop + PATH_CLEARANCE * pathReach - target.y;
      const wanted = Math.asin(Math.min(1, Math.max(-1, eyeMin / distance)));
      elevation = Math.min(MAX_ELEVATION, Math.max(HERO_ELEVATION, wanted));
      dir = heroDirection(elevation);
      fit();
    }
  }

  const position = { x: target.x + dir.x * distance, y: target.y + dir.y * distance, z: target.z + dir.z * distance };
  const { up } = cameraBasis(dir);
  let top = -Infinity;
  let bottom = Infinity;
  for (const p of modelPoints) {
    const q = sub(p, target);
    const depth = distance - dot(q, dir);
    const y = dot(q, up) / (depth * tanV);
    top = Math.max(top, y);
    bottom = Math.min(bottom, y);
  }
  return { target, position, distance, modelHeightFraction: (top - bottom) / 2 };
}

function heroDirection(elevation: number): Vec3 {
  const c = Math.cos(elevation);
  return { x: HERO_AZIMUTH.x * c, y: Math.sin(elevation), z: HERO_AZIMUTH.z * c };
}

/**
 * Distance along `dir` from `target` at which every point projects within
 * `occupancy` of the half-frame, horizontally and vertically.
 */
function fitDistance(points: Vec3[], target: Vec3, dir: Vec3, tanV: number, tanH: number, occupancy: number): number {
  const { right, up } = cameraBasis(dir);
  let distance = 0;
  for (const p of points) {
    const q = sub(p, target);
    const along = dot(q, dir);
    const x = Math.abs(dot(q, right));
    const y = Math.abs(dot(q, up));
    // |lateral| <= occupancy * tan * (distance - along)
    distance = Math.max(distance, along + y / (occupancy * tanV), along + x / (occupancy * tanH));
  }
  return distance;
}

/** Camera right/up vectors for a camera looking back along `dir` with world up. */
function cameraBasis(dir: Vec3): { right: Vec3; up: Vec3 } {
  const forward = { x: -dir.x, y: -dir.y, z: -dir.z };
  const right = unit(cross(forward, { x: 0, y: 1, z: 0 }));
  return { right, up: cross(right, forward) };
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}
function dot(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}
function cross(a: Vec3, b: Vec3): Vec3 {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x };
}
function unit(v: Vec3): Vec3 {
  const l = Math.hypot(v.x, v.y, v.z);
  return { x: v.x / l, y: v.y / l, z: v.z / l };
}
