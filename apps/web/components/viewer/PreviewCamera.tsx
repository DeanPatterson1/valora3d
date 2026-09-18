"use client";

import { useLayoutEffect } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import type { ScenePlan } from "@/lib/schema";
import { handheldOffset, lensToFov, shotAt, shotPathPoint, subjectCentre, type Bounds } from "./cameraPath";

type OrbitLike = { target: THREE.Vector3; update: () => void };

export type PreviewCameraProps = {
  plan: ScenePlan;
  bounds: Bounds;
  /** Absolute timeline time in seconds. */
  seconds: number;
  reducedMotion?: boolean;
};

/**
 * While mounted, drives the default camera along the plan's path. The orbit pose
 * is saved on mount and restored on unmount, so leaving the preview lands exactly
 * where the user left the orbit camera. Driving the existing camera (rather than
 * swapping in a second one) keeps `Bounds` and `OrbitControls` bound to a stable object.
 */
export function PreviewCamera({ plan, bounds, seconds, reducedMotion = false }: PreviewCameraProps) {
  const get = useThree((s) => s.get);

  // Layout effect: the frame loop is already subscribed by then, so save before any preview frame renders.
  useLayoutEffect(() => {
    const { camera, controls } = get();
    const orbit = controls as unknown as OrbitLike | null;
    const position = camera.position.clone();
    const quaternion = camera.quaternion.clone();
    const fov = (camera as THREE.PerspectiveCamera).fov;
    const target = orbit?.target.clone();
    return () => {
      const state = get();
      const cam = state.camera as THREE.PerspectiveCamera;
      cam.position.copy(position);
      cam.quaternion.copy(quaternion);
      cam.fov = fov;
      cam.updateProjectionMatrix();
      const ctl = state.controls as unknown as OrbitLike | null;
      if (ctl && target) {
        ctl.target.copy(target);
        ctl.update();
      }
      state.invalidate();
    };
  }, [get]);

  useFrame(({ camera }) => {
    const cam = camera as THREE.PerspectiveCamera;
    const { shot, t } = shotAt(plan, seconds);
    const p = shotPathPoint(plan, shot, t, bounds);
    const sway =
      plan.camera.style === "handheld" && !reducedMotion
        ? handheldOffset(seconds, plan.camera.motionStrength)
        : { x: 0, y: 0, roll: 0 };
    const centre = subjectCentre(bounds);
    cam.position.set(p.x + sway.x, p.y + sway.y, p.z);
    cam.up.set(0, 1, 0);
    cam.lookAt(centre.x, centre.y, centre.z);
    if (sway.roll) cam.rotateZ(sway.roll);
    const fov = lensToFov(plan.camera.lensMm);
    if (cam.fov !== fov) {
      cam.fov = fov;
      cam.updateProjectionMatrix();
    }
    cam.updateMatrixWorld();
  }, -2);

  return null;
}
