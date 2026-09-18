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
const SKY_FRAGMENT = /* glsl */ `
  uniform vec3 horizon;
  uniform vec3 zenith;
  varying vec3 vWorld;
  void main() {
    float h = clamp(normalize(vWorld).y, 0.0, 1.0);
    float k = pow(h, 0.55);
    gl_FragColor = vec4(mix(horizon, zenith, k), 1.0);
    #include <colorspace_fragment>
  }
`;

export type SkyProps = { horizon: string; zenith: string; radius: number };

/** Gradient sky dome, immune to fog so the horizon stays crisp. */
export function Sky({ horizon, zenith, radius }: SkyProps) {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: { horizon: { value: new THREE.Color(horizon) }, zenith: { value: new THREE.Color(zenith) } },
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
  }, [material, horizon, zenith]);
  useEffect(() => () => material.dispose(), [material]);
  return (
    <mesh material={material} renderOrder={-10} frustumCulled={false}>
      <sphereGeometry args={[radius, 32, 16]} />
    </mesh>
  );
}
