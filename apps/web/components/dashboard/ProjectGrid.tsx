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
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-24 text-center">
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold tracking-tight text-fg">Create your first project</h2>
        <p className="text-sm text-fg-muted">Upload a model, describe the shot, get a cinematic render.</p>
      </div>
      <Button variant="primary" size="lg" onClick={onNew}>
        New project
      </Button>
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
      className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4"
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
