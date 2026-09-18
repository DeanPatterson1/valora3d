import type { Bounds } from "./cameraPath";

/** Nothing in the world is sized below this (metres), so tiny subjects still get a room around them. */
export const MIN_REACH = 1.5;
/** Ground disc radius as a multiple of reach. */
export const GROUND_RADIUS_FACTOR = 60;
/** Sky dome radius as a multiple of reach; larger than the ground so the disc always ends inside the sky. */
export const SKY_RADIUS_FACTOR = 150;

/** The one scale every world element (lights, ground, sky, camera far plane) derives from. */
export function sceneReach(bounds: Bounds): number {
  return Math.max(bounds.radius, MIN_REACH);
}

export function groundRadius(reach: number): number {
  return reach * GROUND_RADIUS_FACTOR;
}

export function skyRadius(reach: number): number {
  return reach * SKY_RADIUS_FACTOR;
}
