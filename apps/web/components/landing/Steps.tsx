"use client";

import { Item, Section } from "./Section";

const ICON = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  className: "size-5",
  "aria-hidden": true,
} as const;

const STEPS = [
  {
    title: "Upload",
    line: "Drop a GLB, FBX or OBJ. We read its size and parts for you.",
    icon: (
      <svg {...ICON}>
        <path d="M12 16V4m0 0-4 4m4-4 4 4" />
        <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
      </svg>
    ),
  },
  {
    title: "Describe",
    line: "Say the shot in plain words: “rainy night, slow orbit”.",
    icon: (
      <svg {...ICON}>
        <path d="M4 6h16M4 12h10M4 18h7" />
      </svg>
    ),
  },
  {
    title: "Render",
    line: "Preview the scene live, then render locally or in the cloud.",
    icon: (
      <svg {...ICON}>
        <rect x="3" y="5" width="18" height="14" rx="3" />
        <path d="m10 9 5 3-5 3V9Z" />
      </svg>
    ),
  },
] as const;

export function Steps() {
  return (
    <Section aria-label="How it works">
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {STEPS.map((s, i) => (
          <Item key={s.title} className="flex flex-col gap-3 rounded-md border border-line bg-bg-1 p-5" role="listitem">
            <span className="flex size-9 items-center justify-center rounded-sm bg-bg-2 text-fg">{s.icon}</span>
            <div className="flex flex-col gap-1">
              <h2 className="text-base font-semibold tracking-tight text-fg">
                <span className="mr-1.5 text-fg-muted tabular">{i + 1}.</span>
                {s.title}
              </h2>
              <p className="text-sm text-fg-muted">{s.line}</p>
            </div>
          </Item>
        ))}
      </ul>
    </Section>
  );
}
