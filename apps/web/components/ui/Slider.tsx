"use client";

import { useId } from "react";
import { cx } from "./cx";

export type SliderProps = {
  label: string;
  min: number;
  max: number;
  step?: number;
  value: number;
  /** Fires on every change while dragging or pressing arrow keys. */
  onChange: (value: number) => void;
  /** Fires once the pointer is released or a key is released. */
  onCommit?: (value: number) => void;
  /** Formats the value for display and `aria-valuetext`. */
  format?: (value: number) => string;
  disabled?: boolean;
  className?: string;
};

export function Slider({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  onCommit,
  format = (v) => String(v),
  disabled,
  className,
}: SliderProps) {
  const id = useId();
  const fill = max > min ? ((value - min) / (max - min)) * 100 : 0;
  const commit = () => onCommit?.(value);

  return (
    <div className={cx("flex flex-col gap-1", className)}>
      <div className="flex items-baseline justify-between text-sm">
        <label htmlFor={id} className="text-fg">
          {label}
        </label>
        <output htmlFor={id} className="font-mono tabular text-fg-muted">
          {format(value)}
        </output>
      </div>
      <input
        id={id}
        type="range"
        className="slider"
        style={{ "--slider-fill": `${fill}%` } as React.CSSProperties}
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        aria-valuetext={format(value)}
        onChange={(e) => onChange(Number(e.currentTarget.value))}
        onPointerUp={commit}
        onKeyUp={commit}
        onBlur={commit}
      />
    </div>
  );
}
