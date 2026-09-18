"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type * as THREE from "three";
import { motion, useReducedMotion } from "motion/react";
import { BRAND } from "@/lib/brand";
import { fadeRise, reduced, staggerList } from "@/lib/motion/variants";
import { analyzeStats } from "@/lib/scene/analyze";
import { Chip } from "@/components/ui";
import { loadModel } from "@/components/viewer/loadModel";
import { computeSceneStats } from "@/components/viewer/sceneStats";
import { Viewer } from "@/components/viewer/Viewer";
import { HERO_CHIPS, heroPlan } from "./chips";

const SAMPLE = "/samples/car.glb";

type Loaded = { root: THREE.Object3D; scaleFactor: number };

/**
 * First screen (spec 8, revised): headline, one line, the page's only canvas, three
 * example chips that re-plan the scene through the real director, one primary action.
 */
export function Hero() {
  const rm = useReducedMotion() ?? false;
  const list = rm ? reduced(staggerList) : staggerList;
  const item = rm ? reduced(fadeRise) : fadeRise;

  const [chipId, setChipId] = useState(HERO_CHIPS[0].id);
  const chip = HERO_CHIPS.find((c) => c.id === chipId) ?? HERO_CHIPS[0];
  const plan = useMemo(() => heroPlan(chip), [chip]);

  const [loaded, setLoaded] = useState<Loaded | null>(null);
  useEffect(() => {
    let cancelled = false;
    loadModel(SAMPLE, "glb").then((r) => {
      if (cancelled || !r.ok) return;
      const analysis = analyzeStats(computeSceneStats(r.value.root));
      setLoaded({ root: r.value.root, scaleFactor: analysis.scaleFactor });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <motion.section
      aria-labelledby="hero-title"
      variants={list}
      initial="hidden"
      animate="visible"
      className="flex w-full flex-col items-center gap-6 px-4 pt-14 text-center sm:px-6 md:pt-16"
    >
      <motion.div variants={item} className="flex max-w-[640px] flex-col gap-3">
        <h1 id="hero-title" className="text-3xl font-semibold tracking-tight text-fg md:text-4xl">
          {BRAND.tagline}
        </h1>
        <p className="text-base text-fg-muted">Upload a 3D model, describe the shot, get a cinematic render.</p>
      </motion.div>

      <motion.div variants={item} className="w-full max-w-[960px]">
        <div className="aspect-video w-full overflow-hidden rounded-lg border border-line bg-bg-0">
          <Viewer root={loaded?.root ?? null} plan={plan} scaleFactor={loaded?.scaleFactor ?? 1} previewSeconds={null} />
        </div>
      </motion.div>

      <motion.ul variants={item} aria-label="Example looks" className="flex flex-wrap justify-center gap-2">
        {HERO_CHIPS.map((c) => (
          <li key={c.id}>
            <Chip selected={c.id === chipId} onClick={() => setChipId(c.id)}>
              {c.label}
            </Chip>
          </li>
        ))}
      </motion.ul>

      <motion.div variants={item}>
        <Link
          href="/projects?new=1"
          className="inline-flex h-10 items-center rounded-full bg-accent px-5 text-sm font-medium text-accent-fg transition-colors duration-fast ease-standard hover:bg-fg focus-visible:focus-ring"
        >
          Start a project
        </Link>
      </motion.div>
    </motion.section>
  );
}
