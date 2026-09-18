"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { BRAND } from "@/lib/brand";
import { DUR, EASE, SPRING } from "@/lib/motion/tokens";
import { fadeRise, staggerList } from "@/lib/motion/variants";
import {
  Badge,
  Button,
  Chip,
  Dialog,
  Field,
  Skeleton,
  Slider,
  TabPanel,
  Tabs,
  useToastStore,
} from "@/components/ui";
import { ChipButton } from "@/components/studio/Composer";
import { CREDIT_COSTS } from "@/lib/pricing";
import { PRESETS } from "@/components/studio/presets";
import { contrast } from "./contrast";
import { COLOURS, RADII, SURFACES, TEXT, TYPE_SCALE } from "./tokens";

const BG0 = SURFACES[0].hex;

function Ratio({ fg, bg, floor = 4.5 }: { fg: string; bg: string; floor?: number }) {
  const r = contrast(fg, bg);
  const ok = r >= floor;
  return (
    <span className={ok ? "tabular text-fg" : "tabular text-danger"}>
      {r.toFixed(1)}:1
    </span>
  );
}

function SectionHeading({ id, children, note }: { id: string; children: React.ReactNode; note?: string }) {
  return (
    <div className="mb-6 flex flex-col gap-1">
      <h2 id={id} className="scroll-mt-20 text-2xl font-semibold tracking-tight text-fg">
        {children}
      </h2>
      {note && <p className="max-w-prose text-sm text-fg-muted">{note}</p>}
    </div>
  );
}

const SECTIONS = [
  ["surfaces", "Surfaces"],
  ["colour", "Colour"],
  ["type", "Type"],
  ["primitives", "Primitives"],
  ["studio", "Studio"],
  ["motion", "Motion"],
] as const;

export default function TokensPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 pb-32 pt-12 sm:px-6">
      <Intro />
      <div className="flex flex-col gap-24">
        <Surfaces />
        <Colour />
        <Type />
        <Primitives />
        <Studio />
        <Motion />
      </div>
    </div>
  );
}

/** A plain bordered panel, one surface step above its container. */
function Panel({ level = 1, className, children }: { level?: 1 | 2; className?: string; children: React.ReactNode }) {
  return (
    <div className={`rounded-md border border-line ${level === 1 ? "bg-bg-1" : "bg-bg-2"} ${className ?? ""}`}>
      {children}
    </div>
  );
}

function Intro() {
  return (
    <header className="mb-20 grid gap-8 md:grid-cols-[1fr_auto] md:items-end">
      <div className="flex max-w-2xl flex-col gap-4">
        <h1 className="text-3xl font-semibold tracking-tight text-fg">{BRAND.name} tokens</h1>
        <p className="max-w-prose text-base text-fg-muted">
          Neutral near-black surfaces in four steps, white text, hairline borders and no accent
          colour. The primary action is white on black. Inter everywhere.
        </p>
      </div>
      <nav aria-label="Sections" className="flex flex-wrap gap-1 md:justify-end">
        {SECTIONS.map(([id, label]) => (
          <a
            key={id}
            href={`#${id}`}
            className="rounded-full px-3 py-1.5 text-sm text-fg-muted transition-colors hover:bg-bg-3 hover:text-fg focus-visible:focus-ring"
          >
            {label}
          </a>
        ))}
      </nav>
    </header>
  );
}

