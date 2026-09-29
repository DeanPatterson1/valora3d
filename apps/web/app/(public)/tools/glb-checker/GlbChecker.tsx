"use client";

import { useCallback, useRef, useState } from "react";
import { cx } from "@/components/ui/cx";
import { formatBytes } from "@/lib/tools/formatBytes";
import type { CheckLevel } from "@/lib/tools/glbCheck";
import type { GlbCheckResult as Result } from "@/lib/tools/glbCheckRun";

/** The one sample the page may fetch: a model shipped with the site, from this origin. */
export const SAMPLE_URL = "/samples/toycar.glb";

type State = { kind: "idle" } | { kind: "working"; fileName: string } | { kind: "done"; result: Result } | { kind: "failed"; message: string };

const LEVEL_LABEL: Record<CheckLevel, string> = { error: "Fix", warning: "Improve", info: "Note", ok: "OK" };
const LEVEL_CLASS: Record<CheckLevel, string> = {
  error: "bg-bg-3 text-danger",
  warning: "bg-bg-3 text-fg",
  info: "bg-bg-3 text-fg-muted",
  ok: "bg-bg-3 text-success",
};

export function GlbChecker() {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const working = state.kind === "working";

  const run = useCallback(async (file: File) => {
    setState({ kind: "working", fileName: file.name });
    try {
      // Loaded on first use, with three.js behind it, so the page's initial JavaScript stays small.
      const { runGlbCheck } = await import("@/lib/tools/glbCheckRun");
      setState({ kind: "done", result: await runGlbCheck(file) });
    } catch {
      setState({ kind: "failed", message: "Something went wrong while reading the file. Try exporting it again." });
    }
  }, []);

  const trySample = useCallback(async () => {
    setState({ kind: "working", fileName: "toycar.glb" });
    try {
      const res = await fetch(SAMPLE_URL);
      if (!res.ok) throw new Error(String(res.status));
      await run(new File([await res.blob()], "toycar.glb", { type: "model/gltf-binary" }));
    } catch {
      setState({ kind: "failed", message: "The sample couldn't be loaded. Check your connection and try again." });
    }
  }, [run]);

  return (
    <div className="mt-10">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file && !working) void run(file);
        }}
        className={cx(
          "flex flex-col items-center gap-4 rounded-lg border border-dashed px-6 py-12 text-center transition-colors",
          dragging ? "border-fg bg-bg-2" : "border-line bg-bg-1",
        )}
      >
        <p className="text-base font-medium">Drop a .glb file here</p>
        <p className="max-w-md text-sm text-fg-muted">The check runs entirely in your browser. Your file is not uploaded or stored.</p>
        <div className="flex flex-wrap justify-center gap-3">
          <button
            type="button"
            disabled={working}
            onClick={() => input.current?.click()}
            className="inline-flex h-10 cursor-pointer items-center rounded-full bg-primary px-5 text-sm font-medium text-primary-fg transition-colors duration-fast ease-standard hover:bg-primary/90 focus-visible:focus-ring disabled:cursor-default disabled:opacity-60"
          >
            Choose a file
          </button>
          <button
            type="button"
            disabled={working}
            onClick={() => void trySample()}
            className="inline-flex h-10 cursor-pointer items-center rounded-full border border-line px-5 text-sm text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring disabled:cursor-default disabled:opacity-60"
          >
            Try with a sample
          </button>
        </div>
        <input
          ref={input}
          type="file"
          accept=".glb,.gltf,model/gltf-binary,model/gltf+json"
          className="sr-only"
          tabIndex={-1}
          aria-label="Choose a .glb file to check"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void run(file);
          }}
        />
      </div>

      <div aria-live="polite" className="mt-8">
        {state.kind === "working" && <p className="text-sm text-fg-muted">Checking {state.fileName}…</p>}
        {state.kind === "failed" && <p className="text-sm text-danger">{state.message}</p>}
        {state.kind === "done" && <Report result={state.result} />}
      </div>
    </div>
  );
}

function Report({ result }: { result: Result }) {
  const { verdict, inspection, scene } = result;
  const textures = inspection?.textures ?? [];
  const stats: [string, string][] = [
    ["File size", formatBytes(result.sizeBytes)],
    ["Triangles", scene ? scene.triangleCount.toLocaleString("en-US") : "—"],
    ["Textures", inspection ? `${textures.length} (${textures.filter((t) => t.embedded).length} embedded)` : "—"],
    ["Size", scene ? scene.dimensionsMeters.map((d) => `${+d.toFixed(2)}`).join(" × ") + " m" : "—"],
  ];
  return (
    <section aria-labelledby="verdict-heading" className="rounded-lg border border-line bg-bg-1 p-5 sm:p-6">
      <p className="text-sm text-fg-muted">{result.fileName}</p>
      <h2 id="verdict-heading" className="mt-1 text-xl font-semibold tracking-tight">
        Ready for Valora3D? {verdict.status === "ready" ? "Yes." : verdict.status === "fixes" ? "Almost." : "Not yet."}
      </h2>
      <p className="mt-2 text-sm text-fg-muted">{verdict.headline}</p>

      <dl className="mt-5 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
        {stats.map(([label, value]) => (
          <div key={label}><dt className="text-fg-muted">{label}</dt><dd className="mt-1 font-medium">{value}</dd></div>
        ))}
      </dl>

      <ul className="mt-6 divide-y divide-line border-t border-line">
        {verdict.checks.map((c) => (
          <li key={c.id} className="flex flex-col gap-1.5 py-4 sm:flex-row sm:gap-4">
            <span className={cx("inline-flex h-6 w-fit shrink-0 items-center rounded-full px-2.5 text-xs font-medium", LEVEL_CLASS[c.level])}>{LEVEL_LABEL[c.level]}</span>
            <div className="min-w-0">
              <p className="font-medium">{c.title}</p>
              <p className="mt-1 text-sm leading-relaxed text-fg-muted">{c.detail}</p>
              {c.fix && <p className="mt-1 break-words text-sm leading-relaxed">{c.fix}</p>}
            </div>
          </li>
        ))}
      </ul>

      {textures.length > 0 && (
        <details className="mt-2 border-t border-line pt-4">
          <summary className="cursor-pointer rounded-sm text-sm font-medium focus-visible:focus-ring">Textures ({textures.length})</summary>
          <ul className="mt-3 flex flex-col gap-2 text-sm text-fg-muted">
            {textures.map((t, i) => (
              <li key={`${i}-${t.name}`} className="flex flex-wrap justify-between gap-x-4">
                <span className="min-w-0 truncate text-fg">{t.name}</span>
                <span>
                  {t.width && t.height ? `${t.width} × ${t.height}` : "size unknown"}
                  {t.bytes !== null ? ` · ${formatBytes(t.bytes)}` : ""}
                  {t.mimeType ? ` · ${t.mimeType.replace("image/", "").toUpperCase()}` : ""}
                  {t.embedded ? "" : " · external"}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
