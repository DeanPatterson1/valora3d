import Link from "next/link";
import { SignupCta } from "@/components/public/SignupCta";
import { JsonLd } from "@/components/seo/JsonLd";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { publicMetadata, SITE_URL } from "@/lib/site";
import { GlbChecker } from "./GlbChecker";

const maxMB = Math.round(MAX_UPLOAD_BYTES / 1024 / 1024);
const DESCRIPTION = "Free .glb checker that runs in your browser: see file size, triangle count, textures, scale and orientation, with concrete fixes. Nothing is uploaded.";

export const metadata = publicMetadata("Free GLB file checker", DESCRIPTION, "/tools/glb-checker");

const glbCheckerSchema = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "GLB checker",
  url: `${SITE_URL}/tools/glb-checker`,
  description: DESCRIPTION,
  applicationCategory: "DeveloperApplication",
  operatingSystem: "Web browser",
  isAccessibleForFree: true,
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
  publisher: { "@id": `${SITE_URL}/#organization` },
};

export default function GlbCheckerPage() {
  return (
    <div className="mx-auto max-w-[860px] px-5 py-12 sm:px-8 sm:py-20">
      <p className="mb-3 text-sm text-fg-muted">Free tool</p>
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Check a .glb file</h1>
      <p className="mt-5 max-w-2xl text-base leading-relaxed text-fg-muted">
        Find out whether a 3D model is ready to render before you upload it anywhere. The check runs on your own device: the file never leaves your browser, and you don&apos;t need an account.
      </p>

      <GlbChecker />

      <section aria-labelledby="what-heading" className="mt-14 border-t border-line pt-10">
        <h2 id="what-heading" className="text-2xl font-semibold tracking-tight">What it checks</h2>
        <ul className="mt-5 list-disc space-y-3 pl-6 text-base leading-7 text-fg-muted">
          <li className="pl-1"><span className="text-fg">Format and size.</span> A valid glTF 2.0 binary (.glb), within Valora3D&apos;s {maxMB} MB upload limit. A .gltf that depends on separate .bin or image files is flagged, with how to pack it into one .glb.</li>
          <li className="pl-1"><span className="text-fg">Textures.</span> How many images the file carries, whether they are embedded, and their pixel size. Very large textures make the file heavy without adding visible detail to a 1080p video.</li>
          <li className="pl-1"><span className="text-fg">Geometry.</span> Triangle, mesh and material counts, and whether the file uses mesh or texture compression that a standard viewer can&apos;t decode without extra tools.</li>
          <li className="pl-1"><span className="text-fg">Scale and orientation.</span> The model&apos;s size in meters and the units it was probably exported in. For car models, whether it stands upright (glTF expects Y to point up).</li>
        </ul>
        <p className="mt-5 text-sm leading-relaxed text-fg-muted">
          Checks use the same model analysis as the Valora3D studio, so a pass here means the studio will read the file the same way. It can&apos;t judge how a model looks; open it in your 3D app&apos;s glTF preview for that.
        </p>
      </section>

      <section aria-labelledby="fix-heading" className="mt-12">
        <h2 id="fix-heading" className="text-2xl font-semibold tracking-tight">Fixing what it finds</h2>
        <p className="mt-3 text-base leading-7 text-fg-muted">
          Most problems are fixed at export time: choose the binary glTF format, keep textures embedded, use real-world units and leave mesh compression off. The export guides walk through those settings app by app. For files you can&apos;t re-export, the free glTF Transform command-line tool can resize textures and simplify meshes.
        </p>
        <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-3 text-sm">
          <li><Link href="/guides" className="rounded-sm underline underline-offset-4 focus-visible:focus-ring">Export guides by app</Link></li>
          <li><Link href="/help/preparing-your-model" className="rounded-sm underline underline-offset-4 focus-visible:focus-ring">Preparing your model</Link></li>
          <li><a href="https://gltf-transform.dev/cli" className="rounded-sm underline underline-offset-4 focus-visible:focus-ring" rel="noopener noreferrer">glTF Transform CLI</a></li>
        </ul>
      </section>

      <SignupCta
        title="Turn the model into a video"
        lead="Upload the .glb, describe the shot in a sentence and render a preview on cloud GPUs. Start free, no card needed."
        secondary={{ href: "/examples", label: "See examples" }}
      />
      <JsonLd data={glbCheckerSchema} />
    </div>
  );
}
