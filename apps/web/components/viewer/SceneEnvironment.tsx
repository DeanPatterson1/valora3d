"use client";

import { Component, Suspense, useEffect, useMemo, useRef, type ReactNode } from "react";
import * as THREE from "three";
import { useThree } from "@react-three/fiber";
import { Environment, Grid } from "@react-three/drei";
import type { ScenePlan } from "@/lib/schema";
import type { Bounds } from "./cameraPath";

type EnvironmentName = ScenePlan["scene"]["environment"];
type LightingStyle = ScenePlan["lighting"]["style"];
type TimeOfDay = ScenePlan["scene"]["time"];
type EnvPreset = "studio" | "sunset" | "dawn" | "night";

/** Everything a preset decides about the world around the model. */
export type EnvironmentLook = {
  /** Sky at the horizon (also the fog colour and, for studios, the whole backdrop). */
  horizon: string;
  /** Sky overhead. Equal to `horizon` for flat studio backdrops. */
  zenith: string;
  ground: string;
  gridCell: string;
  gridSection: string;
  /** Extra fog so studio floors dissolve into their backdrop. */
  baseFog: number;
  /** drei preset for the reflection map, and how strongly it lights the model. */
  preset: EnvPreset;
  envIntensity: number;
  /** Reflection strength on the floor; kept low for the black studio so the void stays black. */
  groundEnv: number;
  practicals: boolean;
};

export function environmentLook(environment: EnvironmentName, time: TimeOfDay): EnvironmentLook {
  switch (environment) {
    case "studio_black":
      return {
        horizon: "#050505",
        zenith: "#050505",
        ground: "#0b0b0b",
        gridCell: "#2e2a25",
        gridSection: "#48413a",
        baseFog: 0.012,
        preset: "studio",
        envIntensity: 0.55,
        groundEnv: 0.08,
        practicals: false,
      };
    case "studio_white":
      return {
        horizon: "#e6e2db",
        zenith: "#f1eee8",
        ground: "#bdb7ae",
        gridCell: "#a29b91",
        gridSection: "#8c857b",
        baseFog: 0.02,
        preset: "studio",
        envIntensity: 0.9,
        groundEnv: 0.45,
        practicals: false,
      };
    case "outdoor_road": {
      if (time === "night")
        return {
          horizon: "#1c1e2c",
          zenith: "#05060c",
          ground: "#1a1a1c",
          gridCell: "#2c2b2f",
          gridSection: "#3a383d",
          baseFog: 0.016,
          preset: "night",
          envIntensity: 0.5,
          groundEnv: 0.35,
          practicals: false,
        };
      if (time === "day")
        return {
          horizon: "#c9d3dc",
          zenith: "#6f9bc8",
          ground: "#3a3a3c",
          gridCell: "#4a4a4d",
          gridSection: "#5a5a5e",
          baseFog: 0.014,
          preset: "dawn",
          envIntensity: 0.9,
          groundEnv: 0.35,
          practicals: false,
        };
      return {
        horizon: "#d8875a",
        zenith: "#2c2140",
        ground: "#2a2729",
        gridCell: "#3e3836",
        gridSection: "#514843",
        baseFog: 0.018,
        preset: "sunset",
        envIntensity: 0.8,
        groundEnv: 0.35,
        practicals: false,
      };
    }
    case "urban_night":
      return {
        horizon: "#182032",
        zenith: "#04060b",
        ground: "#101318",
        gridCell: "#232a38",
        gridSection: "#2f3848",
        baseFog: 0.016,
        preset: "night",
        envIntensity: 0.6,
        groundEnv: 0.4,
        practicals: true,
      };
  }
}

type Rig = {
  ambient: [color: string, intensity: number];
  key: [color: string, intensity: number, elevation: number, azimuth: number];
  fill: [color: string, intensity: number];
  rim: [color: string, intensity: number];
  /** Shadow softness in shadow-map texels. */
  softness: number;
};

