"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import type * as THREE from "three";
import { Button, Chip, Slider } from "@/components/ui";
import type { ScenePlan } from "@/lib/schema";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { analyzeStats } from "@/lib/scene/analyze";
import { computeSceneStats } from "@/components/viewer/sceneStats";
import { loadModel } from "@/components/viewer/loadModel";
import { placeholderCar } from "@/components/viewer/placeholderCar";
import { Viewer } from "@/components/viewer/Viewer";
import { Scrubber } from "@/components/viewer/Scrubber";
import { downscaleThumbnail } from "@/components/viewer/thumbnail";

type Env = ScenePlan["scene"]["environment"];
type Lighting = ScenePlan["lighting"]["style"];
type Action = ScenePlan["shots"][number]["action"];
type Source = "sample" | "placeholder";

const ENVS: Env[] = ["studio_black", "studio_white", "outdoor_road", "urban_night"];
const LIGHTING: Lighting[] = ["soft_studio", "dramatic_three_point", "night_city", "sunset", "overcast"];
const ACTIONS: Action[] = ["slow_orbit", "hero_push_in", "low_tracking", "handheld_walk_toward"];
const TIMES: ScenePlan["scene"]["time"][] = ["day", "dusk", "night"];

type Loaded = { root: THREE.Object3D; scaleFactor: number; label: string };

type SearchParams = Record<string, string | string[] | undefined>;

