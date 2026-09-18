"use client";

import { Component, Suspense, useEffect, useMemo, useRef, type ReactNode } from "react";
import * as THREE from "three";
import { useThree } from "@react-three/fiber";
import { Environment, Grid } from "@react-three/drei";
import type { ScenePlan } from "@/lib/schema";
import type { Bounds } from "./cameraPath";
import { ENV_MAP_FILES, environmentLook, lightingRig } from "./environmentLook";
import { groundRadius, sceneReach, skyRadius } from "./sceneScale";
import { Sky } from "./Sky";

/** Ground grid spacing in metres. */
const GRID_CELL_M = 0.5;
const GRID_SECTION_M = 2.5;
/** Grid fades out at this multiple of reach so it never reaches the ground disc's edge. */
const GRID_FADE_FACTOR = 9;

class SilentBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

function Exposure({ exposure }: { exposure: number }) {
  const get = useThree((s) => s.get);
  useEffect(() => {
    get().gl.toneMappingExposure = 2 ** exposure;
  }, [get, exposure]);
  return null;
}

export type SceneEnvironmentProps = { plan: ScenePlan | null; bounds: Bounds; showGrid?: boolean };

const NEUTRAL: ScenePlan["scene"] = { environment: "studio_black", time: "day", ground: "studio_floor", fogDensity: 0 };

export function SceneEnvironment({ plan, bounds, showGrid = true }: SceneEnvironmentProps) {
  const scene = plan?.scene ?? NEUTRAL;
  const lighting = plan?.lighting ?? { style: "soft_studio" as const, exposure: 0, rim: true, practicals: false };
  const wet = plan?.effects.wetGround ?? 0;
  const look = environmentLook(scene.environment, scene.time);
  const rig = lightingRig(lighting.style);
  const flatSky = look.horizon === look.zenith;
  const fogDensity = scene.fogDensity * 2 + look.baseFog;

  const reach = sceneReach(bounds);
  const keyDistance = reach * 4;
  const keyPosition: [number, number, number] = [
    Math.sin(rig.key[3]) * Math.cos(rig.key[2]) * keyDistance,
    Math.sin(rig.key[2]) * keyDistance,
    Math.cos(rig.key[3]) * Math.cos(rig.key[2]) * keyDistance,
  ];
  const shadowExtent = reach * 1.6;

  const keyRef = useRef<THREE.DirectionalLight>(null);
  useEffect(() => {
    const light = keyRef.current;
    if (!light) return;
    const cam = light.shadow.camera;
    cam.left = -shadowExtent;
    cam.right = shadowExtent;
    cam.top = shadowExtent;
    cam.bottom = -shadowExtent;
    cam.near = 0.1;
    cam.far = keyDistance * 2.5;
    cam.updateProjectionMatrix();
    light.shadow.radius = rig.softness;
    light.shadow.needsUpdate = true;
  }, [shadowExtent, keyDistance, rig.softness]);

  // Dry floors are matte: specularIntensity kills the grazing-angle sheen a dielectric
  // would otherwise show under strong keys. Wet brings the specular (and env reflections) back.
  const groundRoughness = 0.92 - 0.72 * wet;
  const groundMetalness = 0.2 * wet;
  const groundSpecular = 0.12 + 0.88 * wet;
  const groundEnv = look.groundEnv * (1 + 4 * wet);
  const groundColour = useMemo(() => new THREE.Color(look.ground).multiplyScalar(1 - 0.35 * wet), [look.ground, wet]);
  const practicals = look.practicals || lighting.practicals;

  return (
    <>
      <color attach="background" args={[look.horizon]} />
      {fogDensity > 0 && <fogExp2 attach="fog" args={[look.horizon, fogDensity]} />}
      {!flatSky && <Sky horizon={look.horizon} zenith={look.zenith} floor={look.ground} radius={skyRadius(reach)} />}
      <Exposure exposure={lighting.exposure} />

      <SilentBoundary>
        <Suspense fallback={null}>
          <Environment files={ENV_MAP_FILES[look.envMap]} environmentIntensity={look.envIntensity} background={false} />
        </Suspense>
      </SilentBoundary>

      <hemisphereLight args={[look.zenith, look.ground, rig.ambient[1] * 0.6]} />
      <ambientLight color={rig.ambient[0]} intensity={rig.ambient[1] * 0.4} />
      <directionalLight
        ref={keyRef}
        color={rig.key[0]}
        intensity={rig.key[1]}
        position={keyPosition}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0004}
        shadow-normalBias={0.02}
      />
      <directionalLight
        color={rig.fill[0]}
        intensity={rig.fill[1]}
        position={[-keyPosition[0] * 0.8, reach * 2.2, keyPosition[2] * 0.6 + reach]}
      />
      {lighting.rim && (
        <directionalLight color={rig.rim[0]} intensity={rig.rim[1]} position={[-keyPosition[0] * 0.5, reach * 2.6, -keyDistance]} />
      )}
      {practicals && (
        // Street lights, not stage lamps: mounted high (2x reach) and far out with a long falloff,
        // so each pool spreads across the ground at well under half the old peak brightness.
        <>
          <pointLight color="#f2a83b" intensity={reach * 45} distance={reach * 16} decay={2} position={[reach * 3, reach * 2, -reach * 2]} />
          <pointLight color="#ffb35c" intensity={reach * 16} distance={reach * 14} decay={2} position={[-reach * 3.2, reach * 2.2, reach * 1.6]} />
          <pointLight color="#5a7cff" intensity={reach * 11} distance={reach * 16} decay={2} position={[-reach * 1.6, reach * 2, -reach * 3.2]} />
        </>
      )}

      <mesh rotation-x={-Math.PI / 2} position-y={-0.001} receiveShadow>
        <circleGeometry args={[groundRadius(reach), 96]} />
        <meshPhysicalMaterial
          color={groundColour}
          roughness={groundRoughness}
          metalness={groundMetalness}
          specularIntensity={groundSpecular}
          envMapIntensity={groundEnv}
        />
      </mesh>
      {showGrid && (
      <Grid
        position-y={0.002}
        infiniteGrid
        cellSize={GRID_CELL_M}
        cellThickness={0.8}
        cellColor={look.gridCell}
        sectionSize={GRID_SECTION_M}
        sectionThickness={1}
        sectionColor={look.gridSection}
        fadeDistance={reach * GRID_FADE_FACTOR}
        fadeStrength={1.3}
        side={THREE.DoubleSide}
      />
      )}
    </>
  );
}
