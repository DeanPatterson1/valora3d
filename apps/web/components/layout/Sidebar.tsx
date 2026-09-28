"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import {
  animate,
  motion,
  useMotionValue,
  useReducedMotion,
  useTransform,
} from "motion/react";
import { BRAND } from "@/lib/brand";
import { useCreditsStore } from "@/lib/stores/credits";
import { useProjectsStore } from "@/lib/stores/projects";
import { useStudioStore } from "@/lib/stores/studio";
import { DUR, EASE } from "@/lib/motion/tokens";
import { cx } from "@/components/ui/cx";
import { VersionRail } from "@/components/studio/VersionRail";
import { useLabour } from "@/components/studio/useLabour";
import { UserMenu } from "./UserMenu";

const COLLAPSED_KEY = "rs.sidebar.collapsed";

/* Collapsed state lives in memory and mirrors to localStorage when it can. */
let collapsedValue: boolean | null = null;
const collapsedListeners = new Set<() => void>();

function readCollapsed(): boolean {
  if (collapsedValue === null) {
    try {
      collapsedValue = localStorage.getItem(COLLAPSED_KEY) === "1";
    } catch {
      collapsedValue = false;
    }
  }
  return collapsedValue;
}

function writeCollapsed(v: boolean) {
  collapsedValue = v;
  try {
    localStorage.setItem(COLLAPSED_KEY, v ? "1" : "0");
  } catch {
    // Storage may be blocked; the toggle still works for the session.
  }
  collapsedListeners.forEach((l) => l());
}

function subscribeCollapsed(cb: () => void) {
  collapsedListeners.add(cb);
  return () => collapsedListeners.delete(cb);
}

/** Renders a number that ticks from its previous value to the new one. */
function TickingNumber({ value }: { value: number }) {
  const rm = useReducedMotion();
  const raw = useMotionValue(value);
  const rounded = useTransform(raw, (v) => Math.round(v));

  useEffect(() => {
    if (rm) {
      raw.set(value);
      return;
    }
    const controls = animate(raw, value, {
      duration: DUR.slow,
      ease: EASE.emphasized,
    });
    return () => controls.stop();
  }, [value, rm, raw]);

  return <motion.span className="tabular">{rounded}</motion.span>;
}

const ICON = "size-5 shrink-0";
const iconProps = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

function LogoMark() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-6 shrink-0" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.75" />
      <circle cx="12" cy="12" r="3.5" fill="currentColor" />
    </svg>
  );
}

