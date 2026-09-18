"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";

export type RainLayerProps = {
  /** 0..1 from `plan.effects.rain`. */
  intensity: number;
  /** Horizontal radius of the rain volume in metres. */
  radius?: number;
  /** Static streaks, no per-frame update. */
  reducedMotion?: boolean;
};

const MAX_DROPS = 1500;
const HEIGHT = 12;

/** Light streak layer standing in for rain. Each drop is a short vertical segment. */
export function RainLayer({ intensity, radius = 14, reducedMotion = false }: RainLayerProps) {
  const count = intensity > 0 ? Math.round(MAX_DROPS * (0.25 + 0.75 * Math.min(1, intensity))) : 0;

  const { geometry, speeds } = useMemo(() => {
    const positions = new Float32Array(count * 6);
    const speeds = new Float32Array(count);
    const rng = mulberry32(7);
    for (let i = 0; i < count; i++) {
      const a = rng() * Math.PI * 2;
      const r = Math.sqrt(rng()) * radius;
      const x = Math.cos(a) * r;
      const z = Math.sin(a) * r;
      const y = rng() * HEIGHT;
      const len = 0.18 + rng() * 0.22;
      positions.set([x, y, z, x, y + len, z], i * 6);
      speeds[i] = 9 + rng() * 5;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, HEIGHT / 2, 0), Math.hypot(radius, HEIGHT));
    return { geometry, speeds };
  }, [count, radius]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  const ref = useRef<THREE.LineSegments>(null);
  useFrame((_, delta) => {
    if (reducedMotion || count === 0) return;
    const attr = geometry.getAttribute("position") as THREE.BufferAttribute;
    const arr = attr.array as Float32Array;
    const dt = Math.min(delta, 0.05);
    for (let i = 0; i < count; i++) {
      const o = i * 6;
      const fall = speeds[i] * dt;
      arr[o + 1] -= fall;
      arr[o + 4] -= fall;
      if (arr[o + 1] < 0) {
        const len = arr[o + 4] - arr[o + 1];
        arr[o + 1] += HEIGHT;
        arr[o + 4] = arr[o + 1] + len;
      }
    }
    attr.needsUpdate = true;
  });

  if (count === 0) return null;
  return (
    <lineSegments ref={ref} geometry={geometry} frustumCulled={false}>
      <lineBasicMaterial color="#cfd8e6" transparent opacity={0.12 + 0.28 * Math.min(1, intensity)} depthWrite={false} />
    </lineSegments>
  );
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
