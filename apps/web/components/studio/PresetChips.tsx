"use client";

import { Chip } from "@/components/ui";
import { PRESETS, type Preset } from "./presets";

type Props = {
  /** Fills the textarea and focuses it; never submits. */
  onPick: (preset: Preset) => void;
  disabled?: boolean;
  /** The preset whose prompt is currently in the textarea, if any. */
  activeId?: Preset["id"] | null;
  className?: string;
};

/** Example prompts above the input (spec 10: blank-page avoidance, recognition over recall). */
export function PresetChips({ onPick, disabled, activeId = null, className }: Props) {
  return (
    <ul aria-label="Example prompts" className={className ? `flex gap-2 ${className}` : "flex gap-2"}>
      {PRESETS.map((p) => (
        <li key={p.id} className="shrink-0">
          <Chip selected={p.id === activeId} disabled={disabled} onClick={() => onPick(p)}>
            {p.label}
          </Chip>
        </li>
      ))}
    </ul>
  );
}
