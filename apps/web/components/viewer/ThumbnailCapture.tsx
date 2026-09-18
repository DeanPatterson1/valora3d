"use client";

import { useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";

export type ThumbnailCaptureProps = {
  /** Bump to request a capture. */
  captureKey?: number;
  /** Identity of the mounted model; a change arms a capture once framing has settled. */
  modelKey: string | null;
  /** Seconds to wait after arming before capturing, so auto-framing and drop-in finish first. */
  settleS: number;
  onCapture?: (blob: Blob) => void;
};

/**
 * Renders inside the Canvas. When armed, waits `settleS`, then renders the scene and
 * reads the drawing buffer back in the same tick (no `preserveDrawingBuffer` needed).
 */
export function ThumbnailCapture({ captureKey = 0, modelKey, settleS, onCapture }: ThumbnailCaptureProps) {
  const armedAt = useRef<number | null>(null);
  const onCaptureRef = useRef(onCapture);
  useEffect(() => {
    onCaptureRef.current = onCapture;
  }, [onCapture]);
  useEffect(() => {
    if (!modelKey) return;
    // A model just mounted, or the parent asked for a fresh capture.
    armedAt.current = -1;
  }, [captureKey, modelKey]);

  useFrame(({ gl, scene, camera, clock }) => {
    if (armedAt.current === null || !modelKey || !onCaptureRef.current) return;
    if (armedAt.current < 0) armedAt.current = clock.elapsedTime;
    if (clock.elapsedTime - armedAt.current < settleS) return;
    armedAt.current = null;
    gl.render(scene, camera);
    gl.domElement.toBlob(
      (blob) => {
        if (blob) onCaptureRef.current?.(blob);
      },
      "image/jpeg",
      0.8,
    );
  });

  return null;
}
