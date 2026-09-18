"use client";

import { Slider } from "@/components/ui";
import type { ScenePlan } from "@/lib/schema";
import { useStudioStore, type SliderKey } from "@/lib/stores/studio";

type Control = {
  key: SliderKey;
  label: string;
  min: number;
  max: number;
  step: number;
  /** Human words at the ends of the track — read out as the group label, never shown. */
  ends: [string, string];
  read: (plan: ScenePlan) => number;
  format: (v: number) => string;
};

const percent = (v: number) => `${Math.round(v * 100)}%`;
const FOG_MAX = 0.1;
/** Fog density 0–0.1 shown as 0%–100% of the range. */
const fogPercent = (v: number) => `${Math.round((v / FOG_MAX) * 100)}%`;
/** Exposure stops: `−0.7`, `0.0`, `+0.7` (real minus sign). */
export const formatStops = (v: number) => {
  const fixed = Math.abs(v).toFixed(1);
  if (fixed === "0.0") return "0.0";
  return v < 0 ? `−${fixed}` : `+${fixed}`;
};

export const CONTROLS: Control[] = [
  { key: "handheld", label: "Handheld", min: 0, max: 1, step: 0.01, ends: ["Smooth", "Raw"], read: (p) => p.camera.motionStrength, format: percent },
  { key: "depthOfField", label: "Depth of field", min: 0, max: 1, step: 0.01, ends: ["Off", "Strong"], read: (p) => p.effects.depthOfField, format: percent },
  { key: "motionBlur", label: "Motion blur", min: 0, max: 1, step: 0.01, ends: ["Off", "Heavy"], read: (p) => p.effects.motionBlur, format: percent },
  { key: "fog", label: "Fog", min: 0, max: FOG_MAX, step: 0.005, ends: ["None", "Heavy"], read: (p) => p.scene.fogDensity, format: fogPercent },
  { key: "light", label: "Light", min: -3, max: 3, step: 0.1, ends: ["Dark", "Bright"], read: (p) => p.lighting.exposure, format: formatStops },
];

/** Resting positions shown while there is no plan to control. */
const IDLE: Record<SliderKey, number> = { handheld: 0, depthOfField: 0, motionBlur: 0, fog: 0, light: 0 };

/**
 * Right-panel "Controls" tab (spec 6.3). Each slider previews live in memory and, on
 * release, appends a free `manual: <control>` version, so nothing is ever overwritten.
 * Values read from `currentPlan`, so selecting an older version moves the sliders.
 */
export function ControlsPanel() {
  const plan = useStudioStore((s) => s.currentPlan);
  const busy = useStudioStore((s) => s.busy);
  const previewSlider = useStudioStore((s) => s.previewSlider);
  const commitSlider = useStudioStore((s) => s.commitSlider);
  const savedPlan = useStudioStore((s) => s.versions.find((v) => v.id === s.selectedVersionId)?.plan ?? null);

  // Slider commits set busy="editing" for a moment; disabling for that would break a drag.
  const disabled = !plan || busy === "loading" || busy === "analyzing" || busy === "planning";

  // The Slider also commits on blur and key-up; only an actual change deserves a version.
  const commit = (c: Control, v: number) => {
    if (!plan) return;
    if (savedPlan && Math.abs(c.read(savedPlan) - v) < c.step / 2) return;
    void commitSlider(c.key, v);
  };

  return (
    <div className="flex flex-col gap-5 p-4">
      {!plan && (
        <p id="controls-hint" className="text-sm text-fg-muted">
          Generate a scene first
        </p>
      )}
      <fieldset disabled={disabled} className="flex min-w-0 flex-col gap-5 border-0 p-0" aria-describedby={plan ? undefined : "controls-hint"}>
        <legend className="sr-only">Scene controls</legend>
        {CONTROLS.map((c) => (
          // The track's end words are context for assistive tech only; the visible row is label + value.
          <div key={c.key} role="group" aria-label={`${c.label}: ${c.ends[0]} to ${c.ends[1]}`}>
            <Slider
              label={c.label}
              min={c.min}
              max={c.max}
              step={c.step}
              value={plan ? c.read(plan) : IDLE[c.key]}
              onChange={(v) => previewSlider(c.key, v)}
              onCommit={(v) => commit(c, v)}
              format={c.format}
              disabled={disabled}
            />
          </div>
        ))}
      </fieldset>
      <p className="text-xs text-fg-muted">Sliders are free — each release saves a version</p>
    </div>
  );
}
