"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Button } from "@/components/ui";
import { staggerList } from "@/lib/motion/variants";
import type { Project } from "@/lib/schema";
import { ProjectCard } from "./ProjectCard";

export type ProjectGridProps = {
  projects: Project[];
  versionCounts: Record<string, number>;
  onRename: (id: string, name: string) => void | Promise<void>;
  onDelete: (id: string) => void | Promise<void>;
  onNew: () => void;
};

function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="my-auto flex flex-col items-center justify-center gap-6 rounded-[24px] border border-dashed border-line bg-bg-1/50 px-5 py-16 text-center sm:py-24">
      <div className="flex max-w-sm flex-col gap-3">
        <h2 className="text-2xl font-semibold tracking-tight text-fg">Create your first project</h2>
        <p className="text-sm leading-relaxed text-fg-muted">Upload a model or try a sample, then describe your scene. Explore it in the 3D preview.</p>
      </div>
      <Button variant="primary" size="lg" onClick={onNew}>
        New project
      </Button>
      <p className="text-xs text-fg-muted">Upload a .glb model to start planning your shot.</p>
    </div>
  );
}

export function ProjectGrid({ projects, versionCounts, onRename, onDelete, onNew }: ProjectGridProps) {
  const now = useNow(30_000);

  if (projects.length === 0) return <EmptyState onNew={onNew} />;

  return (
    <motion.ul
      variants={staggerList}
      initial="hidden"
      animate="visible"
      aria-label="Projects"
      className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,260px),1fr))] gap-5"
    >
      {projects.map((p) => (
        <ProjectCard
          key={p.id}
          project={p}
          versionCount={versionCounts[p.id] ?? 0}
          now={now}
          onRename={onRename}
          onDelete={onDelete}
        />
      ))}
    </motion.ul>
  );
}
