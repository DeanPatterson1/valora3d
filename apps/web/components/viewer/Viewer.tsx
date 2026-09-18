"use client";

import { Suspense, useCallback, useState } from "react";
import type * as THREE from "three";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useReducedMotion } from "motion/react";
import type { ScenePlan } from "@/lib/schema";
import { CameraPath } from "./CameraPathLine";
import { FitCamera } from "./FitCamera";
import { Model } from "./Model";
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
/** Rain volume radius as a multiple of the subject radius. */
const RAIN_RADIUS_FACTOR = 5;

type Settled = { model: string | null; camera: string | null };

export function Viewer({ root, plan, scaleFactor, previewSeconds, captureKey, onThumbnail, className }: ViewerProps) {
  const reducedMotion = useReducedMotion() ?? false;
  // Measured by <Model/> once it has placed the current root; ignored once the root changes.
  const [measured, setMeasured] = useState<{ rootId: string; key: string; bounds: SubjectBounds } | null>(null);
  const onBounds = useCallback((rootId: string, key: string, bounds: SubjectBounds) => {
    setMeasured({ rootId, key, bounds });
  }, []);
  // Which model key each intro animation has finished for.
  const [settled, setSettled] = useState<Settled>({ model: null, camera: null });
  const onModelSettled = useCallback((key: string) => setSettled((s) => ({ ...s, model: key })), []);

  const current = root && measured?.rootId === root.uuid ? measured : null;
  const bounds = current?.bounds ?? null;
  const modelKey = current?.key ?? null;
  const subject = bounds ?? FALLBACK_BOUNDS;
  const previewing = previewSeconds !== null && plan !== null && bounds !== null;
  const loaded = root !== null && modelKey !== null;
  const atRest = loaded && settled.model === modelKey && settled.camera === modelKey;
  const onCameraSettled = useCallback(() => setSettled((s) => ({ ...s, camera: modelKey })), [modelKey]);

  return (
    <ViewerBoundary>
      <div
        className={`relative h-full min-h-0 w-full overflow-hidden bg-bg-0 ${className ?? ""}`}
        data-model-loaded={loaded ? "true" : undefined}
        data-settled={atRest ? "true" : undefined}
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

          {root && (
            <Model key={root.uuid} root={root} scaleFactor={scaleFactor} reducedMotion={reducedMotion} onBounds={onBounds} onSettled={onModelSettled} />
          )}
          {bounds && <FitCamera key={modelKey} bounds={bounds} plan={plan} reducedMotion={reducedMotion} onSettled={onCameraSettled} />}

          {plan && bounds && <CameraPath plan={plan} bounds={bounds} />}
          {plan && bounds && previewSeconds !== null && (
            <PreviewCamera plan={plan} bounds={bounds} seconds={previewSeconds} reducedMotion={reducedMotion} />
          )}
          {plan && <RainLayer intensity={plan.effects.rain} radius={subject.radius * RAIN_RADIUS_FACTOR} reducedMotion={reducedMotion} />}

          <OrbitControls
            makeDefault
            enabled={!previewing}
            enableDamping={!reducedMotion}
            dampingFactor={0.08}
            minPolarAngle={0.05}
            maxPolarAngle={Math.PI / 2 - 0.02}
            target={[0, subject.height / 2, 0]}
          />
          <ThumbnailCapture captureKey={captureKey} modelKey={modelKey} ready={atRest && previewSeconds === null} onCapture={onThumbnail} />
        </Canvas>
      </div>
    </ViewerBoundary>
  );
}
