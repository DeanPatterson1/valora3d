"use client";

import { useEffect, useMemo } from "react";
import * as THREE from "three";

const SKY_VERTEX = /* glsl */ `
  varying vec3 vWorld;
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vWorld = world.xyz;
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;
/** Share of the dome below the horizon over which the sky blends into the floor colour. */
const BELOW_HORIZON = 0.35;
const SKY_FRAGMENT = /* glsl */ `
  uniform vec3 horizon;
  uniform vec3 zenith;
  uniform vec3 floor;
  varying vec3 vWorld;
  void main() {
    float h = normalize(vWorld).y;
    // Above: a long, gentle ramp to the zenith. Below: continue down into the floor colour so the
    // dome behind the ground disc never shows as a flat band.
    float up = pow(clamp(h, 0.0, 1.0), 0.7);
    float down = smoothstep(0.0, ${BELOW_HORIZON.toFixed(2)}, -h);
    gl_FragColor = vec4(mix(mix(horizon, floor, down), zenith, up), 1.0);
    #include <colorspace_fragment>
  }
`;

export type SkyProps = { horizon: string; zenith: string; floor: string; radius: number };

/** Gradient sky dome, immune to fog so the horizon stays crisp. */
export function Sky({ horizon, zenith, floor, radius }: SkyProps) {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          horizon: { value: new THREE.Color(horizon) },
          zenith: { value: new THREE.Color(zenith) },
          floor: { value: new THREE.Color(floor) },
        },
        vertexShader: SKY_VERTEX,
        fragmentShader: SKY_FRAGMENT,
        side: THREE.BackSide,
        depthWrite: false,
        fog: false,
      }),
    // Colours update through the effect below; the material itself is created once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  useEffect(() => {
    material.uniforms.horizon.value.set(horizon);
    material.uniforms.zenith.value.set(zenith);
    material.uniforms.floor.value.set(floor);
  }, [material, horizon, zenith, floor]);
  useEffect(() => () => material.dispose(), [material]);
  return (
    <mesh material={material} renderOrder={-10} frustumCulled={false}>
      <sphereGeometry args={[radius, 32, 16]} />
    </mesh>
  );
}