export default function ViewerSandbox({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = use(searchParams);
  const param = (name: string) => (typeof params[name] === "string" ? (params[name] as string) : null);
  const [source, setSource] = useState<Source>(() => (param("source") === "placeholder" ? "placeholder" : "sample"));
  const [result, setResult] = useState<{ source: Source; loaded: Loaded; error: string | null } | null>(null);
  const loaded = result?.source === source ? result.loaded : null;
  const loadError = result?.source === source ? result.error : null;
  const [plan, setPlan] = useState<ScenePlan>(() => {
    const p = defaultPlan("car");
    const env = param("env") as Env | null;
    if (env && ENVS.includes(env)) p.scene.environment = env;
    return p;
  });
  const [previewSeconds, setPreviewSeconds] = useState<number | null>(null);
  const [captureKey, setCaptureKey] = useState(0);
  const [thumb, setThumb] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let error: string | null = null;
      if (source === "sample") {
        const r = await loadModel("/samples/car.glb", "glb");
        if (cancelled) return;
        if (r.ok) {
          const stats = computeSceneStats(r.value.root);
          const analysis = analyzeStats(stats);
          const dims = stats.extents.map((e) => (e * analysis.scaleFactor).toFixed(2)).join(" × ");
          const label = `car.glb · ${stats.triangleCount.toLocaleString()} tris · ×${analysis.scaleFactor} · ${dims} m`;
          setResult({ source, loaded: { root: r.value.root, scaleFactor: analysis.scaleFactor, label }, error: null });
          return;
        }
        error = `${r.error.message} Showing the procedural placeholder instead.`;
      }
      const car = placeholderCar();
      const stats = computeSceneStats(car);
      if (!cancelled) {
        const dims = stats.extents.map((e) => e.toFixed(2)).join(" × ");
        setResult({ source, loaded: { root: car, scaleFactor: 1, label: `placeholder · ${stats.triangleCount.toLocaleString()} tris · ${dims} m` }, error });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [source]);

  const onThumbnail = useCallback((blob: Blob) => {
    downscaleThumbnail(blob)
      .then((small) => setThumb((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(small);
      }))
      .catch(() => {});
  }, []);

  const patch = (fn: (p: ScenePlan) => void) =>
    setPlan((p) => {
      const next = structuredClone(p);
      fn(next);
      return next;
    });

  const twoShots = plan.shots.length === 2;
  const shotSummary = useMemo(() => plan.shots.map((s) => `${s.action} ${s.start}–${s.end}s`).join(" → "), [plan.shots]);

  return (
    <div className="flex min-h-0 flex-1 flex-col lg:h-[calc(100dvh-3.5rem-1px)] lg:flex-none lg:flex-row">
      <section className="flex min-h-[60vh] min-w-0 flex-1 flex-col lg:min-h-0">
        <div className="relative min-h-0 flex-1">
          <Viewer
            root={loaded?.root ?? null}
            plan={plan}
            scaleFactor={loaded?.scaleFactor ?? 1}
            previewSeconds={previewSeconds}
            captureKey={captureKey}
            onThumbnail={onThumbnail}
          />
          <div className="pointer-events-none absolute left-3 top-3 flex flex-col gap-1 text-xs text-fg-muted">
            <span className="rounded-sm bg-bg-0/70 px-2 py-1 font-mono">{loaded ? loaded.label : "loading model…"}</span>
            {loadError && <span className="rounded-sm bg-bg-0/70 px-2 py-1 text-danger">{loadError}</span>}
          </div>
        </div>
        <Scrubber plan={plan} seconds={previewSeconds} onChange={setPreviewSeconds} />
      </section>

      <aside className="flex w-full shrink-0 flex-col gap-5 overflow-y-auto border-t border-line bg-bg-1 p-4 lg:w-[340px] lg:border-l lg:border-t-0">
        <header>
          <h1 className="font-display text-lg font-semibold text-fg">Viewer sandbox</h1>
          <p className="text-xs text-fg-muted">Task 20 manual check. Not linked from the app.</p>
        </header>

        <Group title="Model">
          <Chips value={source} options={["sample", "placeholder"] as const} onChange={setSource} />
        </Group>

        <Group title="Environment">
          <Chips value={plan.scene.environment} options={ENVS} onChange={(v) => patch((p) => (p.scene.environment = v))} />
          <Chips value={plan.scene.time} options={TIMES} onChange={(v) => patch((p) => (p.scene.time = v))} />
        </Group>

        <Group title="Lighting">
          <Chips value={plan.lighting.style} options={LIGHTING} onChange={(v) => patch((p) => (p.lighting.style = v))} />
          <div className="flex gap-2">
            <Chip selected={plan.lighting.rim} onClick={() => patch((p) => (p.lighting.rim = !p.lighting.rim))}>
              rim
            </Chip>
            <Chip selected={plan.lighting.practicals} onClick={() => patch((p) => (p.lighting.practicals = !p.lighting.practicals))}>
              practicals
            </Chip>
          </div>
          <Slider label="Exposure" min={-3} max={3} step={0.1} value={plan.lighting.exposure} format={(v) => v.toFixed(1)} onChange={(v) => patch((p) => (p.lighting.exposure = v))} />
        </Group>

        <Group title="Effects">
          <Slider label="Rain" min={0} max={1} step={0.05} value={plan.effects.rain} format={(v) => v.toFixed(2)} onChange={(v) => patch((p) => (p.effects.rain = v))} />
          <Slider label="Wet ground" min={0} max={1} step={0.05} value={plan.effects.wetGround} format={(v) => v.toFixed(2)} onChange={(v) => patch((p) => (p.effects.wetGround = v))} />
          <Slider label="Fog" min={0} max={0.1} step={0.005} value={plan.scene.fogDensity} format={(v) => v.toFixed(3)} onChange={(v) => patch((p) => (p.scene.fogDensity = v))} />
        </Group>

        <Group title="Camera">
          <Chips value={plan.shots[0].action} options={ACTIONS} onChange={(v) => patch((p) => (p.shots[0].action = v))} />
          <div className="flex gap-2">
            <Chip
              selected={twoShots}
              onClick={() =>
                patch((p) => {
                  const d = p.output.durationS;
                  p.shots = twoShots
                    ? [{ ...p.shots[0], start: 0, end: d }]
                    : [
                        { ...p.shots[0], start: 0, end: d * 0.4 },
                        { id: "shot-2", start: d * 0.4, end: d, action: "hero_push_in", distanceMultiplier: 0.9 },
                      ];
                })
              }
            >
              two shots
            </Chip>
            <Chip
              selected={plan.camera.style === "handheld"}
              onClick={() =>
                patch((p) => {
                  const on = p.camera.style !== "handheld";
                  p.camera.style = on ? "handheld" : "smooth";
                  p.camera.motionStrength = on ? 0.6 : 0;
                })
              }
            >
              handheld
            </Chip>
          </div>
          <Slider label="Lens" min={18} max={135} step={1} value={plan.camera.lensMm} format={(v) => `${v}mm`} onChange={(v) => patch((p) => (p.camera.lensMm = v))} />
          <Slider label="Height" min={0.2} max={3} step={0.05} value={plan.camera.heightM} format={(v) => `${v.toFixed(2)}m`} onChange={(v) => patch((p) => (p.camera.heightM = v))} />
          <p className="font-mono text-xs text-fg-muted">{shotSummary}</p>
        </Group>

        <Group title="Thumbnail">
          <div className="flex items-center gap-3">
            <Button size="sm" onClick={() => setCaptureKey((k) => k + 1)}>
              Capture
            </Button>
            <span className="text-xs text-fg-muted">auto-captures after the model settles</span>
          </div>
          {thumb && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={thumb} alt="Latest thumbnail capture" className="w-full rounded-md border border-line" />
          )}
        </Group>
      </aside>
    </div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-xs font-medium uppercase tracking-wide text-fg-muted">{title}</h2>
      {children}
    </div>
  );
}

function Chips<T extends string>({ value, options, onChange }: { value: T; options: readonly T[]; onChange: (v: T) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <Chip key={o} selected={o === value} onClick={() => onChange(o)}>
          {o.replaceAll("_", " ")}
        </Chip>
      ))}
    </div>
  );
}