export function lightingRig(style: LightingStyle): Rig {
  switch (style) {
    case "soft_studio":
      return { ambient: ["#ffffff", 0.55], key: ["#fff4e6", 2.2, 0.95, -0.7], fill: ["#e8eef8", 0.9], rim: ["#ffffff", 1.4], softness: 8 };
    case "dramatic_three_point":
      return { ambient: ["#ffffff", 0.15], key: ["#fff1dd", 3.4, 0.8, -1.1], fill: ["#c8d3e6", 0.25], rim: ["#ffffff", 2.6], softness: 2 };
    case "night_city":
      return { ambient: ["#5c6f9e", 0.35], key: ["#a9bce6", 1.0, 1.1, -0.4], fill: ["#3b4d78", 0.45], rim: ["#f2a83b", 2.2], softness: 4 };
    case "sunset":
      return { ambient: ["#ffd2a8", 0.35], key: ["#ffb26b", 2.8, 0.28, -0.9], fill: ["#6e7fb0", 0.55], rim: ["#ffd9b0", 1.6], softness: 3 };
    case "overcast":
      return { ambient: ["#dfe6ee", 1.1], key: ["#f2f5f8", 1.2, 1.2, -0.5], fill: ["#d0d8e2", 0.6], rim: ["#ffffff", 0.5], softness: 10 };
  }
}

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

/** Gradient sky dome, immune to fog so the horizon stays crisp. */
function Sky({ horizon, zenith }: { horizon: string; zenith: string }) {
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
      <sphereGeometry args={[220, 32, 16]} />
    </mesh>
  );
}

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

export type SceneEnvironmentProps = { plan: ScenePlan | null; bounds: Bounds };

const NEUTRAL: ScenePlan["scene"] = { environment: "studio_black", time: "day", ground: "studio_floor", fogDensity: 0 };

export function SceneEnvironment({ plan, bounds }: SceneEnvironmentProps) {
  const scene = plan?.scene ?? NEUTRAL;
  const lighting = plan?.lighting ?? { style: "soft_studio" as const, exposure: 0, rim: true, practicals: false };
  const wet = plan?.effects.wetGround ?? 0;
  const look = environmentLook(scene.environment, scene.time);
  const rig = lightingRig(lighting.style);
  const flatSky = look.horizon === look.zenith;
  const fogDensity = scene.fogDensity * 2 + look.baseFog;

  const reach = Math.max(bounds.radius, 1.5);
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
      {!flatSky && <Sky horizon={look.horizon} zenith={look.zenith} />}
      <Exposure exposure={lighting.exposure} />

      <SilentBoundary>
        <Suspense fallback={null}>
          <Environment preset={look.preset} environmentIntensity={look.envIntensity} background={false} />
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
        <>
          <pointLight color="#f2a83b" intensity={reach * 14} distance={reach * 9} decay={2} position={[reach * 2.4, 1.8, -reach * 1.6]} />
          <pointLight color="#ffb35c" intensity={reach * 9} distance={reach * 8} decay={2} position={[-reach * 2.6, 2.4, reach * 1.2]} />
          <pointLight color="#5a7cff" intensity={reach * 5} distance={reach * 9} decay={2} position={[-reach * 1.2, 2.2, -reach * 2.6]} />
        </>
      )}

      <mesh rotation-x={-Math.PI / 2} position-y={-0.001} receiveShadow>
        <circleGeometry args={[reach * 60, 96]} />
        <meshPhysicalMaterial
          color={groundColour}
          roughness={groundRoughness}
          metalness={groundMetalness}
          specularIntensity={groundSpecular}
          envMapIntensity={groundEnv}
        />
      </mesh>
      <Grid
        position-y={0.002}
        infiniteGrid
        cellSize={0.5}
        cellThickness={0.8}
        cellColor={look.gridCell}
        sectionSize={2.5}
        sectionThickness={1}
        sectionColor={look.gridSection}
        fadeDistance={reach * 9}
        fadeStrength={1.3}
        side={THREE.DoubleSide}
      />
    </>
  );
}
