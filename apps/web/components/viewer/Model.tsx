"use client";

import { useLayoutEffect, useRef } from "react";
import * as THREE from "three";
import { animate } from "motion/react";
import { SPRING } from "@/lib/motion/tokens";
import type { Bounds } from "./cameraPath";
import { normalize } from "./loadModel";

/** Drop-in starts this fraction of the model's height below the floor (at least `DROP_MIN_M`). */
const DROP_FRACTION = 0.12;
const DROP_MIN_M = 0.05;

export type ModelProps = {
  root: THREE.Object3D;
  scaleFactor: number;
  reducedMotion: boolean;
  onBounds: (rootId: string, key: string, bounds: Bounds) => void;
  /** Fires once the drop-in spring has come to rest (immediately under reduced motion). */
  onSettled?: (key: string) => void;
};

/** Places the model: normalise once, scale by analysis factor, measure, then drop in. */
export function Model({ root, scaleFactor, reducedMotion, onBounds, onSettled }: ModelProps) {
  const lift = useRef<THREE.Group>(null);
  const scaled = useRef<THREE.Group>(null);
  const onSettledRef = useRef(onSettled);
  useLayoutEffect(() => {
    onSettledRef.current = onSettled;
  }, [onSettled]);

  useLayoutEffect(() => {
    normalize(root);
    root.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh) {
        mesh.castShadow = true;
        mesh.receiveShadow = true;
      }
    });
  }, [root]);

  // Measure, then drop in: rise from slightly below the floor with a short spring settle.
  // Layout effect so the first frame already shows the model at its start position.
  useLayoutEffect(() => {
    const group = scaled.current;
    const drop = lift.current;
    if (!group || !drop) return;
    group.updateWorldMatrix(true, true);
    const size = new THREE.Box3().setFromObject(group).getSize(new THREE.Vector3());
    const key = `${root.uuid}:${scaleFactor}`;
    onBounds(root.uuid, key, { radius: Math.max(size.x, size.z) / 2, height: size.y });

    if (reducedMotion) {
      drop.position.y = 0;
      onSettledRef.current?.(key);
      return;
    }
    const from = -Math.max(DROP_MIN_M, size.y * DROP_FRACTION);
    drop.position.y = from;
    const controls = animate(from, 0, {
      ...SPRING.gentle,
      onUpdate: (v) => {
        drop.position.y = v;
      },
      onComplete: () => onSettledRef.current?.(key),
    });
    return () => {
      controls.stop();
      drop.position.y = 0;
    };
  }, [root, scaleFactor, reducedMotion, onBounds]);

  return (
    <group ref={lift}>
      <group ref={scaled} scale={scaleFactor}>
        <primitive object={root} />
      </group>
    </group>
  );
}
