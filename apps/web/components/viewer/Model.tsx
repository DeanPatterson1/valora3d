"use client";

import { useLayoutEffect, useRef } from "react";
import * as THREE from "three";
import type { ThreeEvent } from "@react-three/fiber";
import { animate } from "motion/react";
import { SPRING } from "@/lib/motion/tokens";
import type { Bounds } from "./cameraPath";
import { normalize } from "./loadModel";
import { nodeId } from "./meshTree";

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
  /** Bumped by the editor whenever the scene graph changed, so bounds are re-measured. */
  revision?: number;
  /** Set in edit mode: a click on a mesh reports its stable node id. */
  onPick?: (id: string, additive: boolean) => void;
};

/** Places the model: normalise once, scale by analysis factor, measure, then drop in. */
export function Model({ root, scaleFactor, reducedMotion, onBounds, onSettled, revision = 0, onPick }: ModelProps) {
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
  const placed = useRef<string | null>(null);
  useLayoutEffect(() => {
    const group = scaled.current;
    const drop = lift.current;
    if (!group || !drop) return;
    group.updateWorldMatrix(true, true);
    const box = new THREE.Box3().setFromObject(group);
    // Deleting every mesh leaves an empty box; keep the last good bounds rather than NaN.
    const size = box.isEmpty() ? new THREE.Vector3(1, 1, 1) : box.getSize(new THREE.Vector3());
    const key = `${root.uuid}:${scaleFactor}`;
    onBounds(root.uuid, key, { radius: Math.max(size.x, size.z) / 2, height: size.y });

    // An edit re-measures but must not replay the drop-in; only a new model does that.
    if (placed.current === key) return;
    placed.current = key;

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
  }, [root, scaleFactor, reducedMotion, onBounds, revision]);

  const pick = (event: ThreeEvent<MouseEvent>) => {
    if (!onPick) return;
    event.stopPropagation();
    const id = nodeId(event.object);
    if (id) onPick(id, event.shiftKey || event.ctrlKey || event.metaKey);
  };

  return (
    <group ref={lift} onClick={onPick ? pick : undefined}>
      <group ref={scaled} scale={scaleFactor}>
        <primitive object={root} />
      </group>
    </group>
  );
}
