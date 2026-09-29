"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
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
  /** Draw the camera path and fit it into the hero view. False lets the model fill the frame. Default true. */
  showPath?: boolean;
  /** Ground grid; capture/marketing frames turn it off. */
  showGrid?: boolean;
  /** Text alternative for the canvas (`role="img"`), describing the loaded model and scene (viewerLabel.ts). */
  label?: string;
};

/** The <canvas> itself carries the label: R3F puts extra props on its wrapper div, which screen readers skip past. */
function labelCanvas(canvas: HTMLCanvasElement | null | undefined, label: string) {
  if (!canvas) return;
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", label);
}

const FALLBACK_BOUNDS: SubjectBounds = { radius: 2.4, height: 1.4 };
/** Rain volume radius as a multiple of the subject radius. */
const RAIN_RADIUS_FACTOR = 5;

type Settled = { model: string | null; camera: string | null };

export function Viewer({ root, plan, scaleFactor, previewSeconds, captureKey, onThumbnail, showPath = true, showGrid = true, label = "3D preview" }: ViewerProps) {
  const frame = useRef<HTMLDivElement>(null);
  useEffect(() => labelCanvas(frame.current?.querySelector("canvas"), label), [label]);
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
        ref={frame}
        className="relative h-full min-h-0 w-full overflow-hidden bg-bg-0"
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
          onCreated={({ gl }) => labelCanvas(gl.domElement, label)}
        >
          <Suspense fallback={null}>
            <SceneEnvironment plan={plan} bounds={subject} showGrid={showGrid} />
          </Suspense>

          {root && (
            <Model key={root.uuid} root={root} scaleFactor={scaleFactor} reducedMotion={reducedMotion} onBounds={onBounds} onSettled={onModelSettled} />
          )}
          {bounds && <FitCamera key={modelKey} bounds={bounds} plan={plan} showPath={showPath} reducedMotion={reducedMotion} onSettled={onCameraSettled} />}

          {plan && bounds && showPath && <CameraPath plan={plan} bounds={bounds} />}
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
