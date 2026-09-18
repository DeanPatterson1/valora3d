"use client";

import { useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";

export type ThumbnailCaptureProps = {
  /** Bump to request a capture. */
  captureKey?: number;
  /** Identity of the mounted model; a change arms a capture. */
  modelKey: string | null;
  /** True once framing and drop-in have settled and no preview is showing. Captures wait for it. */
  ready: boolean;
  /** Extra seconds after `ready` before capturing, so the last animation frame has been drawn. */
  settleS?: number;
  onCapture?: (blob: Blob) => void;
};

/**
 * Renders inside the Canvas. When armed and the scene is `ready`, renders the scene and
 * reads the drawing buffer back in the same tick (no `preserveDrawingBuffer` needed).
 * A request made while not ready (still settling, or previewing) is held until it is.
 */
export function ThumbnailCapture({ captureKey = 0, modelKey, ready, settleS = 0.1, onCapture }: ThumbnailCaptureProps) {
  const armed = useRef(false);
  const readyAt = useRef<number | null>(null);
  const onCaptureRef = useRef(onCapture);
  useEffect(() => {
    onCaptureRef.current = onCapture;
  }, [onCapture]);
  useEffect(() => {
    if (!modelKey) return;
    // A model just mounted, or the parent asked for a fresh capture.
    armed.current = true;
  }, [captureKey, modelKey]);
  useEffect(() => {
    readyAt.current = null;
  }, [ready]);

  useFrame(({ gl, scene, camera, clock }) => {
    if (!armed.current || !ready || !modelKey || !onCaptureRef.current) return;
    if (readyAt.current === null) readyAt.current = clock.elapsedTime;
    if (clock.elapsedTime - readyAt.current < settleS) return;
    armed.current = false;
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
