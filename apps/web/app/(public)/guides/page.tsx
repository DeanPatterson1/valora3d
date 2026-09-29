import Link from "next/link";
import { SignupCta } from "@/components/public/SignupCta";
import { GUIDES } from "@/lib/guides";
import { publicMetadata } from "@/lib/site";

export const metadata = publicMetadata(
  "Export a .glb from your 3D app",
  "Step-by-step guides to exporting a single self-contained .glb from Blender, SketchUp, 3ds Max, Cinema 4D, Rhino, Unreal Engine and Unity, based on each vendor's own documentation.",
  "/guides",
);

export default function GuidesPage() {
  return (
    <div className="mx-auto max-w-[920px] px-5 py-12 sm:px-8 sm:py-20">
      <p className="mb-3 text-sm text-fg-muted">Export guides</p>
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Get a .glb out of your 3D app.</h1>
      <p className="mt-5 max-w-2xl text-base leading-relaxed text-fg-muted">
        Valora3D renders from one self-contained .glb file. These guides cover the export settings that matter in each app, following the vendor&apos;s own documentation, which is linked on every page.
      </p>
      <ul className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {GUIDES.map((g) => (
          <li key={g.slug}>
            <Link href={`/guides/${g.slug}`} className="flex h-full flex-col rounded-lg border border-line bg-bg-1 p-5 transition-colors hover:bg-bg-2 focus-visible:focus-ring">
              <span className="font-medium">{g.app}</span>
              <span className="mt-2 text-sm leading-relaxed text-fg-muted">{g.summary}</span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-8 max-w-2xl text-sm leading-relaxed text-fg-muted">
        Using Maya, Fusion or another app without a built-in glTF exporter? Export a format Blender can import, then follow the{" "}
        <Link href="/guides/export-glb-from-blender" className="rounded-sm text-fg underline underline-offset-4 focus-visible:focus-ring">Blender guide</Link>. Already have a file?{" "}
        <Link href="/tools/glb-checker" className="rounded-sm text-fg underline underline-offset-4 focus-visible:focus-ring">Check it in your browser</Link>.
      </p>
      <SignupCta
        title="Have your .glb ready?"
        lead="Upload it, describe the shot in a sentence and render a preview on cloud GPUs."
        secondary={{ href: "/tools/glb-checker", label: "Check a .glb file" }}
      />
    </div>
  );
}
