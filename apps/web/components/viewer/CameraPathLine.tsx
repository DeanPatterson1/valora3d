"use client";

import { useMemo } from "react";
import { Line } from "@react-three/drei";
import type { ScenePlan } from "@/lib/schema";
import { shotPathPoint, type Bounds } from "./cameraPath";
import { ACCENT_HEX } from "./palette";

const SAMPLES = 64;
/** Start/end marker radius as a share of the subject radius, with a floor for tiny subjects. */
const MARKER_FACTOR = 0.02;
const MARKER_MIN_M = 0.008;

export type CameraPathProps = { plan: ScenePlan; bounds: Bounds };

/** Every shot's camera route as a line: accent for the first shot, dimmer for the second. */
export function CameraPath({ plan, bounds }: CameraPathProps) {
  const paths = useMemo(
    () =>
      plan.shots.map((shot) => {
        const points: [number, number, number][] = [];
        for (let i = 0; i < SAMPLES; i++) {
          const p = shotPathPoint(plan, shot, i / (SAMPLES - 1), bounds);
          points.push([p.x, p.y, p.z]);
        }
        return { id: shot.id, points };
      }),
    [plan, bounds],
  );

  const marker = Math.max(MARKER_MIN_M, bounds.radius * MARKER_FACTOR);

  return (
    <>
      {paths.map(({ id, points }, index) => {
        const opacity = index === 0 ? 0.7 : 0.35;
        const start = points[0];
        const end = points[points.length - 1];
        return (
          <group key={id}>
            <Line points={points} color={ACCENT_HEX} lineWidth={index === 0 ? 1.6 : 1.2} transparent opacity={opacity} depthWrite={false} />
            <mesh position={start}>
              <sphereGeometry args={[marker, 12, 8]} />
              <meshBasicMaterial color={ACCENT_HEX} transparent opacity={opacity} depthWrite={false} />
            </mesh>
            <mesh position={end}>
              <sphereGeometry args={[marker * 0.65, 12, 8]} />
              <meshBasicMaterial color={ACCENT_HEX} transparent opacity={opacity * 0.6} depthWrite={false} />
            </mesh>
          </group>
        );
      })}
    </>
  );
}
