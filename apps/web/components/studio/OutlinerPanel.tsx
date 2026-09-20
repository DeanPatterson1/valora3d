"use client";

import { useState } from "react";
import { Button, cx } from "@/components/ui";
import { hasEdits } from "@/components/viewer/meshEdits";
import type { OutlineNode } from "@/components/viewer/meshTree";
import { useEditorStore } from "@/lib/stores/editor";

const count = new Intl.NumberFormat("en-GB");

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
      {open ? (
        <>
          <path d="M1.5 8s2.4-4 6.5-4 6.5 4 6.5 4-2.4 4-6.5 4S1.5 8 1.5 8Z" />
          <circle cx="8" cy="8" r="1.8" />
        </>
      ) : (
        <>
          <path d="M2.5 5.2C1.9 6 1.5 8 1.5 8s2.4 4 6.5 4c1 0 1.9-.2 2.7-.6" />
          <path d="M13.2 10.4C14.1 9.4 14.5 8 14.5 8s-2.4-4-6.5-4c-.5 0-1 .1-1.5.2" />
          <path d="M2 2l12 12" />
        </>
      )}
    </svg>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 16 16"
      className={cx("size-3 transition-transform duration-fast ease-standard", open ? "rotate-90" : "")}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 3.5 10.5 8 6 12.5" />
    </svg>
  );
}

type RowProps = {
  node: OutlineNode;
  depth: number;
  selection: string[];
  hidden: string[];
  collapsed: Set<string>;
  onToggleCollapse: (id: string) => void;
};

function Row({ node, depth, selection, hidden, collapsed, onToggleCollapse }: RowProps) {
  const select = useEditorStore((s) => s.select);
  const toggleHidden = useEditorStore((s) => s.toggleHidden);
  const isSelected = selection.includes(node.id);
  const isHidden = hidden.includes(node.id);
  const hasChildren = node.children.length > 0;
  const open = hasChildren && !collapsed.has(node.id);

  return (
    <>
      <div
        className={cx(
          "group flex items-center gap-1 rounded-md pr-1.5 text-sm transition-colors duration-fast ease-standard",
          isSelected ? "bg-primary/15 text-fg" : "text-fg-muted hover:bg-bg-2 hover:text-fg",
        )}
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
      >
        <button
          type="button"
          onClick={() => hasChildren && onToggleCollapse(node.id)}
          aria-label={hasChildren ? (open ? `Collapse ${node.name}` : `Expand ${node.name}`) : undefined}
          aria-hidden={!hasChildren}
          tabIndex={hasChildren ? 0 : -1}
          className={cx(
            "flex size-4 shrink-0 cursor-pointer items-center justify-center rounded-sm focus-visible:focus-ring",
            hasChildren ? "" : "pointer-events-none opacity-0",
          )}
        >
          <Chevron open={open} />
        </button>

        <button
          type="button"
          data-testid="outliner-row"
          onClick={(e) => select(node.id, e.shiftKey || e.ctrlKey || e.metaKey)}
          aria-pressed={isSelected}
          className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 py-1 text-left focus-visible:focus-ring"
        >
          <span className={cx("truncate", isHidden && "opacity-45")}>{node.name}</span>
          <span className="ml-auto shrink-0 tabular-nums text-[11px] text-fg-muted/70">{count.format(node.triangles)}</span>
        </button>

        <button
          type="button"
          onClick={() => toggleHidden(node.id)}
          aria-label={isHidden ? `Show ${node.name}` : `Hide ${node.name}`}
          className={cx(
            "flex size-5 shrink-0 cursor-pointer items-center justify-center rounded-sm hover:text-fg focus-visible:focus-ring",
            isHidden ? "text-fg-muted" : "text-fg-muted/0 group-hover:text-fg-muted",
          )}
        >
          <EyeIcon open={!isHidden} />
        </button>
      </div>

      {open &&
        node.children.map((child) => (
          <Row
            key={child.id}
            node={child}
            depth={depth + 1}
            selection={selection}
            hidden={hidden}
            collapsed={collapsed}
            onToggleCollapse={onToggleCollapse}
          />
        ))}
    </>
  );
}

/**
 * Right-panel "Model" tab: the parts list for the editing viewport.
 *
 * The viewport is a workspace — clay shaded, no textures — because the product is the
 * rendered video, not the preview. Separate splits a mesh into its loose parts, Delete
 * removes geometry from the render as well, and Hide is viewport-only.
 */
export function OutlinerPanel() {
  const outline = useEditorStore((s) => s.outline);
  const selection = useEditorStore((s) => s.selection);
  const edits = useEditorStore((s) => s.edits);
  const notice = useEditorStore((s) => s.notice);
  const historyLength = useEditorStore((s) => s.history.length);
  const splitSelected = useEditorStore((s) => s.splitSelected);
  const deleteSelected = useEditorStore((s) => s.deleteSelected);
  const undo = useEditorStore((s) => s.undo);

  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const onToggleCollapse = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const nothing = selection.length === 0;

  return (
    <div className="flex h-full flex-col">
      <div className="px-4 pt-1 pb-3">
        <p className="text-xs text-fg-muted">
          Solid view, textures off. Separate a mesh into its loose parts, then delete what the shot does not need.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5 px-3 pb-2">
        <Button size="sm" variant="secondary" onClick={splitSelected} disabled={nothing} data-testid="separate-parts">
          Separate
        </Button>
        <Button size="sm" variant="danger" onClick={deleteSelected} disabled={nothing} data-testid="delete-parts">
          Delete
        </Button>
        <Button size="sm" variant="ghost" onClick={undo} disabled={historyLength === 0} data-testid="undo-edit">
          Undo
        </Button>
      </div>

      {notice && (
        <p role="status" className="px-4 pb-2 text-xs text-fg-muted">
          {notice}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3" data-testid="outliner">
        {outline.length === 0 ? (
          <p className="px-1 py-2 text-sm text-fg-muted">No geometry left. Undo to bring a part back.</p>
        ) : (
          outline.map((node) => (
            <Row
              key={node.id}
              node={node}
              depth={0}
              selection={selection}
              hidden={edits.hidden}
              collapsed={collapsed}
              onToggleCollapse={onToggleCollapse}
            />
          ))
        )}
      </div>

      <div className="border-t border-line px-4 py-3 text-[11px] leading-relaxed text-fg-muted">
        <p>
          Click a part in the viewport or here. Shift-click adds to the selection.
          <br />
          <kbd className="font-sans">P</kbd> separate · <kbd className="font-sans">H</kbd> hide ·{" "}
          <kbd className="font-sans">Del</kbd> delete · <kbd className="font-sans">Ctrl+Z</kbd> undo
        </p>
        {hasEdits(edits) && (
          <p className="mt-2 text-fg-muted/80">
            {edits.deleted.length} deleted · {edits.split.length} separated. Deleted parts are left out of the render too.
          </p>
        )}
      </div>
    </div>
  );
}
