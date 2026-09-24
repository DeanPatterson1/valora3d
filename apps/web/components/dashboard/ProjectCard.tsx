"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Button, Dialog, Field, cx } from "@/components/ui";
import { fadeRise, reduced } from "@/lib/motion/variants";
import type { Project } from "@/lib/schema";
import { projectMeta } from "./meta";
import { useThumbnail } from "./useThumbnail";

export type ProjectCardProps = {
  project: Project;
  versionCount: number;
  now: number;
  onRename: (id: string, name: string) => void | Promise<void>;
  onDelete: (id: string) => void | Promise<void>;
};

function ModelGlyph() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="size-8 text-fg-muted/30"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinejoin="round"
    >
      <path d="M12 3 20 7.5v9L12 21l-8-4.5v-9L12 3Z" />
      <path d="M4 7.5 12 12l8-4.5M12 12v9" />
    </svg>
  );
}

function Thumbnail({ assetId, name }: { assetId: string | null; name: string }) {
  const url = useThumbnail(assetId);
  return (
    <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 overflow-hidden rounded-t-[11px] border-b border-line bg-bg-1">
      {url ? (
        // Object URL from IndexedDB; next/image cannot optimise it.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="" className="size-full object-cover" draggable={false} />
      ) : (
        <><ModelGlyph /><span className="text-xs text-fg-muted">No preview yet</span></>
      )}
      <span className="sr-only">{name}</span>
    </div>
  );
}

function DotsIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="currentColor">
      <circle cx="3" cy="8" r="1.4" />
      <circle cx="8" cy="8" r="1.4" />
      <circle cx="13" cy="8" r="1.4" />
    </svg>
  );
}

type MenuProps = {
  projectName: string;
  onRename: () => void;
  onDelete: () => void;
};

function OverflowMenu({ projectName, onRename, onDelete }: MenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const item =
    "flex h-9 w-full cursor-pointer items-center rounded-sm px-3 text-left text-sm transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring";

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label={`More options for ${projectName}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen((v) => !v)}
        className={cx(
          "flex size-11 cursor-pointer items-center justify-center rounded-full text-fg-muted transition-colors duration-fast ease-standard hover:bg-bg-3 hover:text-fg focus-visible:focus-ring sm:size-8",
          open && "bg-bg-3 text-fg",
        )}
      >
        <DotsIcon />
      </button>
      {open && (
        <div
          id={id}
          role="menu"
          aria-label={`Options for ${projectName}`}
          className="absolute right-0 top-full z-20 mt-1 w-40 rounded-sm bg-bg-2 p-1 shadow-raise"
        >
          <button
            type="button"
            role="menuitem"
            className={cx(item, "text-fg")}
            onClick={() => {
              setOpen(false);
              onRename();
            }}
          >
            Rename
          </button>
          <button
            type="button"
            role="menuitem"
            className={cx(item, "text-danger hover:bg-danger/10")}
            onClick={() => {
              setOpen(false);
              onDelete();
            }}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

function RenameField({
  initial,
  onCommit,
  onCancel,
}: {
  initial: string;
  onCommit: (name: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  const done = useRef(false);

  const commit = () => {
    if (done.current) return;
    done.current = true;
    const next = value.trim();
    if (next && next !== initial) onCommit(next);
    else onCancel();
  };
  const cancel = () => {
    if (done.current) return;
    done.current = true;
    onCancel();
  };

  return (
    <Field
      label="Rename"
      autoFocus
      value={value}
      maxLength={80}
      onChange={(e) => setValue(e.target.value)}
      onFocus={(e) => e.target.select()}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          commit();
        } else if (e.key === "Escape") {
          e.preventDefault();
          cancel();
        }
      }}
    />
  );
}

export function ProjectCard({ project, versionCount, now, onRename, onDelete }: ProjectCardProps) {
  const rm = useReducedMotion();
  const [renaming, setRenaming] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const href = `/projects/${project.id}`;

  return (
    <motion.li
      variants={rm ? reduced(fadeRise) : fadeRise}
      whileHover={rm ? undefined : { y: -1 }}
      data-testid="project-card"
      className="group relative flex flex-col rounded-md border border-line bg-bg-2 transition-colors duration-fast ease-standard hover:bg-bg-3"
    >
      {/* Stretched link: the whole card opens the project. Controls sit above it. */}
      {!renaming && (
        <Link
          href={href}
          aria-label={`Open ${project.name}`}
          className="absolute inset-0 z-[1] rounded-md focus-visible:focus-ring"
        />
      )}

      <Thumbnail assetId={project.assetId} name={project.name} />

      <div className="flex items-start gap-2 p-3 pl-4">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          {renaming ? (
            <div className="relative z-[2]">
              <RenameField
                initial={project.name}
                onCommit={(name) => {
                  setRenaming(false);
                  void onRename(project.id, name);
                }}
                onCancel={() => setRenaming(false)}
              />
            </div>
          ) : (
            <h3 className="truncate text-sm font-medium text-fg" title={project.name}>
              {project.name}
            </h3>
          )}
          <p className="truncate text-xs text-fg-muted">{projectMeta(project, versionCount, now)}</p>
        </div>
        <div className="relative z-[2] -mr-1 -mt-1">
          <OverflowMenu
            projectName={project.name}
            onRename={() => setRenaming(true)}
            onDelete={() => setConfirming(true)}
          />
        </div>
      </div>

      <Dialog
        open={confirming}
        onClose={() => {
          if (!deleting) setConfirming(false);
        }}
        title="Delete project and its model?"
        description={`"${project.name}" and its uploaded model will be removed from this browser. Versions are deleted with it.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirming(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={deleting}
              onClick={async () => {
                setDeleting(true);
                try {
                  await onDelete(project.id);
                } finally {
                  setDeleting(false);
                  setConfirming(false);
                }
              }}
            >
              Delete
            </Button>
          </>
        }
      />
    </motion.li>
  );
}
