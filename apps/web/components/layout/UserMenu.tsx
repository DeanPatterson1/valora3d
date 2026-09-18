"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { cx } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import { useAuthStore } from "@/lib/stores/auth";
import { GUEST_ID } from "@/lib/services/local/auth";
import { Avatar } from "@/components/account/Avatar";
import { PLAN_LABEL } from "@/components/account/planLabel";

const ITEMS = [
  { href: "/profile", label: "Profile" },
  { href: "/settings", label: "Settings" },
  { href: "/pricing", label: "Pricing" },
] as const;

export type UserMenuProps = {
  collapsed: boolean;
  onNavigate?: () => void;
};

/**
 * The sidebar's bottom row: avatar, name and plan, opening a small menu above it.
 * A guest sees a link to sign in instead of a menu.
 */
export function UserMenu({ collapsed, onNavigate }: UserMenuProps) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const signOut = useAuthStore((s) => s.signOut);
  const rm = useReducedMotion() ?? false;
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    // First item takes focus so the menu is keyboard-complete.
    rootRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;

  const rowClass = cx(
    "flex h-11 w-full cursor-pointer items-center gap-2.5 rounded-sm px-1.5 text-left text-sm text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring",
    collapsed && "justify-center px-0",
  );

  if (user.id === GUEST_ID) {
    return (
      <Link href="/login" onClick={onNavigate} className={rowClass} title={collapsed ? "Guest · sign in" : undefined}>
        <Avatar name={user.name} seed={user.avatarSeed} size="sm" />
        {!collapsed && (
          <span className="min-w-0 flex-1 truncate">
            Guest <span className="text-fg-muted">· sign in</span>
          </span>
        )}
      </Link>
    );
  }

  const close = () => setOpen(false);
  const logOut = async () => {
    close();
    onNavigate?.();
    await signOut();
    router.replace("/login");
  };

  const onMenuKey = (e: React.KeyboardEvent) => {
    const items = Array.from(rootRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
    const i = items.indexOf(document.activeElement as HTMLElement);
    if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length]?.focus(); }
    if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length]?.focus(); }
    if (e.key === "Home") { e.preventDefault(); items[0]?.focus(); }
    if (e.key === "End") { e.preventDefault(); items[items.length - 1]?.focus(); }
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={collapsed ? `${user.name}. Account menu` : undefined}
        title={collapsed ? user.name : undefined}
        onClick={() => setOpen((v) => !v)}
        className={cx(rowClass, open && "bg-bg-3")}
      >
        <Avatar name={user.name} seed={user.avatarSeed} size="sm" />
        {!collapsed && (
          <span className="flex min-w-0 flex-1 flex-col leading-tight">
            <span className="truncate">{user.name}</span>
            <span className="truncate text-xs text-fg-muted">{PLAN_LABEL[user.plan]}</span>
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            id={menuId}
            role="menu"
            aria-label="Account"
            onKeyDown={onMenuKey}
            initial={rm ? false : { opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={rm ? undefined : { opacity: 0, y: 4 }}
            transition={{ duration: DUR.fast, ease: EASE.standard }}
            className={cx(
              "absolute bottom-full z-50 mb-1 flex w-56 flex-col rounded-md bg-bg-2 p-1 shadow-raise",
              collapsed ? "left-0" : "left-0 right-0 w-auto",
            )}
          >
            <div className="flex flex-col gap-0.5 border-b border-line px-2.5 pb-2 pt-1.5">
              <span className="truncate text-xs text-fg-muted">{user.email}</span>
            </div>
            {ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                role="menuitem"
                onClick={() => {
                  close();
                  onNavigate?.();
                }}
                className="flex h-9 items-center rounded-sm px-2.5 text-sm text-fg transition-colors hover:bg-bg-3 focus-visible:focus-ring"
              >
                {item.label}
              </Link>
            ))}
            <button
              type="button"
              role="menuitem"
              onClick={() => void logOut()}
              className="flex h-9 w-full cursor-pointer items-center rounded-sm px-2.5 text-left text-sm text-fg transition-colors hover:bg-bg-3 focus-visible:focus-ring"
            >
              Log out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