function Surfaces() {
  return (
    <section aria-labelledby="surfaces">
      <SectionHeading
        id="surfaces"
        note="Each step sits inside the one below it, the way panels nest in the studio. Ratios are for fg and fg-muted text on that surface; body text needs 4.5:1."
      >
        Surfaces
      </SectionHeading>
      <div className="rounded-lg border border-line bg-bg-0 p-4 sm:p-6">
        <SurfaceRow s={SURFACES[0]} />
        <div className="mt-4 rounded-lg border border-line bg-bg-1 p-4 sm:p-6">
          <SurfaceRow s={SURFACES[1]} />
          <div className="mt-4 rounded-lg border border-line bg-bg-2 p-4 sm:p-6">
            <SurfaceRow s={SURFACES[2]} />
            <div className="mt-4 rounded-lg border border-line bg-bg-3 p-4 sm:p-6">
              <SurfaceRow s={SURFACES[3]} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function SurfaceRow({ s }: { s: (typeof SURFACES)[number] }) {
  return (
    <div className="grid gap-x-6 gap-y-1 sm:grid-cols-[7rem_1fr_auto] sm:items-baseline">
      <div className="flex items-baseline gap-3">
        <span className="text-base font-semibold text-fg">{s.name}</span>
        <span className="text-sm text-fg-muted">{s.hex}</span>
      </div>
      <span className="text-sm text-fg-muted">{s.role}</span>
      <dl className="flex gap-5 text-sm">
        <div className="flex items-baseline gap-2">
          <dt className="text-fg">fg</dt>
          <dd>
            <Ratio fg={TEXT[0].hex} bg={s.hex} />
          </dd>
        </div>
        <div className="flex items-baseline gap-2">
          <dt className="text-fg-muted">fg-muted</dt>
          <dd>
            <Ratio fg={TEXT[1].hex} bg={s.hex} />
          </dd>
        </div>
      </dl>
    </div>
  );
}

function Colour() {
  return (
    <section aria-labelledby="colour">
      <SectionHeading
        id="colour"
        note="No accent hue: the primary action is white. Ratios are against bg-0; primary-fg is measured on primary itself."
      >
        Colour
      </SectionHeading>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[...TEXT, ...COLOURS].map((c) => {
          const onPrimary = c.name === "primary-fg";
          const bg = onPrimary ? COLOURS[0].hex : BG0;
          return (
            <Panel key={c.name} className="overflow-hidden">
              <div
                className="flex h-24 items-end p-4"
                style={{ background: onPrimary ? COLOURS[0].hex : c.hex }}
              >
                {onPrimary && (
                  <span className="rounded-full bg-primary px-4 py-2 text-sm font-medium" style={{ color: c.hex }}>
                    Start a project
                  </span>
                )}
              </div>
              <div className="flex flex-col gap-1 p-4">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-base font-semibold text-fg">{c.name}</span>
                  <span className="text-sm text-fg-muted">{c.hex}</span>
                </div>
                <p className="text-sm text-fg-muted">{c.role}</p>
                <p className="mt-1 text-sm text-fg-muted">
                  {onPrimary ? "on primary " : "on bg-0 "}
                  {c.name === "line" ? (
                    <span className="text-fg-muted">white at 10%</span>
                  ) : (
                    <Ratio fg={c.hex} bg={bg} floor={c.name === "danger" ? 3 : 4.5} />
                  )}
                </p>
              </div>
            </Panel>
          );
        })}
      </div>
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {RADII.map((r) => (
          <div key={r.name} className="flex items-center gap-4">
            <div
              className="size-14 shrink-0 border border-line bg-bg-2"
              style={{ borderRadius: r.px }}
            />
            <div className="flex flex-col">
              <span className="text-fg">
                radius-{r.name} <span className="text-sm text-fg-muted">{r.px}px</span>
              </span>
              <span className="text-sm text-fg-muted">{r.role}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Type() {
  return (
    <section aria-labelledby="type">
      <SectionHeading
        id="type"
        note="Inter for everything. Headings are 600 with tight tracking; UI text is 14px, the composer 16px. Numbers use tabular figures; a monospace face is reserved for code."
      >
        Type
      </SectionHeading>
      <div className="flex flex-col gap-10">
        <div className="flex flex-col gap-6">
          <p className="max-w-4xl text-[clamp(2rem,5vw,3.5rem)] font-semibold leading-[1.1] tracking-tight text-fg">
            {BRAND.tagline}
          </p>
          <p className="max-w-prose text-base text-fg-muted">
            Upload a model, describe the shot in plain words, and watch the scene take shape in
            the viewer. Every change is saved as a version you can go back to.
          </p>
          <p className="tabular text-sm text-fg-muted">
            10 s · 1080p · 30 fps · High · {CREDIT_COSTS.local_final} credits
          </p>
        </div>

        <div className="flex flex-col">
          {TYPE_SCALE.map((t) => (
            <div
              key={t.name}
              className="grid grid-cols-[4rem_1fr] items-baseline gap-4 border-t border-line py-4 last:border-b sm:grid-cols-[4rem_1fr_9rem]"
            >
              <span className="text-sm text-fg-muted">{t.name}</span>
              <span
                className={t.rem >= 1.25 ? "font-semibold tracking-tight text-fg" : "text-fg"}
                style={{ fontSize: `${t.rem}rem`, lineHeight: t.lh }}
              >
                {t.rem >= 1.25 ? "Describe the shot" : "Describe the shot you want, then refine it."}
              </span>
              <span className="col-start-2 text-sm text-fg-muted sm:col-start-3 sm:text-right">
                {t.rem * 16}px / {t.lh}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Primitives() {
  const push = useToastStore((s) => s.push);
  const [chip, setChip] = useState<string>(PRESETS[1].id);
  const [slider, setSlider] = useState(35);
  const [committed, setCommitted] = useState(35);
  const [dialog, setDialog] = useState(false);
  const [name, setName] = useState("");

  const variants = ["primary", "secondary", "ghost", "danger"] as const;
  const hover: Record<(typeof variants)[number], string> = {
    primary: "bg-primary/90",
    secondary: "bg-bg-3",
    ghost: "text-fg bg-bg-3",
    danger: "bg-danger/10",
  };

  return (
    <section aria-labelledby="primitives">
      <SectionHeading id="primitives" note="Every primitive, in every state it can be in.">
        Primitives
      </SectionHeading>
      <div className="flex flex-col gap-12">
        <Block title="Button" note="Columns: default, hover, focused, disabled, loading. Rows: primary, secondary, ghost, danger.">
          <div className="overflow-x-auto">
            <div className="grid min-w-[36rem] grid-cols-5 items-center gap-x-4 gap-y-3">
              {variants.map((v) => (
                <div key={v} className="contents">
                  <Button variant={v}>Render</Button>
                  <Button variant={v} className={hover[v]}>
                    Render
                  </Button>
                  <Button variant={v} className="focus-ring">
                    Render
                  </Button>
                  <Button variant={v} disabled>
                    Render
                  </Button>
                  <Button variant={v} loading>
                    Render
                  </Button>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button variant="primary" size="sm">
              Small
            </Button>
            <Button variant="primary" size="md">
              Medium
            </Button>
            <Button variant="primary" size="lg">
              Large
            </Button>
            <Button
              variant="secondary"
              icon={
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M8 2v9M4.5 7.5 8 11l3.5-3.5M3 13.5h10" />
                </svg>
              }
            >
              With icon
            </Button>
          </div>
        </Block>

        <Block title="Chip" note="Suggested phrasings under a prompt error. A button with aria-pressed; arrow keys are not needed, Tab moves between chips.">
          <div className="flex flex-wrap gap-2">
            {PRESETS.slice(0, 4).map((p) => (
              <Chip key={p.id} selected={chip === p.id} onClick={() => setChip(p.id)}>
                {p.label}
              </Chip>
            ))}
            <Chip disabled>Unavailable</Chip>
            <Chip className="focus-ring">Focused</Chip>
          </div>
        </Block>

        <Block title="Badge">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>No model</Badge>
            <Badge tone="success">Model ready</Badge>
            <Badge tone="warning">Low credits</Badge>
          </div>
        </Block>

        <div className="grid gap-12 lg:grid-cols-2">
          <Block title="Field">
            <div className="flex flex-col gap-5">
              <Field
                label="Project name"
                placeholder="Untitled project"
                value={name}
                onChange={(e) => setName(e.target.value)}
                hint="Shown on the dashboard card."
              />
              <Field label="Project name" defaultValue="Untitled project" className="[&_input]:focus-ring" />
              <Field
                label="Project name"
                defaultValue=""
                error="Give the project a name before saving."
              />
              <Field label="Project name" defaultValue="Locked" disabled />
            </div>
          </Block>

          <Block title="Slider" note="Live value on change; commit fires on release, which is when a scene patch is written.">
            <div className="flex flex-col gap-6">
              <Slider
                label="Lens"
                min={18}
                max={135}
                value={slider}
                onChange={setSlider}
                onCommit={setCommitted}
                format={(v) => `${v} mm`}
              />
              <p className="text-sm text-fg-muted">
                Committed <span className="tabular text-fg">{committed} mm</span>
              </p>
              <Slider label="Fog density" min={0} max={1} step={0.05} value={0.3} onChange={() => {}} format={(v) => v.toFixed(2)} />
              <Slider label="Locked" min={0} max={100} value={60} onChange={() => {}} disabled />
            </div>
          </Block>
        </div>

        <div className="grid gap-12 lg:grid-cols-2">
          <Block title="Dialog" note="Native dialog with showModal, so focus is trapped and Escape closes it.">
            <Button variant="secondary" onClick={() => setDialog(true)}>
              Delete project
            </Button>
            <Dialog
              open={dialog}
              onClose={() => setDialog(false)}
              title="Delete this project?"
              description="Its model, versions and thumbnails are removed from this device. This cannot be undone."
              footer={
                <>
                  <Button variant="ghost" onClick={() => setDialog(false)}>
                    Keep project
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => {
                      setDialog(false);
                      push({ kind: "info", message: "Project deleted" });
                    }}
                  >
                    Delete project
                  </Button>
                </>
              }
            />
          </Block>

          <Block title="Toast" note="Bottom centre pill, dismisses itself after four seconds.">
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => push({ kind: "info", message: "Version saved" })}>
                Info
              </Button>
              <Button variant="secondary" onClick={() => push({ kind: "success", message: "Scene ready" })}>
                Success
              </Button>
              <Button
                variant="secondary"
                onClick={() => push({ kind: "danger", message: "Not enough credits for this render" })}
              >
                Danger
              </Button>
            </div>
          </Block>
        </div>

        <div className="grid gap-12 lg:grid-cols-2">
          <Block title="Skeleton" note="A project card on the dashboard while its thumbnail loads.">
            <Panel className="flex flex-col gap-3 p-5">
              <Skeleton className="aspect-video w-full rounded-md" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
            </Panel>
          </Block>
        </div>
      </div>
    </section>
  );
}

/**
 * The studio's own idioms, built from the real pieces: the composer pill, its second-row
 * chips (`ChipButton`) and the scene-details drawer tabs (`Tabs`).
 */
function Studio() {
  const [tab, setTab] = useState("analysis");
  const [scrubber, setScrubber] = useState(false);

  return (
    <section aria-labelledby="studio">
      <SectionHeading
        id="studio"
        note="Progressive disclosure: the composer is the whole interface until a scene exists; then one row of chips and one drawer."
      >
        Studio
      </SectionHeading>
      <div className="flex flex-col gap-12">
        <Block title="Composer" note="One pill, max 768px wide: + menu, a textarea that grows to six lines, a round send button. The second row appears with the first version; Render is the primary action from then on.">
          <div className="flex w-full max-w-[768px] flex-col rounded-3xl bg-bg-2 px-2.5 py-2 shadow-raise">
            <div className="flex items-end gap-2">
              <button type="button" aria-label="Model options" className="flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-full text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring sm:size-9">
                <svg aria-hidden viewBox="0 0 20 20" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round">
                  <path d="M10 4v12M4 10h12" />
                </svg>
              </button>
              <textarea
                aria-label="Describe your render"
                rows={1}
                defaultValue="Rainy night city street, handheld camera walking toward the car"
                className="my-1.5 min-h-6 w-full min-w-0 flex-1 resize-none bg-transparent px-1 text-base leading-6 text-fg outline-none placeholder:text-fg-muted/80"
              />
              <button type="button" aria-label="Apply edit · 1 credit" className="flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-full bg-primary text-primary-fg transition-colors duration-fast ease-standard hover:bg-primary/90 focus-visible:focus-ring sm:size-9">
                <svg aria-hidden viewBox="0 0 20 20" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10 16V4m0 0-5 5m5-5 5 5" />
                </svg>
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-1 px-1 pt-1.5">
              <ChipButton aria-label="Output settings: 10 s · 1080p · 30 fps · High" className="tabular">
                <svg aria-hidden viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M2 4h12M2 8h8M2 12h5" />
                </svg>
                10 s · 1080p · 30 fps · High
              </ChipButton>
              <ChipButton>Start over · {CREDIT_COSTS.scene_generation} credits</ChipButton>
              <ChipButton>Controls</ChipButton>
              <ChipButton selected={scrubber} aria-pressed={scrubber} onClick={() => setScrubber((v) => !v)}>Preview path</ChipButton>
              <button type="button" className="ml-auto inline-flex h-8 shrink-0 cursor-pointer select-none items-center whitespace-nowrap rounded-full bg-primary px-3.5 text-xs font-medium text-primary-fg transition-colors duration-fast ease-standard hover:bg-primary/90 focus-visible:focus-ring">
                Render · {CREDIT_COSTS.local_final} credits
              </button>
            </div>
          </div>
        </Block>

        <Block title="Chip row" note="ChipButton: text-xs, 32px tall, muted until hovered; `selected` for toggles such as Preview path; disabled at 40% while the director works.">
          <div className="flex flex-wrap items-center gap-1 rounded-full bg-bg-2 p-1">
            <ChipButton>Default</ChipButton>
            <ChipButton className="bg-bg-3 text-fg">Hover</ChipButton>
            <ChipButton selected>Selected</ChipButton>
            <ChipButton className="focus-ring">Focused</ChipButton>
            <ChipButton disabled>Disabled</ChipButton>
          </div>
        </Block>

        <Block title="Drawer tabs" note="The scene-details drawer: Analysis alone until a scene exists, then Controls and Render. Arrow keys move between tabs; the selected pill follows with the snappy spring.">
          <Panel className="flex w-full max-w-[360px] flex-col gap-4 p-3">
            <Tabs
              id="demo-tabs"
              label="Scene details"
              items={[
                { id: "analysis", label: "Analysis" },
                { id: "controls", label: "Controls" },
                { id: "render", label: "Render" },
              ]}
              value={tab}
              onChange={setTab}
            />
            <TabPanel tabsId="demo-tabs" id={tab} active className="px-1 pb-1 text-sm text-fg-muted">
              {tab === "analysis" && "What the model looks like: category, size, parts and what it can do."}
              {tab === "controls" && "Sliders for lens, light and environment. Each release saves a version."}
              {tab === "render" && "Output summary, local or cloud target, and the render itself."}
            </TabPanel>
          </Panel>
        </Block>
      </div>
    </section>
  );
}

function Block({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-0.5">
        <h3 className="text-lg font-medium text-fg">{title}</h3>
        {note && <p className="max-w-prose text-sm text-fg-muted">{note}</p>}
      </div>
      {children}
    </div>
  );
}

/**
 * This page is a client component, so Next still renders it on the server. Nothing here may
 * branch on `useReducedMotion()`: the hook reads `null` on the server and the real preference
 * on the very first client render, so both the note copy and the `style` motion bakes from
 * `initial="hidden"` would differ between the two and break hydration. One set of variants
 * for everyone; `<MotionConfig reducedMotion="user">` in app/layout.tsx snaps the transform
 * keys to their target. That snap is not enough on the way out — `fadeRise.exit` would land
 * its 12px while the element is still opaque — so `data-motion-demo` freezes the demos'
 * transforms from app/globals.css.
 */
function Motion() {
  const [key, setKey] = useState({ fade: 0, list: 0 });
  const replay = (k: keyof typeof key) => setKey((s) => ({ ...s, [k]: s[k] + 1 }));

  const ease = (e: readonly number[]) => `cubic-bezier(${e.join(", ")})`;

  return (
    <section aria-labelledby="motion">
      <SectionHeading
        id="motion"
        note="Motion marks a change of state. Nothing on this page moves until you ask it to. Under prefers-reduced-motion the demos below keep the fade and drop the travel."
      >
        Motion
      </SectionHeading>

      <div className="mb-8 grid gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
        <dl className="flex flex-col gap-1">
          {(Object.keys(DUR) as Array<keyof typeof DUR>).map((k) => (
            <div key={k} className="flex justify-between gap-4 border-b border-line py-1.5">
              <dt className="text-fg-muted">{k}</dt>
              <dd className="tabular text-fg">{DUR[k] * 1000} ms</dd>
            </div>
          ))}
        </dl>
        <dl className="flex flex-col gap-1">
          {(Object.keys(EASE) as Array<keyof typeof EASE>).map((k) => (
            <div key={k} className="flex justify-between gap-4 border-b border-line py-1.5">
              <dt className="text-fg-muted">{k}</dt>
              <dd className="tabular text-fg">{ease(EASE[k])}</dd>
            </div>
          ))}
        </dl>
        <dl className="flex flex-col gap-1">
          {(Object.keys(SPRING) as Array<keyof typeof SPRING>).map((k) => (
            <div key={k} className="flex justify-between gap-4 border-b border-line py-1.5">
              <dt className="text-fg-muted">{k}</dt>
              <dd className="tabular text-fg">
                {SPRING[k].stiffness} / {SPRING[k].damping}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Demo title="fadeRise" onReplay={() => replay("fade")}>
          <AnimatePresence mode="wait">
            <motion.div
              key={key.fade}
              data-motion-demo
              variants={fadeRise}
              initial="hidden"
              animate="visible"
              className="rounded-full bg-bg-2 px-4 py-2.5 text-sm text-fg shadow-raise"
            >
              Version 3 saved
            </motion.div>
          </AnimatePresence>
        </Demo>

        <Demo title="staggerList" onReplay={() => replay("list")}>
          <AnimatePresence mode="wait">
            <motion.ul
              key={key.list}
              variants={staggerList}
              initial="hidden"
              animate="visible"
              className="flex flex-col gap-2"
            >
              {["Reading geometry", "Identifying parts", "Choosing lens", "Placing light"].map((s) => (
                <motion.li
                  key={s}
                  data-motion-demo
                  variants={fadeRise}
                  className="rounded-sm bg-bg-2 px-3 py-1.5 text-sm text-fg"
                >
                  {s}
                </motion.li>
              ))}
            </motion.ul>
          </AnimatePresence>
        </Demo>
      </div>
    </section>
  );
}

function Demo({ title, onReplay, children }: { title: string; onReplay: () => void; children: React.ReactNode }) {
  return (
    <Panel className="flex flex-col">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="text-sm text-fg">{title}</span>
        <Button size="sm" variant="ghost" onClick={onReplay}>
          Replay
        </Button>
      </div>
      <div className="flex h-44 flex-col justify-center p-4">{children}</div>
    </Panel>
  );
}
