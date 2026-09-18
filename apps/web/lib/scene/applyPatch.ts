import type { ScenePlan, ScenePatch } from "@/lib/schema";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function applyPatch(plan: ScenePlan, patch: ScenePatch): ScenePlan {
  const p = structuredClone(plan);
  switch (patch.operation) {
    case "update_lighting":
      if (patch.exposureDelta !== undefined) p.lighting.exposure = clamp(p.lighting.exposure + patch.exposureDelta, -3, 3);
      if (patch.style) p.lighting.style = patch.style;
      if (patch.rim !== undefined) p.lighting.rim = patch.rim;
      if (patch.practicals !== undefined) p.lighting.practicals = patch.practicals;
      break;
    case "modify_camera":
      if (patch.lensMm !== undefined) p.camera.lensMm = clamp(patch.lensMm, 18, 135);
      if (patch.heightDelta !== undefined) p.camera.heightM = clamp(p.camera.heightM + patch.heightDelta, 0.2, 3);
      if (patch.style) p.camera.style = patch.style;
      if (patch.motionStrength !== undefined) p.camera.motionStrength = clamp(patch.motionStrength, 0, 1);
      if (patch.distanceMultiplier !== undefined) {
        for (const s of p.shots) {
          if (patch.shotId && s.id !== patch.shotId) continue;
          s.distanceMultiplier = clamp(s.distanceMultiplier * patch.distanceMultiplier, 0.4, 2.5);
        }
      }
      break;
    case "set_shot_action": {
      const s = p.shots.find((x) => x.id === patch.shotId);
      if (s) s.action = patch.action;
      break;
    }
    case "set_effect":
      p.effects[patch.effect] = clamp(patch.value, 0, 1);
      break;
    case "set_scene":
      if (patch.environment) p.scene.environment = patch.environment;
      if (patch.time) p.scene.time = patch.time;
      if (patch.ground) p.scene.ground = patch.ground;
      if (patch.fogDensity !== undefined) p.scene.fogDensity = clamp(patch.fogDensity, 0, 0.1);
      break;
    case "set_output": {
      const prev = p.output.durationS;
      // Explicit `undefined` fields must not erase existing values.
      const given = Object.fromEntries(Object.entries(patch.output).filter(([, v]) => v !== undefined));
      p.output = { ...p.output, ...given };
      if (p.output.durationS !== prev) {
        const k = p.output.durationS / prev;
        p.shots = p.shots.map((s) => ({ ...s, start: s.start * k, end: s.end * k }));
        p.shots[p.shots.length - 1].end = p.output.durationS;
      }
      break;
    }
  }
  return p;
}