function PanelIcon() {
  return (
    <svg aria-hidden className={ICON} {...iconProps}>
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <path d="M9 4v16" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg aria-hidden className={ICON} {...iconProps}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

function PencilSquareIcon() {
  return (
    <svg aria-hidden className={ICON} {...iconProps}>
      <path d="M12 5H7a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" />
      <path d="M17.5 3.5a2.1 2.1 0 0 1 3 3L13 14l-4 1 1-4 7.5-7.5Z" />
    </svg>
  );
}

function TagIcon() {
  return (
    <svg aria-hidden className={ICON} {...iconProps}>
      <path d="M20 12.5 12.5 20a1.5 1.5 0 0 1-2.1 0L4 13.6V4h9.6l6.4 6.4a1.5 1.5 0 0 1 0 2.1Z" />
      <circle cx="8.5" cy="8.5" r="1" fill="currentColor" />
    </svg>
  );
}

function CoinIcon() {
  return (
    <svg aria-hidden className={ICON} {...iconProps}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5v9M9.5 10a2.5 2 0 0 1 5 0c0 2-5 2-5 4a2.5 2 0 0 0 5 0" />
    </svg>
  );
}

type RowProps = {
  href: string;
  icon?: React.ReactNode;
  label: React.ReactNode;
  ariaLabel?: string;
  active?: boolean;
  collapsed: boolean;
  onNavigate?: () => void;
  title?: string;
  className?: string;
};

/** A sidebar row: 36px tall (40px on touch widths), rounded, bg-3 when active or hovered. */
function Row({ href, icon, label, ariaLabel, active, collapsed, onNavigate, title, className }: RowProps) {
  return (
    <Link
      href={href}
      aria-label={ariaLabel}
      aria-current={active ? "page" : undefined}
      title={collapsed ? title : undefined}
      onClick={onNavigate}
      className={cx(
        "flex h-10 items-center gap-2.5 rounded-sm px-2.5 text-sm text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring sm:h-9",
        active && "bg-bg-3",
        collapsed && "justify-center px-0",
        className,
      )}
    >
      {icon}
      {!collapsed && <span className="min-w-0 flex-1 truncate">{label}</span>}
    </Link>
  );
}

/**
 * Scene history under the open project (spec 8, revised): collapsed to a "3 versions"
 * caret by default; expanding lists the versions, frozen during the labour sequence.
 */
function ProjectHistory({ projectId }: { projectId: string }) {
  const openProjectId = useStudioStore((s) => s.project?.id ?? null);
  const versions = useStudioStore((s) => s.versions);
  const { labouring, frozenVersionCount } = useLabour();
  const [open, setOpen] = useState(false);
  const id = `history-${projectId}`;

  const shown = labouring ? versions.slice(0, frozenVersionCount) : versions;
  const count = shown.length;
  // Nothing to disclose until the first scene exists.
  if (openProjectId !== projectId || count === 0) return null;

  // Indented under the active row with a hairline guide, so row and history read as one group.
  return (
    <div className="ml-3.5 border-l border-line pb-1 pl-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={id}
        className="flex h-10 w-full cursor-pointer items-center gap-1.5 rounded-sm pl-2 pr-2 text-xs text-fg-muted transition-colors duration-fast ease-standard hover:bg-bg-3 hover:text-fg focus-visible:focus-ring sm:h-7"
      >
        <svg
          aria-hidden
          viewBox="0 0 16 16"
          className={cx("size-3.5 transition-transform duration-fast ease-standard", open && "rotate-90")}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M6 4l4 4-4 4" />
        </svg>
        {count === 1 ? "1 version" : `${count} versions`}
      </button>
      {open && (
        <div id={id} className="pl-2">
          <VersionRail versions={shown} />
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useSyncExternalStore(subscribeCollapsed, readCollapsed, () => false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const balance = useCreditsStore((s) => s.balance);
  const refreshCredits = useCreditsStore((s) => s.refresh);
  const projects = useProjectsStore((s) => s.projects);
  const loaded = useProjectsStore((s) => s.loaded);
  const refreshProjects = useProjectsStore((s) => s.refresh);

  useEffect(() => {
    void refreshCredits();
    void refreshProjects();
  }, [refreshCredits, refreshProjects]);

  // Mobile drawer: focus moves in when it opens and back to the menu button when it closes.
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDialogElement>(null);
  const wasOpen = useRef(false);
  useEffect(() => {
    const drawer = drawerRef.current;
    if (!drawer) return;
    if (drawerOpen) {
      wasOpen.current = true;
      if (!drawer.open) drawer.showModal();
      drawer.querySelector<HTMLElement>("a, button")?.focus();
      const desktop = window.matchMedia("(min-width: 768px)");
      const closeOnDesktop = () => { if (desktop.matches) setDrawerOpen(false); };
      desktop.addEventListener("change", closeOnDesktop);
      return () => desktop.removeEventListener("change", closeOnDesktop);
    }
    if (drawer.open) drawer.close();
    if (wasOpen.current) {
      wasOpen.current = false;
      menuButtonRef.current?.focus();
    }
  }, [drawerOpen]);

  const toggleCollapsed = () => writeCollapsed(!collapsed);

  const closeDrawer = () => setDrawerOpen(false);
  const recent = [...projects].sort((a, b) => b.updatedAt - a.updatedAt);

  const renderNav = (collapsed: boolean) => (
    <nav
      aria-label="Primary"
      className="flex h-full flex-col gap-1 p-2"
    >
      <div className={cx("flex h-11 items-center", collapsed ? "justify-center" : "justify-between pl-2.5")}>
        {!collapsed && (
          <Link
            href="/"
            className="flex min-w-0 items-center gap-2 rounded-sm text-fg focus-visible:focus-ring"
          >
            <LogoMark />
            <span className="truncate text-sm font-semibold tracking-tight">{BRAND.name}</span>
          </Link>
        )}
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? "Open sidebar" : "Close sidebar"}
          aria-expanded={!collapsed}
          className="hidden size-9 shrink-0 cursor-pointer items-center justify-center rounded-sm text-fg-muted transition-colors duration-fast ease-standard hover:bg-bg-3 hover:text-fg focus-visible:focus-ring md:flex"
        >
          <PanelIcon />
        </button>
        <button
          type="button"
          onClick={closeDrawer}
          aria-label="Close sidebar"
          className="flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-sm text-fg-muted transition-colors duration-fast ease-standard hover:bg-bg-3 hover:text-fg focus-visible:focus-ring md:hidden"
        >
          <PanelIcon />
        </button>
      </div>

      <Row
        href="/projects"
        icon={<PanelIcon />}
        label="All projects"
        title="All projects"
        ariaLabel={collapsed ? "All projects" : undefined}
        active={pathname === "/projects"}
        collapsed={collapsed}
        onNavigate={closeDrawer}
      />

      <Row
        href="/projects?new=1"
        icon={<PencilSquareIcon />}
        label="New project"
        title="New project"
        ariaLabel={collapsed ? "New project" : undefined}
        collapsed={collapsed}
        onNavigate={closeDrawer}
      />

      {!collapsed && (
        <div className="mt-4 flex min-h-0 flex-1 flex-col">
          <h2 className="px-2.5 pb-1.5 text-xs font-medium text-fg-muted">Projects</h2>
          {loaded && recent.length === 0 ? (
            <p className="px-2.5 py-1.5 text-[13px] text-fg-muted">No projects yet</p>
          ) : (
            <ul className="-mx-2 flex min-h-0 flex-1 flex-col gap-px overflow-y-auto px-2">
              {recent.map((p) => {
                const href = `/projects/${p.id}`;
                return (
                  <li key={p.id}>
                    <Row
                      href={href}
                      label={p.name}
                      active={pathname === href}
                      collapsed={false}
                      onNavigate={closeDrawer}
                    />
                    {pathname === href && <ProjectHistory projectId={p.id} />}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
      {collapsed && <div className="flex-1" />}

      <div className="mt-2 flex flex-col gap-1 border-t border-line pt-2">
        <Row href="/help" icon={<svg aria-hidden className={ICON} {...iconProps}><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4M12 16h.01" /></svg>} label="Help" title="Help" ariaLabel={collapsed ? "Help" : undefined} active={pathname.startsWith("/help")} collapsed={collapsed} onNavigate={closeDrawer} />
        <Row href="/profile" icon={<svg aria-hidden className={ICON} {...iconProps}><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></svg>} label="Profile" title="Profile" ariaLabel={collapsed ? "Profile" : undefined} active={pathname === "/profile"} collapsed={collapsed} onNavigate={closeDrawer} />
        <Row href="/settings" icon={<svg aria-hidden className={ICON} {...iconProps}><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="2" fill="var(--color-bg-1)" /><circle cx="15" cy="17" r="2" fill="var(--color-bg-1)" /></svg>} label="Settings" title="Settings" ariaLabel={collapsed ? "Settings" : undefined} active={pathname === "/settings"} collapsed={collapsed} onNavigate={closeDrawer} />
        <Row
          href="/pricing"
          icon={<TagIcon />}
          label="Pricing"
          title="Pricing"
          ariaLabel={collapsed ? "Pricing" : undefined}
          active={pathname === "/pricing"}
          collapsed={collapsed}
          onNavigate={closeDrawer}
        />
        <Row
          href="/pricing"
          icon={<CoinIcon />}
          label={
            <>
              <TickingNumber value={balance} /> credits
            </>
          }
          ariaLabel={`${balance} credits. Buy more`}
          title={`${balance} credits`}
          collapsed={collapsed}
          onNavigate={closeDrawer}
          className="text-fg-muted hover:text-fg"
        />
        <UserMenu collapsed={collapsed} onNavigate={closeDrawer} />
      </div>
    </nav>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        data-collapsed={collapsed || undefined}
        className={cx(
          "hidden h-full shrink-0 flex-col border-r border-line bg-bg-1 transition-[width] duration-base ease-standard motion-reduce:transition-none md:flex",
          collapsed ? "w-14" : "w-[260px]",
        )}
      >
        {renderNav(collapsed)}
      </aside>

      {/* Mobile: hamburger + off-canvas drawer */}
      <button
        ref={menuButtonRef}
        type="button"
        onClick={() => setDrawerOpen(true)}
        aria-label="Open sidebar"
        aria-expanded={drawerOpen}
        aria-controls="sidebar-drawer"
        className="fixed left-1 top-1 z-40 flex size-11 cursor-pointer items-center justify-center rounded-md bg-bg-0/80 text-fg backdrop-blur-sm transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring md:hidden"
      >
        <MenuIcon />
      </button>
      <dialog
        ref={drawerRef}
        id="sidebar-drawer"
        aria-label="Navigation"
        onKeyDown={(e) => {
          if (e.key !== "Tab") return;
          const targets = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex="0"]'))
            .filter((el) => el.getClientRects().length > 0);
          const first = targets[0];
          const last = targets[targets.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }}
        onCancel={() => setDrawerOpen(false)}
        onClose={() => setDrawerOpen(false)}
        onClick={(e) => { if (e.target === e.currentTarget) closeDrawer(); }}
        className="fixed inset-0 m-0 h-dvh max-h-none w-full max-w-none bg-transparent p-0 text-fg backdrop:bg-black/60"
      >
        <aside className="h-full w-[280px] max-w-[85vw] border-r border-line bg-bg-1 shadow-raise">
          {drawerOpen && renderNav(false)}
        </aside>
      </dialog>
    </>
  );
}
