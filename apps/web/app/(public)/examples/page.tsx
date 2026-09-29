import Image from "next/image";
import Link from "next/link";
import { SignupCta } from "@/components/public/SignupCta";
import { JsonLd } from "@/components/seo/JsonLd";
import { EXAMPLES } from "@/lib/examples";
import { publicMetadata, SITE_URL } from "@/lib/site";

export const metadata = publicMetadata(
  "3D model to video examples",
  "Example shots rendered from 3D models: studio product orbits and rainy car walk-ins, each with the prompt, the world and notes on why the camera and light work.",
  "/examples",
);

export default function ExamplesPage() {
  const list = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    itemListElement: EXAMPLES.map((e, i) => ({ "@type": "ListItem", position: i + 1, url: `${SITE_URL}/examples/${e.slug}`, name: e.title })),
  };
  return (
    <div className="mx-auto max-w-[1100px] px-5 py-12 sm:px-8 sm:py-20">
      <p className="mb-3 text-sm text-fg-muted">Examples</p>
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Shots, and why they work.</h1>
      <p className="mt-5 max-w-2xl text-base leading-relaxed text-fg-muted">
        Each example shows a short clip, the prompt that set it up, the world it was rendered in and notes on what to change to use the idea with your own model.
      </p>
      <ul className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {EXAMPLES.map((e) => (
          <li key={e.slug}>
            <Link href={`/examples/${e.slug}`} className="group flex h-full flex-col overflow-hidden rounded-lg border border-line bg-bg-1 transition-colors hover:bg-bg-2 focus-visible:focus-ring">
              <div className="relative aspect-[16/10] w-full bg-bg-2">
                <Image src={e.media.poster} alt="" fill sizes="(min-width: 1024px) 340px, (min-width: 640px) 50vw, 100vw" className="object-cover" />
              </div>
              <div className="flex flex-1 flex-col gap-2 p-5">
                <span className="text-xs text-fg-muted">{e.worldLabel} · {e.item.model === "car" ? "Car" : "Product"}</span>
                <span className="font-medium leading-snug">{e.title}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-8 max-w-2xl text-xs leading-relaxed text-fg-muted">
        These clips were rendered with Blender Cycles through the offline pipeline behind Valora3D, on a workstation, to show what it produces. They were not made through the web app.
      </p>
      <SignupCta
        title="Try it with your own model"
        lead="Upload a .glb, describe the shot in a sentence and render a preview. Not sure your file is ready? Check it first, in your browser."
        secondary={{ href: "/tools/glb-checker", label: "Check a .glb file" }}
      />
      <JsonLd data={list} />
    </div>
  );
}
