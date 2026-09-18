"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { useThree } from "@react-three/fiber";
import { animate } from "motion/react";
import type { ScenePlan } from "@/lib/schema";
import { DUR, EASE } from "@/lib/motion/tokens";
import type { Bounds } from "./cameraPath";
import { heroFraming } from "./framing";
import { sceneReach, skyRadius } from "./sceneScale";

export const FIT_SECONDS = DUR.slow * 2;

type OrbitLike = { target: THREE.Vector3; maxDistance: number; update: () => void };

export type FitCameraProps = {
  bounds: Bounds;
  /** When present, the hero view also fits every shot's camera path. */
  plan: ScenePlan | null;
  reducedMotion: boolean;
  /** Fires once the camera has reached its hero pose. */
  onSettled?: () => void;
};

/**
 * Frames the subject once per model: eases the orbit camera from wherever it is to a
 * three-quarter view that fits the bounds (and the camera path, if a plan exists), and
 * sets near/far so the whole world - ground disc and sky dome included - stays visible.
 */
export function FitCamera({ bounds, plan, reducedMotion, onSettled }: FitCameraProps) {
  const get = useThree((s) => s.get);
  const onSettledRef = useRef(onSettled);
  useEffect(() => {
    onSettledRef.current = onSettled;
  }, [onSettled]);
  useEffect(() => {
    const settle = () => onSettledRef.current?.();
    const { camera, controls, invalidate } = get();
    const cam = camera as THREE.PerspectiveCamera;
    const orbit = controls as unknown as OrbitLike | null;
    const framing = heroFraming(bounds, plan, cam.fov, cam.aspect);
    const target = new THREE.Vector3(framing.target.x, framing.target.y, framing.target.z);
    const goal = new THREE.Vector3(framing.position.x, framing.position.y, framing.position.z);
    const { distance } = framing;

    // The orbit camera may back off up to `maxDistance`; the far plane covers the sky dome from there.
    const sky = skyRadius(sceneReach(bounds));
    const maxDistance = Math.min(distance * 10, sky * 0.5);
    cam.near = Math.max(0.01, distance / 100);
    cam.far = Math.max(distance * 100, (sky + maxDistance + target.y) * 1.1);
    cam.updateProjectionMatrix();
    if (orbit) orbit.maxDistance = maxDistance;

    const fromPosition = cam.position.clone();
    const fromTarget = orbit ? orbit.target.clone() : new THREE.Vector3();
    const currentTarget = fromTarget.clone();
    const apply = (k: number) => {
      cam.position.lerpVectors(fromPosition, goal, k);
      currentTarget.lerpVectors(fromTarget, target, k);
      if (orbit) {
        orbit.target.copy(currentTarget);
        orbit.update();
      } else {
        cam.lookAt(currentTarget);
      }
      invalidate();
    };
    if (reducedMotion) {
      apply(1);
      settle();
      return;
    }
    const anim = animate(0, 1, { duration: FIT_SECONDS, ease: [...EASE.emphasized], onUpdate: apply, onComplete: settle });
    return () => anim.stop();
    // The plan only changes the initial fit; re-fitting on every plan edit would fight the user's orbit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [get, bounds, reducedMotion]);
  return null;
}
