"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { cx } from "@/components/ui";
import { Container, Reveal, SectionHead } from "./Reveal";

export type GalleryItem = {
  file: string;
  caption: string;
  prompt: string;
  model: "car" | "product";
  /** Large stills span two columns on wide screens. */
  size: "wide" | "large";
  width: number;
  height: number;
};

/** Stills captured in the built-in viewer, captioned with the prompt that produced each one. */
export function Gallery({ items, base = "/landing/gallery/" }: { items: GalleryItem[]; base?: string }) {
  const [open, setOpen] = useState<GalleryItem | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  return (
    <section id="gallery" aria-labelledby="gallery-title" className="scroll-mt-24 py-20 md:py-28">
      <Container>
        <Reveal>
          <SectionHead id="gallery-title" title="What it renders" lead="Captured in the built-in viewer. Each caption is the prompt that set up the shot." />
        </Reveal>
        <Reveal className="mt-12 grid grid-flow-dense grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <figure key={item.file} className={cx(item.size === "large" && "sm:col-span-2")}>
              <button
                type="button"
                onClick={() => setOpen(item)}
                aria-label={`Open: ${item.caption}`}
                className="group relative block aspect-[16/10] w-full cursor-zoom-in overflow-hidden rounded-[14px] border border-white/10 bg-bg-1 focus-visible:focus-ring"
              >
                <Image
                  src={`${base}${item.file}`}
                  alt={item.caption}
                  fill
                  sizes={item.size === "large" ? "(min-width: 1024px) 780px, 100vw" : "(min-width: 1024px) 380px, (min-width: 640px) 50vw, 100vw"}
                  className="object-cover transition-transform duration-[600ms] ease-standard group-hover:scale-[1.03] motion-reduce:transition-none motion-reduce:group-hover:scale-100"
                />
              </button>
              <figcaption className="mt-2.5 px-1 text-[13px] leading-snug text-fg-muted">
                <span className="text-fg/50">{item.model === "car" ? "Car" : "Product"} · </span>
                {item.caption}
              </figcaption>
            </figure>
          ))}
        </Reveal>
      </Container>

      <dialog
        ref={dialogRef}
        onClose={() => setOpen(null)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setOpen(null);
        }}
        aria-label={open ? open.caption : "Image"}
        className="m-auto w-[min(96vw,1200px)] rounded-[18px] border border-white/10 bg-bg-0 p-0 text-fg backdrop:bg-black/80 backdrop:backdrop-blur-sm"
      >
        {open && (
          <figure className="flex flex-col">
            <div className="relative aspect-[16/10] w-full overflow-hidden rounded-t-[18px] bg-bg-1">
              <Image src={`${base}${open.file}`} alt={open.caption} fill sizes="96vw" className="object-cover" priority />
            </div>
            <figcaption className="flex items-center justify-between gap-4 px-5 py-4 text-sm text-fg-muted">
              <span>{open.prompt}</span>
              <button
                type="button"
                onClick={() => setOpen(null)}
                className="inline-flex h-8 shrink-0 cursor-pointer items-center rounded-full border border-line px-3 text-xs text-fg hover:bg-bg-3 focus-visible:focus-ring"
              >
                Close
              </button>
            </figcaption>
          </figure>
        )}
      </dialog>
    </section>
  );
}
