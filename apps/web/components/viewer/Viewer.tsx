"use client";

import { Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import * as THREE from "three";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { animate, useReducedMotion } from "motion/react";
import type { ScenePlan } from "@/lib/schema";
import { DUR, EASE, SPRING } from "@/lib/motion/tokens";
import { normalize } from "./loadModel";
import { CameraPath } from "./CameraPathLine";
import { PreviewCamera } from "./PreviewCamera";
import { RainLayer } from "./RainLayer";
import { SceneEnvironment } from "./SceneEnvironment";
import { ThumbnailCapture } from "./ThumbnailCapture";
import { ViewerBoundary } from "./ViewerBoundary";
import type { Bounds as SubjectBounds } from "./cameraPath";

export type ViewerProps = {
  /** Loaded model in file units. The viewer normalises it in place and never scales it directly. */
  root: THREE.Object3D | null;
  plan: ScenePlan | null;
  /** File units to metres, from analysis. */
  scaleFactor: number;
  /** Absolute timeline time in seconds while scrubbing; `null` shows the orbit camera. */
  previewSeconds: number | null;
  /** Bump to request a fresh thumbnail. */
  captureKey?: number;
  onThumbnail?: (blob: Blob) => void;
  className?: string;
};

const FALLBACK_BOUNDS: SubjectBounds = { radius: 2.4, height: 1.4 };
const FIT_SECONDS = DUR.slow * 2;

export function Viewer({ root, plan, scaleFactor, previewSeconds, captureKey, onThumbnail, className }: ViewerProps) {
  const reducedMotion = useReducedMotion() ?? false;
  // Measured by <Model/> once it has placed the current root; ignored once the root changes.
  const [measured, setMeasured] = useState<{ rootId: string; key: string; bounds: SubjectBounds } | null>(null);
  const onBounds = useCallback((rootId: string, key: string, bounds: SubjectBounds) => {
    setMeasured({ rootId, key, bounds });
  }, []);

  const current = root && measured?.rootId === root.uuid ? measured : null;
  const bounds = current?.bounds ?? null;
  const modelKey = current?.key ?? null;
  const subject = bounds ?? FALLBACK_BOUNDS;
  const previewing = previewSeconds !== null && plan !== null && bounds !== null;
  const loaded = root !== null && modelKey !== null;

  return (
    <ViewerBoundary>
      <div
        className={`relative h-full min-h-0 w-full overflow-hidden bg-bg-0 ${className ?? ""}`}
        data-model-loaded={loaded ? "true" : undefined}
        data-previewing={previewing ? "true" : undefined}
      >
        <Canvas
          dpr={[1, 2]}
          shadows="percentage"
          gl={{ antialias: true, powerPreference: "high-performance" }}
          camera={{ fov: 35, position: [6, 2.6, 7.5], near: 0.05, far: 1000 }}
          className="!absolute inset-0"
        >
          <Suspense fallback={null}>
            <SceneEnvironment plan={plan} bounds={subject} />
          </Suspense>

          {root && <Model key={root.uuid} root={root} scaleFactor={scaleFactor} reducedMotion={reducedMotion} onBounds={onBounds} />}
          {bounds && <FitCamera key={modelKey} bounds={bounds} reducedMotion={reducedMotion} />}

          {plan && bounds && <CameraPath plan={plan} bounds={bounds} />}
          {plan && bounds && previewSeconds !== null && (
            <PreviewCamera plan={plan} bounds={bounds} seconds={previewSeconds} reducedMotion={reducedMotion} />
          )}
          {plan && <RainLayer intensity={plan.effects.rain} radius={subject.radius * 5} reducedMotion={reducedMotion} />}

          <OrbitControls
            makeDefault
            enabled={!previewing}
            enableDamping={!reducedMotion}
            dampingFactor={0.08}
            minPolarAngle={0.05}
            maxPolarAngle={Math.PI / 2 - 0.02}
            target={[0, subject.height / 2, 0]}
          />
          <ThumbnailCapture
            captureKey={captureKey}
            modelKey={modelKey}
            settleS={reducedMotion ? 0.1 : FIT_SECONDS + 0.3}
            onCapture={onThumbnail}
          />
        </Canvas>
      </div>
    </ViewerBoundary>
  );
}

type OrbitLike = { target: THREE.Vector3; maxDistance: number; update: () => void };

/** A three-quarter hero angle, unit length. */
const HERO_DIRECTION = new THREE.Vector3(0.66, 0.27, 0.7).normalize();

/**
 * Frames the subject once per model: eases the orbit camera from wherever it is to a
 * three-quarter view that fits the bounds, and sets near/far to suit the scene scale.
 */
function FitCamera({ bounds, reducedMotion }: { bounds: SubjectBounds; reducedMotion: boolean }) {
  const get = useThree((s) => s.get);
  useEffect(() => {
    const { camera, controls, invalidate } = get();
    const cam = camera as THREE.PerspectiveCamera;
    const orbit = controls as unknown as OrbitLike | null;
    const target = new THREE.Vector3(0, bounds.height / 2, 0);
    const maxSize = Math.max(bounds.radius * 2, bounds.height);
    const fitHeight = maxSize / (2 * Math.tan((cam.fov * Math.PI) / 360));
    const fitWidth = fitHeight / Math.max(cam.aspect, 0.5);
    const distance = 1.55 * Math.max(fitHeight, fitWidth);
    const goal = target.clone().addScaledVector(HERO_DIRECTION, distance);

    cam.near = Math.max(0.01, distance / 100);
    cam.far = distance * 100;
    cam.updateProjectionMatrix();
    if (orbit) orbit.maxDistance = distance * 10;

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
      return;
    }
    const anim = animate(0, 1, { duration: FIT_SECONDS, ease: [...EASE.emphasized], onUpdate: apply });
    return () => anim.stop();
  }, [get, bounds, reducedMotion]);
  return null;
}

type ModelProps = {
  root: THREE.Object3D;
  scaleFactor: number;
  reducedMotion: boolean;
  onBounds: (rootId: string, key: string, bounds: SubjectBounds) => void;
};

/** Places the model: normalise once, scale by analysis factor, measure, then drop in. */
function Model({ root, scaleFactor, reducedMotion, onBounds }: ModelProps) {
  const lift = useRef<THREE.Group>(null);
  const scaled = useRef<THREE.Group>(null);
  const height = useRef(1);

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

  useLayoutEffect(() => {
    const group = scaled.current;
    if (!group) return;
    group.updateWorldMatrix(true, true);
    const size = new THREE.Box3().setFromObject(group).getSize(new THREE.Vector3());
    height.current = size.y;
    onBounds(root.uuid, `${root.uuid}:${scaleFactor}`, { radius: Math.max(size.x, size.z) / 2, height: size.y });
  }, [root, scaleFactor, onBounds]);

  // Drop-in: rise from slightly below the floor with a short spring settle.
  useEffect(() => {
    const group = lift.current;
    if (!group || reducedMotion) return;
    const from = -Math.max(0.05, height.current * 0.12);
    group.position.y = from;
    const controls = animate(from, 0, {
      ...SPRING.gentle,
      onUpdate: (v) => {
        group.position.y = v;
      },
    });
    return () => {
      controls.stop();
      group.position.y = 0;
    };
  }, [root, reducedMotion]);

  return (
    <group ref={lift}>
      <group ref={scaled} scale={scaleFactor}>
        <primitive object={root} />
      </group>
    </group>
  );
}
